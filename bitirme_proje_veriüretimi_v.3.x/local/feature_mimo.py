"""
feature_mimo.py — MIMO Model (1 & 2) Özellik Mühendisliği
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ERD referansları (MIMO-MODEL-ERD):
  X_Time (LSTM):
    - mdl_logstore_standard_log  → haftalık tık (sent weekly logs)
    - mdl_grade_grades_history   → haftalık not (sent weekly finalgrade)

  X_Static (Dense):
    - mdl_logstore_standard_log  → son 7 gün view sayısı
    - mdl_assign_submission      → timemodified - duedate (sent timemodified-duedate)
    - mdl_grade_grades           → finalgrade (sent finalgrade)
    - mdl_quiz_attempts          → timefinish - timestart (sent timefinish-timestart)
    - mdl_course_modules_completion → completionstate (sent completionstate)

Çıktılar:
  y_risk_score      0–1  Sigmoid
  y_predicted_grade 0–100 Regression
"""

import numpy as np
import pandas as pd
from typing import Dict, Any
from config import CFG
from student_registry import STUDENT_REGISTRY


def _uids() -> np.ndarray:
    return STUDENT_REGISTRY["userid"].values


# ─────────────────────────────────────────────────────────────────
# X_Time — LSTM Kanalı
# ─────────────────────────────────────────────────────────────────
def build_x_time(
    log_df:        pd.DataFrame,
    grade_hist_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Son N hafta için (haftalık_tık, haftalık_not) çifti.
    Eksik hafta → önceki hafta forward-fill | ilk hafta eksikse 50.
    """
    n    = CFG.general.n_lookback
    uids = _uids()

    weekly_clicks = (
        log_df[log_df["action"] == "view"]
        .groupby(["userid", "_week"])
        .size()
        .reset_index(name="clicks")
    )
    # Engine tablosunda _week yoksa timemodified'dan türet
    if "_week" not in grade_hist_df.columns:
        from engine import TimeCalc
        _BASE_TS = int(TimeCalc.week_start(1).timestamp())
        grade_hist_df = grade_hist_df.copy()
        grade_hist_df["_week"] = ((grade_hist_df["timemodified"] - _BASE_TS) // (7 * 86_400) + 1).clip(lower=1)
    weekly_grades = grade_hist_df[["userid", "_week", "finalgrade"]].copy()

    records = []
    for uid in uids:
        u_cl = weekly_clicks[weekly_clicks["userid"] == uid].groupby("_week")["clicks"].sum()
        u_gr = weekly_grades[weekly_grades["userid"] == uid].groupby("_week")["finalgrade"].mean()

        row        = {"userid": uid}
        max_week   = CFG.general.n_weeks
        last_grade = 50.0

        for lag in range(n, 0, -1):
            week_idx = max_week - lag + 1
            label    = f"w_minus_{lag}"

            clicks = float(u_cl.get(week_idx, 0))
            raw_g  = u_gr.get(week_idx, None)
            if raw_g is None or pd.isna(raw_g):
                grade = last_grade
            else:
                grade = float(raw_g)
                last_grade = grade

            row[f"{label}_clicks"] = clicks
            row[f"{label}_grade"]  = grade

        records.append(row)

    return pd.DataFrame(records)


def reshape_x_time_3d(df: pd.DataFrame) -> np.ndarray:
    """DataFrame → (N, lookback, 2) LSTM shape."""
    n    = CFG.general.n_lookback
    cols = [c for c in df.columns if c != "userid"]
    return df[cols].values.reshape(len(df), n, 2).astype(np.float32)


# ─────────────────────────────────────────────────────────────────
# X_Static — Dense Kanalı
# ─────────────────────────────────────────────────────────────────
def build_x_static(
    log_df:          pd.DataFrame,
    grade_df:        pd.DataFrame,
    assign_df:       pd.DataFrame,
    assign_sub_df:   pd.DataFrame,
    quiz_att_df:     pd.DataFrame,
    completion_df:   pd.DataFrame,
    course_mod_df:   pd.DataFrame,
) -> pd.DataFrame:
    """
    5 boyutlu statik vektör:
    [login_7d, delay_hours, current_grade, quiz_effort_min, completion_ratio]

    Eksik veri stratejisi (segment uyumlu):
      - Not yok        → 50.0  (nötr)
      - Ödev teslim yok → 48.0 saat (yüksek gecikme)
      - Quiz yok       → 3.0 dk (minimum süre)
      - Tamamlama yok  → 0.0
    """
    uids      = _uids()
    n_modules = len(course_mod_df)

    # Son 7 günün view sayısı
    max_ts    = log_df["timecreated"].max()
    recent    = log_df[(log_df["timecreated"] >= max_ts - 7 * 86_400) &
                       (log_df["action"] == "view")]
    login_7d  = recent.groupby("userid").size().reindex(uids, fill_value=0)

    # Ödev teslim gecikmesi
    delay = assign_sub_df.groupby("userid")["delay_hours"].mean().reindex(uids, fill_value=48.0)

    # Anlık not
    cur_grade = grade_df.groupby("userid")["finalgrade"].mean().reindex(uids, fill_value=50.0)   # BUG-3 FIX: duplicate userid index → crash önlemi

    # Quiz süresi
    quiz_eff  = quiz_att_df.groupby("userid")["duration_minutes"].mean().reindex(uids, fill_value=3.0)

    # Tamamlama oranı
    completed = completion_df.groupby("userid").size().reindex(uids, fill_value=0)
    comp_ratio = (completed / max(n_modules, 1)).clip(0, 1)

    return pd.DataFrame({
        "userid":            uids,
        "login_count_7d":    login_7d.values.astype(np.float32),
        "delay_score":       delay.values.astype(np.float32),
        "current_avg_grade": cur_grade.values.astype(np.float32),
        "quiz_effort_min":   quiz_eff.values.astype(np.float32),
        "completion_ratio":  comp_ratio.values.astype(np.float32),
    })


# ─────────────────────────────────────────────────────────────────
# ÇIKTILAR
# ─────────────────────────────────────────────────────────────────
def build_mimo_targets(
    grade_df:      pd.DataFrame,
    assign_sub_df: pd.DataFrame,
    completion_df: pd.DataFrame,
    quiz_att_df:   pd.DataFrame,
    course_mod_df: pd.DataFrame,
) -> pd.DataFrame:
    uids      = _uids()
    n_modules = len(course_mod_df)

    grade     = grade_df.groupby("userid")["finalgrade"].mean().reindex(uids, fill_value=50.0)   # BUG-3 FIX: duplicate userid index → crash önlemi
    delay     = assign_sub_df.groupby("userid")["delay_hours"].mean().reindex(uids, fill_value=48.0)
    completed = completion_df.groupby("userid").size().reindex(uids, fill_value=0)
    comp      = (completed / max(n_modules, 1)).clip(0, 1)
    quiz_sc   = quiz_att_df.groupby("userid")["sumgrades"].mean().reindex(uids, fill_value=20.0)

    raw_risk = (
        (100 - grade.values)              * 0.40
        + np.clip(delay.values, 0, 72) / 72 * 100 * 0.25
        + (1 - comp.values) * 100         * 0.20
        + (100 - quiz_sc.values)          * 0.15
    )
    risk   = 1 / (1 + np.exp(-0.05 * (raw_risk - 50)))
    p_grad = np.clip(grade.values * 0.50 + quiz_sc.values * 0.30 + comp.values * 100 * 0.20, 0, 100)

    return pd.DataFrame({
        "userid":                             uids,
        CFG.mimo_target.risk_score_col:       np.round(risk,   4).astype(np.float32),
        CFG.mimo_target.predicted_grade_col:  np.round(p_grad, 2).astype(np.float32),
    })


# ─────────────────────────────────────────────────────────────────
# ANA BORU HATTI
# ─────────────────────────────────────────────────────────────────
def build_mimo_dataset(tables: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    print("\n🔧 MIMO özellik mühendisliği başlıyor...")

    x_time_df = build_x_time(
        tables["mdl_logstore_standard_log"],
        tables["mdl_grade_grades_history"],
    )
    x_static_df = build_x_static(
        tables["mdl_logstore_standard_log"],
        tables["mdl_grade_grades"],
        tables["mdl_assign"],
        tables["mdl_assign_submission"],
        tables["mdl_quiz_attempts"],
        tables["mdl_course_modules_completion"],
        tables["mdl_course_modules"],
    )
    targets_df = build_mimo_targets(
        tables["mdl_grade_grades"],
        tables["mdl_assign_submission"],
        tables["mdl_course_modules_completion"],
        tables["mdl_quiz_attempts"],
        tables["mdl_course_modules"],
    )

    x_time_3d  = reshape_x_time_3d(x_time_df)
    x_static_2d = x_static_df.drop(columns="userid").values.astype(np.float32)

    print(f"   X_Time   shape : {x_time_3d.shape}")
    print(f"   X_Static shape : {x_static_2d.shape}")
    print(f"   Targets  shape : {targets_df.shape}")

    return {
        "x_time_df":   x_time_df,
        "x_static_df": x_static_df,
        "targets_df":  targets_df,
        "X_Time":      x_time_3d,
        "X_Static":    x_static_2d,
        "y_risk":      targets_df[CFG.mimo_target.risk_score_col].values,
        "y_grade":     targets_df[CFG.mimo_target.predicted_grade_col].values,
    }
