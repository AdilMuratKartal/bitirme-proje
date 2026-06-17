"""
local/predict_models.py — Tahmin (Inference) Motoru
=====================================================
SADECE lokal ortamda calistirilir. Render.com'a GITMEZ.

Eğitilmiş modelleri saved_models/'den yükler, predict verisi üretir/yükler,
çıkarım yapıp outputs/predict/ altına yazar.

Çalıştırma:
    cd bitirme_proje_veriuretimi_v.3.x
    python local/predict_models.py

Gereksinim:
    Önce train_models.py çalıştırılmış olmalı (saved_models/ dolu olmalı).

Veri dizini:
    output/predict/raw_tables/   ← predict CSVleri (userid 10001-11000)

Çıktı dizini:
    outputs/predict/mimo_predictions.csv
    outputs/predict/mimo_predictions.json
    outputs/predict/hkar_predictions.csv
    outputs/predict/hkar_predictions.json
"""

from __future__ import annotations

import os
import sys
import json
import pickle
import numpy as np
import pandas as pd

# ── Proje kökü + local/ dizinini Python path'e ekle ─────────────
ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, LOCAL)

import tensorflow as tf
from sklearn.preprocessing import StandardScaler

from config.predict_config import PREDICT_CUTOFF, PREDICT_OUT_DIR, PREDICT_SEED
from feature_mimo import build_x_time, build_x_static, reshape_x_time_3d
from feature_hkar import build_hkar_dataset
from datafile_generator.csv.csv_data_generator import load_tables
from datafile_generator.predict.predict_data_generator import run_predict_simulation
from datafile_generator.predict.predict_registry import build_predict_registry

# ── Yol sabitleri ─────────────────────────────────────────────────
SAVED_MODELS_DIR  = os.path.join(ROOT, "saved_models")
OUTPUTS_PRED_DIR  = os.path.join(ROOT, "outputs", "predict")
MIMO_MODEL_PATH   = os.path.join(SAVED_MODELS_DIR, "mimo_model.keras")
HKAR_MODEL_PATH   = os.path.join(SAVED_MODELS_DIR, "hkar_model.keras")
MIMO_META_PATH    = os.path.join(SAVED_MODELS_DIR, "mimo_meta.pkl")
HKAR_META_PATH    = os.path.join(SAVED_MODELS_DIR, "hkar_meta.pkl")
MIMO_PRED_PATH    = os.path.join(OUTPUTS_PRED_DIR, "mimo_predictions.csv")
HKAR_PRED_PATH    = os.path.join(OUTPUTS_PRED_DIR, "hkar_predictions.csv")
MIMO_PRED_JSON    = os.path.join(OUTPUTS_PRED_DIR, "mimo_predictions.json")
HKAR_PRED_JSON    = os.path.join(OUTPUTS_PRED_DIR, "hkar_predictions.json")

_SEG_LABEL = {0: "S1", 1: "S2", 2: "S3", 3: "S4"}
_SEP = "=" * 65


# =================================================================
# Yardımcı: klasör oluşturma
# =================================================================
def _ensure_dirs() -> None:
    os.makedirs(SAVED_MODELS_DIR, exist_ok=True)
    os.makedirs(OUTPUTS_PRED_DIR, exist_ok=True)


# =================================================================
# Veri: üret veya yükle
# =================================================================
def _load_or_generate_tables() -> dict:
    _data_missing = not os.path.isdir(
        os.path.join(PREDICT_OUT_DIR, "raw_tables")
    )

    if _data_missing:
        print("[Veri] output/predict/raw_tables/ bulunamadi -- uretim zorunlu.")
        _gen = True
    else:
        ans  = input("\nYeni predict verisi uretilsin mi? (E/H): ").strip().upper()
        _gen = (ans == "E")

    if _gen:
        print("\n[1/3] Predict simulasyonu baslatiliyor...")
        run_predict_simulation()
        print("  Predict verisi uretildi ve kaydedildi.")
        return load_tables(PREDICT_OUT_DIR)
    else:
        print("\n[1/3] Mevcut predict verisi yukleniyor...")
        tables = load_tables(PREDICT_OUT_DIR)
        print(f"  {len(tables)} tablo yuklendi.")
        return tables


# =================================================================
# MIMO Çıkarımı
# =================================================================
def _run_mimo_inference(tables: dict) -> None:
    if not os.path.exists(MIMO_MODEL_PATH):
        print(f"\n[MIMO] Model bulunamadi: {MIMO_MODEL_PATH}")
        print("  Once train_models.py calistirin.")
        return

    print(f"\n[MIMO] Model yukleniyor: {MIMO_MODEL_PATH}")
    model = tf.keras.models.load_model(MIMO_MODEL_PATH)

    with open(MIMO_META_PATH, "rb") as f:
        meta = pickle.load(f)

    scaler = StandardScaler()
    scaler.mean_  = meta["scaler_mean"]
    scaler.scale_ = meta["scaler_scale"]
    scaler.n_features_in_ = len(meta["scaler_mean"])

    grade_min = meta["grade_min"]
    grade_max = meta["grade_max"]

    print(f"[MIMO] Ozellikler cikariliyor (cutoff=H{PREDICT_CUTOFF})...")

    import student_registry as _sr
    pred_registry = build_predict_registry(seed=PREDICT_SEED)
    original_reg  = _sr.STUDENT_REGISTRY.copy()
    _sr.set_registry(pred_registry)

    try:
        x_time_df   = build_x_time(
            tables["mdl_logstore_standard_log"],
            tables["mdl_grade_grades_history"],
            cutoff_week=PREDICT_CUTOFF,
        )
        x_static_df = build_x_static(
            tables["mdl_logstore_standard_log"],
            tables["mdl_grade_grades"],
            tables["mdl_assign"],
            tables["mdl_assign_submission"],
            tables["mdl_quiz_attempts"],
            tables["mdl_course_modules_completion"],
            tables["mdl_course_modules"],
            cutoff_week=PREDICT_CUTOFF,
        )
    finally:
        _sr.set_registry(original_reg)

    uids          = x_time_df["userid"].values
    X_time        = reshape_x_time_3d(x_time_df).astype(np.float32)
    X_static      = x_static_df.drop(columns="userid").values.astype(np.float32)
    X_static_norm = scaler.transform(X_static).astype(np.float32)

    print(f"  X_Time   : {X_time.shape}")
    print(f"  X_Static : {X_static_norm.shape}")

    print("[MIMO] Tahmin yapiliyor...")
    preds      = model.predict([X_time, X_static_norm], verbose=0)
    pred_risk  = preds[0].flatten()
    pred_grade = (preds[1].flatten() * (grade_max - grade_min) + grade_min).clip(0, 100)
    pred_seg   = np.argmax(preds[2], axis=1)

    # CSV
    df = pd.DataFrame({
        "student_id":   uids,
        "pred_risk":    pred_risk.round(4),
        "pred_grade":   pred_grade.round(2),
        "pred_segment": pred_seg,
    })
    df.to_csv(MIMO_PRED_PATH, index=False)
    print(f"  [MIMO] CSV kaydedildi: {MIMO_PRED_PATH}")

    # JSON
    records = [
        {
            "student_id":   int(uids[i]),
            "pred_risk":    round(float(pred_risk[i]), 4),
            "pred_grade":   round(float(pred_grade[i]), 2),
            "pred_segment": _SEG_LABEL[int(pred_seg[i])],
        }
        for i in range(len(uids))
    ]
    with open(MIMO_PRED_JSON, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"  [MIMO] JSON kaydedildi: {MIMO_PRED_JSON}")


# =================================================================
# HKAR Çıkarımı
# =================================================================
def _run_hkar_inference(tables: dict) -> None:
    if not os.path.exists(HKAR_MODEL_PATH):
        print(f"\n[HKAR] Model bulunamadi: {HKAR_MODEL_PATH}")
        print("  Onre train_models.py calistirin.")
        return

    print(f"\n[HKAR] Model yukleniyor: {HKAR_MODEL_PATH}")
    model = tf.keras.models.load_model(HKAR_MODEL_PATH)

    with open(HKAR_META_PATH, "rb") as f:
        meta = pickle.load(f)

    scaler = StandardScaler()
    scaler.mean_  = meta["scaler_mean"]
    scaler.scale_ = meta["scaler_scale"]
    scaler.n_features_in_ = len(meta["scaler_mean"])

    print("[HKAR] Ozellikler cikariliyor...")

    import student_registry as _sr
    pred_registry = build_predict_registry(seed=PREDICT_SEED)
    original_reg  = _sr.STUDENT_REGISTRY.copy()
    _sr.set_registry(pred_registry)

    try:
        ds   = build_hkar_dataset(tables)
        uids = _sr.STUDENT_REGISTRY["userid"].values.copy()
    finally:
        _sr.set_registry(original_reg)

    X_seq        = ds["X_Sequence"].astype(np.float32)
    X_habit_norm = scaler.transform(ds["X_UserHabit"]).astype(np.float32)

    print(f"  X_Sequence  : {X_seq.shape}")
    print(f"  X_UserHabit : {X_habit_norm.shape}")

    print("[HKAR] Tahmin yapiliyor...")
    preds    = model.predict([X_seq, X_habit_norm], verbose=0)
    pred_seg = np.argmax(preds, axis=1)

    # CSV
    n = len(X_seq)
    df = pd.DataFrame({
        "student_id":   uids[:n],
        "pred_segment": pred_seg[:n],
        "conf_S1": preds[:n, 0].round(4),
        "conf_S2": preds[:n, 1].round(4),
        "conf_S3": preds[:n, 2].round(4),
        "conf_S4": preds[:n, 3].round(4),
    })
    df.to_csv(HKAR_PRED_PATH, index=False)
    print(f"  [HKAR] CSV kaydedildi: {HKAR_PRED_PATH}")

    # JSON — öğrenci bazlı analiz verileri
    topic_status_df = ds["topic_status_df"]
    recs_df         = ds["recommendations_df"]

    topic_status_by_uid = {uid: grp for uid, grp in topic_status_df.groupby("userid")}
    recs_by_uid         = recs_df.set_index("userid")

    records = []
    for i in range(n):
        uid = int(uids[i])

        ts_grp = topic_status_by_uid.get(uid, pd.DataFrame())
        if not ts_grp.empty:
            weak_topics = (
                ts_grp[ts_grp["has_data"] & (ts_grp["success_rate"] < 0.6)]
                .sort_values("success_rate")
                [["topic", "success_rate", "attempt_count"]]
                .to_dict("records")
            )
        else:
            weak_topics = []

        recs = recs_by_uid.at[uid, "recommended_content"] if uid in recs_by_uid.index else []

        records.append({
            "student_id":   uid,
            "pred_segment": _SEG_LABEL[int(pred_seg[i])],
            "confidence": {
                "S1": round(float(preds[i, 0]), 4),
                "S2": round(float(preds[i, 1]), 4),
                "S3": round(float(preds[i, 2]), 4),
                "S4": round(float(preds[i, 3]), 4),
            },
            "analysis": {
                "weak_topics":     weak_topics,
                "recommendations": recs,
            },
        })
    with open(HKAR_PRED_JSON, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"  [HKAR] JSON kaydedildi: {HKAR_PRED_JSON}")


# =================================================================
# Ana akış
# =================================================================
def main() -> None:
    print(_SEP)
    print("  LOCAL TAHMIN (INFERENCE) MOTORU")
    print("  Lokal ortam -- Render'a gitmez")
    print(f"  TensorFlow: {tf.__version__}")
    print(_SEP)

    _ensure_dirs()

    # ── 1. Veri ──────────────────────────────────────────────────
    tables = _load_or_generate_tables()

    # ── 2. MIMO çıkarımı ─────────────────────────────────────────
    print("\n[2/3] MIMO cikarimlari...")
    _run_mimo_inference(tables)

    # ── 3. HKAR çıkarımı ─────────────────────────────────────────
    print("\n[3/3] HKAR cikarimlari...")
    _run_hkar_inference(tables)

    # ── Özet ─────────────────────────────────────────────────────
    print("\n  Tamamlandi.")
    print("\n  Kaydedilen dosyalar:")
    files = [MIMO_PRED_PATH, MIMO_PRED_JSON, HKAR_PRED_PATH, HKAR_PRED_JSON]
    for p in files:
        exists = "+" if os.path.exists(p) else "-"
        size   = f"({os.path.getsize(p)/1024:.1f} KB)" if os.path.exists(p) else ""
        print(f"  [{exists}] {p}  {size}")
    print(_SEP)


if __name__ == "__main__":
    main()
