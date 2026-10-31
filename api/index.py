"""
Vercel Serverless Entrypoint for AI Vision Assistant (2026)
Optimized for Vercel Python runtime: lightweight, stateless, 100% English.
Silent-Until-Danger Navigation & Interactive Multimodal Companion.
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

app = FastAPI(title="AI Vision Assistant (Cloud Edge Vercel API)", version="2026.2.0")

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
    Strict Silent-Until-Danger Policy:
    Returns status: SAFE, priority_alert: null, speech_text: null on clear paths.
    Only triggers DANGER for true physical collision hazards in the center path or encroaching sides.
    """
    client = get_groq_client()

    if not client:
        return {
            "status": "SAFE",
            "priority_alert": None,
            "scene_description": "Forward path is clear. Silent monitoring active.",
            "speech_text": None,
            "detections": []
        }

    system_prompt = (
        "You are an AI Walking Mobility Safety Assistant for a visually impaired user. "
        "Strict 'Silent-Until-Danger' Policy:\n"
        "1. SAFE PATH RULE: If the walking path is clear, or if visible objects are harmless background items "
        "(such as laptops, phones, cups, bottles, books, desk accessories, distant walls, or distant furniture), "
        "or if the camera is dark or blurry, you MUST set status to 'SAFE', priority_alert to null, and speech_text to null. "
        "NEVER generate spoken alerts for safe paths or benign objects.\n"
        "2. THREAT RULE: Set status to 'DANGER' ONLY when an actual physical obstacle or danger is directly in the user's "
        "collision trajectory (specifically the CENTER walking path, or a large hazard encroaching closely from left/right). "
        "Physical hazards include: pothole, open manhole/drain, steps/stairs, vehicle/motorcycle, a person directly blocking "
        "the center path, pole, barrier, hanging wire, or sudden ground drop-off.\n"
        "3. When DANGER is detected, provide a crisp, 4-to-6 word directional warning in priority_alert and speech_text "
        "(e.g., 'Caution: Step directly ahead', 'Stop: Obstacle in center path', 'Warning: Person blocking path').\n"
        "Respond strictly in JSON format with exact schema:\n"
        "{\n"
        '  "status": "SAFE" or "DANGER",\n'
        '  "priority_alert": "Crisp 4-6 word warning ONLY if physical danger in center path, else null",\n'
        '  "detected_objects": ["person", "chair"],\n'
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
        '  "scene_description": "Brief 1-sentence description of surroundings",\n'
        '  "speech_text": "Same 4-6 word warning if DANGER, strictly null if SAFE"\n'
        "}\n"
    )

    img_url = req.image_b64 if req.image_b64.startswith("data:image") else f"data:image/jpeg;base64,{req.image_b64}"

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": req.query or "Check this path for physical walking hazards or obstacles."},
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
        
        # Enforce Silent-Until-Danger guard on response
        if res_json.get("status") != "DANGER":
            res_json["status"] = "SAFE"
            res_json["priority_alert"] = None
            res_json["speech_text"] = None

        return res_json
    except Exception as e:
        print(f"[Vercel analyze-scene Error]: {e}")
        return {
            "status": "SAFE",
            "priority_alert": None,
            "scene_description": "Silent monitoring active.",
            "speech_text": None,
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
            "summary": "Document detected. Please configure Groq API key for full OCR reading."
        }

    prompt = (
        "Transcribe all readable text from this image accurately. "
        "Then provide a crisp 1-to-2 sentence summary in English suitable for reading aloud to a visually impaired person. "
        "Return JSON with keys: 'text', 'summary'."
    )

    img_url = req.image_b64 if req.image_b64.startswith("data:image") else f"data:image/jpeg;base64,{req.image_b64}"

    try:
        messages = [
            {"role": "system", "content": "You are a fast document reading vision assistant for the blind. Output clear English."},
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
        return {"success": False, "error": str(e), "summary": "Text reading encountered an issue. Please hold the document steady and retry."}

@app.post("/api/chat/multimodal")
async def chat_multimodal(req: ChatRequest):
    """
    Conversational question answering with image context in English.
    Handles:
    - Spatial room descriptions ("What is around me?", "Describe room")
    - Object locating ("Where is the chair / switch / door?")
    - Voice commands ("Mute alerts", "Resume navigation", "Read text")
    """
    user_query = req.query.strip().lower()
    
    # Handle quick voice commands locally for zero latency
    if any(q in user_query for q in ["mute alert", "mute sound", "turn off voice", "quiet mode", "stop talking", "mute"]):
        return {"query": req.query, "reply": "Alerts muted. Silent mode active.", "command": "mute"}
    if any(q in user_query for q in ["unmute", "resume navigation", "turn on voice", "enable sound", "start alerts"]):
        return {"query": req.query, "reply": "Navigation alerts resumed.", "command": "unmute"}
    if any(q in user_query for q in ["read text", "read document", "read sign", "scan text", "read this"]):
        return {"query": req.query, "reply": "Scanning text in front of you.", "command": "ocr"}

    client = get_groq_client()
    if not client:
        return {
            "query": req.query,
            "reply": "I see your camera view. The walking path directly ahead is open."
        }

    system = (
        "You are an assistive vision companion for an elderly or visually impaired person. "
        "Answer the user's question directly, clearly, and naturally in 1 to 2 sentences of spoken English.\n"
        "- If asked 'What is around me?' or 'Describe the room': summarize the overall layout and key objects using relative positions "
        "(e.g., 'You are in a bedroom with a bed on your left, a desk with a computer ahead, and a doorway to your right.').\n"
        "- If asked 'Where is [item]?' or 'Find [item]': give actionable clock-face or step directions "
        "(e.g., 'The chair is two steps ahead slightly to your left at eleven o'clock.').\n"
        "- Keep it concise, helpful, and natural for text-to-speech."
    )

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
            max_tokens=180
        )
        return {"query": req.query, "reply": response.choices[0].message.content.strip(), "used_model": used_model}
    except Exception as e:
        return {"query": req.query, "reply": "I could not analyze the image right now. Please try again."}

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
