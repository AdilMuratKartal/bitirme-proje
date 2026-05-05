"""
render_backend/features/predict.py — TFLite Inference Motoru

Sadece tflite-runtime + numpy kullanir. TensorFlow veya Keras gerektirmez.

Model dosyalari (render_backend/saved_models/):
  mimo_model.tflite  —  risk, grade, segment tahmini
  hkar_model.tflite  —  konu bazli segment siniflandirmasi
  mimo_meta.json     —  normalizasyon parametreleri
  hkar_meta.json     —  topic list, scaler, esikler

Kullanim:
    from features.predict import predict_student_risk, predict_student_competence
    result = predict_student_risk(userid=42, tables=tables_dict)
    result = predict_student_competence(userid=42, tables=tables_dict)
"""

from __future__ import annotations

import functools
import json
import os
from typing import Any, Dict, List

import numpy as np
import pandas as pd

try:
    import tflite_runtime.interpreter as tflite
    _HAS_TFLITE = True
except ImportError:
    _HAS_TFLITE = False

_PROJECT_ROOT    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SAVED_MODELS    = os.path.join(_PROJECT_ROOT, "saved_models")
_MIMO_TFLITE_PATH = os.path.join(_SAVED_MODELS, "mimo_model.tflite")
_HKAR_TFLITE_PATH = os.path.join(_SAVED_MODELS, "hkar_model.tflite")
_MIMO_META_PATH   = os.path.join(_SAVED_MODELS, "mimo_meta.json")
_HKAR_META_PATH   = os.path.join(_SAVED_MODELS, "hkar_meta.json")

_SEG_IDX_TO_STR = {0: "S1", 1: "S2", 2: "S3", 3: "S4"}


# =============================================================
# Model ve meta yukleme — lru_cache ile tek seferlik
# =============================================================

@functools.lru_cache(maxsize=4)
def _load_tflite(path: str) -> "tflite.Interpreter":
    if not _HAS_TFLITE:
        raise ImportError(
            "tflite-runtime yuklu degil.\n"
            "  pip install tflite-runtime==2.14.0"
        )
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"TFLite model bulunamadi: {path}\n"
            "  Oncelikle: .venv_gpu/Scripts/python local/convert_to_tflite.py"
        )
    interp = tflite.Interpreter(model_path=path)
    interp.allocate_tensors()
    return interp


@functools.lru_cache(maxsize=4)
def _load_meta_json(path: str) -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Meta JSON bulunamadi: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# =============================================================
# Tensor dizin tespiti — shape tabanli (isim prefix'inden bagimsiz)
# =============================================================

def _get_mimo_tensor_indices(interp: "tflite.Interpreter"):
    """
    MIMO: 2 giris (3D LSTM + 2D Dense), 3 cikis (risk, grade, segment).
    Cikis sirasi Keras Model(outputs=[risk, grade, seg]) tanimini korur.
    """
    inp = interp.get_input_details()
    time_idx   = next(d['index'] for d in inp if len(d['shape']) == 3)
    static_idx = next(d['index'] for d in inp if len(d['shape']) == 2)

    out = sorted(interp.get_output_details(), key=lambda d: d['index'])
    # [0]=y_risk(shape[-1]==1), [1]=y_grade(shape[-1]==1), [2]=y_segment(shape[-1]==4)
    risk_idx  = out[0]['index']
    grade_idx = out[1]['index']
    seg_idx   = out[2]['index']

    return time_idx, static_idx, risk_idx, grade_idx, seg_idx


def _get_hkar_tensor_indices(interp: "tflite.Interpreter"):
    """HKAR: 2 giris (3D LSTM + 2D Dense), 1 cikis (segment softmax-4)."""
    inp = interp.get_input_details()
    seq_idx   = next(d['index'] for d in inp if len(d['shape']) == 3)
    habit_idx = next(d['index'] for d in inp if len(d['shape']) == 2)
    out_idx   = interp.get_output_details()[0]['index']
    return seq_idx, habit_idx, out_idx


# =============================================================
# Ozellik hesaplama yardimcilari — tek kullanici
# =============================================================

def _x_static_single(uid: int, tables: Dict[str, pd.DataFrame]) -> np.ndarray:
    """X_Static: [login_7d, delay_hours, cur_grade, quiz_eff, comp_ratio]  shape=(5,)"""
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


def _x_time_single(uid: int, tables: Dict[str, pd.DataFrame], n_lookback: int) -> np.ndarray:
    """
    X_Time: shape=(n_lookback, 2) — [clicks_norm, grade_norm] haftalik zaman serisi.
    clicks_norm: log1p(click_count) / 5.0  (~0-1)
    grade_norm : finalgrade / 100.0
    """
    logs   = tables["mdl_logstore_standard_log"]
    grades = tables["mdl_grade_grades"]
    u_logs = logs[logs["userid"] == uid]
    u_grd  = grades[grades["userid"] == uid]

    avg_grade_norm = float(u_grd["finalgrade"].mean() / 100.0) if not u_grd.empty else 0.5

    if not u_logs.empty:
        max_ts = int(u_logs["timecreated"].max())
        week_clicks = []
        for w in range(n_lookback - 1, -1, -1):
            t0  = max_ts - (w + 1) * 7 * 86_400
            t1  = max_ts - w * 7 * 86_400
            cnt = int(((u_logs["timecreated"] >= t0) & (u_logs["timecreated"] < t1)).sum())
            week_clicks.append(float(cnt))
    else:
        week_clicks = [0.0] * n_lookback

    clicks_norm = [min(np.log1p(c) / 5.0, 1.0) for c in week_clicks]
    x = np.array(
        [[c, avg_grade_norm] for c in clicks_norm],
        dtype=np.float32,
    )
    return x  # (n_lookback, 2)


def _x_sequence_single(
    uid: int,
    tables: Dict[str, pd.DataFrame],
    topic_to_idx: dict,
    state_to_idx: dict,
    top_k: int = 10,
) -> np.ndarray:
    """
    X_Sequence: shape=(top_k, 3) — HKAR LSTM girdisi.
    [topic_idx_norm, success_rate, state_idx_norm]
    """
    qatt    = tables["mdl_quiz_attempts"]
    qa_df   = tables["mdl_question_attempts"]
    qstep   = tables["mdl_question_attempt_steps"]
    q_df    = tables["mdl_question"]
    qcat_df = tables["mdl_question_categories"]

    n_topics = max(len(topic_to_idx), 1)
    n_states = max(len(state_to_idx), 1)

    user_uids = qatt[qatt["userid"] == uid]["uniqueid"].tolist()
    if not user_uids:
        return np.zeros((top_k, 3), dtype=np.float32)

    ua = qa_df[qa_df["questionusageid"].isin(user_uids)].copy()
    if ua.empty:
        return np.zeros((top_k, 3), dtype=np.float32)

    ua = ua.merge(
        q_df[["id", "category"]].rename(columns={"id": "q_pk", "category": "cat_id"}),
        left_on="questionid", right_on="q_pk", how="left",
    ).drop(columns="q_pk")

    ua = ua.merge(
        qcat_df[["id", "name"]].rename(columns={"id": "qcat_id", "name": "topic_name"}),
        left_on="cat_id", right_on="qcat_id", how="left",
    ).drop(columns="qcat_id")

    ua["is_correct"] = (ua["fraction"] >= 1.0).astype(int)

    # Son adim durumu
    if not qstep.empty:
        last_step = (
            qstep.sort_values("sequencenumber")
            .groupby("questionattemptid")["state"]
            .last()
            .reset_index()
        )
        ua = ua.merge(last_step, left_on="id", right_on="questionattemptid", how="left")
    else:
        ua["state"] = "unknown"

    rows = []
    for _, row in ua.iterrows():
        t_idx = topic_to_idx.get(str(row.get("topic_name", "")), 0)
        s_rate = float(row["is_correct"])
        st_idx = state_to_idx.get(str(row.get("state", "")), 0)
        rows.append([t_idx / n_topics, s_rate, st_idx / n_states])

    if not rows:
        return np.zeros((top_k, 3), dtype=np.float32)

    arr = np.array(rows, dtype=np.float32)
    if len(arr) >= top_k:
        return arr[-top_k:]
    pad = np.zeros((top_k - len(arr), 3), dtype=np.float32)
    return np.vstack([pad, arr])


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


def _recommendations_single(
    uid: int,
    topic_status: Dict[str, float],
    tables: Dict[str, pd.DataFrame],
    hkar_meta: dict,
) -> List[Dict[str, Any]]:
    mods          = tables["mdl_course_modules"]
    logs          = tables["mdl_logstore_standard_log"]
    thresholds    = hkar_meta["content_thresholds"]
    ctype_map     = hkar_meta["component_type_map"]
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
# PUBLIC API
# =============================================================

def predict_student_risk(
    userid: int,
    tables: Dict[str, pd.DataFrame],
) -> Dict[str, Any]:
    """
    MIMO TFLite tahmini: risk skoru, tahmin notu ve segment sinifi.

    Donus:
        {userid, risk_score, predicted_grade, predicted_class, segment_probs}
    """
    interp = _load_tflite(_MIMO_TFLITE_PATH)
    meta   = _load_meta_json(_MIMO_META_PATH)

    # Tensor dizin tespiti — shape tabanli
    time_idx, static_idx, risk_idx, grade_idx, seg_idx = _get_mimo_tensor_indices(interp)

    # n_lookback: 3D input tensorunun ikinci boyutu
    inp = interp.get_input_details()
    n_lookback = next(d['shape'][1] for d in inp if len(d['shape']) == 3)

    # Giris verisi
    x_time   = _x_time_single(userid, tables, n_lookback)[np.newaxis]     # (1, n, 2)
    x_static = _x_static_single(userid, tables)
    x_static_norm = (
        (x_static - np.array(meta["scaler_mean"], dtype=np.float32))
        / np.array(meta["scaler_scale"], dtype=np.float32)
    )[np.newaxis]  # (1, n_feat)

    interp.set_tensor(time_idx,   x_time)
    interp.set_tensor(static_idx, x_static_norm)
    interp.invoke()

    risk    = float(interp.get_tensor(risk_idx)[0][0])
    grade_n = float(interp.get_tensor(grade_idx)[0][0])
    probs   = np.array(interp.get_tensor(seg_idx)[0], dtype=np.float64)
    # probs: model ciktisi zaten softmax — tekrar exp/sum uygulanmaz

    grade_min = float(meta.get("grade_min", 0.0))
    grade_max = float(meta.get("grade_max", 100.0))
    grade = float(np.clip(grade_n * (grade_max - grade_min) + grade_min, 0.0, 100.0))
    seg   = _SEG_IDX_TO_STR[int(np.argmax(probs))]

    return {
        "userid":          userid,
        "risk_score":      round(float(np.clip(risk, 0.0, 1.0)), 4),
        "predicted_grade": round(grade, 2),
        "predicted_class": seg,
        "segment_probs":   {_SEG_IDX_TO_STR[i]: round(float(p), 4) for i, p in enumerate(probs)},
    }


def predict_student_competence(
    userid: int,
    tables: Dict[str, pd.DataFrame],
) -> Dict[str, Any]:
    """
    HKAR TFLite tahmini: konu basari oranlari ve icerik onerileri.

    Donus:
        {userid, topic_status, recommendations, predicted_class}
    """
    interp   = _load_tflite(_HKAR_TFLITE_PATH)
    hkar_meta = _load_meta_json(_HKAR_META_PATH)

    topic_list   = hkar_meta["topic_list"]
    topic_to_idx = hkar_meta["topic_to_idx"]
    state_to_idx = hkar_meta["state_to_idx"]

    # Tensor dizin tespiti
    seq_idx, habit_idx, out_idx = _get_hkar_tensor_indices(interp)
    inp = interp.get_input_details()
    top_k = next(d['shape'][1] for d in inp if len(d['shape']) == 3)

    # Giris verisi
    x_seq   = _x_sequence_single(userid, tables, topic_to_idx, state_to_idx, top_k)[np.newaxis]
    x_habit = _x_static_single(userid, tables)
    x_habit_norm = (
        (x_habit - np.array(hkar_meta["scaler_mean"], dtype=np.float32))
        / np.array(hkar_meta["scaler_scale"], dtype=np.float32)
    )[np.newaxis]

    interp.set_tensor(seq_idx,   x_seq)
    interp.set_tensor(habit_idx, x_habit_norm)
    interp.invoke()

    probs = np.array(interp.get_tensor(out_idx)[0], dtype=np.float64)
    # probs: model ciktisi zaten softmax — tekrar exp/sum uygulanmaz
    seg   = _SEG_IDX_TO_STR[int(np.argmax(probs))]

    topic_status = _topic_status_single(userid, tables, topic_list)
    recs         = _recommendations_single(userid, topic_status, tables, hkar_meta)

    return {
        "userid":          userid,
        "topic_status":    topic_status,
        "recommendations": recs,
        "predicted_class": seg,
    }
