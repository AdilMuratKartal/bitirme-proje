"""
feature_hkar.py — HKAR Model (3 & 4) Özellik Mühendisliği  v2.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Temporal ayrım:
  X_Sequence / X_UserHabit → H1–H{FUTURE_CUTOFF_WEEK} (gözlem)
  y_segment                → STUDENT_REGISTRY.segment (sızıntısız)

ERD referansları (HKRT-MODEL-ERD):
  X_Sequence (LSTM — DKT Girdisi):
    mdl_quiz_attempts.uniqueid
      → mdl_question_attempts.questionusageid
      → mdl_question_attempts.questionid → mdl_question.id
      → mdl_question.category → mdl_question_categories.id → .name
    mdl_question_attempt_steps.questionattemptid → mdl_question_attempts.id

  X_UserHabit (Dense):
    mdl_logstore_standard_log → component → içerik tipi dağılımı

Çıktılar:
  topic_status dict          {konu: başarı_oranı}
  recommended_content list   [{topic, content_type, module_ids, success_rate}]
"""

import datetime
import numpy as np
import pandas as pd
from typing import Dict, List, Any

from config import CFG, COMPONENT_TYPE_MAP, FUTURE_CUTOFF_WEEK
import student_registry as _sr_mod


TOP_K_WRONG    = 10
N_SEQ_FEATURES = 3   # (konu_idx_norm, başarı_oranı, son_adım_state_idx_norm)


def _effective_cutoff_week() -> int:
    return min(CFG.general.n_weeks, FUTURE_CUTOFF_WEEK)


def _cutoff_ts() -> int:
    """H{effective_cutoff} bitişi Unix timestamp."""
    return int(
        (CFG.general.semester_start
         + datetime.timedelta(weeks=_effective_cutoff_week())).timestamp()
    )


# ─────────────────────────────────────────────────────────────────
# YARDIMCI: Tam zincir birleştirmesi
# ─────────────────────────────────────────────────────────────────
def _build_enriched_attempts(
    quiz_att_df:  pd.DataFrame,
    qa_df:        pd.DataFrame,
    q_df:         pd.DataFrame,
    qcat_df:      pd.DataFrame,
    qsteps_df:    pd.DataFrame,
) -> pd.DataFrame:
    """
    HKRT ERD zinciri:
      quiz_attempts.uniqueid
        → question_attempts.questionusageid   (sınav ↔ sorular)
        → question_attempts.questionid
          → question.id → question.category
            → question_categories.id → .name  (konu adı)
      question_attempt_steps.questionattemptid
        → question_attempts.id               (adım ↔ deneme)

    Ek sütunlar:
      topic_name   : konu adı
      is_correct   : fraction >= 1.0
      final_state  : o denemenin son adım state'i
    """
    qa = qa_df.copy()

    qa = qa.merge(
        q_df[["id", "category"]].rename(columns={"id": "q_pk", "category": "cat_id"}),
        left_on="questionid", right_on="q_pk", how="left"
    ).drop(columns="q_pk")

    qa = qa.merge(
        qcat_df[["id", "name"]].rename(columns={"id": "qcat_id", "name": "topic_name"}),
        left_on="cat_id", right_on="qcat_id", how="left"
    ).drop(columns="qcat_id")

    qa["is_correct"] = (qa["fraction"] >= 1.0).astype(int)

    if not qsteps_df.empty:
        last_steps = (
            qsteps_df.sort_values("timecreated")
                     .groupby("questionattemptid")["state"]
                     .last()
                     .reset_index()
                     .rename(columns={"questionattemptid": "qa_id", "state": "final_state"})
        )
        qa = qa.merge(
            last_steps, left_on="id", right_on="qa_id", how="left"
        ).drop(columns="qa_id")
    else:
        qa["final_state"] = "gradedright"

    qa["final_state"] = qa["final_state"].fillna("gradedwrong")
    return qa


# ─────────────────────────────────────────────────────────────────
# ADIM 1: analyze_performance → topics_status
# ─────────────────────────────────────────────────────────────────
def analyze_performance(enriched_df: pd.DataFrame) -> pd.DataFrame:
    """
    Öğrenci × konu başarı oranı.
    Denenmeyen konular → has_data=False, success_rate=0.0
    """
    stats = (
        enriched_df
        .groupby(["userid", "topic_name"])["is_correct"]
        .agg(correct="sum", total="count")
        .reset_index()
        .rename(columns={"topic_name": "topic"})
    )
    stats["success_rate"] = (stats["correct"] / stats["total"]).round(3)

    uids     = _sr_mod.STUDENT_REGISTRY["userid"].values
    full_idx = pd.MultiIndex.from_product([uids, CFG.topics], names=["userid", "topic"])
    stats    = (
        stats.set_index(["userid", "topic"])
             .reindex(full_idx, fill_value=np.nan)
             .reset_index()
    )
    stats["has_data"]      = stats["success_rate"].notna()
    stats["attempt_count"] = stats["total"].fillna(0).astype(int)
    stats["success_rate"]  = stats["success_rate"].fillna(0.0)
    return stats[["userid", "topic", "success_rate", "attempt_count", "has_data"]]


# ─────────────────────────────────────────────────────────────────
# ADIM 2: X_Sequence (LSTM / DKT girdisi)
# ─────────────────────────────────────────────────────────────────
def build_x_sequence(
    enriched_df:     pd.DataFrame,
    topic_status_df: pd.DataFrame,
) -> np.ndarray:
    """
    Her öğrenci için en çok yanlış yapılan TOP_K_WRONG konu.
    Shape: (n_students, TOP_K_WRONG, 3)
      [0] konu indeksi (normalize 0–1)
      [1] o konudaki başarı oranı
      [2] son adım state indeksi (normalize 0–1)
    """
    topic_to_idx = {t: i for i, t in enumerate(CFG.topics)}
    state_to_idx = {s: i for i, s in enumerate(CFG.step_states)}

    uids   = _sr_mod.STUDENT_REGISTRY["userid"].values
    tensor = np.zeros((len(uids), TOP_K_WRONG, N_SEQ_FEATURES), dtype=np.float32)

    wrong     = enriched_df[enriched_df["is_correct"] == 0]
    wrong_cnt = (
        wrong.groupby(["userid", "topic_name"])
             .size()
             .reset_index(name="wrong_count")
    )
    topic_sr   = topic_status_df.set_index(["userid", "topic"])["success_rate"]
    last_state = enriched_df.groupby(["userid", "topic_name"])["final_state"].last()

    for i, uid in enumerate(uids):
        user_wrong = (
            wrong_cnt[wrong_cnt["userid"] == uid]
            .sort_values("wrong_count", ascending=False)
            .head(TOP_K_WRONG)
        )
        for j, row in enumerate(user_wrong.itertuples()):
            t_idx = topic_to_idx.get(row.topic_name, 0)
            sr    = float(topic_sr.get((uid, row.topic_name), 0.0))
            state = last_state.get((uid, row.topic_name), "gradedwrong")
            s_idx = state_to_idx.get(state, 4)

            tensor[i, j, 0] = t_idx / max(len(CFG.topics) - 1, 1)
            tensor[i, j, 1] = sr
            tensor[i, j, 2] = s_idx / max(len(CFG.step_states) - 1, 1)

    return tensor


# ─────────────────────────────────────────────────────────────────
# ADIM 3: X_UserHabit (Dense girdisi)
# ─────────────────────────────────────────────────────────────────
def build_x_user_habit(log_df: pd.DataFrame) -> np.ndarray:
    """
    İçerik tipi kullanım oranı: [İzleme, Okuma, Ödev, Forum, Diğer]
    Shape: (N, 5)
    """
    content_types = ["İzleme", "Okuma", "Ödev", "Forum", "Diğer"]
    uids          = _sr_mod.STUDENT_REGISTRY["userid"].values

    log          = log_df.copy()
    log["ctype"] = log["component"].map(COMPONENT_TYPE_MAP).fillna("Diğer")
    counts       = (
        log.groupby(["userid", "ctype"])
           .size()
           .unstack(fill_value=0)
           .reindex(columns=content_types, fill_value=0)
    )
    counts = counts.reindex(uids, fill_value=0)
    totals = counts.sum(axis=1).replace(0, 1)
    return (counts.div(totals, axis=0)).values.astype(np.float32)


# ─────────────────────────────────────────────────────────────────
# ADIM 4: İçerik önerisi
# ─────────────────────────────────────────────────────────────────
def recommend_content(
    topic_status_df: pd.DataFrame,
    course_mod_df:   pd.DataFrame,
    user_habit:      np.ndarray,
) -> pd.DataFrame:
    content_types = ["İzleme", "Okuma", "Ödev", "Forum", "Diğer"]
    thresholds    = CFG.content_thresholds
    topic_modules = (
        course_mod_df.groupby(["topic", "content_type"])["id"]
                     .apply(list).to_dict()
    )
    uids    = _sr_mod.STUDENT_REGISTRY["userid"].values
    records = []

    for i, uid in enumerate(uids):
        user_sr     = topic_status_df[topic_status_df["userid"] == uid].set_index("topic")["success_rate"]
        weak_topics = user_sr[user_sr < 0.6].sort_values().index.tolist() or \
                      user_sr.sort_values().index[:2].tolist()
        habit_score = dict(zip(content_types, user_habit[i].tolist()))
        sorted_ctypes = sorted(habit_score, key=habit_score.get, reverse=True)

        recommendations: List[Dict] = []
        for topic in weak_topics[:3]:
            chosen_type, chosen_mods = None, []
            for ct in sorted_ctypes:
                if float(user_sr.get(topic, 0.0)) < thresholds.get(ct, 0.5):
                    mods = topic_modules.get((topic, ct), [])
                    if mods:
                        chosen_type, chosen_mods = ct, mods
                        break
            if not chosen_mods:
                for ct in content_types:
                    mods = topic_modules.get((topic, ct), [])
                    if mods:
                        chosen_type, chosen_mods = ct, mods
                        break
            recommendations.append({
                "topic":        topic,
                "content_type": chosen_type or "Bilinmiyor",
                "module_ids":   chosen_mods[:3],
                "success_rate": float(user_sr.get(topic, 0.0)),
            })

        records.append({
            "userid": uid,
            CFG.hkar_target.topic_status_col:        {t: float(v) for t, v in user_sr.items()},
            CFG.hkar_target.recommended_content_col: recommendations,
        })

    return pd.DataFrame(records)


# ─────────────────────────────────────────────────────────────────
# ANA BORU HATTI
# ─────────────────────────────────────────────────────────────────
def build_hkar_dataset(tables: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    print("\n[HKAR] Ozellik muhendisligi basliyor...")
    cutoff = _cutoff_ts()
    print(f"   Gözlem penceresi: H1–H{_effective_cutoff_week()} (cutoff_ts={cutoff})")

    # ── Gözlem penceresine kısıtla ────────────────────────────────
    quiz_att_past   = tables["mdl_quiz_attempts"][
        tables["mdl_quiz_attempts"]["timefinish"] < cutoff
    ]
    qsteps_past     = tables["mdl_question_attempt_steps"][
        tables["mdl_question_attempt_steps"]["timecreated"] < cutoff
    ]
    qa_past         = tables["mdl_question_attempts"][
        tables["mdl_question_attempts"]["timecreated"] < cutoff
    ]
    log_past        = tables["mdl_logstore_standard_log"][
        tables["mdl_logstore_standard_log"]["timecreated"] < cutoff
    ]

    # Tam zincir birleştirmesi (sadece gözlem dönemi)
    enriched = _build_enriched_attempts(
        quiz_att_past,
        qa_past,
        tables["mdl_question"],
        tables["mdl_question_categories"],
        qsteps_past,
    )
    print(f"   ✅ Zincir join tamamlandı → {len(enriched)} satır (H1-H{_effective_cutoff_week()})")
    print(f"      quiz_attempts → question_attempts → question → categories + steps")

    topic_status_df = analyze_performance(enriched)
    print(f"   ✅ analyze_performance → {len(topic_status_df)} satır")

    x_seq      = build_x_sequence(enriched, topic_status_df)
    user_habit = build_x_user_habit(log_past)
    recs_df    = recommend_content(topic_status_df, tables["mdl_course_modules"], user_habit)

    print(f"   X_Sequence shape  : {x_seq.shape}")
    print(f"   X_UserHabit shape : {user_habit.shape}")
    print(f"   Recommendations   : {len(recs_df)} öğrenci")

    return {
        "enriched_df":        enriched,
        "topic_status_df":    topic_status_df,
        "recommendations_df": recs_df,
        "X_Sequence":         x_seq,       # (N, TOP_K_WRONG, 3) — LSTM/DKT
        "X_UserHabit":        user_habit,  # (N, 5)             — Dense
    }
