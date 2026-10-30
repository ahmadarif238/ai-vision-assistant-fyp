import os
import sys
import yaml
import onnxruntime as ort

print("="*60)
print("MODEL AUDIT & INSPECTION REPORT")
print("="*60)

# 1. Inspect metadata.yaml
print("\n[1] metadata.yaml:")
if os.path.exists("metadata.yaml"):
    with open("metadata.yaml", "r") as f:
        meta = yaml.safe_load(f)
    print(f"  Description: {meta.get('description')}")
    print(f"  Task: {meta.get('task')}, Image Size: {meta.get('imgsz')}")
    names = meta.get("names", {})
    print(f"  Total Classes: {len(names)}")
    print(f"  Class IDs 0-9: {[names[i] for i in range(min(10, len(names)))]}")
else:
    print("  File not found.")

# 2. Inspect yolov8n.onnx
print("\n[2] yolov8n.onnx:")
if os.path.exists("yolov8n.onnx"):
    sess = ort.InferenceSession("yolov8n.onnx", providers=["CPUExecutionProvider"])
    meta = sess.get_modelmeta().custom_metadata_map
    inp = [(i.name, i.shape) for i in sess.get_inputs()]
    out = [(o.name, o.shape) for o in sess.get_outputs()]
    names = eval(meta.get("names", "{}"))
    print(f"  Inputs: {inp}")
    print(f"  Outputs: {out}")
    print(f"  Total Classes: {len(names)}")
    print(f"  Sample Classes: {list(names.items())[:10]}")
else:
    print("  File not found.")

# 3. Inspect yolov8n-oiv7.onnx
print("\n[3] yolov8n-oiv7.onnx (Open Images V7):")
if os.path.exists("yolov8n-oiv7.onnx"):
    sess = ort.InferenceSession("yolov8n-oiv7.onnx", providers=["CPUExecutionProvider"])
    meta = sess.get_modelmeta().custom_metadata_map
    inp = [(i.name, i.shape) for i in sess.get_inputs()]
    out = [(o.name, o.shape) for o in sess.get_outputs()]
    names = eval(meta.get("names", "{}"))
    print(f"  Inputs: {inp}")
    print(f"  Outputs: {out}")
    print(f"  Total Classes: {len(names)}")
    print(f"  Sample Classes: {list(names.items())[:10]}")
else:
    print("  File not found.")

# 4. Inspect yolov8n_openvino_model
print("\n[4] yolov8n_openvino_model (OpenVINO IR):")
ov_dir = "yolov8n_openvino_model"
if os.path.exists(ov_dir):
    files = os.listdir(ov_dir)
    print(f"  Files in dir: {files}")
    ov_meta_path = os.path.join(ov_dir, "metadata.yaml")
    if os.path.exists(ov_meta_path):
        with open(ov_meta_path, "r") as f:
            ov_meta = yaml.safe_load(f)
        names = ov_meta.get("names", {})
        print(f"  OpenVINO IR metadata task: {ov_meta.get('task')}, imgsz: {ov_meta.get('imgsz')}")
        print(f"  Total Classes: {len(names)}")
        print(f"  Sample Classes: {list(names.items())[:10]}")
else:
    print("  Directory not found.")

# 5. Inspect PyTorch models: yolo-tuned.pt & yolo11n.pt
import zipfile, re

def inspect_pt_strings(path):
    print(f"\n[5] PyTorch Checkpoint: {path}")
    if not os.path.exists(path):
        print("  File not found.")
        return
    with zipfile.ZipFile(path, "r") as z:
        data_pkl_name = [n for n in z.namelist() if n.endswith("data.pkl")][0]
        raw = z.read(data_pkl_name)
        idx = raw.find(b"names")
        if idx != -1:
            snippet = raw[idx:idx+1500]
            strings = re.findall(b"[\x20-\x7e]{3,}", snippet)
            cleaned = [s.decode("latin1").rstrip("rq").replace("r", "") for s in strings if len(s) > 2]
            print(f"  Classes detected in weights header: {cleaned[:15]} ... (total ~80)")
        # search dataset training info
        matches = re.findall(b"[\x20-\x7e]{4,}", raw)
        info = [m.decode("latin1") for m in matches if any(k in m.lower().decode("latin1") for k in ["coco", "dataset", "train", "yaml"])]
        print(f"  Training dataset / cfg hints: {info[:5]}")

inspect_pt_strings("yolo-tuned.pt")
inspect_pt_strings("yolo11n.pt")
print("\n" + "="*60)
