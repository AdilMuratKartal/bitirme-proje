# engine.py — Uyumluluk shim; asıl kod engine_pkg/ paketinde.
# Bu dosya kaldırılmadan önce tüm importlar engine_pkg'ye taşınmalıdır.
from engine_pkg import SimulationEngine  # noqa: F401

__all__ = ["SimulationEngine"]
