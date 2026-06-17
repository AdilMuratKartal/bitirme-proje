"""
render_backend/orchestration/model_registry.py — Model Sağlık Kontrolü

Startup'ta dosya varlığını doğrular, ONNX oturumunu ön belleğe alır
ve tensor şekil uyumluluğunu kontrol eder.
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
    "student_success_model.onnx",
    "student_success_meta.json",
]


def _validate_onnx_shapes(models_dir: str) -> None:
    """
    student_success_model ONNX tensor adlarını ve şekillerini doğrula.
    Beklenen: float_input[None, 42] → label[N] + probabilities[N, 2]
    """
    from features.predict import _load_onnx, _RISK_PREMODEL_ONNX_PATH

    session  = _load_onnx(_RISK_PREMODEL_ONNX_PATH)
    inp_map  = {inp.name: inp for inp in session.get_inputs()}
    out_list = [out.name for out in session.get_outputs()]

    if not inp_map:
        raise RuntimeError("risk_premodel ONNX: hiç giriş bulunamadı.")

    first_inp = list(inp_map.values())[0]
    n_features = first_inp.shape[-1] if first_inp.shape else None
    if n_features is not None and n_features != 42:
        raise RuntimeError(
            f"risk_premodel ONNX: 42 özellik bekleniyor, bulundu: {n_features}. "
            f"Model student_success_model.onnx ile eşleşmiyor."
        )

    if len(out_list) < 2:
        raise RuntimeError(
            f"risk_premodel ONNX: en az 2 çıkış bekleniyor (label + probabilities), "
            f"bulundu: {out_list}"
        )

    logger.info("onnx_shapes_validated", extra={"model": "student_success_model"})


class ModelRegistry:
    """
    Model dosyalarının varlığını doğrular, ONNX oturumunu ön belleğe alır.
    Gerçek model yükleme predict.py içinde lru_cache ile yapılır.
    """

    _instance: "ModelRegistry | None" = None

    def __init__(self):
        self._loaded = False

    @classmethod
    def load_all(cls) -> "ModelRegistry":
        """Singleton. Dosya varlığını kontrol eder, ONNX oturumunu ön belleğe alır."""
        if cls._instance is not None and cls._instance._loaded:
            return cls._instance

        instance = cls()
        models_dir = os.environ.get("MODELS_DIR", _SAVED_MODELS_DIR)

        # Dosya varlık kontrolü
        missing = []
        for fname in _REQUIRED_FILES:
            path = os.path.join(models_dir, fname)
            if not os.path.exists(path):
                missing.append(path)

        if missing:
            raise FileNotFoundError(
                f"Model dosyaları bulunamadı: {missing}\n"
                "render_backend/saved_models/ içine onnx ve json dosyalarını ekleyin.\n"
                "Kaynak: localv2/saved_models/student_success_model.onnx"
            )

        # lru_cache'i doldur
        from features.predict import (
            _load_onnx,
            _load_meta_json,
            _RISK_PREMODEL_ONNX_PATH,
            _RISK_PREMODEL_META_PATH,
        )

        _load_onnx(_RISK_PREMODEL_ONNX_PATH)
        logger.info("model_warmed_up", extra={"file": "student_success_model.onnx"})

        _load_meta_json(_RISK_PREMODEL_META_PATH)
        logger.info("meta_warmed_up", extra={"file": "student_success_meta.json"})

        # ONNX tensor ad/şekil doğrulaması
        _validate_onnx_shapes(models_dir)

        instance._loaded = True
        cls._instance = instance
        logger.info("model_registry_ready")
        return instance

    @property
    def loaded(self) -> bool:
        return self._loaded
