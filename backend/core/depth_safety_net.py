import os
import cv2
import numpy as np
import onnxruntime as ort
import asyncio
from typing import Dict, Any, Optional
from backend.core.config import settings

class DepthSafetyNet:
    """
    Asynchronous Monocular Depth Safety Net using Depth-Anything-V2-Small INT8 ONNX.
    Slices depth predictions into Left, Center, and Right corridors.
    Detects physical obstacles and ground drop-offs/potholes without requiring class labels.
    """
    
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or settings.DEPTH_ANYTHING_ONNX_PATH
        self.session: Optional[ort.InferenceSession] = None
        self.is_ready = False
        self._init_session()
        
    def _init_session(self):
        if os.path.exists(self.model_path):
            try:
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = 4
                opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                self.session = ort.InferenceSession(
                    self.model_path,
                    sess_options=opts,
                    providers=["CPUExecutionProvider"]
                )
                self.input_name = self.session.get_inputs()[0].name
                self.is_ready = True
                print(f"[DepthSafetyNet] Loaded Depth Anything V2 INT8 ONNX from: {self.model_path}")
            except Exception as e:
                print(f"[DepthSafetyNet] Failed to load ONNX model: {e}")
                self.session = None
        else:
            print(f"[DepthSafetyNet] Model file not found at {self.model_path}, using heuristic fallback.")

    def preprocess(self, bgr_frame: np.ndarray, target_size: int = 266) -> np.ndarray:
        """Resize and normalize for Depth Anything V2"""
        # Ensure dimensions are divisible by 14
        h, w = target_size, target_size
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (w, h), interpolation=cv2.INTER_CUBIC)
        
        # ImageNet normalization
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        norm = (resized.astype(np.float32) / 255.0 - mean) / std
        
        # HWC -> CHW -> NCHW
        tensor = np.transpose(norm, (2, 0, 1))[None, ...].astype(np.float32)
        return tensor

    def estimate_depth(self, bgr_frame: np.ndarray) -> np.ndarray:
        """
        Runs depth inference. Returns normalized depth map (0.0 to 1.0),
        where 1.0 represents the closest proximity and 0.0 represents the furthest.
        """
        if self.session is not None:
            tensor = self.preprocess(bgr_frame)
            outputs = self.session.run(None, {self.input_name: tensor})
            depth = np.squeeze(outputs[0])
            
            # Normalize to 0.0 - 1.0
            d_min, d_max = float(depth.min()), float(depth.max())
            if d_max > d_min:
                depth_norm = (depth - d_min) / (d_max - d_min)
            else:
                depth_norm = np.zeros_like(depth)
            return depth_norm
        else:
            # Fallback relative gradient estimator
            gray = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2GRAY)
            small = cv2.resize(gray, (266, 266))
            norm = small.astype(np.float32) / 255.0
            return norm

    async def analyze_corridors_async(self, bgr_frame: np.ndarray) -> Dict[str, Any]:
        """Run non-blocking in worker thread"""
        return await asyncio.to_thread(self.analyze_corridors, bgr_frame)

    def analyze_corridors(self, bgr_frame: np.ndarray) -> Dict[str, Any]:
        """
        Slices the frame depth map into Left, Center, and Right corridors.
        Assesses:
          1. Obstacle Zone (30% - 75% height) for oncoming obstructions.
          2. Ground Zone (75% - 100% height) for sudden drop-offs/dips.
        """
        depth_map = self.estimate_depth(bgr_frame)
        h, w = depth_map.shape
        
        # Corridors
        w_split_1 = int(w * settings.CORRIDOR_LEFT)
        w_split_2 = int(w * settings.CORRIDOR_RIGHT)
        
        corridor_slices = {
            "left": depth_map[:, :w_split_1],
            "center": depth_map[:, w_split_1:w_split_2],
            "right": depth_map[:, w_split_2:]
        }
        
        corridor_results = {}
        depth_alerts = []
        
        # Zone splits
        h_mid_start = int(h * 0.30)
        h_mid_end = int(h * 0.75)
        h_ground_start = int(h * 0.75)
        
        for name, c_slice in corridor_slices.items():
            mid_zone = c_slice[h_mid_start:h_mid_end, :]
            ground_zone = c_slice[h_ground_start:, :]
            
            # Mean proximity in obstacle zone (higher = closer obstacle)
            obstacle_proximity = float(np.mean(mid_zone)) if mid_zone.size > 0 else 0.0
            max_obstacle_proximity = float(np.percentile(mid_zone, 90)) if mid_zone.size > 0 else 0.0
            
            # Ground continuity (expected ground should be close; a deep void = drop-off / hole)
            ground_mean = float(np.mean(ground_zone)) if ground_zone.size > 0 else 1.0
            
            status = "CLEAR"
            warning_msg = None
            
            # Condition 1: High proximity obstacle directly in path
            if max_obstacle_proximity >= settings.DEPTH_MAX_ALERT_SCORE:
                status = "OBSTACLE_DANGER"
                if name == "center":
                    warning_msg = "Caution: Physical obstacle directly ahead!"
                else:
                    warning_msg = f"Obstacle close on your {name} side."
            elif obstacle_proximity >= 0.55:
                status = "OBSTACLE_NEAR"
                if name == "center":
                    warning_msg = "Approaching object ahead in center path."
                    
            # Condition 2: Ground drop-off or void (e.g. open ditch, stairs down, hole)
            if ground_mean < settings.DEPTH_DROP_OFF_THRESHOLD:
                status = "DROP_OFF_HAZARD"
                if name == "center":
                    warning_msg = "Warning: Ground drop-off or hole directly ahead!"
                else:
                    warning_msg = f"Watch step: ground drop-off on {name} side."
                    
            if warning_msg:
                depth_alerts.append(warning_msg)
                
            corridor_results[name] = {
                "status": status,
                "obstacle_score": round(obstacle_proximity, 3),
                "ground_score": round(ground_mean, 3),
                "alert": warning_msg
            }
            
        return {
            "corridors": corridor_results,
            "depth_alert": depth_alerts[0] if depth_alerts else None,
            "depth_map_min": round(float(depth_map.min()), 3),
            "depth_map_max": round(float(depth_map.max()), 3)
        }

depth_safety_net = DepthSafetyNet()

