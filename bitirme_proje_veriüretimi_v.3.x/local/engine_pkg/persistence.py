"""
engine_pkg/persistence.py — Motor durumu kayıt/yükleme (StateManager).
Faz 2 / cron sürekliliği için JSON tabanlı state yönetimi.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from events import GradingEvent

from .context import SimContext


class StateManager:
    """
    SimContext durumunu JSON'a yazar ve okur; CSV'den transaction satırlarını yükler.
    """
    _FMT = "%Y-%m-%dT%H:%M:%S"

    def save(self, ctx: SimContext, path: str = "output/engine_state.json") -> None:
        state = {
            "ids": ctx.store._ids,
            "completion_state": {
                f"{k[0]},{k[1]}": v
                for k, v in ctx.completion_state.items()
            },
            "s3_course_done": {
                f"{k[0]},{k[1]}": v
                for k, v in ctx.s3_course_done.items()
            },
            "assign_meta": {
                str(aid): {
                    "item_id": v["item_id"],
                    "due_dt":  v["due_dt"].strftime(self._FMT),
                }
                for aid, v in ctx.assign_meta.items()
            },
            "pending_grading": [
                {
                    "week":       g.week,
                    "assign_id":  g.assign_id,
                    "due_dt":     g.due_dt.strftime(self._FMT),
                    "grading_dt": g.grading_dt.strftime(self._FMT),
                }
                for g in ctx.pending_grading
            ],
        }
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        print(f"   State kaydedildi -> {p}")

    def load(self, ctx: SimContext, path: str = "output/engine_state.json") -> None:
        p = Path(path)
        if not p.exists():
            return

        with open(p, encoding="utf-8") as f:
            state = json.load(f)

        ctx.store._ids.update({k: int(v) for k, v in state.get("ids", {}).items()})

        for k_str, v in state.get("completion_state", {}).items():
            uid, cid = map(int, k_str.split(","))
            ctx.completion_state[(uid, cid)] = {
                "miss_count":  int(v.get("miss_count", 0)),
                "prev_missed": bool(v.get("prev_missed", False)),
            }

        for k_str, v in state.get("s3_course_done", {}).items():
            uid, cid = map(int, k_str.split(","))
            ctx.s3_course_done[(uid, cid)] = int(v)

        for k_str, v in state.get("assign_meta", {}).items():
            ctx.assign_meta[int(k_str)] = {
                "item_id": int(v["item_id"]),
                "due_dt":  datetime.strptime(v["due_dt"], self._FMT),
            }

        for g_dict in state.get("pending_grading", []):
            ctx.pending_grading.append(GradingEvent(
                week       = int(g_dict["week"]),
                assign_id  = int(g_dict["assign_id"]),
                due_dt     = datetime.strptime(g_dict["due_dt"],     self._FMT),
                grading_dt = datetime.strptime(g_dict["grading_dt"], self._FMT),
            ))

        print(f"   State yuklendi <- {p}")

    def load_rows_from_csv(self, ctx: SimContext, out_dir: str = "output") -> None:
        """
        Cron restart sonrası önkoşul kontrolü için gereken transaction tablolarını yükler.
        Yalnızca handler'lar tarafından OKUNAN tablolar yüklenir; sadece yazılan tablolar atlanır.
        """
        _TRANSACTION_TABLES = [
            "mdl_course_modules_completion",
            "mdl_assign_submission",
        ]
        raw     = Path(out_dir) / "raw_tables"
        loaded  = 0
        skipped = 0
        for tname in _TRANSACTION_TABLES:
            fpath = raw / f"{tname}.csv"
            if fpath.exists():
                df = pd.read_csv(fpath)
                ctx.store._rows[tname] = (
                    df.where(pd.notna(df), other=None).to_dict("records")
                )
                loaded += 1
            else:
                skipped += 1
        print(f"   load_rows_from_csv: {loaded} tablo yuklendi, {skipped} atlandi <- {raw}")
