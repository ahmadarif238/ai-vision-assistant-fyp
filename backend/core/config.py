import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Vision Assistant for the Visually Impaired"
    VERSION: str = "2026.1.0-SOTA"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Groq Multi-Modal & Speech Configuration
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_VISION_MODEL: str = os.getenv("GROQ_VISION_MODEL", "llama-3.2-11b-vision-preview")
    GROQ_FALLBACK_MODEL: str = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.3-70b-versatile")
    GROQ_WHISPER_MODEL: str = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")
    
    # Model Weights Paths
    BASE_DIR_PATH: Path = BASE_DIR
    MODELS_DIR: Path = BASE_DIR / "models"
    
    YOLOV8_OPENVINO_DIR: str = str(BASE_DIR / "models" / "yolov8n_openvino_model")
    YOLOV8_ONNX_PATH: str = str(BASE_DIR / "models" / "yolov8n.onnx")
    YOLO_OIV7_ONNX_PATH: str = str(BASE_DIR / "models" / "yolov8n-oiv7.onnx")
    DEPTH_ANYTHING_ONNX_PATH: str = str(BASE_DIR / "models" / "depth_anything_v2_small_int8.onnx")
    YOLO_TUNED_PATH: str = str(BASE_DIR / "models" / "yolo-tuned.pt")
    YOLO11N_PATH: str = str(BASE_DIR / "models" / "yolo11n.pt")
    
    # Open-Vocabulary Zero-Shot Hazard Prompts (Pakistani Pedestrian & Indoor Hazards)
    HAZARD_PROMPTS: List[str] = [
        "pothole",
        "open manhole",
        "unpaved ditch",
        "step",
        "electrical switchboard",
        "hanging wire",
        "motorcycle",
        "barrier",
        "stairs",
        "pole",
        "curb"
    ]
    
    # Spatial Corridors & Thresholds
    CORRIDOR_LEFT: float = 0.33
    CORRIDOR_RIGHT: float = 0.67
    
    # Bounding Box Area Proximity Ratios (Area_Ratio = BBox_Area / Frame_Area)
    PROXIMITY_CRITICAL_RATIO: float = 0.16   # Trigger immediate audio chime & urgent speech
    PROXIMITY_WARNING_RATIO: float = 0.07    # Noticeable obstacle approaching
    PROXIMITY_FAR_RATIO: float = 0.02        # Far background
    
    # Depth Safety Net Parameters
    DEPTH_MAX_ALERT_SCORE: float = 0.75      # Critical obstacle close in corridor
    DEPTH_DROP_OFF_THRESHOLD: float = 0.20   # Ground drop-off (hole, sudden slope, ditch)
    
    # WebRTC & Streaming Defaults
    INFERENCE_IMG_SIZE: int = 320
    MAX_WS_QUEUE_SIZE: int = 2

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

