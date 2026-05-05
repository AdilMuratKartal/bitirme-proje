"""
pipeline.py — Giriş Noktası v5.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Lokal calistirma:
    python pipeline.py            -> 14 haftalik tam donem (CSV)
    python pipeline.py --weeks 8  -> sadece 8 hafta
    python pipeline.py --view     -> uretilmis verileri goruntule
    python pipeline.py --view --table mdl_quiz_attempts --limit 20

CSV ve PostgreSQL uretimi icin:
    python datafile_generator/csv/csv_data_generator.py
    python datafile_generator/postgresql/postgresql_data_generator.py
"""

import sys
import os

_LOCAL = os.path.dirname(os.path.abspath(__file__))
_ROOT  = os.path.dirname(_LOCAL)
for _p in (_LOCAL, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import argparse

from config import CFG
from engine import SimulationEngine
from datafile_generator.base import save_meta
from datafile_generator.csv.csv_data_generator import save_tables, view_data


# ─────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Moodle Sentetik Veri Uretici v5.0 -- SimulationEngine",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""Ornekler:
  python pipeline.py                         -> 14 haftalik tam donem
  python pipeline.py --weeks 8              -> sadece 8 hafta
  python pipeline.py --week 5               -> cron modu: sadece hafta 5 (append)
  python pipeline.py --view
  python pipeline.py --view --table mdl_quiz_attempts --limit 25
""",
    )
    parser.add_argument("--weeks", type=int, default=CFG.general.n_weeks,
                        help=f"Hafta sayisi (varsayilan: {CFG.general.n_weeks})")
    parser.add_argument("--week",   type=int, default=None,
                        help="Cron modu: tek hafta simule et ve CSV'ye append et")
    parser.add_argument("--output", type=str, default="output",
                        help="Cikti dizini (varsayilan: output)")
    parser.add_argument("--view",   action="store_true",
                        help="Uretilmis verileri goruntule")
    parser.add_argument("--table",  type=str, default=None,
                        help="--view ile: belirli tabloyu onizle")
    parser.add_argument("--limit",  type=int, default=10,
                        help="--view --table ile: gosterilecek satir sayisi")
    args = parser.parse_args()

    if args.view:
        view_data(args.output, args.table, args.limit)

    elif args.week is not None:
        # Cron modu: state yukle, tek hafta calistir, CSV'ye append et.
        # BUG-2: state once kaydedilir (crash safety — ID cakismasi onlenir).
        state_path = f"{args.output}/engine_state.json"
        engine = SimulationEngine()
        engine.load_state(state_path)
        engine.load_rows_from_csv(args.output)
        engine.simulate_week(args.week)
        tables = engine.to_dataframes()
        engine.save_state(state_path)
        save_tables(tables, args.output, append=True)
        save_meta(tables, args.week, args.output)

    else:
        engine = SimulationEngine()
        tables = engine.simulate_full_semester(weeks=args.weeks)
        save_tables(tables, args.output)
        save_meta(tables, args.weeks, args.output)
