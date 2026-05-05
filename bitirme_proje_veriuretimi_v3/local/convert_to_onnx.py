"""
local/convert_to_onnx.py — Keras -> ONNX + meta.pkl -> meta.json

TFLite LSTM katmanini (TensorListReserve) desteklemez.
ONNX, LSTM'yi yerel olarak destekler ve onnxruntime-cpu (~150MB) ile
inference yapilabilir (tensorflow-cpu ~500MB gerektirmez).

Calistirma (.venv_gpu aktifken):
    python local/convert_to_onnx.py

Gereksinimler (lokal — sadece donusum icin):
    pip install tf2onnx onnxruntime

Uretilen dosyalar (render_backend/saved_models/):
    mimo_model.onnx   hkar_model.onnx
    mimo_meta.json    hkar_meta.json
"""
from __future__ import annotations

import json
import os
import pickle
import sys

import numpy as np

try:
    import tensorflow as tf
    import tf2onnx
    import tf2onnx.convert
except ImportError as e:
    print(f"[HATA] Eksik bagimlilik: {e}")
    print("       pip install tf2onnx onnxruntime")
    sys.exit(1)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC  = os.path.join(_ROOT, "saved_models")
_DST  = os.path.join(_ROOT, "render_backend", "saved_models")
_SEP  = "=" * 60


def _np_to_json(obj):
    """numpy array ve dict iceren yapilari JSON-uyumlu hale getirir."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {str(k): _np_to_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_np_to_json(x) for x in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    return obj


def _print_onnx_info(session, label: str) -> None:
    """ONNX input/output tensor adlari ve sekilleri."""
    print(f"\n  [{label}] ONNX Tensor Bilgisi:")
    print("    Inputs :")
    for inp in session.get_inputs():
        print(f"      name={inp.name!r:<30s}  shape={inp.shape}")
    print("    Outputs:")
    for out in session.get_outputs():
        print(f"      name={out.name!r:<30s}  shape={out.shape}")


def convert_keras_to_onnx(name: str) -> None:
    keras_path = os.path.join(_SRC, f"{name}_model.keras")
    onnx_path  = os.path.join(_DST, f"{name}_model.onnx")
    meta_pkl   = os.path.join(_SRC, f"{name}_meta.pkl")
    meta_json  = os.path.join(_DST, f"{name}_meta.json")

    print(_SEP)
    print(f"  [{name.upper()}] Donusum basliyor...")

    if not os.path.exists(keras_path):
        print(f"  [HATA] Keras model bulunamadi: {keras_path}")
        print("         Once 'python local/train_models.py' calistirin.")
        return

    # 1. Keras modeli yukle
    model = tf.keras.models.load_model(keras_path)

    # Giris sekilleri: modelin input katmanlarindan al
    input_specs = []
    for inp_layer in model.inputs:
        shape = [1] + list(inp_layer.shape[1:])   # batch=1 olarak sabitle
        input_specs.append(
            tf.TensorSpec(shape, tf.float32, name=inp_layer.name.split(":")[0])
        )

    # 2. ONNX donusumu (opset 13 — LSTM icin yeterli)
    model_proto, _ = tf2onnx.convert.from_keras(
        model,
        input_signature=input_specs,
        opset=13,
        output_path=onnx_path,
    )

    file_size = os.path.getsize(onnx_path)
    print(f"  [OK]  {onnx_path}")
    print(f"        Boyut: {file_size:,} byte")

    # 3. Tensor bilgisini yazdir — predict.py icin referans
    import onnxruntime as ort
    session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    _print_onnx_info(session, name.upper())

    # 4. meta.pkl -> meta.json
    if not os.path.exists(meta_pkl):
        print(f"  [UYARI] Meta pkl bulunamadi: {meta_pkl}  (JSON atlanacak)")
        return

    with open(meta_pkl, "rb") as f:
        meta = pickle.load(f)
    with open(meta_json, "w", encoding="utf-8") as f:
        json.dump(_np_to_json(meta), f, ensure_ascii=False, indent=2)
    print(f"  [OK]  {meta_json}")


def main() -> None:
    print(_SEP)
    print("  Keras -> ONNX + meta.pkl -> meta.json")
    print(f"  Kaynak : {_SRC}")
    print(f"  Hedef  : {_DST}")
    print(_SEP)

    os.makedirs(_DST, exist_ok=True)

    convert_keras_to_onnx("mimo")
    convert_keras_to_onnx("hkar")

    print(_SEP)
    print("  Donusum tamamlandi.")
    print("  Tensor adlarini kontrol et, sonra predict.py'yi commit et.")
    print(_SEP)


if __name__ == "__main__":
    main()
