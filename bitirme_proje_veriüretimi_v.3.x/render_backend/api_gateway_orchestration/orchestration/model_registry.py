"""
render_backend/orchestration/model_registry.py — Model Sağlık Kontrolü

predict.py modellerini lru_cache ile kendi içinde yükler.
Bu sınıf: startup'ta dosya varlığını doğrular, loaded flag'i tutar.
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
    "mimo_model.pkl",
    "hkar_model.pkl",
]


class ModelRegistry:
    """
    Model dosyalarının varlığını doğrular.
    Gerçek model yükleme predict.py içinde lru_cache ile yapılır.
    """

    _instance: "ModelRegistry | None" = None

    def __init__(self):
        self._loaded = False

    @classmethod
    def load_all(cls) -> "ModelRegistry":
        """Singleton. Dosya varlığını kontrol eder, yüklenmiş flag'ini set eder."""
        if cls._instance is not None and cls._instance._loaded:
            return cls._instance

        instance = cls()
        models_dir = os.environ.get("MODELS_DIR", _SAVED_MODELS_DIR)

        missing = []
        for fname in _REQUIRED_FILES:
            path = os.path.join(models_dir, fname)
            if not os.path.exists(path):
                missing.append(path)

        if missing:
            raise FileNotFoundError(
                f"Model dosyaları bulunamadı: {missing}\n"
                f"saved_models/ dizinini Render Disk'e yükleyin."
            )

        # predict.py'nin lru_cache'ini önceden ısıt (warm-up)
        from features.predict import predict_student_risk  # noqa: F401
        import pickle
        for fname in _REQUIRED_FILES:
            path = os.path.join(models_dir, fname)
            with open(path, "rb") as f:
                pickle.load(f)
            logger.info("model_file_verified", extra={"file": fname})

        instance._loaded = True
        cls._instance = instance
        logger.info("model_registry_ready")
        return instance

    @property
    def loaded(self) -> bool:
        return self._loaded
