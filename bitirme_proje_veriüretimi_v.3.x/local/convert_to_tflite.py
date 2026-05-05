"""
local/convert_to_tflite.py — Keras → TFLite + meta.pkl → meta.json

Calistirma (.venv_gpu aktifken):
    python local/convert_to_tflite.py

Uretilen dosyalar (render_backend/saved_models/):
    mimo_model.tflite   hkar_model.tflite
    mimo_meta.json      hkar_meta.json
"""
from __future__ import annotations

import json
import os
import pickle
import sys

import numpy as np

try:
    import tensorflow as tf
except ImportError:
    print("[HATA] tensorflow bulunamadi. '.venv_gpu' ortaminda calistirin:")
    print("       .venv_gpu/Scripts/activate && python local/convert_to_tflite.py")
    sys.exit(1)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC  = os.path.join(_ROOT, "saved_models")
_DST  = os.path.join(_ROOT, "render_backend", "saved_models")

_SEP = "=" * 60


def _np_to_json(obj):
    """numpy array ve dict iceren yapilari JSON-uyumlu hale getirir."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {str(k): _np_to_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_np_to_json(x) for x in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    return obj


def _print_tensor_info(interp: "tf.lite.Interpreter", label: str) -> None:
    """Tensor isimleri ve sekilleri — predict.py yazimi icin referans."""
    print(f"\n  [{label}] Tensor Bilgisi:")
    print("    Inputs :")
    for d in interp.get_input_details():
        print(f"      idx={d['index']}  name={d['name']!r:<50s}  shape={list(d['shape'])}")
    print("    Outputs (index sirasi):")
    for d in sorted(interp.get_output_details(), key=lambda x: x['index']):
        print(f"      idx={d['index']}  name={d['name']!r:<50s}  shape={list(d['shape'])}")


def convert_keras_to_tflite(name: str) -> None:
    keras_path  = os.path.join(_SRC, f"{name}_model.keras")
    tflite_path = os.path.join(_DST, f"{name}_model.tflite")
    meta_pkl    = os.path.join(_SRC, f"{name}_meta.pkl")
    meta_json   = os.path.join(_DST, f"{name}_meta.json")

    print(_SEP)
    print(f"  [{name.upper()}] Donusum basliyor...")

    # 1. Keras modeli yükle ve TFLite'a donustur
    if not os.path.exists(keras_path):
        print(f"  [HATA] Keras model bulunamadi: {keras_path}")
        print("         Once 'python local/train_models.py' calistirin.")
        return

    model        = tf.keras.models.load_model(keras_path)
    converter    = tf.lite.TFLiteConverter.from_keras_model(model)
    tflite_model = converter.convert()

    with open(tflite_path, "wb") as f:
        f.write(tflite_model)
    print(f"  [OK]  {tflite_path}")
    print(f"        Boyut: {len(tflite_model):,} byte")

    # 2. Tensor bilgisini yazdir — predict.py icin referans
    interp = tf.lite.Interpreter(model_content=tflite_model)
    interp.allocate_tensors()
    _print_tensor_info(interp, name.upper())

    # 3. meta.pkl → meta.json
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
    print("  Keras → TFLite + meta.pkl → meta.json")
    print(f"  Kaynak : {_SRC}")
    print(f"  Hedef  : {_DST}")
    print(_SEP)

    os.makedirs(_DST, exist_ok=True)

    convert_keras_to_tflite("mimo")
    convert_keras_to_tflite("hkar")

    print(_SEP)
    print("  Donusum tamamlandi.")
    print("  Tensor bilgisini kontrol et, sonra predict.py'yi commit et.")
    print(_SEP)


if __name__ == "__main__":
    main()
