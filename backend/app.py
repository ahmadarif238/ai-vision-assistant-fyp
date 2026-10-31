import os
import time
import base64
import asyncio
from typing import Optional, Dict, Any
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from backend.core.config import settings
from backend.core.detection_engine import detection_engine
from backend.core.hazard_analyzer import hazard_analyzer
from backend.core.depth_safety_net import depth_safety_net
from backend.core.ocr_engine import ocr_engine
from backend.core.groq_agent import groq_agent

# Initialize FastAPI App
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Production-grade AI Vision & Navigation Assistant for the Visually Impaired"
)

# CORS Configuration for Mobile and Web Clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files directory for Progressive Web App
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

# Request Schemas
class ChatQuery(BaseModel):
    query: str
    image_b64: Optional[str] = None
    lang: Optional[str] = "en"

class TTSQuery(BaseModel):
    text: str
    lang: Optional[str] = "en"

class SceneAnalysisQuery(BaseModel):
    image_b64: str
    query: Optional[str] = None
    lang: Optional[str] = "en"

class FrameOCRRequest(BaseModel):
    image_b64: str

class SettingsUpdateRequest(BaseModel):
    groq_api_key: Optional[str] = None
    engine_mode: Optional[str] = None  # "openvino", "onnx", "zeroshot", "ultralytics"
    hazard_prompts: Optional[list] = None

# Helper to decode base64 JPEG to numpy image
def decode_base64_image(b64_str: str) -> Optional[np.ndarray]:
    try:
        if "," in b64_str:
            b64_str = b64_str.split(",", 1)[1]
        img_bytes = base64.b64decode(b64_str)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        print(f"[decode_base64_image] Error: {e}")
        return None

# ==========================================
# REST API ENDPOINTS
# ==========================================

@app.get("/")
async def serve_index():
    """Serve PWA Interface"""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "AI Vision Assistant 2026 API is running."}

@app.get("/manifest.json")
async def serve_manifest():
    manifest_file = FRONTEND_DIR / "manifest.json"
    if manifest_file.exists():
        return FileResponse(str(manifest_file), media_type="application/json")
    raise HTTPException(status_code=404, detail="Manifest not found")

@app.get("/sw.js")
async def serve_sw():
    sw_file = FRONTEND_DIR / "sw.js"
    if sw_file.exists():
        return FileResponse(str(sw_file), media_type="application/javascript")
    raise HTTPException(status_code=404, detail="Service worker not found")

@app.post("/api/tts")
async def server_tts(req: TTSQuery):
    """Server-side TTS fallback when browser local speech engine fails"""
    try:
        from gtts import gTTS
        import io
        from fastapi.responses import Response
        tts = gTTS(text=req.text, lang="en", slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        return Response(content=buf.read(), media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analyze-scene")
async def analyze_scene_api(req: SceneAnalysisQuery):
    """REST Scene analysis endpoint matching Cloud Edge mode"""
    img = decode_base64_image(req.image_b64)
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image")
    
    h, w = img.shape[:2]
    detections, _ = await detection_engine.detect_async(img)
    hazard_res = hazard_analyzer.analyze(detections, frame_w=w, frame_h=h)
    depth_res = await depth_safety_net.analyze_corridors_async(img)
    
    status = "DANGER" if hazard_res["has_critical_hazard"] else "SAFE"
    alert = hazard_res["priority_alert"] or (depth_res.get("depth_alert") if depth_res else None)
    speech = alert if (alert and status == "DANGER") else None
        
    return {
        "status": status,
        "priority_alert": alert,
        "scene_description": hazard_res["scene_description"],
        "speech_text": speech,
        "corridors": hazard_res["corridors"],
        "depth_safety": depth_res
    }

@app.get("/api/health")
async def get_health():
    """System health check and engine statuses"""
    return {
        "status": "online",
        "version": settings.VERSION,
        "engine_active": detection_engine.active_mode,
        "openvino_ready": detection_engine.ov_compiled is not None,
        "onnx_ready": detection_engine.onnx_sess is not None,
        "depth_net_ready": depth_safety_net.is_ready,
        "ocr_engine": "rapidocr-onnxruntime (sub-250ms CPU)",
        "groq_configured": bool(groq_agent.api_key),
        "hazard_classes_count": len(detection_engine.classes)
    }

@app.post("/api/settings/update")
async def update_settings(req: SettingsUpdateRequest):
    """Dynamic updates for API key and engine mode"""
    if req.groq_api_key:
        groq_agent.set_api_key(req.groq_api_key)
    if req.engine_mode and req.engine_mode in ["openvino", "onnx", "zeroshot", "ultralytics"]:
        if req.engine_mode == "zeroshot":
            detection_engine.init_zero_shot_hazards(req.hazard_prompts)
        else:
            detection_engine.active_mode = req.engine_mode
    return {"success": True, "active_mode": detection_engine.active_mode, "groq_active": bool(groq_agent.api_key)}

@app.post("/api/ocr/scan")
async def ocr_scan_file(file: UploadFile = File(...)):
    """Upload PDF or Image file for high-speed OCR extraction and speech summary"""
    try:
        content = await file.read()
        res = await ocr_engine.extract_async(content, file.filename or "uploaded.png")
        if res.get("success") and res.get("text"):
            # Generate speech-ready summary
            summary = await groq_agent.summarize_document(res["text"])
            res["summary"] = summary
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ocr/frame")
async def ocr_scan_frame(req: FrameOCRRequest):
    """Snapshot OCR: extract text directly from the current camera frame"""
    img = decode_base64_image(req.image_b64)
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image data")
    res = await ocr_engine.extract_from_frame_async(img)
    if res.get("success") and res.get("text"):
        summary = await groq_agent.summarize_document(res["text"])
        res["summary"] = summary
    return res

@app.post("/api/chat/multimodal")
async def chat_multimodal(req: ChatQuery):
    """Ask questions about the current visual view using Llama 4 Scout / Vision on Groq"""
    try:
        reply = await groq_agent.describe_scene_multimodal(req.query, req.image_b64)
        return {"query": req.query, "reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribe microphone audio query using Whisper-large-v3-turbo"""
    try:
        audio_bytes = await file.read()
        transcript = await groq_agent.transcribe_audio_bytes(audio_bytes, file.filename or "query.wav")
        return {"transcript": transcript}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/benchmark")
async def run_benchmark():
    """Live CPU Benchmark comparing PyTorch, ONNX, and OpenVINO inference speed"""
    try:
        dummy_img = np.random.randint(0, 255, (320, 320, 3), dtype=np.uint8)
        results = {}

        # 1. OpenVINO
        if detection_engine.ov_compiled is not None:
            blob, _, _ = detection_engine.preprocess(dummy_img, 320)
            # warmup
            for _ in range(3): detection_engine.ov_compiled([blob])
            t0 = time.perf_counter()
            for _ in range(15): detection_engine.ov_compiled([blob])
            t_ov = (time.perf_counter() - t0) / 15 * 1000
            results["OpenVINO_IR"] = {"latency_ms": round(t_ov, 2), "fps": round(1000 / t_ov, 1)}

        # 2. ONNX Runtime
        if detection_engine.onnx_sess is not None:
            blob, _, _ = detection_engine.preprocess(dummy_img, 320)
            inp_name = detection_engine.onnx_sess.get_inputs()[0].name
            for _ in range(3): detection_engine.onnx_sess.run(None, {inp_name: blob})
            t0 = time.perf_counter()
            for _ in range(15): detection_engine.onnx_sess.run(None, {inp_name: blob})
            t_onnx = (time.perf_counter() - t0) / 15 * 1000
            results["ONNX_Runtime"] = {"latency_ms": round(t_onnx, 2), "fps": round(1000 / t_onnx, 1)}

        # 3. RapidOCR
        t0 = time.perf_counter()
        ocr_engine.ocr(dummy_img)
        t_ocr = (time.perf_counter() - t0) * 1000
        results["RapidOCR_ONNX"] = {"latency_ms": round(t_ocr, 2)}

        return {"benchmark": results, "device": "Host CPU", "resolution": "320x320"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# WEBSOCKET REAL-TIME FRAME STREAMING
# ==========================================

@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """
    High-frequency non-blocking frame streamer.
    Receives camera frame base64 -> returns real-time detections,
    spatial corridor breakdown, priority voice alerts, and depth safety warnings.
    """
    await websocket.accept()
    frame_counter = 0
    fps_start = time.time()
    last_depth_check = 0.0
    cached_depth_res = None

    try:
        while True:
            data = await websocket.receive_json()
            frame_b64 = data.get("frame")
            if not frame_b64:
                continue

            mode = data.get("mode", "navigation")  # "navigation", "detection", "hazard_depth"
            conf_thresh = float(data.get("conf_thresh", 0.35))
            include_depth = data.get("include_depth", True)

            # Decode frame
            img = decode_base64_image(frame_b64)
            if img is None:
                await websocket.send_json({"error": "Failed to decode frame"})
                continue

            h, w = img.shape[:2]

            # 1. Non-blocking Asynchronous Object Detection
            detections, det_latency = await detection_engine.detect_async(img, conf_thresh=conf_thresh)

            # 2. Spatial Navigation & Proximity Hazard Analysis
            hazard_analysis = hazard_analyzer.analyze(detections, frame_w=w, frame_h=h)

            # 3. Monocular Depth Safety Net (run asynchronously every ~1.2s or on demand)
            now = time.time()
            if include_depth and (now - last_depth_check >= 1.2 or cached_depth_res is None):
                cached_depth_res = await depth_safety_net.analyze_corridors_async(img)
                last_depth_check = now

            # Compute real-time FPS
            frame_counter += 1
            elapsed_total = time.time() - fps_start
            current_fps = round(frame_counter / max(1e-3, elapsed_total), 1)
            if elapsed_total > 5.0:
                frame_counter = 0
                fps_start = time.time()

            # Merge priority alerts (Depth alert + Object proximity alert)
            combined_alert = hazard_analysis["priority_alert"]
            if not combined_alert and cached_depth_res and cached_depth_res.get("depth_alert"):
                combined_alert = cached_depth_res["depth_alert"]

            # Response Payload
            response_payload = {
                "timestamp": round(time.time(), 3),
                "fps": current_fps,
                "latency_ms": round(det_latency, 1),
                "active_engine": detection_engine.active_mode,
                "detections": hazard_analysis["objects"],
                "corridors": hazard_analysis["corridors"],
                "scene_description": hazard_analysis["scene_description"],
                "priority_alert": combined_alert,
                "has_critical_hazard": hazard_analysis["has_critical_hazard"],
                "depth_safety": cached_depth_res
            }

            await websocket.send_json(response_payload)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WebSocket Error]: {e}")

