"""
render_backend/features/feature_student_success.py

build_student_success_features(uid, tables) → np.ndarray shape (1, 42)

Feature sırası student_success_meta.json["features"] ile birebir eşleşir.
course_z ve pctile alanları 0 / 50 ile yaklaşık hesaplanır (kurs dağılımı
anlık sorguda mevcut değil; XGBoost eşik tabanlı olduğu için bu yeterlidir).
"""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

_SESSION_GAP_S: int = 30 * 60  # 30 dakika arası = yeni seans

_PERF_COMPS: frozenset = frozenset({
    "mod_quiz", "mod_assign", "mod_workshop", "mod_survey",
})
_FORUM_COMPS: frozenset = frozenset({"mod_forum"})
_RESOURCE_COMPS: frozenset = frozenset({
    "mod_resource", "mod_page", "mod_book", "mod_folder",
})


def build_student_success_features(
    uid: int,
    tables: Dict[str, pd.DataFrame],
) -> np.ndarray:
    """
    42 feature vektörü döndürür. Shape: (1, 42), dtype float32.
    """
    logs  = tables.get("mdl_logstore_standard_log", pd.DataFrame())
    asub  = tables.get("mdl_assign_submission", pd.DataFrame())
    qatt  = tables.get("mdl_quiz_attempts", pd.DataFrame())
    grd   = tables.get("mdl_grade_grades", pd.DataFrame())

    u_logs = logs[logs["userid"] == uid].copy() if not logs.empty else pd.DataFrame(
        columns=["timecreated", "action", "component", "objectid"]
    )
    u_sub  = asub[asub["userid"] == uid].copy() if not asub.empty else pd.DataFrame()
    u_qatt = qatt[qatt["userid"] == uid].copy() if not qatt.empty else pd.DataFrame()
    u_grd  = grd[grd["userid"] == uid].copy() if not grd.empty else pd.DataFrame()

    # ── Temel log sayıları ───────────────────────────────────────────
    n_log = float(len(u_logs))

    if not u_logs.empty:
        perf_mask      = u_logs["component"].isin(_PERF_COMPS)
        n_perf_log     = float(perf_mask.sum())
        n_pure_log     = float((~perf_mask).sum())

        view_mask      = u_logs["action"].isin(["viewed", "view"])
        n_view         = float(view_mask.sum())

        forum_mask     = u_logs["component"].isin(_FORUM_COMPS)
        forum_view     = float((forum_mask & view_mask).sum())
        forum_submit   = float((forum_mask & ~view_mask).sum())

        res_mask       = u_logs["component"].isin(_RESOURCE_COMPS)
        resource_view  = float((res_mask & view_mask).sum())

        n_modul_cesit  = float(u_logs["component"].nunique())

        # ── Zaman tabanlı özellikler ─────────────────────────────────
        ts             = pd.to_datetime(u_logs["timecreated"], unit="s", utc=True)
        night_ratio    = float((((ts.dt.hour >= 22) | (ts.dt.hour < 6))).mean())
        weekend_ratio  = float((ts.dt.dayofweek >= 5).mean())

        # ── Aktif gün & varyanslar ───────────────────────────────────
        dates          = ts.dt.date
        n_aktif_gun    = float(dates.nunique())
        daily_counts   = u_logs.groupby(dates).size()
        log_per_gun    = float(daily_counts.mean()) if len(daily_counts) > 0 else 0.0
        log_var        = float(daily_counts.var(ddof=0)) if len(daily_counts) > 0 else 0.0

        # aktif_sure_gun: her günün ilk-son log arasındaki süre (saat), gün ortalaması
        u_logs["_date"] = dates.values
        def _day_span(grp):
            mn, mx = grp["timecreated"].min(), grp["timecreated"].max()
            return (mx - mn) / 3600.0
        day_spans      = u_logs.groupby("_date").apply(_day_span)
        aktif_sure_gun = float(day_spans.mean()) if len(day_spans) > 0 else 0.0

        # max_hissizlik: arka arkaya en uzun pasif gün sayısı
        sorted_dates   = sorted(dates.unique())
        if len(sorted_dates) > 1:
            gaps = [(sorted_dates[i + 1] - sorted_dates[i]).days - 1
                    for i in range(len(sorted_dates) - 1)]
            max_hissizlik = float(max(gaps)) if gaps else 0.0
        else:
            max_hissizlik = 0.0

        # ── Seans sayısı ─────────────────────────────────────────────
        ts_sorted      = u_logs["timecreated"].sort_values().values
        diffs          = np.diff(ts_sorted)
        n_sessions     = float(1 + (diffs > _SESSION_GAP_S).sum())
        clicks_per_session = n_log / max(n_sessions, 1.0)

        # ── Oran özellikleri ─────────────────────────────────────────
        view_ratio         = n_view / max(n_log, 1.0)
        perf_ratio         = n_perf_log / max(n_log, 1.0)
        resource_view_pct  = resource_view / max(n_view, 1.0)

    else:
        n_perf_log = n_pure_log = n_view = 0.0
        forum_view = forum_submit = resource_view = 0.0
        n_modul_cesit = 0.0
        night_ratio = weekend_ratio = 0.0
        n_aktif_gun = log_per_gun = log_var = 0.0
        aktif_sure_gun = max_hissizlik = 0.0
        n_sessions = clicks_per_session = 0.0
        view_ratio = perf_ratio = resource_view_pct = 0.0

    # ── Ödev özellikleri ────────────────────────────────────────────
    n_teslim = float(len(u_sub))
    teslim_per_gun = n_teslim / max(n_aktif_gun, 1.0)
    if not u_sub.empty and "timecreated" in u_sub.columns and len(u_sub) > 1:
        sub_ts    = pd.to_datetime(u_sub["timecreated"], unit="s").dt.date
        sub_daily = u_sub.groupby(sub_ts).size()
        teslim_var = float(sub_daily.var(ddof=0)) if len(sub_daily) > 0 else 0.0
    else:
        teslim_var = 0.0

    # ── Quiz özellikleri ────────────────────────────────────────────
    n_quiz_deneme = float(len(u_qatt))
    quiz_act      = n_quiz_deneme   # quiz girişimi ≈ quiz aksiyonu
    quiz_act_pct  = quiz_act / max(n_log, 1.0)

    # ── Performans skoru ────────────────────────────────────────────
    if not u_grd.empty and "finalgrade" in u_grd.columns:
        valid_grd = u_grd["finalgrade"].dropna()
        if "grademax" in u_grd.columns:
            grademax = u_grd["grademax"].fillna(100.0)
            ratios = (valid_grd / grademax.loc[valid_grd.index].clip(lower=1.0)).dropna()
            performans_skoru = float(ratios.mean()) if len(ratios) > 0 else 0.5
        else:
            performans_skoru = float(valid_grd.mean() / 100.0) if len(valid_grd) > 0 else 0.5
        performans_skoru = float(np.clip(performans_skoru, 0.0, 1.0))
    else:
        performans_skoru = 0.5

    # ── log1p dönüşümleri ───────────────────────────────────────────
    n_aktif_gun_log1p  = float(np.log1p(n_aktif_gun))
    n_log_log1p        = float(np.log1p(n_log))
    n_perf_log_log1p   = float(np.log1p(n_perf_log))
    n_sessions_pctile  = 50.0  # kurs dağılımı yok → ortalama varsayım
    n_teslim_log1p     = float(np.log1p(n_teslim))
    n_view_log1p       = float(np.log1p(n_view))
    n_quiz_deneme_log1p = float(np.log1p(n_quiz_deneme))

    # ── course_z ve pctile yaklaşımları (0 / 50) ───────────────────
    aktif_sure_gun_course_z = 0.0
    n_aktif_gun_course_z    = 0.0
    n_aktif_gun_pctile      = 50.0
    n_log_course_z          = 0.0
    n_log_pctile            = 50.0
    n_modul_cesit_pctile    = 50.0
    n_perf_log_course_z     = 0.0
    n_perf_log_pctile       = 50.0

    # ── Feature vektörü (student_success_meta.json sırasıyla) ──────
    features = [
        aktif_sure_gun,           # 0
        aktif_sure_gun_course_z,  # 1
        clicks_per_session,       # 2
        forum_submit,             # 3
        forum_view,               # 4
        log_per_gun,              # 5
        log_var,                  # 6
        max_hissizlik,            # 7
        n_aktif_gun,              # 8
        n_aktif_gun_course_z,     # 9
        n_aktif_gun_log1p,        # 10
        n_aktif_gun_pctile,       # 11
        n_log,                    # 12
        n_log_course_z,           # 13
        n_log_log1p,              # 14
        n_log_pctile,             # 15
        n_modul_cesit,            # 16
        n_modul_cesit_pctile,     # 17
        n_perf_log,               # 18
        n_perf_log_course_z,      # 19
        n_perf_log_log1p,         # 20
        n_perf_log_pctile,        # 21
        n_pure_log,               # 22
        n_quiz_deneme,            # 23
        n_quiz_deneme_log1p,      # 24
        n_sessions,               # 25
        n_sessions_pctile,        # 26
        n_teslim,                 # 27
        n_teslim_log1p,           # 28
        n_view,                   # 29
        n_view_log1p,             # 30
        night_ratio,              # 31
        perf_ratio,               # 32
        performans_skoru,         # 33
        quiz_act,                 # 34
        quiz_act_pct,             # 35
        resource_view,            # 36
        resource_view_pct,        # 37
        teslim_per_gun,           # 38
        teslim_var,               # 39
        view_ratio,               # 40
        weekend_ratio,            # 41
    ]

    return np.array(features, dtype=np.float32).reshape(1, 42)
