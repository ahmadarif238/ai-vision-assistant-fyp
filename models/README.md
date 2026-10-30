# Model Weights & Optimization Artifacts

This directory houses the neural network weights and optimized execution graphs for the local high-performance runtime. 

In accordance with Git repository size policies and cloud deployment boundaries (Vercel Serverless 250MB limit), binary model weights (`*.onnx`, `*.pt`, `*.bin`, `*.xml`) are excluded from Git version control.

---

## 1. Local Model Specifications

| Model Checkpoint | Format / Engine | Classes / Task | Download / Export Source | Local Path |
| :--- | :--- | :--- | :--- | :--- |
| **YOLOv8n OpenVINO IR** | OpenVINO IR (`.xml` + `.bin`) | 80 COCO Classes (~10.9ms CPU) | `yolo export model=yolov8n.pt format=openvino imgsz=320` | `models/yolov8n_openvino_model/` |
| **Depth Anything V2 Small** | INT8 ONNX (`.onnx`) | Relative Inverse Depth Slicing | HuggingFace Hub: `onnx-community/depth-anything-v2-small` | `models/depth_anything_v2_small_int8.onnx` |
| **YOLOv8n ONNX** | ONNX Runtime (`.onnx`) | 80 COCO Classes (~18.9ms CPU) | `yolo export model=yolov8n.pt format=onnx imgsz=320` | `models/yolov8n.onnx` |
| **YOLOv8n Open Images V7** | ONNX Runtime (`.onnx`) | 601 Open Images V7 Classes | Ultralytics Open Images Export | `models/yolov8n-oiv7.onnx` |
| **YOLO-Tuned** | PyTorch Checkpoint (`.pt`) | Fine-Tuned Local Hazards | Custom Undergraduate FYP Checkpoint | `models/yolo-tuned.pt` |
| **YOLO11n** | PyTorch Checkpoint (`.pt`) | YOLO11 Nano Backbone | `ultralytics.YOLO('yolo11n.pt')` | `models/yolo11n.pt` |

---

## 2. Automated Download Script for Local Execution

Run the provided script to restore all local models in one command:

```bash
python -c "
import os
from huggingface_hub import hf_hub_download
from ultralytics import YOLO

os.makedirs('models', exist_ok=True)

# 1. Download Depth Anything V2 Small INT8 ONNX
print('Downloading Depth Anything V2 Small INT8...')
p = hf_hub_download(repo_id='onnx-community/depth-anything-v2-small', filename='onnx/model_int8.onnx', local_dir='models')
os.rename('models/onnx/model_int8.onnx', 'models/depth_anything_v2_small_int8.onnx')

# 2. Export YOLOv8n to OpenVINO and ONNX
print('Exporting YOLOv8n to OpenVINO & ONNX...')
model = YOLO('yolov8n.pt')
model.export(format='openvino', imgsz=320)
model.export(format='onnx', imgsz=320)
"
```

---

## 3. Vercel Cloud Edge Deployment

When deployed to Vercel (`https://...vercel.app`), the application automatically activates **Cloud Edge Mode**. It offloads visual hazard detection and document OCR to **Groq Multimodal Cloud Vision (Llama 4 Scout / 3.2 Vision)**, requiring zero local model weights on Vercel's serverless infrastructure.
