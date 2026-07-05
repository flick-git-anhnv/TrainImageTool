# model_infer.py — chạy detect model (YOLO / RF-DETR / ONNX) trên 1 ảnh PIL
# Gom nhánh yolo vs rfdetr/onnx dùng chung giữa BBoxEditorTab (Detect/Verify/Test vùng zoom)
# và các nơi khác cần detect 1 ảnh đơn — tránh lặp code đã có ở nhiều chỗ trong tab_bbox.py.
from __future__ import annotations


def run_model_predict(model, model_type: str, pil_img, conf: float) -> list:
    """Trả về list [cid, x1, y1, x2, y2, conf_score] (tọa độ pixel trên `pil_img`)."""
    boxes = []
    if model_type == "yolo":
        import numpy as np
        img_arr = np.array(pil_img.convert("RGB"))
        results = model.predict(img_arr, conf=conf, verbose=False)
        if results and results[0].boxes is not None:
            for box in results[0].boxes:
                cid = int(box.cls[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                boxes.append([cid, x1, y1, x2, y2, float(box.conf[0])])
    else:
        # RF-DETR và ONNX (_OnnxRunner/_InlineRunner) đều expose cùng interface
        # .predict(pil, threshold=conf) -> object có .xyxy/.class_id/.confidence
        dets = model.predict(pil_img, threshold=conf)
        if dets and len(dets) > 0:
            for i in range(len(dets.xyxy)):
                cid = int(dets.class_id[i]) if dets.class_id is not None else 0
                x1, y1, x2, y2 = dets.xyxy[i].tolist()
                conf_val = float(dets.confidence[i]) if dets.confidence is not None else conf
                boxes.append([cid, x1, y1, x2, y2, conf_val])
    return boxes
