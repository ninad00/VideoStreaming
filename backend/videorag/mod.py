import modal
import os
import whisper
import google.generativeai as genai
from groq import Groq
from transformers import AutoModel, AutoProcessor
from sentence_transformers import SentenceTransformer
from google.generativeai import GenerativeModel
from dotenv import load_dotenv
import numpy as np
import torch
from sklearn.cluster import KMeans
from transformers import AutoModel, AutoProcessor
import json
import boto3
from io import BytesIO
from PIL import Image
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor
import tempfile
import subprocess
from PIL import Image

class ProcessRequest(BaseModel):
    video_id: str
    duration: int

class ChatRequest(BaseModel):
    video_id:str
    query: str
    top_k: int
    history: list[dict]

app = modal.App(name="videorag")
volume = modal.Volume.from_name("videorag-vol", create_if_missing=True)

def download_models():
    """Download models at build time"""
    from transformers import AutoModel, AutoProcessor
    from sentence_transformers import SentenceTransformer
    
    # Download SiGLIP
    AutoModel.from_pretrained("google/siglip-so400m-patch14-384")
    AutoProcessor.from_pretrained("google/siglip-so400m-patch14-384", use_fast=True)
    
    # Download sentence transformer
    SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    whisper.load_model("base", device="cpu")
    
    print("✓ Models downloaded")


image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg","texlive-latex-base","texlive-latex-extra","texlive-fonts-recommended")
    .pip_install(
        "openai-whisper==20250625",
        "numpy",
        "fastapi",
        "opencv-python-headless",
        "Pillow",
        "numpy",
        "boto3",
        "scikit-learn",
        "torch",
        "transformers",
        "sentencepiece",
        "python-dotenv",
        "google-generativeai",
        "groq",
        "sentence-transformers",
        "supabase"
    ).run_function(download_models)
)

import time
import functools

def benchmark(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"[BENCHMARK] {func.__name__} took {elapsed:.3f}s")
        return result
    return wrapper

# @benchmark
def upload_frame_to_s3(frame_np,bucket: str,video_id: str,frame_index: int,s3_client=None,quality: int = 70):
    img = Image.fromarray(frame_np).convert("RGB")
    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=quality, optimize=True)
    buffer.seek(0)
    key = f"{video_id}/frames/{frame_index}.jpg"
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=buffer,
        ContentType="image/jpeg",
    )

    return key

# @benchmark
def extract_keyframes(duration: int, video_id: str,siglip_model=None,siglip_processor=None, device=None, s3_client=None,):
    
    video_path=f"https://{os.environ['AWS_OUT_BUCKET']}.s3.{os.environ['AWS_REGION']}.amazonaws.com/{video_id}/master.m3u8"
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    if siglip_model is None:
        raise RuntimeError("Model not loaded")
    if siglip_processor is None:
        raise RuntimeError("Processor not loaded")
        

    clusters = 40 if duration <= 300 else 80 if duration <= 800 else 100
    probe_cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "json",
        video_path
    ]
    data = json.loads(subprocess.check_output(probe_cmd))
    w, h = data["streams"][0]["width"], data["streams"][0]["height"]

    scale_w = 384
    raw_h = h * scale_w / w
    scale_h = int(raw_h) if int(raw_h) % 2 == 0 else int(raw_h) + 1  # match -2 rounding

    frame_size = scale_w * scale_h * 3

    # ---- FFmpeg frame extraction (NO timestamps) ----
    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vf", f"fps=0.5,scale={scale_w}:{scale_h}",
        # "-vsync", "vfr",
        "-f", "rawvideo",
        "-pix_fmt", "rgb24",
        "-an",
        "pipe:1"
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        bufsize=10**8
    )

    # scale_w = 384
    # scale_h = int(h * (384 / w))

    # frame_size = scale_w * scale_h * 3
    frames_list = []

    try:
        while True:
            raw = process.stdout.read(frame_size)
            if not raw or len(raw) < frame_size:
                break
            frame = np.frombuffer(raw, np.uint8).reshape((scale_h, scale_w, 3))
            frames_list.append(frame)
    finally:
        process.stdout.close()
        process.wait(timeout=10)


    if not frames_list:
        return [], np.empty((0,))

    all_frames = frames_list
    num_frames = len(all_frames)

    embeddings = []
    batch_size = 8

    for i in range(0, num_frames, batch_size):
        imgs = [Image.fromarray(f) for f in all_frames[i:i + batch_size]]
        inputs = siglip_processor(images=imgs, return_tensors="pt").to(device)
        with torch.no_grad():
            output = siglip_model.get_image_features(**inputs)

        if hasattr(output, "pooler_output"):
            emb = output.pooler_output
        else:
            emb = output

        embeddings.append(emb.detach().cpu().numpy())


    embeddings = np.vstack(embeddings)

    k = min(clusters, num_frames//2)
    kmeans = KMeans(n_clusters=k, random_state=42, n_init="auto")
    labels = kmeans.fit_predict(embeddings)
    centroids = kmeans.cluster_centers_

    selected_indices = []
    for i in range(k):
        idxs = np.where(labels == i)[0]
        if len(idxs) == 0:
            continue
        dists = np.linalg.norm(embeddings[idxs] - centroids[i], axis=1)
        selected_indices.append(idxs[np.argmin(dists)])

    selected_indices = sorted(set(selected_indices))

    keyframe_emb_list = []
    keyframes_meta = []

    for src_idx in selected_indices:
        frame = all_frames[src_idx]

        s3_key = upload_frame_to_s3(
            frame,
            os.environ["AWS_OUT_BUCKET"],
            video_id,
            frame_index=src_idx,  
            s3_client=s3_client, 
            quality=70
        )

        keyframe_emb_list.append(embeddings[src_idx])
        keyframes_meta.append({
            "frame_index": int(src_idx),   
            "s3_key": s3_key
        })

    keyframe_embeddings = np.array(keyframe_emb_list)

    return keyframes_meta, keyframe_embeddings

# @benchmark
def chunk_full_transcript(text: str, max_chars=300):
    words = text.split()
    chunks = []
    current = []

    for w in words:
        current.append(w)
        if len(" ".join(current)) >= max_chars:
            chunks.append(" ".join(current))
            current = []

    if current:
        chunks.append(" ".join(current))

    return chunks
    
# @benchmark
def store_text_embeddings(full_transcript: str,video_id:str,sentence_model=None,supabase=None,):
    
    chunks = chunk_full_transcript(full_transcript)
    embeddings = [
        sentence_model.encode(chunk).tolist()
        for chunk in chunks
    ]

    rows = []
    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        rows.append({
            "session_id": video_id,
            "chunk_index": i,
            "content": chunk,
            "embedding": emb,
        })

    supabase.table("text_embeddings").upsert(rows).execute()

@benchmark
def store_image_embeddings(keyframes_meta: list[dict],image_embeddings: list[list[float]],video_id:str,supabase=None):
    rows = []
    for meta, emb in zip(keyframes_meta, image_embeddings):
        rows.append({
            "session_id": video_id,
            "frame_index": meta["frame_index"],
            "embedding": emb.tolist(),
        })

    supabase.table("image_embeddings").upsert(rows).execute()

def retrieve_text_by_query(query: str,video_id: str, top_k: int = 5,sentence_model=None,supabase=None
):
    query_embedding = sentence_model.encode(query).tolist()
    response = supabase.rpc(
        "match_text_embeddings",
        {
            "query_embedding": query_embedding,
            "match_session_id": video_id,
            "match_count": top_k,
        },
    ).execute()

    return [row["content"] for row in response.data]

def retrieve_images_by_query(vlm_query: str,video_id: str, top_k: int = 8,siglip_model=None,siglip_processor=None, device=None,supabase=None):
    
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    if siglip_processor is None:
        raise RuntimeError("Processor not loaded")
    
    if siglip_model is None:
        raise RuntimeError("Model not loaded")
    
    inputs = siglip_processor(
        text=[vlm_query],
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=64,
    ).to(device)

    with torch.no_grad():
        output = siglip_model.get_text_features(**inputs)
        if hasattr(output, "pooler_output"):
            emb = output.pooler_output[0]
        else:
            emb = output[0]

        query_embedding = emb.detach().cpu().numpy().tolist()


    response = supabase.rpc(
        "match_image_embeddings",
        {
            "query_embedding": query_embedding,
            "match_session_id": video_id,
            "match_count": top_k,
        },
    ).execute()
    return [row["frame_index"] for row in response.data]
def generate_text_answer(query: str,video_id: str, history: list[dict],groq_client=None, top_k: int = 5, sentence_model=None, supabase=None) -> str:

    chat_history = "\n".join(
        f"{m['role'].capitalize()}: {m['content']}"
        for m in history[-2:]
    )

    retrieved_docs = retrieve_text_by_query(query,video_id=video_id, sentence_model= sentence_model, supabase=supabase, top_k=top_k)
    
    context = "\n\n".join(retrieved_docs)


    prompt = f"""
You are a helpful and precise assistant.

Answer the question in DETAIL using  the information provided in the Context.



If the user asks for a summary, provide a clear and detailed summary
based strictly on the Context.

---

Answer format:

Answer:
<concise, direct answer>

Sources:
<merge all relevant sentences from the Context into one coherent paragraph>

---

Conversation History:
{chat_history}

Context:
{context}

Question:
{query}

"""

    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )

    return response.choices[0].message.content
def make_query_for_vlm(user_query: str, rag_text: str, groq_client=None) -> str:
    prompt = f"""
You are an assistant that rewrites queries so they are optimized for retrieving the most relevant images from a vision-embedding model.

Inputs:
User Question: {user_query}
RAG Answer: {rag_text}

Output:
A rewritten visual-focused image-retrieval query in less than 64 tokens

"""

    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )

    return response.choices[0].message.content
def download_image_from_s3(object_key: str, s3_client=None) -> Image.Image:
    try:
        response = s3_client.get_object(
            Bucket=os.environ["AWS_OUT_BUCKET"],
            Key=object_key
        )
        return Image.open(BytesIO(response["Body"].read())).convert("RGB")
    except s3_client.exceptions.NoSuchKey:
        print(f"[WARN] Missing S3 key: {object_key}")
        return None

@benchmark
def transcribe( video_id: str, whisper_model=None) -> str:
    m3u8_url=f"https://{os.environ['AWS_OUT_BUCKET']}.s3.{os.environ['AWS_REGION']}.amazonaws.com/{video_id}/audio/index.m3u8"
    
    cmd = [
            "ffmpeg",
            "-i", m3u8_url,
            "-vn",
            "-f", "s16le",
            "-acodec", "pcm_s16le",
            "-ac", "1",
            "-ar", "16000",
            "pipe:1"
    ]
    process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
    )
    raw_audio = process.stdout.read()
    audio = (
            np.frombuffer(raw_audio, np.int16)
            .astype(np.float32) / 32768.0
        )
    text = whisper_model.transcribe(audio,fp16=True,verbose=False)['text']
    return text
def rag_with_gemini(video_id:str,query_actual: str,query_vlm: str,rag_text: str,top_k: int = 8,siglip_model=None,siglip_processor=None, device=None,gemini_model=None,s3_client=None,supabase=None):
    frame_indices = retrieve_images_by_query(query_vlm,video_id=video_id, supabase=supabase, top_k=top_k,siglip_model=siglip_model,siglip_processor=siglip_processor, device=device)
    images=[]
    for frame_index in frame_indices[:6]:
        # image_url = f"https://{os.environ['AWS_OUT_BUCKET']}.s3.{os.environ['AWS_REGION']}.amazonaws.com/{video_id}/frames/{int(frame_index)}.jpg"
        images.append(download_image_from_s3(f"{video_id}/frames/{int(frame_index)}.jpg", s3_client=s3_client))

    STRICT_CONTEXT = (
        "You are a knowledgeable and professional assistant specialized in answering questions about videos.\n"
        "Use the provided context (text and images) to answer the user's question.\n"
        "if the context has absolutely no information relevant to the question, respond with 'I don't know.But if something related is found,you can elaborate'\n"
        "Provide a detailed, clear, and well-structured explanation.\n"
        "Maintain a professional, instructional tone similar to that of an expert tutor."
        "### Output Format Rules (MANDATORY)\n\n"

    "Your response MUST follow this structure:\n\n"

    "## Answer\n"
    "- Provide a clear, concise, and direct answer to the user's question.\n"
    "- Maintain a professional, instructional tone.\n\n"

    "## Evidence from Context\n"
    "- List specific observations from the provided text and/or images.\n"
    "- Use bullet points.\n"
    )

    message_parts = [
        f"{STRICT_CONTEXT}\nQuestion: {query_actual}\nContext:\n{rag_text+query_vlm}"
    ]

    for item in images:
        message_parts.append(item)

    response = gemini_model.generate_content(message_parts)
    return response.text


def generate_intro_section(all_chunks: list[str], gemini_model):
    """
    Generates a short introduction section for study notes.
    Returns:
        {
            "title": "...",
            "intro": "..."
        }
    """

    STRICT_PROMPT = (
        "You are a professional academic notes generator.\n\n"
        "Based on the full transcript provided, generate a concise introduction "
        "for study notes. The introduction should:\n"
        "- Provide a brief overview of the video's content\n"
        "- Highlight the main themes covered\n"
        "- Be clear and professional\n"
        "- Be 3-5 sentences maximum\n\n"
        "OUTPUT FORMAT (JSON ONLY):\n"
        "{\n"
        '  "title": "Short descriptive title for the notes",\n'
        '  "intro": "Concise introductory paragraph"\n'
        "}\n\n"
        "Return ONLY valid JSON. No markdown. No explanations."
    )

    full_transcript = "\n\n".join(all_chunks)

    response = gemini_model.generate_content([
        f"{STRICT_PROMPT}\n\nTranscript:\n{full_transcript}"
    ])

    try:
        parsed = json.loads(response.text)
    except Exception:
        
        cleaned = response.text.strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        parsed = json.loads(cleaned[start:end])

    return parsed

################################
#PDF GENERATION                #
################################

def generate_pdf(video_id:str,gemini_model=None,supabase=None,sentence_model=None,siglip_model=None,siglip_processor=None, device=None):
    RETRIEVAL_QUERY="GIVE ME ALL THE IMPORTANT CONCEPTS PRESENTED IN THE VIDEO,TO BE USED TO MAKE NOTES FOR STUDYING PURPOSES"
    all_chunks=retrieve_text_by_query(video_id=video_id,top_k=50,query=RETRIEVAL_QUERY,sentence_model=sentence_model,supabase=supabase)
    half_transcript = "\n\n".join(all_chunks[:len(all_chunks)//2])
    end_transcript = "\n\n".join(all_chunks[len(all_chunks)//2:])
    
    STRICT_CONTEXT = (
    "You are a smart professional notes generator that creates study notes for students based on video transcripts.\n"
    "You are currently given a PART of the transcript of a video, and your task is to generate study notes that summarize the key concepts, ideas, and information presented in this part of the video.\n"
    "The notes should be clear and detailed for students to use for revision and understanding of the video content.\n\n"
    "Also,only if required add a visual query that can be used to retrieve relevant images/diagrams that would help in understanding the topic better. This visual query should be specific and descriptive to ensure the retrieved images are highly relevant to the topic.\n\n"
    "OUTPUT FORMAT (JSON):\n"
    "{\n"
    '  "topics": [\n'
    "    {\n"
    '      "topic_number": 1,\n'
    '      "topic_title": "Clear, descriptive title",\n'
    '      "topic_description": "Detailed explanation of the topic covering key concepts, definitions, examples, and important points",\n'
    '      "visual_query": "If required a visual query to retrieve relevant images/diagrams for this topic.Else leave empty"\n'
    "    }\n"
    "  ]\n"
    "}\n\n"
    
    "REQUIREMENTS:\n"
    "- Identify 1-5 major topics from this transcript segment\n"
    "- Each topic_description should be comprehensive (2-5 sentences)\n"
    "- visual_query should be specific and descriptive if required\n"
    "- Return ONLY valid JSON, no markdown formatting or code blocks\n"
)
    gemini_response = gemini_model.generate_content([
        f"{STRICT_CONTEXT}\nTranscript Segment:\n{half_transcript}"
    ])

    gemini_response2 = gemini_model.generate_content([
        f"{STRICT_CONTEXT}\nTranscript Segment:\n{end_transcript}"
    ])

    intro_response = generate_intro_section(all_chunks, gemini_model)  
    
    resp1 = json.loads(gemini_response.text)
    resp2 = json.loads(gemini_response2.text)

    notes = resp1.get("topics", []) + resp2.get("topics", [])

    for i, note in enumerate(notes):
        if note["visual_query"]:
            images_indices = retrieve_images_by_query(note["visual_query"],video_id=video_id, supabase=supabase, top_k=1,siglip_model=siglip_model,siglip_processor=siglip_processor, device=device)
            note["image_url"] = []
            for frame_index in images_indices:
                image_url = f"https://{os.environ['AWS_OUT_BUCKET']}.s3.{os.environ['AWS_REGION']}.amazonaws.com/{video_id}/frames/{int(frame_index)}.jpg"
                note["image_url"].append(image_url)
        note.pop("visual_query",None)

    # HISTORY_PROMPT = ("Generate a Doubts section citing the question and answer pairs from the conversation history that are relevant to the video content. This section should be helpful for students to clarify common doubts and misconceptions related to the video topics. If no relevant Q&A pairs are found, return an empty list."
    #                   "it should be titled 'Doubts' and each doubt should be in the format:\n\n"
    #                     "## Doubt\n"
    #                     "- Question: <the question>\n"
    #                     "- Answer: <the answer>\n\n"
    #                     "Return ONLY the Doubts section in markdown format, no explanations or additional text.")
    # history_response = gemini_model.generate_content([
    #     f"{HISTORY_PROMPT}\nConversation History:\n{history}"])
    notes_pdf_content = {
        "title": intro_response.get("title", "Study Notes"),
        "introduction": intro_response.get("intro", ""),
        "notes": notes
    }
    return notes_pdf_content

def escape_latex(text: str) -> str:
    replacements = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "\\": r"\textbackslash{}",
    }
    for key, val in replacements.items():
        text = text.replace(key, val)
    return text

def upload_pdf_to_s3(
    pdf_path: str,
    bucket: str,
    video_id: str,
    s3_client=None
):
    key = f"{video_id}/sn.pdf"

    with open(pdf_path, "rb") as f:
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=f,
            ContentType="application/pdf",
        )

    return key

def build_and_upload_pdf(
    notes_pdf_content: dict,
    video_id: str,
    s3_client=None
):

    with tempfile.TemporaryDirectory() as tmpdir:

        tex_path = os.path.join(tmpdir, "notes.tex")
        pdf_path = os.path.join(tmpdir, "notes.pdf")

        # ----------------------------
        # LaTeX Header + Title Page
        # ----------------------------
        latex_content = r"""
\documentclass[12pt]{article}

\usepackage[a4paper,margin=1in]{geometry}
\usepackage{graphicx}
\usepackage{float}
\usepackage{titlesec}
\usepackage{fancyhdr}
\usepackage{hyperref}
\usepackage{xcolor}
\usepackage{lmodern}
\usepackage{setspace}
\usepackage{parskip}

\hypersetup{
    colorlinks=true,
    linkcolor=blue,
    urlcolor=blue
}

\pagestyle{fancy}
\fancyhf{}
\rhead{\thepage}
\lhead{Study Notes}

\definecolor{sectionblue}{RGB}{25, 70, 150}

\titleformat{\section}
  {\Large\bfseries\color{sectionblue}}
  {\thesection}{1em}{}

\title{%s}
\author{}
\date{\today}

\begin{document}

\begin{titlepage}
    \centering
    \vspace*{2cm}
    {\Huge\bfseries %s\par}
    \vspace{1cm}
    {\Large Comprehensive Study Notes\par}
    \vfill
    {\large Generated on \today\par}
\end{titlepage}

\tableofcontents
\newpage

\section*{Introduction}
\addcontentsline{toc}{section}{Introduction}
\onehalfspacing
%s
\newpage
""" % (
            escape_latex(notes_pdf_content["title"]),
            escape_latex(notes_pdf_content["title"]),
            escape_latex(notes_pdf_content["introduction"])
        )
        for idx, topic in enumerate(notes_pdf_content["notes"], start=1):

            latex_content += "\n\\section{%s}\n" % escape_latex(topic["topic_title"])
            latex_content += "\\vspace{0.3cm}\n"
            latex_content += "%s\n\n" % escape_latex(topic["topic_description"])
            latex_content += "\\vspace{0.5cm}\n"

            if topic.get("image_url"):

                for img_i, img_url in enumerate(topic["image_url"]):

                    object_key = img_url.split(".amazonaws.com/")[-1]
                    image = download_image_from_s3(object_key, s3_client=s3_client)

                    if image:
                        local_img_path = os.path.join(tmpdir, f"{idx}_{img_i}.jpg")
                        image.save(local_img_path)

                        latex_content += r"""
\begin{figure}[H]
\centering
\includegraphics[width=0.75\linewidth]{%s}
\caption{Illustration related to the topic}
\vspace{0.3cm}
\end{figure}
""" % local_img_path

        latex_content += "\n\\end{document}"

        # Write .tex file
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(latex_content)

        # Compile
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "notes.tex"],
            cwd=tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        upload_pdf_to_s3(
            pdf_path,
            bucket=os.environ["AWS_OUT_BUCKET"],
            video_id=video_id,
            s3_client=s3_client
        )

        return {
            "status": "uploaded",
            "s3_key": f"{video_id}/sn.pdf"
        }

    
##################################
#ENDPOINTS
##################################
@app.cls(
    image=image,
    gpu="L4",
    timeout=60 * 60,
    max_containers=1,
    enable_memory_snapshot=True,
    secrets=[modal.Secret.from_name("videorag-secrets")]
)
class VideoProcessor:
    @modal.enter(snap=True)
    def load_models(self):
        from supabase import create_client
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        load_dotenv()

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        def load_siglip_model():
            return AutoModel.from_pretrained(
                "google/siglip-so400m-patch14-384",
                torch_dtype=torch.float16
            ).to(self.device)
        
        def load_siglip_processor():
            return AutoProcessor.from_pretrained(
                "google/siglip-so400m-patch14-384",
                use_fast=True
            )
        
        def load_sentence_model():
            return SentenceTransformer(
                "sentence-transformers/all-MiniLM-L6-v2"
            )
        
        def load_gemini():
            import google.generativeai as genai
            from google.generativeai import GenerativeModel
            genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
            return GenerativeModel("gemini-2.5-flash")
        
        def load_groq():
            from groq import Groq
            return Groq(api_key=os.environ["GROQ_API_KEY"])
        
        def load_s3():
            import boto3
            session = boto3.Session(
                aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
                aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
                region_name=os.environ["AWS_REGION"],
            )
            return session.client("s3")
        
        def load_supabase():
            from supabase import create_client
            return create_client(
                os.environ["SUPABASE_URL"],
                os.environ["SUPABASE_SERVICE_KEY"]
            )
        def load_whisper():
            return whisper.load_model("base", device=self.device)
        
        # Load all models concurrently
        load_functions_map = {
            "siglip_model": load_siglip_model,
            "siglip_processor": load_siglip_processor,
            "sentence_model": load_sentence_model,
            "gemini_model": load_gemini,
            "groq_client": load_groq,
            "s3": load_s3,
            "supabase": load_supabase,
            "whisper_model": load_whisper

        }
        
        components = {}
        with ThreadPoolExecutor(max_workers=len(load_functions_map)) as executor:
            future_to_model_id = {
                executor.submit(load_fn): model_id 
                for model_id, load_fn in load_functions_map.items()
            }
            
            for future in as_completed(future_to_model_id.keys()):
                model_id = future_to_model_id[future]
                try:
                    components[model_id] = future.result()
                except Exception as exc:
                    print(f'{model_id} generated an exception: {exc}')
                    raise
        
        
        self.siglip_model = components["siglip_model"]
        self.siglip_processor = components["siglip_processor"]
        self.sentence_model = components["sentence_model"]
        self.gemini_model = components["gemini_model"]
        self.groq_client = components["groq_client"]
        self.s3 = components["s3"]
        self.supabase = components["supabase"]
        self.whisper_model = components["whisper_model"]
        
    @modal.method()
    def process(self, video_id: str, duration: int):
        
        metadata, embeddings = extract_keyframes(
            duration=duration,
            video_id=video_id,
            siglip_model=self.siglip_model,
            siglip_processor=self.siglip_processor,
            device=self.device,
            s3_client=self.s3
        )

        text = transcribe(video_id, whisper_model=self.whisper_model)

        store_text_embeddings(
            text,
            video_id=video_id,
            sentence_model=self.sentence_model,
            supabase=self.supabase
        )

        store_image_embeddings(
            metadata,
            video_id=video_id,
            image_embeddings=embeddings,
            supabase=self.supabase
        )
        # notes=generate_pdf(
        #     video_id=video_id,
        #     gemini_model=self.gemini_model,
        #     supabase=self.supabase,
        #     sentence_model=self.sentence_model,
        #     siglip_model=self.siglip_model,
        #     siglip_processor=self.siglip_processor,
        #     device=self.device
        # )
        # build_and_upload_pdf(video_id=video_id,notes_pdf_content=notes,s3_client=self.s3)

        return {"status": "processed", "video_id": video_id}

@app.cls(
    image=image,
    gpu="A100",
    timeout=60 * 10,
    max_containers=1,
    enable_memory_snapshot=True,
    # experimental_options={"enable_gpu_snapshot": True},
    secrets=[modal.Secret.from_name("videorag-secrets")]
)
class VideoChat:
    @modal.enter(snap=True)
    def load_models(self):
        from concurrent.futures import ThreadPoolExecutor, as_completed
        load_dotenv()
        import torch
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Define loading functions
        def load_siglip_model():
            return AutoModel.from_pretrained(
                "google/siglip-so400m-patch14-384",
                torch_dtype=torch.float16
            ).to(self.device)
        
        def load_siglip_processor():
            return AutoProcessor.from_pretrained(
                "google/siglip-so400m-patch14-384",
                use_fast=True
            )
        
        def load_sentence_model():
            return SentenceTransformer(
                "sentence-transformers/all-MiniLM-L6-v2"
            ).half()
        
        def load_gemini():
            import google.generativeai as genai
            from google.generativeai import GenerativeModel
            genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
            return GenerativeModel("gemini-2.5-flash")
        
        def load_groq():
            from groq import Groq
            return Groq(api_key=os.environ["GROQ_API_KEY"])
        
        def load_s3():
            import boto3
            session = boto3.Session(
                aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
                aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
                region_name=os.environ["AWS_REGION"],
            )
            return session.client("s3")
        
        def load_supabase():
            from supabase import create_client
            return create_client(
                os.environ["SUPABASE_URL"],
                os.environ["SUPABASE_SERVICE_KEY"]
            )
        
        # Load all models concurrently
        load_functions_map = {
            "siglip_model": load_siglip_model,
            "siglip_processor": load_siglip_processor,
            "sentence_model": load_sentence_model,
            "gemini_model": load_gemini,
            "groq_client": load_groq,
            "s3": load_s3,
            "supabase": load_supabase,
        }
        
        components = {}
        with ThreadPoolExecutor(max_workers=len(load_functions_map)) as executor:
            future_to_model_id = {
                executor.submit(load_fn): model_id 
                for model_id, load_fn in load_functions_map.items()
            }
            
            for future in as_completed(future_to_model_id.keys()):
                model_id = future_to_model_id[future]
                try:
                    components[model_id] = future.result()
                except Exception as exc:
                    print(f'{model_id} generated an exception: {exc}')
                    raise
        
        # Assign to self
        self.siglip_model = components["siglip_model"]
        self.siglip_processor = components["siglip_processor"]
        self.sentence_model = components["sentence_model"]
        self.gemini_model = components["gemini_model"]
        self.groq_client = components["groq_client"]
        self.s3 = components["s3"]
        self.supabase = components["supabase"]
        

    @modal.method()
    def chat(self, video_id: str, query: str, history: list[dict]|None = None, top_k: int = 8):
        if history is None:
            history = []
        text_ans = generate_text_answer(
            query=query,
            video_id=video_id,
            history=history,
            groq_client=self.groq_client,
            sentence_model=self.sentence_model,
            supabase=self.supabase,
            top_k=top_k
        )

        vlm_query = make_query_for_vlm(query, text_ans, self.groq_client)
        short_note_resp=generate_pdf(
            video_id=video_id,
            history=history,
            gemini_model=self.gemini_model,
            supabase=self.supabase,
            sentence_model=self.sentence_model,
            siglip_model=self.siglip_model,
            siglip_processor=self.siglip_processor,
            device=self.device
        )
        rag_response=rag_with_gemini(
            video_id=video_id,
            query_actual=query,
            query_vlm=vlm_query,
            rag_text=text_ans,
            top_k=top_k,
            siglip_model=self.siglip_model,
            siglip_processor=self.siglip_processor,
            device=self.device,
            gemini_model=self.gemini_model,
            s3_client=self.s3,
            supabase=self.supabase
        )

        return {
            "short_notes": short_note_resp,
            "rag_response": rag_response
        }
    
video_processor = VideoProcessor()
video_chat = VideoChat()

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("videorag-secrets")]
)
@modal.fastapi_endpoint(method="POST")
def process_endpoint(req: ProcessRequest):
    video_processor.process.spawn(
        video_id=req.video_id,
        duration=req.duration
    )

    return {"status": "processing started"}


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("videorag-secrets")]
)
@modal.fastapi_endpoint(method="POST")
def chat_endpoint(req: ChatRequest):
    return video_chat.chat.remote(
        video_id=req.video_id,
        query=req.query,
        history=req.history,
        top_k=req.top_k
    )
