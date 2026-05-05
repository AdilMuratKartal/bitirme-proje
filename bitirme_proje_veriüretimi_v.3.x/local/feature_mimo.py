"""
feature_mimo.py — MIMO Model (1 & 2) Özellik Mühendisliği  v3.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Temporal ayrım:
  X_Time / X_Static → H1 – H{cutoff_week} (gözlem penceresi)
  y_risk / y_grade  → H{FUTURE_CUTOFF_WEEK+1}+ gerçek not veya segment proj.
                       (cutoff_week bağımsız — tutarlı etiket)

ERD referansları:
  X_Time (LSTM)  : mdl_logstore_standard_log + mdl_grade_grades_history
  X_Static (Dense): mdl_logstore + mdl_grade_grades + mdl_assign_submission
                    + mdl_quiz_attempts + mdl_course_modules_completion

Çıktılar:
  y_risk_score      0–1   Sigmoid (segment + dropout_week bazlı)
  y_predicted_grade 0–100 Regression (FUTURE_CUTOFF_WEEK sonrası gerçek not)
  y_segment         0–3   Sınıf indeksi (S1=0 … S4=3)

Multi-Cutoff API:
  build_mimo_dataset(tables, cutoff_week=8)
  → Farklı haftalarda alınan snapshot'lar için çağrılabilir.
  → Etiketler (y_risk, y_grade, y_segment) HER ZAMAN FUTURE_CUTOFF_WEEK=10
    sınırı kullanılarak üretilir — observation cutoff'tan bağımsız.
  → X_Static 6. özellik olarak current_week içerir (drift önleme).
"""

import datetime
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional

from config import CFG, FUTURE_CUTOFF_WEEK
from student_registry import STUDENT_REGISTRY

_SEG_IDX: Dict[str, int] = {"S1": 0, "S2": 1, "S3": 2, "S4": 3}


def _uids() -> np.ndarray:
    return STUDENT_REGISTRY["userid"].values


def _resolve_cutoff(cutoff_week: Optional[int] = None) -> int:
    """cutoff_week verilmişse kullan; yoksa global FUTURE_CUTOFF_WEEK'i al.
    Her ikisini de CFG.general.n_weeks ile kırp.
    """
    cw = cutoff_week if cutoff_week is not None else FUTURE_CUTOFF_WEEK
    return min(CFG.general.n_weeks, cw)


def _cutoff_ts(cutoff_week: Optional[int] = None) -> int:
    """
    H{resolved_cutoff} bitişi = H{resolved_cutoff+1} başlangıcı.
    X özellikleri bu timestamp'ten ÖNCE; y hedefleri bu timestamp'ten SONRA.
    """
    return int(
        (CFG.general.semester_start
         + datetime.timedelta(weeks=_resolve_cutoff(cutoff_week))).timestamp()
    )


def _label_cutoff_ts() -> int:
    """Etiket sınırı: her zaman FUTURE_CUTOFF_WEEK kullanılır.
    Observation cutoff'tan bağımsız → multi-cutoff'ta tutarlı etiket.
    """
    return int(
        (CFG.general.semester_start
         + datetime.timedelta(weeks=min(CFG.general.n_weeks, FUTURE_CUTOFF_WEEK))).timestamp()
    )


# ─────────────────────────────────────────────────────────────────
# X_Time — LSTM Kanalı  (gözlem penceresi: H1 – H{cutoff})
# ─────────────────────────────────────────────────────────────────
def build_x_time(
    log_df:        pd.DataFrame,
    grade_hist_df: pd.DataFrame,
    cutoff_week:   Optional[int] = None,
) -> pd.DataFrame:
    """
    Son n_lookback hafta için (haftalık_tık, haftalık_not) çifti.
    Pencere: H(cutoff-n+1) … H(cutoff)  — gelecek haftalar dahil edilmez.
    Eksik hafta → forward-fill; ilk hafta eksikse 50.
    """
    n        = CFG.general.n_lookback
    cutoff   = _cutoff_ts(cutoff_week)
    max_week = _resolve_cutoff(cutoff_week)
    uids     = _uids()

    # Gözlem penceresine kısıtla
    log_past = log_df[log_df["timecreated"] < cutoff]

    weekly_clicks = (
        log_past[log_past["action"] == "view"]
        .groupby(["userid", "_week"])
        .size()
        .reset_index(name="clicks")
    )

    if "_week" not in grade_hist_df.columns:
        from engine_pkg.schedule import TimeCalc
        _BASE_TS = int(TimeCalc.week_start(1).timestamp())
        grade_hist_df = grade_hist_df.copy()
        grade_hist_df["_week"] = (
            (grade_hist_df["timemodified"] - _BASE_TS) // (7 * 86_400) + 1
        ).clip(lower=1)

    # Sadece gözlem penceresi
    grade_hist_past = grade_hist_df[
        grade_hist_df["timemodified"] < cutoff
    ][["userid", "_week", "finalgrade"]].copy()

    records = []
    for uid in uids:
        u_cl = weekly_clicks[weekly_clicks["userid"] == uid].groupby("_week")["clicks"].sum()
        u_gr = grade_hist_past[grade_hist_past["userid"] == uid].groupby("_week")["finalgrade"].mean()

        row        = {"userid": uid}
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
# X_Static — Dense Kanalı  (H1 – H{cutoff} snapshot)
# ─────────────────────────────────────────────────────────────────
def build_x_static(
    log_df:          pd.DataFrame,
    grade_df:        pd.DataFrame,
    assign_df:       pd.DataFrame,
    assign_sub_df:   pd.DataFrame,
    quiz_att_df:     pd.DataFrame,
    completion_df:   pd.DataFrame,
    course_mod_df:   pd.DataFrame,
    cutoff_week:     Optional[int] = None,
) -> pd.DataFrame:
    """
    6 boyutlu statik vektör (sadece gözlem penceresi H1-H{cutoff}):
    [login_7d, delay_hours, obs_avg_grade, quiz_effort_min, completion_ratio,
     current_week]

    current_week: model hangi hafta kesitinde olduğunu bilir → data drift önlenir.
    Temporal cutoff: tüm kaynak tablolar cutoff timestamp'ten önce filtrelenir.
    Eksik veri stratejisi (segment uyumlu):
      - Not yok        → 50.0
      - Ödev teslim yok → 48.0 saat
      - Quiz yok       → 3.0 dk
      - Tamamlama yok  → 0.0
    """
    uids         = _uids()
    n_modules    = len(course_mod_df)
    cutoff       = _cutoff_ts(cutoff_week)
    effective_cw = _resolve_cutoff(cutoff_week)

    # ── Gözlem penceresine kısıtla ────────────────────────────────
    log_past        = log_df[log_df["timecreated"] < cutoff]
    grade_past      = grade_df[grade_df["timemodified"] < cutoff]
    assign_sub_past = assign_sub_df[assign_sub_df["timemodified"] < cutoff]
    quiz_past       = quiz_att_df[quiz_att_df["timefinish"] < cutoff]
    comp_past       = completion_df[completion_df["timemodified"] < cutoff]

    # Son 7 gün (cutoff öncesinde)
    recent   = log_past[
        (log_past["timecreated"] >= cutoff - 7 * 86_400)
        & (log_past["action"] == "view")
    ]
    login_7d = recent.groupby("userid").size().reindex(uids, fill_value=0)

    # Ödev teslim gecikmesi (H1-H{cutoff})
    delay = assign_sub_past.groupby("userid")["delay_hours"].mean().reindex(
        uids, fill_value=48.0
    )

    # Gözlem dönemi not ortalaması
    obs_grade = grade_past.groupby("userid")["finalgrade"].mean().reindex(
        uids, fill_value=50.0
    )

    # Quiz süresi (H1-H{cutoff})
    quiz_eff = quiz_past.groupby("userid")["duration_minutes"].mean().reindex(
        uids, fill_value=3.0
    )

    # Tamamlama oranı (H1-H{cutoff})
    completed  = comp_past.groupby("userid").size().reindex(uids, fill_value=0)
    comp_ratio = (completed / max(n_modules, 1)).clip(0, 1)

    return pd.DataFrame({
        "userid":           uids,
        "login_count_7d":   login_7d.values.astype(np.float32),
        "delay_score":      delay.values.astype(np.float32),
        "obs_avg_grade":    obs_grade.values.astype(np.float32),
        "quiz_effort_min":  quiz_eff.values.astype(np.float32),
        "completion_ratio": comp_ratio.values.astype(np.float32),
        "current_week":     np.full(len(uids), effective_cw, dtype=np.float32),
    })


# ─────────────────────────────────────────────────────────────────
# ÇIKTILAR — Leakage-free, Multi-Cutoff Tutarlı
# ─────────────────────────────────────────────────────────────────
def build_mimo_targets(
    grade_df:      pd.DataFrame,
    assign_sub_df: pd.DataFrame,
    completion_df: pd.DataFrame,
    quiz_att_df:   pd.DataFrame,
    course_mod_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Sızıntısız hedef değişkenler — FUTURE_CUTOFF_WEEK'e sabitlenmiş
    (observation cutoff'tan bağımsız → multi-cutoff eğitimde tutarlı etiket).

    y_risk  — segment + dropout_week bazlı ground truth (0-1)
              S1→~0.12  S2→~0.42  S3→~0.68  S4→~0.85
              dropout_week ≤ FUTURE_CUTOFF_WEEK → ~0.93 (çok yüksek risk)

    y_grade — H{FUTURE_CUTOFF_WEEK+1}+ final notu (gerçek gelecek notu, varsa)
              Yoksa segment bazlı stokastik projeksiyon:
              S1→N(87,6)  S2→N(68,9)  S3→N(50,12)  S4→N(33,15)

    y_segment — Segment indeksi: S1=0, S2=1, S3=2, S4=3
    """
    uids         = _uids()
    rng          = np.random.default_rng(CFG.general.seed + 7)
    label_cutoff = _label_cutoff_ts()

    # H{FUTURE_CUTOFF_WEEK+1}+ final notları (gerçek hedef)
    future_grades = grade_df[grade_df["timemodified"] >= label_cutoff]
    fg_max = (
        future_grades.groupby("userid")["finalgrade"].max()
        if not future_grades.empty else pd.Series(dtype=float)
    )

    RISK_PARAMS: Dict[str, tuple] = {
        "S1": (0.12, 0.05),
        "S2": (0.42, 0.08),
        "S3": (0.68, 0.08),
        "S4": (0.85, 0.06),
    }
    GRADE_PARAMS: Dict[str, tuple] = {
        "S1": (87.0,  6.0, 70.0, 100.0),
        "S2": (68.0,  9.0, 45.0,  85.0),
        "S3": (50.0, 12.0, 20.0,  68.0),
        "S4": (33.0, 15.0,  5.0,  55.0),
    }

    reg          = STUDENT_REGISTRY.set_index("userid")
    y_risk_vals  = np.empty(len(uids), dtype=np.float32)
    y_grade_vals = np.empty(len(uids), dtype=np.float32)
    y_seg_vals   = np.empty(len(uids), dtype=np.int32)

    for i, uid in enumerate(uids):
        seg = reg.at[uid, "segment"]
        dw  = reg.at[uid, "dropout_week"]

        # y_risk: segment + early-dropout boost
        rm, rs = RISK_PARAMS[seg]
        risk = float(np.clip(rng.normal(rm, rs), 0.01, 0.99))
        if dw is not None and dw <= FUTURE_CUTOFF_WEEK:
            risk = float(np.clip(rng.normal(0.93, 0.03), 0.85, 1.0))
        y_risk_vals[i] = risk

        # y_grade: H{FUTURE_CUTOFF_WEEK+1}+ gerçek not → segment projeksiyonu
        if uid in fg_max.index and not pd.isna(fg_max[uid]):
            y_grade_vals[i] = float(np.clip(fg_max[uid], 0.0, 100.0))
        else:
            gm, gs, gl, gh = GRADE_PARAMS[seg]
            if dw is not None and dw <= FUTURE_CUTOFF_WEEK:
                y_grade_vals[i] = float(np.clip(rng.normal(12.0, 8.0), 0.0, 25.0))
            else:
                y_grade_vals[i] = float(np.clip(rng.normal(gm, gs), gl, gh))

        # y_segment: S1=0 … S4=3
        y_seg_vals[i] = _SEG_IDX.get(seg, 0)

    return pd.DataFrame({
        "userid":                            uids,
        CFG.mimo_target.risk_score_col:      np.round(y_risk_vals,  4).astype(np.float32),
        CFG.mimo_target.predicted_grade_col: np.round(y_grade_vals, 2).astype(np.float32),
        "y_segment":                         y_seg_vals,
    })


# ─────────────────────────────────────────────────────────────────
# ANA BORU HATTI
# ─────────────────────────────────────────────────────────────────
def build_mimo_dataset(
    tables:      Dict[str, pd.DataFrame],
    cutoff_week: Optional[int] = None,
) -> Dict[str, Any]:
    """
    cutoff_week: gözlem penceresi hafta sayısı (varsayılan: FUTURE_CUTOFF_WEEK).
    Etiketler (y_risk, y_grade, y_segment) HER ZAMAN FUTURE_CUTOFF_WEEK=10
    kullanılır — tutarlı multi-cutoff eğitim için.
    """
    effective_cw = _resolve_cutoff(cutoff_week)
    print(f"\n[MIMO] Ozellik muhendisligi basliyor... (cutoff=H{effective_cw})")
    print(f"   Gözlem penceresi: H1–H{effective_cw}  |  "
          f"Hedef: H{min(CFG.general.n_weeks, FUTURE_CUTOFF_WEEK)+1}+ veya segment proj.")

    x_time_df = build_x_time(
        tables["mdl_logstore_standard_log"],
        tables["mdl_grade_grades_history"],
        cutoff_week=cutoff_week,
    )
    x_static_df = build_x_static(
        tables["mdl_logstore_standard_log"],
        tables["mdl_grade_grades"],
        tables["mdl_assign"],
        tables["mdl_assign_submission"],
        tables["mdl_quiz_attempts"],
        tables["mdl_course_modules_completion"],
        tables["mdl_course_modules"],
        cutoff_week=cutoff_week,
    )
    targets_df = build_mimo_targets(
        tables["mdl_grade_grades"],
        tables["mdl_assign_submission"],
        tables["mdl_course_modules_completion"],
        tables["mdl_quiz_attempts"],
        tables["mdl_course_modules"],
    )

    x_time_3d   = reshape_x_time_3d(x_time_df)
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
        "y_segment":   targets_df["y_segment"].values,
    }
