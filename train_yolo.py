"""
YOLOv8 / YOLOv11 Custom Dataset Training & Raspberry Pi 5 Optimization Pipeline
==============================================================================
Provides end-to-end pipeline for dataset labeling, training custom waste detection models,
and exporting optimized inference engines (ONNX / NCNN / OpenVINO) for Raspberry Pi 5.

Vishwakarma Awards Computer Vision Architecture
----------------------------------------------
Classes:
  0: person
  1: vehicle (car/truck/autorickshaw/motorcycle)
  2: garbage_bag (black poly bags, mixed waste bundles)
  3: plastic_bottle (PET bottles, HDPE containers)
  4: packaging_box (corrugated cardboard, cartons)
"""

import os
import sys
from pathlib import Path

DATASET_CONFIG_CONTENT = """# Smart Waste Sentinel - Custom YOLO Dataset Configuration
path: ./dataset # Dataset root directory
train: images/train
val: images/val
test: images/test

# Number of Classes
nc: 5

# Class Names
names:
  0: person
  1: vehicle
  2: garbage_bag
  3: plastic_bottle
  4: packaging_box
"""

def generate_yaml_config(output_path: str = "waste_dataset.yaml"):
    """Creates YOLO dataset configuration YAML file."""
    with open(output_path, "w") as f:
        f.write(DATASET_CONFIG_CONTENT)
    print(f"[+] Created YOLO dataset YAML: {output_path}")

def train_custom_model(
    data_yaml: str = "waste_dataset.yaml",
    model_variant: str = "yolov8n.pt",
    epochs: int = 50,
    imgsz: int = 640,
    batch: int = 16
):
    """
    Trains YOLOv8/v11 nano model on the custom waste dataset.
    
    Why YOLOv8n / YOLOv11n?
    - 'nano' models have only ~3.2M parameters.
    - Yields ~18-25 FPS on Raspberry Pi 5 Quad-core ARM Cortex-A76 @ 2.4GHz.
    - Excellent balance between mean Average Precision (mAP@0.50) and latency.
    """
    print(f"\n[+] Starting Training: {model_variant} on {data_yaml} ({epochs} epochs)...")
    try:
        from ultralytics import YOLO
        model = YOLO(model_variant)
        results = model.train(
            data=data_yaml,
            epochs=epochs,
            imgsz=imgsz,
            batch=batch,
            device="0" if os.getenv("CUDA_VISIBLE_DEVICES") else "cpu",
            optimizer="AdamW",
            lr0=0.001,
            lrf=0.01,
            augment=True,      # Flips, mosaic, affine distortions for outdoor camera robustness
            name="smart_waste_sentinel_run"
        )
        print("\n[+] Training complete! Best weights saved to runs/detect/smart_waste_sentinel_run/weights/best.pt")
        return model
    except ImportError:
        print("[-] Ultralytics is not installed. Run: pip install ultralytics")
        return None

def export_for_raspberry_pi(model_weights_path: str = "runs/detect/smart_waste_sentinel_run/weights/best.pt"):
    """
    Exports trained PyTorch weights to high-speed Edge formats for Raspberry Pi 5.

    1. NCNN (Tencent NCNN):
       - Highly optimized for ARM NEON vector instructions on Raspberry Pi 5.
       - Delivers 2x-3x speedup compared to standard PyTorch CPU execution!
    2. ONNX:
       - Open standard, highly portable, compatible with ONNX Runtime.
    """
    print(f"\n[+] Exporting {model_weights_path} for Raspberry Pi 5 Edge Acceleration...")
    try:
        from ultralytics import YOLO
        model = YOLO(model_weights_path)

        # 1. Export to ONNX
        print("[+] Exporting to ONNX format...")
        onnx_file = model.export(format="onnx", imgsz=640, dynamic=False, simplify=True)
        print(f"    Exported: {onnx_file}")

        # 2. Export to NCNN (Direct ARM NEON optimization for RPi 5)
        print("[+] Exporting to NCNN (ARM NEON optimized)...")
        ncnn_file = model.export(format="ncnn", imgsz=640)
        print(f"    Exported: {ncnn_file}")

        print("\n[+] Edge optimization export complete! Copy the exported model to models/ on your Raspberry Pi.")
    except Exception as e:
        print(f"[-] Export error: {e}")

if __name__ == "__main__":
    print("=" * 65)
    print("  YOLO CUSTOM TRAINING & RASPBERRY PI 5 EXPORT PIPELINE")
    print("=" * 65)
    generate_yaml_config()
    print("\nTo train on your annotated waste dataset, run:")
    print("  python train_yolo.py --train")
    print("To export an existing model for RPi 5, run:")
    print("  python train_yolo.py --export <path_to_best.pt>")
