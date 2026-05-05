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
    "mimo_model.tflite",
    "hkar_model.tflite",
    "mimo_meta.json",
    "hkar_meta.json",
]


def _validate_tflite_shapes(models_dir: str) -> None:
    """
    TFLite tensor sekillerini dogrula.
    Shape tabanli esleme (predict.py) icin on kosullar:
      MIMO: 3D girdi (X_Time) + 2D girdi (X_Static), 3 cikis (risk, grade, segment-4)
      HKAR: 3D girdi (X_Sequence) + 2D girdi (X_UserHabit), 1 cikis (segment-4)
    """
    from features.predict import _load_tflite, _MIMO_TFLITE_PATH, _HKAR_TFLITE_PATH

    mimo = _load_tflite(_MIMO_TFLITE_PATH)
    inp  = mimo.get_input_details()
    out  = sorted(mimo.get_output_details(), key=lambda d: d['index'])

    has_3d = any(len(d['shape']) == 3 for d in inp)
    has_2d = any(len(d['shape']) == 2 for d in inp)
    if not (has_3d and has_2d):
        raise RuntimeError(
            f"MIMO tensor girdileri beklenmiyor: "
            f"{[(d['name'], list(d['shape'])) for d in inp]}"
        )
    if len(out) < 3 or out[2]['shape'][-1] != 4:
        raise RuntimeError(
            f"MIMO y_segment (4 sinif) 3. cikista bulunamadi: "
            f"{[list(d['shape']) for d in out]}"
        )

    hkar  = _load_tflite(_HKAR_TFLITE_PATH)
    out_h = hkar.get_output_details()
    if not out_h or out_h[0]['shape'][-1] != 4:
        raise RuntimeError(
            f"HKAR cikis (4 sinif) bulunamadi: "
            f"{[list(d['shape']) for d in out_h]}"
        )

    logger.info("tflite_shapes_validated")


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
            _load_tflite,
            _load_meta_json,
            _MIMO_TFLITE_PATH,
            _HKAR_TFLITE_PATH,
            _MIMO_META_PATH,
            _HKAR_META_PATH,
        )

        _load_tflite(_MIMO_TFLITE_PATH)
        logger.info("model_warmed_up", extra={"file": "mimo_model.tflite"})

        _load_tflite(_HKAR_TFLITE_PATH)
        logger.info("model_warmed_up", extra={"file": "hkar_model.tflite"})

        _load_meta_json(_MIMO_META_PATH)
        logger.info("meta_warmed_up", extra={"file": "mimo_meta.json"})

        _load_meta_json(_HKAR_META_PATH)
        logger.info("meta_warmed_up", extra={"file": "hkar_meta.json"})

        # Tensor sekil dogrulamasi
        _validate_tflite_shapes(models_dir)

        instance._loaded = True
        cls._instance = instance
        logger.info("model_registry_ready")
        return instance

    @property
    def loaded(self) -> bool:
        return self._loaded
