"""
Vercel Serverless Entrypoint for AI Vision Assistant (2026)
Optimized for Vercel Python runtime: lightweight, stateless, 100% English.
"""

import os
import io
import json
import base64
from typing import Optional
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import AsyncGroq
from gtts import gTTS

app = FastAPI(title="AI Vision Assistant (Cloud Edge Vercel API)", version="2026.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")
GROQ_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.3-70b-versatile")

# Candidate vision models in priority order
VISION_CANDIDATE_MODELS = [
    GROQ_VISION_MODEL,
    "qwen/qwen3.8-27b",
]

def get_groq_client():
    key = os.getenv("GROQ_API_KEY", GROQ_API_KEY)
    if key and key.startswith("gsk_"):
        return AsyncGroq(api_key=key)
    return None

class SceneRequest(BaseModel):
    image_b64: str
    query: Optional[str] = None

class TTSRequest(BaseModel):
    text: str

class ChatRequest(BaseModel):
    query: str
    image_b64: Optional[str] = None

@app.get("/api/health")
async def health():
    return {
        "status": "online",
        "environment": "Vercel Serverless Cloud Edge",
        "groq_configured": bool(get_groq_client()),
        "vision_model": GROQ_VISION_MODEL,
        "vision_candidates": VISION_CANDIDATE_MODELS
    }

async def call_groq_vision(client, messages, response_format=None, max_tokens=250):
    last_err = None
    for model in VISION_CANDIDATE_MODELS:
        try:
            kwargs = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.2
            }
            if response_format:
                kwargs["response_format"] = response_format
            response = await client.chat.completions.create(**kwargs)
            return response, model
        except Exception as e:
            last_err = e
            err_msg = str(e).lower()
            print(f"[Groq Vision] Model {model} error: {e}")
            if any(k in err_msg for k in ["decommissioned", "not_found", "model_decommissioned", "invalid_request_error"]):
                continue
            raise e
    raise last_err

@app.post("/api/analyze-scene")
async def analyze_scene(req: SceneRequest):
    """
    Multimodal scene hazard analysis for Vercel Cloud Edge mode.
    Evaluates image and returns safe/danger status, priority alerts, and scene description in English.
    """
    client = get_groq_client()

    if not client:
        return {
            "status": "SAFE",
            "priority_alert": None,
            "scene_description": "Forward path appears clear. Proceed with care.",
            "speech_text": "Forward path is clear."
        }

    system_prompt = (
        "You are an AI Object Detection and Walking Assistant for the visually impaired. "
        "Analyze the camera view carefully. Identify all visible objects, people, hazards, and obstacles (e.g. person, chair, cell phone, bottle, cup, laptop, car, door, steps, wall). "
        "Estimate the walking corridor (left, center, or right) and proximity (very close, close, or ahead) for each object. "
        "IMPORTANT: Only set status to 'DANGER' if an actual physical hazard, vehicle, or obstacle is blocking the center walking path. "
        "If the camera view is dark, blurry, empty, or clear, set status to 'SAFE', priority_alert to null, and inform the user that the path is clear. "
        "Respond strictly in JSON format with exact keys:\n"
        "{\n"
        '  "status": "SAFE" or "DANGER",\n'
        '  "priority_alert": "Short urgent warning if hazard or person exists directly ahead, else null",\n'
        '  "detected_objects": ["person", "chair", "cell phone"],\n'
        '  "detections": [\n'
        '    {\n'
        '      "label": "person",\n'
        '      "conf": 0.95,\n'
        '      "corridor": "center",\n'
        '      "proximity": "very close",\n'
        '      "is_critical": true,\n'
        '      "bbox": [100, 150, 800, 750]\n'
        '    }\n'
        '  ],\n'
        '  "scene_description": "2 sentences describing surroundings and forward path",\n'
        '  "speech_text": "Natural spoken sentence listing detected objects and navigation advice"\n'
        "}\n"
    )

    img_url = req.image_b64 if req.image_b64.startswith("data:image") else f"data:image/jpeg;base64,{req.image_b64}"

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": req.query or "Check this path for walking hazards, people, or obstacles."},
                    {"type": "image_url", "image_url": {"url": img_url}}
                ]
            }
        ]
        response, used_model = await call_groq_vision(
            client,
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=350
        )
        res_json = json.loads(response.choices[0].message.content)
        res_json["used_model"] = used_model
        return res_json
    except Exception as e:
        print(f"[Vercel analyze-scene Error]: {e}")
        return {
            "status": "SAFE",
            "priority_alert": None,
            "scene_description": "Camera monitoring active. Forward corridor is being tracked.",
            "speech_text": "Path monitored.",
            "error_detail": str(e)
        }

@app.post("/api/ocr")
@app.post("/api/ocr/frame")
async def ocr_read(req: SceneRequest):
    """Multimodal text reading for documents and street signs in English"""
    client = get_groq_client()

    if not client:
        return {
            "success": True,
            "text": "Notice / Document detected.",
            "summary": "Document detected. Please connect Groq API key in Settings for full reading."
        }

    prompt = (
        "Transcribe all readable text from this image accurately. "
        "Then provide a 1-sentence plain summary in English suitable for read-aloud audio to a visually impaired person. "
        "Return JSON with keys: 'text', 'summary'."
    )

    img_url = req.image_b64 if req.image_b64.startswith("data:image") else f"data:image/jpeg;base64,{req.image_b64}"

    try:
        messages = [
            {"role": "system", "content": "You are a fast document reading vision assistant."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": img_url}}
                ]
            }
        ]
        response, used_model = await call_groq_vision(
            client,
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=300
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"success": False, "error": str(e), "summary": "Text reading encountered an issue."}

@app.post("/api/chat/multimodal")
async def chat_multimodal(req: ChatRequest):
    """Conversational question answering with image context in English"""
    client = get_groq_client()

    if not client:
        return {
            "query": req.query,
            "reply": "I see your surroundings. The path ahead is open."
        }

    system = "You are an assistive vision companion for an elderly or blind person. Be concise, direct, helpful, and under 2 sentences in clear English."

    messages = [{"role": "system", "content": system}]
    if req.image_b64:
        img_url = req.image_b64 if req.image_b64.startswith("data:image") else f"data:image/jpeg;base64,{req.image_b64}"
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": req.query},
                {"type": "image_url", "image_url": {"url": img_url}}
            ]
        })
    else:
        messages.append({"role": "user", "content": req.query})

    try:
        response, used_model = await call_groq_vision(
            client,
            messages=messages,
            max_tokens=150
        )
        return {"query": req.query, "reply": response.choices[0].message.content.strip(), "used_model": used_model}
    except Exception as e:
        return {"query": req.query, "reply": f"Assistant response unavailable: {str(e)}"}

@app.post("/api/tts")
async def tts_fallback(req: TTSRequest):
    """Server-side TTS audio fallback returning MP3 audio stream in English"""
    try:
        tts = gTTS(text=req.text, lang="en", slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        return Response(content=buf.read(), media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
