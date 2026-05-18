import modal
import os
import boto3
import tempfile
import re
from fastapi import Request

app = modal.App(name="subtitles")


def download_whisper():
    import whisper
    whisper.load_model("base")


image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "numpy",
        "openai-whisper==20250625",
        "boto3",
        "python-multipart",
        "fastapi"
    ).apt_install("ffmpeg")
    .run_function(download_whisper)
)


@app.cls(
    image=image,
    gpu="L4",
    timeout=60 * 60,
    max_containers=1,
    enable_memory_snapshot=True,
    secrets=[modal.Secret.from_name("custom-secret")],
)
class SubtitleWorker:

    # Load model into snapshot (CPU)
    @modal.enter(snap=True)
    def load_model(self):
        import whisper
        self.model = whisper.load_model("base")

    # Move model to GPU after restore
    @modal.enter(snap=False)
    def to_gpu(self):
        self.model = self.model.to("cuda")

    @staticmethod
    def _fmt_srt(t: float) -> str:
        h, r = divmod(int(t), 3600)
        m, s = divmod(r, 60)
        ms = int((t - int(t)) * 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    @staticmethod
    def _build_srt(segments) -> str:
        lines = []
        for i, seg in enumerate(segments, 1):
            lines += [
                str(i),
                f"{SubtitleWorker._fmt_srt(seg['start'])} --> {SubtitleWorker._fmt_srt(seg['end'])}",
                seg["text"].strip(),
                "",
            ]
        return "\n".join(lines)

    @staticmethod
    def _patch_master(s3, bucket: str, prefix: str):
        """Inject subtitle track into HLS master playlist."""
        key = f"{prefix}/master.m3u8"

        obj = s3.get_object(Bucket=bucket, Key=key)
        master = obj["Body"].read().decode()

        # Add subtitle media if not present
        if "TYPE=SUBTITLES" not in master:
            sub_media = (
                '\n#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",'
                'NAME="English",DEFAULT=YES,AUTOSELECT=YES,'
                'FORCED=NO,LANGUAGE="en",'
                'URI="subtitles/en.vtt"\n'
            )
            master = master.replace("#EXT-X-STREAM-INF:", sub_media + "#EXT-X-STREAM-INF:", 1)

        # Attach subtitles to all streams
        master = re.sub(
            r"(#EXT-X-STREAM-INF:[^\n]+)",
            lambda m: m.group(1) + ',SUBTITLES="subs"' if "SUBTITLES" not in m.group(1) else m.group(1),
            master,
        )

        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=master.encode(),
            ContentType="application/vnd.apple.mpegurl",
        )

    @modal.web_endpoint(method="POST")
    async def transcribe(self, request: Request):
        form = await request.json()

        video_id   = form["video_id"]
        out_bucket = form["out_bucket"]
        out_prefix = form["out_prefix"]
        audio_key  = form["audio_key"]

        s3 = boto3.client("s3")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            audio_path = f.name

        try:
            s3.download_file(out_bucket, audio_key, audio_path)

            result = self.model.transcribe(
                audio_path,
                fp16=(self.model.device.type == "cuda"),
                verbose=False,
                task="transcribe",
            )
        finally:
            if os.path.exists(audio_path):
                os.unlink(audio_path)

        srt = self._build_srt(result["segments"])
        vtt = "WEBVTT\n\n" + srt.replace(",", ".")

        # Upload to S3
        # s3 = boto3.client("s3")

        for ext, body in [("srt", srt), ("vtt", vtt)]:
            s3.put_object(
                Bucket=out_bucket,
                Key=f"{out_prefix}/subtitles/en.{ext}",
                Body=body.encode(),
                ContentType="text/vtt" if ext == "vtt" else "text/srt",
            )

        # Patch HLS master playlist
        self._patch_master(s3, out_bucket, out_prefix)

        s3.delete_object(Bucket=out_bucket, Key=audio_key)

        return {
            "status": "ok",
            "video_id": video_id,
            "language": result.get("language"),
            "segments": len(result["segments"]),
        }

        
