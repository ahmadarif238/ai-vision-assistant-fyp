import os
import cv2
import time
import numpy as np
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional, Tuple
from backend.core.config import settings

def xywh2xyxy(x: np.ndarray) -> np.ndarray:
    """Convert bounding box coordinates from [x_center, y_center, width, height] to [x1, y1, x2, y2]"""
    y = np.copy(x)
    y[..., 0] = x[..., 0] - x[..., 2] / 2  # x1
    y[..., 1] = x[..., 1] - x[..., 3] / 2  # y1
    y[..., 2] = x[..., 0] + x[..., 2] / 2  # x2
    y[..., 3] = x[..., 1] + x[..., 3] / 2  # y2
    return y

def nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float = 0.45) -> List[int]:
    """Pure NumPy Non-Maximum Suppression"""
    if len(boxes) == 0:
        return []
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep = []
    
    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        
        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        inter = w * h
        ovr = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
        inds = np.where(ovr <= iou_threshold)[0]
        order = order[inds + 1]
        
    return keep

class DetectionEngine:
    """
    Production-grade Unified Detection Engine:
      1. OpenVINO IR Engine (Default high-speed ~10ms CPU inference)
      2. ONNX Runtime Engine (yolov8n.onnx & yolov8n-oiv7.onnx)
      3. Zero-Shot Hazard Detection (YOLO-World open-vocabulary text prompts)
      4. Ultralytics PyTorch Checkpoint Fallback (yolo-tuned.pt & yolo11n.pt)
    """

    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.active_mode = "openvino"  # "openvino", "onnx", "zeroshot", "yolo11"
        self.ov_compiled = None
        self.onnx_sess = None
        self.yolo_model = None
        self.classes: Dict[int, str] = {}
        
        # Load COCO classes
        self._load_classes()
        # Initialize primary OpenVINO engine
        self._init_openvino()
        
    def _load_classes(self):
        meta_path = os.path.join(settings.YOLOV8_OPENVINO_DIR, "metadata.yaml")
        if not os.path.exists(meta_path):
            meta_path = os.path.join(settings.BASE_DIR_PATH, "metadata.yaml")
        if os.path.exists(meta_path):
            import yaml
            try:
                with open(meta_path, "r") as f:
                    meta = yaml.safe_load(f)
                    self.classes = meta.get("names", {})
            except Exception:
                pass
        if not self.classes:
            # Standard COCO fallback
            self.classes = {0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck", 9: "traffic light", 10: "fire hydrant", 11: "stop sign", 56: "chair", 57: "couch", 59: "bed", 60: "dining table"}

    def _init_openvino(self):
        xml_path = os.path.join(settings.YOLOV8_OPENVINO_DIR, "yolov8n.xml")
        if os.path.exists(xml_path):
            try:
                import openvino as ov
                core = ov.Core()
                model = core.read_model(xml_path)
                self.ov_compiled = core.compile_model(model, "CPU")
                self.active_mode = "openvino"
                print(f"[DetectionEngine] OpenVINO CPU Engine initialized ({xml_path})")
                return
            except Exception as e:
                print(f"[DetectionEngine] OpenVINO init failed: {e}")
                
        # Fallback to ONNX
        self._init_onnx()

    def _init_onnx(self):
        onnx_path = settings.YOLOV8_ONNX_PATH
        if os.path.exists(onnx_path):
            try:
                import onnxruntime as ort
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = 4
                self.onnx_sess = ort.InferenceSession(onnx_path, sess_options=opts, providers=["CPUExecutionProvider"])
                self.active_mode = "onnx"
                print(f"[DetectionEngine] ONNX Runtime Engine initialized ({onnx_path})")
                return
            except Exception as e:
                print(f"[DetectionEngine] ONNX init failed: {e}")

        # Fallback to Ultralytics
        self._init_ultralytics()

    def _init_ultralytics(self):
        try:
            from ultralytics import YOLO
            pt_path = settings.YOLO11N_PATH if os.path.exists(settings.YOLO11N_PATH) else settings.YOLO_TUNED_PATH
            if os.path.exists(pt_path):
                self.yolo_model = YOLO(pt_path)
                self.active_mode = "ultralytics"
                print(f"[DetectionEngine] Ultralytics YOLO initialized ({pt_path})")
        except Exception as e:
            print(f"[DetectionEngine] Ultralytics fallback failed: {e}")

    def init_zero_shot_hazards(self, custom_prompts: Optional[List[str]] = None):
        """
        Configure zero-shot open-vocabulary hazard detection with custom prompts
        specifically tailored for Pakistani pedestrian & indoor safety.
        """
        prompts = custom_prompts or settings.HAZARD_PROMPTS
        try:
            from ultralytics import YOLOWorld
            world_path = os.path.join(settings.MODELS_DIR, "yolov8s-worldv2.pt")
            # If not locally cached, YOLOWorld automatically resolves or falls back
            world_model = YOLOWorld("yolov8s-worldv2.pt")
            world_model.set_classes(prompts)
            self.yolo_model = world_model
            self.active_mode = "zeroshot"
            self.classes = {i: name for i, name in enumerate(prompts)}
            print(f"[DetectionEngine] Zero-shot hazard detection activated for prompts: {prompts}")
            return True
        except Exception as e:
            print(f"[DetectionEngine] Zero-shot YOLOWorld init deferred: {e}. Using tuned model weights.")
            return False

    def preprocess(self, bgr_img: np.ndarray, imgsz: int = 320) -> Tuple[np.ndarray, float, Tuple[int, int]]:
        """Resize with letterbox padding to maintain aspect ratio"""
        h0, w0 = bgr_img.shape[:2]
        r = min(imgsz / h0, imgsz / w0)
        new_unpad = (int(round(w0 * r)), int(round(h0 * r)))
        dw, dh = imgsz - new_unpad[0], imgsz - new_unpad[1]
        dw /= 2
        dh /= 2
        
        resized = cv2.resize(bgr_img, new_unpad, interpolation=cv2.INTER_LINEAR)
        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        padded = cv2.copyMakeBorder(resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114))
        
        blob = padded[:, :, ::-1].transpose(2, 0, 1)  # BGR to RGB, HWC to CHW
        blob = np.ascontiguousarray(blob, dtype=np.float32) / 255.0
        blob = blob[None, ...]  # Add batch dim [1, 3, 320, 320]
        return blob, r, (dw, dh)

    def postprocess(self, output: np.ndarray, orig_shape: Tuple[int, int], r: float, dwdh: Tuple[float, float], conf_thresh: float = 0.35) -> List[Dict[str, Any]]:
        """Post-process raw YOLO output [1, 84, anchors]"""
        predictions = np.squeeze(output)
        if predictions.shape[0] < predictions.shape[1]:
            predictions = predictions.T  # Transpose to [anchors, 84]
            
        boxes_xywh = predictions[:, :4]
        class_scores = predictions[:, 4:]
        
        max_scores = np.max(class_scores, axis=1)
        class_ids = np.argmax(class_scores, axis=1)
        
        mask = max_scores >= conf_thresh
        if not np.any(mask):
            return []
            
        filtered_boxes = boxes_xywh[mask]
        filtered_scores = max_scores[mask]
        filtered_classes = class_ids[mask]
        
        # Convert to xyxy
        boxes_xyxy = xywh2xyxy(filtered_boxes)
        
        # Scale back to original frame coordinates
        dw, dh = dwdh
        boxes_xyxy[:, [0, 2]] = (boxes_xyxy[:, [0, 2]] - dw) / r
        boxes_xyxy[:, [1, 3]] = (boxes_xyxy[:, [1, 3]] - dh) / r
        
        # Clip to bounds
        h0, w0 = orig_shape
        boxes_xyxy[:, [0, 2]] = np.clip(boxes_xyxy[:, [0, 2]], 0, w0)
        boxes_xyxy[:, [1, 3]] = np.clip(boxes_xyxy[:, [1, 3]], 0, h0)
        
        keep_indices = nms(boxes_xyxy, filtered_scores, iou_threshold=0.45)
        
        results = []
        for idx in keep_indices:
            cid = int(filtered_classes[idx])
            lbl = self.classes.get(cid, f"class_{cid}")
            results.append({
                "label": lbl,
                "conf": float(filtered_scores[idx]),
                "bbox": [float(c) for c in boxes_xyxy[idx]]
            })
            
        return results

    def detect_sync(self, bgr_frame: np.ndarray, conf_thresh: float = 0.35) -> Tuple[List[Dict[str, Any]], float]:
        """Synchronous frame detection"""
        t0 = time.perf_counter()
        orig_shape = bgr_frame.shape[:2]
        
        # 1. OpenVINO Inference
        if self.active_mode == "openvino" and self.ov_compiled is not None:
            blob, r, dwdh = self.preprocess(bgr_frame, imgsz=settings.INFERENCE_IMG_SIZE)
            results_dict = self.ov_compiled([blob])
            raw_out = next(iter(results_dict.values()))
            detections = self.postprocess(raw_out, orig_shape, r, dwdh, conf_thresh=conf_thresh)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return detections, elapsed_ms
            
        # 2. ONNX Runtime Inference
        elif self.active_mode == "onnx" and self.onnx_sess is not None:
            blob, r, dwdh = self.preprocess(bgr_frame, imgsz=settings.INFERENCE_IMG_SIZE)
            inp_name = self.onnx_sess.get_inputs()[0].name
            raw_out = self.onnx_sess.run(None, {inp_name: blob})[0]
            detections = self.postprocess(raw_out, orig_shape, r, dwdh, conf_thresh=conf_thresh)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return detections, elapsed_ms
            
        # 3. Ultralytics PyTorch / ZeroShot Inference
        elif self.yolo_model is not None:
            results = self.yolo_model(bgr_frame, imgsz=settings.INFERENCE_IMG_SIZE, conf=conf_thresh, verbose=False)[0]
            detections = []
            for box in results.boxes:
                cls_id = int(box.cls[0])
                detections.append({
                    "label": self.classes.get(cls_id, results.names.get(cls_id, "object")),
                    "conf": float(box.conf[0]),
                    "bbox": [float(c) for c in box.xyxy[0].tolist()]
                })
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return detections, elapsed_ms
            
        return [], 0.0

    async def detect_async(self, bgr_frame: np.ndarray, conf_thresh: float = 0.35) -> Tuple[List[Dict[str, Any]], float]:
        """Asynchronous non-blocking wrapper running in thread pool"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.executor, self.detect_sync, bgr_frame, conf_thresh)

detection_engine = DetectionEngine()

