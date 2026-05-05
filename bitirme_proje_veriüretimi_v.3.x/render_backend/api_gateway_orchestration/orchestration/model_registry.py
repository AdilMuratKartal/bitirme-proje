"""
render_backend/orchestration/model_registry.py — Model Saglik Kontrolu

Startup'ta dosya varligini dogrular, TFLite interpreter'lari on belleğe alir
ve tensor sekil uyumluluğunu kontrol eder.
"""

from __future__ import annotations

import os
import logging

logger = logging.getLogger(__name__)

_RENDER_BACKEND = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_SAVED_MODELS_DIR = os.path.join(_RENDER_BACKEND, "saved_models")

_REQUIRED_FILES = [
    "mimo_model.onnx",
    "hkar_model.onnx",
    "mimo_meta.json",
    "hkar_meta.json",
]


def _validate_onnx_shapes(models_dir: str) -> None:
    """
    ONNX tensor adlari ve sekillerini dogrula.
    MIMO: X_Time[1,n,2] + X_Static[1,6] -> y_risk, y_grade, y_segment[1,4]
    HKAR: X_Sequence[1,10,3] + X_UserHabit[1,5] -> y_segment[1,4]
    """
    from features.predict import _load_onnx, _MIMO_ONNX_PATH, _HKAR_ONNX_PATH

    mimo     = _load_onnx(_MIMO_ONNX_PATH)
    inp_map  = {inp.name: inp for inp in mimo.get_inputs()}
    out_list = [out.name for out in mimo.get_outputs()]

    for expected in ("X_Time", "X_Static"):
        if expected not in inp_map:
            raise RuntimeError(
                f"MIMO ONNX: '{expected}' girdisi bulunamadi. "
                f"Mevcut: {list(inp_map.keys())}"
            )
    if "y_segment" not in out_list:
        raise RuntimeError(
            f"MIMO ONNX: 'y_segment' cikisi bulunamadi. Mevcut: {out_list}"
        )
    if inp_map["X_Static"].shape[-1] != 6:
        raise RuntimeError(
            f"MIMO X_Static 6 ozellik bekleniyor, bulundu: {inp_map['X_Static'].shape}"
        )

    hkar      = _load_onnx(_HKAR_ONNX_PATH)
    hinp_map  = {inp.name: inp for inp in hkar.get_inputs()}
    hout_list = [out.name for out in hkar.get_outputs()]

    for expected in ("X_Sequence", "X_UserHabit"):
        if expected not in hinp_map:
            raise RuntimeError(
                f"HKAR ONNX: '{expected}' girdisi bulunamadi. "
                f"Mevcut: {list(hinp_map.keys())}"
            )
    if "y_segment" not in hout_list:
        raise RuntimeError(
            f"HKAR ONNX: 'y_segment' cikisi bulunamadi. Mevcut: {hout_list}"
        )

    logger.info("onnx_shapes_validated")


class ModelRegistry:
    """
    Model dosyalarinin varligini dogrular, TFLite interpreter'lari on belleğe alir.
    Gercek model yukleme predict.py icinde lru_cache ile yapilir.
    """

    _instance: "ModelRegistry | None" = None

    def __init__(self):
        self._loaded = False

    @classmethod
    def load_all(cls) -> "ModelRegistry":
        """Singleton. Dosya varligini kontrol eder, interpreter ve meta'yi on belleğe alir."""
        if cls._instance is not None and cls._instance._loaded:
            return cls._instance

        instance = cls()
        models_dir = os.environ.get("MODELS_DIR", _SAVED_MODELS_DIR)

        # Dosya varlik kontrolu
        missing = []
        for fname in _REQUIRED_FILES:
            path = os.path.join(models_dir, fname)
            if not os.path.exists(path):
                missing.append(path)

        if missing:
            raise FileNotFoundError(
                f"Model dosyalari bulunamadi: {missing}\n"
                "render_backend/saved_models/ icine tflite ve json dosyalarini ekleyin.\n"
                "Oncelikle: .venv_gpu/Scripts/python local/convert_to_tflite.py"
            )

        # lru_cache'i doldur: _load_tflite ve _load_meta_json path argumaniyla cagrilmali
        from features.predict import (
            _load_onnx,
            _load_meta_json,
            _MIMO_ONNX_PATH,
            _HKAR_ONNX_PATH,
            _MIMO_META_PATH,
            _HKAR_META_PATH,
        )

        _load_onnx(_MIMO_ONNX_PATH)
        logger.info("model_warmed_up", extra={"file": "mimo_model.onnx"})

        _load_onnx(_HKAR_ONNX_PATH)
        logger.info("model_warmed_up", extra={"file": "hkar_model.onnx"})

        _load_meta_json(_MIMO_META_PATH)
        logger.info("meta_warmed_up", extra={"file": "mimo_meta.json"})

        _load_meta_json(_HKAR_META_PATH)
        logger.info("meta_warmed_up", extra={"file": "hkar_meta.json"})

        # ONNX tensor ad/sekil dogrulamasi
        _validate_onnx_shapes(models_dir)

        instance._loaded = True
        cls._instance = instance
        logger.info("model_registry_ready")
        return instance

    @property
    def loaded(self) -> bool:
        return self._loaded
