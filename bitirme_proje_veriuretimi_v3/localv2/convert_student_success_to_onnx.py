"""
localv2/convert_student_success_to_onnx.py

student_success modelini GERÇEK ONNX formatına dönüştürür (tek kaynak).

NOT: XGBoost'un xgb.save_model("...onnx") çağrısı ONNX DEĞİL, kendi JSON
formatını üretir. Bu modül onnxmltools/skl2onnx ile gerçek ONNX üretir ve
hem student_success_prediction.py hem de elle çağrı için kullanılır.

Çıktı ONNX şeması (zipmap=False):
    input : float_input [None, n_features]
    output[0] = label         [N]      (int64)
    output[1] = probabilities [N, 2]   (float32)

Elle çalıştırma (PKL'den, yeniden eğitmeden):
    .venv_gpu/Scripts/python localv2/convert_student_success_to_onnx.py
"""

from __future__ import annotations

import os
import pickle

_HERE         = os.path.dirname(os.path.abspath(__file__))
_SAVED_MODELS = os.path.join(_HERE, "saved_models")
_PKL_PATH     = os.path.join(_SAVED_MODELS, "student_success_model.pkl")
_ONNX_PATH    = os.path.join(_SAVED_MODELS, "student_success_model.onnx")


def export_to_onnx(model, model_name: str, features: list, onnx_path: str) -> None:
    """
    Verilen modeli gerçek ONNX'e çevirip onnx_path'e yazar.
    XGBoost/LightGBM DataFrame ile eğitildiyse booster'da gerçek özellik adları
    saklanır; onnxmltools 'f0..fN' bekler → adlar temizlenir.
    """
    from onnxmltools.convert.common.data_types import FloatTensorType

    n = len(features)
    initial_types = [("float_input", FloatTensorType([None, n]))]

    if model_name in ("XGBoost", "LightGBM"):
        try:
            model.get_booster().feature_names = None  # yalnızca XGBoost'ta var
        except AttributeError:
            pass

    if model_name == "XGBoost":
        from onnxmltools.convert import convert_xgboost
        onx = convert_xgboost(model, initial_types=initial_types, target_opset=12)
    elif model_name == "LightGBM":
        from onnxmltools.convert import convert_lightgbm
        onx = convert_lightgbm(
            model, initial_types=initial_types, target_opset=12, zipmap=False,
        )
    else:  # RandomForest vb.
        from skl2onnx import convert_sklearn
        onx = convert_sklearn(
            model, initial_types=initial_types, target_opset=12,
            options={id(model): {"zipmap": False}},
        )

    with open(onnx_path, "wb") as f:
        f.write(onx.SerializeToString())


def main() -> None:
    import numpy as np
    import onnxruntime as ort

    with open(_PKL_PATH, "rb") as f:
        bundle = pickle.load(f)

    features  = bundle["features"]
    best_name = bundle["best_name"]
    model     = bundle["trained"][best_name]

    print(f"En iyi model: {best_name} | özellik sayısı: {len(features)}")
    export_to_onnx(model, best_name, features, _ONNX_PATH)
    print(f"ONNX yazıldı: {_ONNX_PATH}")

    # Doğrulama: yükle + dummy inference
    sess = ort.InferenceSession(_ONNX_PATH, providers=["CPUExecutionProvider"])
    print("INPUTS :", [(i.name, i.shape) for i in sess.get_inputs()])
    print("OUTPUTS:", [(o.name, o.shape) for o in sess.get_outputs()])
    x = np.random.rand(1, len(features)).astype(np.float32)
    out = sess.run(None, {sess.get_inputs()[0].name: x})
    for i, o in enumerate(out):
        print(f"out[{i}] {type(o).__name__} ->", repr(o)[:160])


if __name__ == "__main__":
    main()
