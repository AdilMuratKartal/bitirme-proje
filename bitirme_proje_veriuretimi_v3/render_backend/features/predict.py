"""
render_backend/features/predict.py — ONNX Inference Motoru

onnxruntime-cpu kullanır (tensorflow gerektirmez, ~150MB).
student_success_model (XGBoost, 42 özellik, binary pass/fail) ONNX ile çalışır.

Model dosyaları (render_backend/saved_models/):
  student_success_model.onnx  — pass/fail tahmini (XGBoost, AUC=0.91)
  student_success_meta.json   — feature listesi, model metrikleri

Kullanım:
    from features.predict import predict_student_success
    result = predict_student_success(userid=42, tables=tables_dict)
"""

from __future__ import annotations

import functools
import json
import os
from typing import Any, Dict

import numpy as np
import pandas as pd

try:
    import onnxruntime as ort
    _HAS_ORT = True
except ImportError:
    _HAS_ORT = False

_PROJECT_ROOT              = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SAVED_MODELS              = os.path.join(_PROJECT_ROOT, "saved_models")
_RISK_PREMODEL_ONNX_PATH   = os.path.join(_SAVED_MODELS, "student_success_model.onnx")
_RISK_PREMODEL_META_PATH   = os.path.join(_SAVED_MODELS, "student_success_meta.json")


# =============================================================
# Model ve meta yükleme — lru_cache ile tek seferlik
# =============================================================

@functools.lru_cache(maxsize=4)
def _load_onnx(path: str) -> "ort.InferenceSession":
    if not _HAS_ORT:
        raise ImportError(
            "onnxruntime yüklü değil.\n"
            "  pip install onnxruntime-cpu"
        )
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"ONNX model bulunamadı: {path}\n"
            "  localv2/saved_models/student_success_model.onnx → render_backend/saved_models/"
        )
    return ort.InferenceSession(path, providers=["CPUExecutionProvider"])


@functools.lru_cache(maxsize=4)
def _load_meta_json(path: str) -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Meta JSON bulunamadı: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# =============================================================
# PUBLIC API
# =============================================================

def predict_student_success(
    userid: int,
    tables: Dict[str, pd.DataFrame],
) -> Dict[str, Any]:
    """
    student_success_model ONNX tahmini: geçme olasılığı ve risk skoru.

    Dönüş:
        {
          "userid":           int,
          "pass_probability": float,  # 0.0–1.0 (1 = kesin geçer)
          "will_pass":        int,    # 1 = geçer, 0 = kalır (model tahmini)
          "risk_score":       float,  # 1 - pass_probability (geriye dönük uyumluluk)
          "risk_level":       str,    # "high" / "medium" / "low"
        }
    """
    from features.feature_student_success import build_student_success_features

    session = _load_onnx(_RISK_PREMODEL_ONNX_PATH)
    x = build_student_success_features(userid, tables)  # (1, 42) float32

    outputs = session.run(None, {session.get_inputs()[0].name: x})

    # XGBoost ONNX çıktısı:
    #   outputs[0] → label   : int64 [N] veya [[int]]
    #   outputs[1] → probs   : Seq(Map) veya float32 [N, 2]
    label_raw = outputs[0]
    probs_raw = outputs[1]

    # will_pass (model sınıf etiketi: 1 = geçer, 0 = kalır)
    if hasattr(label_raw, "__iter__"):
        will_pass = int(np.array(label_raw).flat[0])
    else:
        will_pass = int(label_raw)

    # pass_probability — class 1 olasılığı
    try:
        probs_arr = np.array(probs_raw)
        if probs_arr.ndim == 2:
            pass_prob = float(probs_arr[0, 1])
        elif probs_arr.ndim == 1 and len(probs_arr) == 2:
            pass_prob = float(probs_arr[1])
        else:
            # Seq(Map) formatı: [{0: p0, 1: p1}, ...]
            row = probs_raw[0] if isinstance(probs_raw, (list, tuple)) else probs_raw
            pass_prob = float(row.get(1, 0.5) if isinstance(row, dict) else 0.5)
    except Exception:
        pass_prob = float(will_pass)

    pass_prob  = float(np.clip(pass_prob, 0.0, 1.0))
    risk_score = round(1.0 - pass_prob, 4)

    if risk_score >= 0.7:
        risk_level = "high"
    elif risk_score >= 0.4:
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        "userid":           userid,
        "pass_probability": round(pass_prob, 4),
        "will_pass":        will_pass,
        "risk_score":       risk_score,
        "risk_level":       risk_level,
    }
