"""
features/predict.py — Inference / Tahmin Motoru
================================================
Render.com dahil Cloud ortamları icin tasarlanmistir.

YASAK islemler (bu dosyada hicbiri yoktur):
  - model.fit()
  - model.save()
  - SimulationEngine()
  - raw_tables import

Sadece:
  1. saved_models/ icindeki hazir .pkl dosyalarini yukler.
  2. Tek bir kullanicinin ozellikleri (X_static, X_sequence) inline hesaplanir
     (STUDENT_REGISTRY bagimliligisiz — RAM dostu).
  3. JSON-serializable dict doner.

Kullanim:
    from features.predict import predict_student_risk, predict_student_competence

    result = predict_student_risk(userid=42, tables=tables_dict)
    # {"userid": 42, "risk_score": 0.73, "predicted_grade": 61.4, "predicted_class": "S3", ...}

    result = predict_student_competence(userid=42, tables=tables_dict)
    # {"userid": 42, "topic_status": {...}, "recommendations": [...], "predicted_class": "S2"}
"""

from __future__ import annotations

import os
import pickle
import functools
import numpy as np
import pandas as pd
from typing import Dict, Any, List

# Proje kokunu bul (features/ uzerindeki dizin)
_PROJECT_ROOT    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SAVED_MODELS    = os.path.join(_PROJECT_ROOT, "saved_models")
_MIMO_MODEL_PATH = os.path.join(_SAVED_MODELS, "mimo_model.pkl")
_HKAR_MODEL_PATH = os.path.join(_SAVED_MODELS, "hkar_model.pkl")

# Segment etiketi: indeks -> string
_SEG_IDX_TO_STR = {0: "S1", 1: "S2", 2: "S3", 3: "S4"}


# =============================================================
# Yardimci: model yukleme
# =============================================================
@functools.lru_cache(maxsize=4)
def _load_pkl(path: str, model_name: str) -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"[{model_name}] Model bulunamadi: {path}\n"
            "Lütfen once 'local/train_models.py' ile lokal ortamda egitip kaydedin."
        )
    with open(path, "rb") as f:
        return pickle.load(f)


# =============================================================
# Yardimci: Tek kullanici icin X_Static (5-dim)
# Mirrors build_x_static() — STUDENT_REGISTRY gerektirmez
# =============================================================
def _x_static_single(uid: int, tables: Dict[str, pd.DataFrame]) -> np.ndarray:
    logs  = tables["mdl_logstore_standard_log"]
    grd   = tables["mdl_grade_grades"]
    asub  = tables["mdl_assign_submission"]
    qatt  = tables["mdl_quiz_attempts"]
    comp  = tables["mdl_course_modules_completion"]
    mods  = tables["mdl_course_modules"]

    max_ts   = int(logs["timecreated"].max()) if not logs.empty else 0
    login_7d = float(len(logs[
        (logs["userid"] == uid) &
        (logs["timecreated"] >= max_ts - 7 * 86_400) &
        (logs["action"] == "view")
    ]))

    u_sub    = asub[asub["userid"] == uid]
    delay    = float(u_sub["delay_hours"].mean()) if not u_sub.empty else 48.0

    u_gr     = grd[grd["userid"] == uid]
    cur_grade = float(u_gr["finalgrade"].mean()) if not u_gr.empty else 50.0

    u_q      = qatt[qatt["userid"] == uid]
    quiz_eff = float(u_q["duration_minutes"].mean()) if not u_q.empty else 3.0

    u_comp     = comp[comp["userid"] == uid]
    comp_ratio = float(np.clip(len(u_comp) / max(len(mods), 1), 0.0, 1.0))

    return np.array([login_7d, delay, cur_grade, quiz_eff, comp_ratio], dtype=np.float32)


# =============================================================
# Yardimci: Tek kullanici icin konu basari dict'i
# Mirrors analyze_performance() — STUDENT_REGISTRY gerektirmez
# =============================================================
def _topic_status_single(
    uid: int,
    tables: Dict[str, pd.DataFrame],
    topic_list: List[str],
) -> Dict[str, float]:
    qatt    = tables["mdl_quiz_attempts"]
    qa_df   = tables["mdl_question_attempts"]
    q_df    = tables["mdl_question"]
    qcat_df = tables["mdl_question_categories"]

    user_uids = qatt[qatt["userid"] == uid]["uniqueid"].tolist()
    if not user_uids:
        return {t: 0.0 for t in topic_list}

    ua = qa_df[qa_df["questionusageid"].isin(user_uids)].copy()
    if ua.empty:
        return {t: 0.0 for t in topic_list}

    ua = ua.merge(
        q_df[["id", "category"]].rename(columns={"id": "q_pk", "category": "cat_id"}),
        left_on="questionid", right_on="q_pk", how="left",
    ).drop(columns="q_pk")

    ua = ua.merge(
        qcat_df[["id", "name"]].rename(columns={"id": "qcat_id", "name": "topic_name"}),
        left_on="cat_id", right_on="qcat_id", how="left",
    ).drop(columns="qcat_id")

    ua["is_correct"] = (ua["fraction"] >= 1.0).astype(int)

    stats  = ua.groupby("topic_name")["is_correct"].agg(correct="sum", total="count")
    result = {t: 0.0 for t in topic_list}
    for topic, row in stats.iterrows():
        if topic in result:
            result[topic] = round(float(row["correct"] / max(row["total"], 1)), 3)
    return result


# =============================================================
# Yardimci: Icerik onerisi (tek kullanici)
# Mirrors recommend_content() icindeki tek-kullanici dongusu
# =============================================================
def _recommendations_single(
    uid: int,
    topic_status: Dict[str, float],
    tables: Dict[str, pd.DataFrame],
    hkar_model: dict,
) -> List[Dict[str, Any]]:
    mods          = tables["mdl_course_modules"]
    logs          = tables["mdl_logstore_standard_log"]
    thresholds    = hkar_model["content_thresholds"]
    ctype_map     = hkar_model["component_type_map"]
    content_types = ["Izleme", "Okuma", "Odev", "Forum", "Diger"]

    topic_modules = (
        mods.groupby(["topic", "content_type"])["id"]
        .apply(list).to_dict()
    ) if not mods.empty else {}

    weak_topics = sorted(topic_status, key=topic_status.get)[:3]

    log_u = logs[logs["userid"] == uid].copy()
    log_u["ctype"] = log_u["component"].map(ctype_map).fillna("Diger")
    habit = (
        log_u["ctype"].value_counts(normalize=True)
        .reindex(content_types, fill_value=0.0)
    )
    sorted_ctypes = habit.sort_values(ascending=False).index.tolist()

    recs = []
    for topic in weak_topics:
        chosen_type, chosen_mods = None, []
        sr = topic_status.get(topic, 0.0)
        for ct in sorted_ctypes:
            if sr < thresholds.get(ct, 0.5):
                mlist = topic_modules.get((topic, ct), [])
                if mlist:
                    chosen_type, chosen_mods = ct, mlist
                    break
        if not chosen_mods:
            for ct in content_types:
                mlist = topic_modules.get((topic, ct), [])
                if mlist:
                    chosen_type, chosen_mods = ct, mlist
                    break
        recs.append({
            "topic":        topic,
            "content_type": chosen_type or "Bilinmiyor",
            "module_ids":   chosen_mods[:3],
            "success_rate": sr,
        })
    return recs


# =============================================================
# PUBLIC API — Render.com bu fonksiyonlari cagirir
# =============================================================
def predict_student_risk(
    userid: int,
    tables: Dict[str, pd.DataFrame],
) -> Dict[str, Any]:
    """
    MIMO tahmini: risk skoru, tahmin notu ve segment sinifi.

    Parametreler
    ------------
    userid : Hedef ogrencinin ID'si
    tables : mdl_* tablolarini iceren dict (canli DB'den veya pipeline ciktisindan)

    Donus
    -----
    {
        "userid":          int,
        "risk_score":      float  (0.0 – 1.0, sigmoid),
        "predicted_grade": float  (0.0 – 100.0),
        "predicted_class": str    ("S1" | "S2" | "S3" | "S4"),
        "segment_probs":   dict   {S1: p, S2: p, S3: p, S4: p},
    }
    """
    mdl = _load_pkl(_MIMO_MODEL_PATH, "MIMO")

    x      = _x_static_single(userid, tables).astype(np.float64)
    x_norm = (x - mdl["scaler_mean"]) / mdl["scaler_std"]
    x_b    = np.append(x_norm, 1.0)          # bias terimi

    risk  = float(np.clip(float(x_b @ mdl["w_risk"]),  0.0, 1.0))
    grade = float(np.clip(float(x_b @ mdl["w_grade"]), 0.0, 100.0))

    # Segment tahmini — softmax
    logits = mdl["w_segment"] @ x_b          # (4,)
    e      = np.exp(logits - logits.max())
    probs  = e / e.sum()
    seg    = _SEG_IDX_TO_STR[int(np.argmax(probs))]

    return {
        "userid":          userid,
        "risk_score":      round(risk,  4),
        "predicted_grade": round(grade, 2),
        "predicted_class": seg,
        "segment_probs":   {_SEG_IDX_TO_STR[i]: round(float(p), 4) for i, p in enumerate(probs)},
    }


def predict_student_competence(
    userid: int,
    tables: Dict[str, pd.DataFrame],
) -> Dict[str, Any]:
    """
    HKAR tahmini: konu basari oranları ve icerik onerileri.

    Parametreler
    ------------
    userid : Hedef ogrencinin ID'si
    tables : mdl_* tablolarini iceren dict

    Donus
    -----
    {
        "userid":          int,
        "topic_status":    dict  {konu: basari_orani},
        "recommendations": list  [{topic, content_type, module_ids, success_rate}],
        "predicted_class": str   ("S1" | "S2" | "S3" | "S4"),
    }
    """
    hkar_mdl    = _load_pkl(_HKAR_MODEL_PATH, "HKAR")
    topic_list  = hkar_mdl["topic_list"]

    topic_status = _topic_status_single(userid, tables, topic_list)
    recs         = _recommendations_single(userid, topic_status, tables, hkar_mdl)

    # Segment tahmini — hkar_model'daki segment logistic agirliklar
    mean_sr  = float(np.mean(list(topic_status.values())) if topic_status else 0.0)
    seg_feat = np.array([mean_sr, 1.0 - mean_sr, 1.0], dtype=np.float64)
    if "w_seg_hkar" in hkar_mdl:
        logits = hkar_mdl["w_seg_hkar"] @ seg_feat
        e      = np.exp(logits - logits.max())
        probs  = e / e.sum()
        seg    = _SEG_IDX_TO_STR[int(np.argmax(probs))]
    else:
        # Fallback: kural tabanli segment
        if   mean_sr >= 0.75: seg = "S1"
        elif mean_sr >= 0.50: seg = "S2"
        elif mean_sr >= 0.25: seg = "S3"
        else:                 seg = "S4"

    return {
        "userid":          userid,
        "topic_status":    topic_status,
        "recommendations": recs,
        "predicted_class": seg,
    }
