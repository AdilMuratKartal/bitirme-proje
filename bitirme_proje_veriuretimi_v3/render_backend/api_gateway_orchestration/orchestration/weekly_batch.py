import os
import sys
import logging

# Support local testing by loading .env from parent folders
try:
    from dotenv import load_dotenv
    # Go up 4 levels: orchestration -> api_gateway_orchestration -> render_backend -> bitirme_proje_veriuretimi_v3
    path = os.path.abspath(__file__)
    for _ in range(4):
        path = os.path.dirname(path)
    env_path = os.path.join(path, ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass

from dependencies import build_dao
from ServiceLayer.risk_service import recalculate_all_users_risk

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("weekly_batch")

def main():
    logger.info("Starting weekly batch risk recalculation (bulk processing)...")
    dao = build_dao()
    
    try:
        count = recalculate_all_users_risk(dao)
        logger.info(f"Batch completed successfully. Recalculated {count} users.")
    except Exception as e:
        logger.error(f"Batch recalculation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
