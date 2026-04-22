"""
render_backend/orchestration/weekly_batch.py — Cron Job Entrypoint

Render.yaml'daki cron command:
    python -m api_gateway_orchestration.orchestration.weekly_batch

Her Pazartesi 02:00 UTC çalışır.
"""

from __future__ import annotations

import os
import sys
import logging
from datetime import datetime

# render_backend/ dizinini sys.path'e ekle
_HERE = os.path.dirname(os.path.abspath(__file__))
_RENDER_BACKEND = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
sys.path.insert(0, _RENDER_BACKEND)

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)


def current_week() -> int:
    """ISO hafta numarasını döner (1-53). Cron trigger tarihinden alınır."""
    return datetime.utcnow().isocalendar()[1]


def main():
    from dependencies import build_dao
    from api_gateway_orchestration.orchestration.model_registry import ModelRegistry
    from api_gateway_orchestration.orchestration.orchestration import BatchOrchestrator

    logger.info("cron_weekly_batch_starting")

    dao = build_dao()
    models = ModelRegistry.load_all()
    orchestrator = BatchOrchestrator(dao=dao, models=models)

    week = int(os.environ.get("OVERRIDE_WEEK", current_week()))
    summary = orchestrator.run_weekly_batch(week=week, dao=dao)

    logger.info("cron_weekly_batch_done", extra=summary)

    if summary["failed"] > 0:
        logger.warning("cron_partial_failure",
                       extra={"failed_count": summary["failed"]})


if __name__ == "__main__":
    main()
