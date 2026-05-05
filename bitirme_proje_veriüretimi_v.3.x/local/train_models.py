"""
local/train_models.py — Derin Öğrenme Eğitim ve Kaydetme Merkezi
=================================================================
SADECE lokal ortamda çalıştırılır. Render.com'a GİTMEZ.

Mimari:
  MIMO  (Model 1 & 2) : LSTM(32) + Dense(16) → y_risk | y_grade | y_segment
  HKAR  (Model 3 & 4) : LSTM(16) + Dense(16) → y_segment

Çalıştırma:
    cd bitirme_proje_veriuretimi_v.3.x
    python local/train_models.py

Çıktı klasörleri:
  saved_models/mimo_model.keras   ← Keras modeli
  saved_models/hkar_model.keras   ← Keras modeli
  saved_models/mimo_meta.pkl      ← Scaler + eşik değerleri
  saved_models/hkar_meta.pkl      ← Konu/durum indeks haritaları
  outputs/mimo_predictions.csv    ← Örnek MIMO tahmin çıktısı
  outputs/hkar_predictions.csv    ← Örnek HKAR tahmin çıktısı
  outputs/mimo_history.json       ← MIMO eğitim geçmişi
  outputs/hkar_history.json       ← HKAR eğitim geçmişi
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
sys.path.insert(0, ROOT)   # render_backend, local paketi için
sys.path.insert(0, LOCAL)  # config, engine, feature_mimo vb. düz import için

# TensorFlow / Keras
import tensorflow as tf
from tensorflow.keras import Input, Model
from tensorflow.keras.layers import (
    LSTM, Dense, Concatenate, Dropout, BatchNormalization
)
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from sklearn.preprocessing import StandardScaler

from config import CFG, COMPONENT_TYPE_MAP
from engine import SimulationEngine
from feature_mimo import build_mimo_dataset
from feature_hkar import build_hkar_dataset
from student_registry import STUDENT_REGISTRY
from datafile_generator.csv.csv_data_generator import save_tables, load_tables

# ── Yol sabitleri ─────────────────────────────────────────────────
SAVED_MODELS_DIR     = os.path.join(ROOT, "saved_models")
OUTPUTS_DIR          = os.path.join(ROOT, "outputs", "train")
MIMO_MODEL_PATH      = os.path.join(SAVED_MODELS_DIR, "mimo_model.keras")
HKAR_MODEL_PATH      = os.path.join(SAVED_MODELS_DIR, "hkar_model.keras")
MIMO_META_PATH       = os.path.join(SAVED_MODELS_DIR, "mimo_meta.pkl")
HKAR_META_PATH       = os.path.join(SAVED_MODELS_DIR, "hkar_meta.pkl")
MIMO_HISTORY_PATH    = os.path.join(OUTPUTS_DIR, "mimo_history.json")
HKAR_HISTORY_PATH    = os.path.join(OUTPUTS_DIR, "hkar_history.json")
MIMO_PRED_PATH       = os.path.join(OUTPUTS_DIR, "mimo_predictions.csv")
HKAR_PRED_PATH       = os.path.join(OUTPUTS_DIR, "hkar_predictions.csv")
MIMO_PRED_JSON_PATH  = os.path.join(OUTPUTS_DIR, "mimo_predictions.json")
HKAR_PRED_JSON_PATH  = os.path.join(OUTPUTS_DIR, "hkar_predictions.json")

# Segment: string → indeks
_SEG_MAP = {"S1": 0, "S2": 1, "S3": 2, "S4": 3}

# Eğitim ayarları
EPOCHS      = 40
BATCH_SIZE  = 32
VAL_SPLIT   = 0.15
RANDOM_SEED = 42

tf.random.set_seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)


# =================================================================
# Yardımcı: klasör oluşturma
# =================================================================
def _ensure_dirs() -> None:
    os.makedirs(SAVED_MODELS_DIR, exist_ok=True)
    os.makedirs(OUTPUTS_DIR, exist_ok=True)


# =================================================================
# Yardımcı: interaktif yeniden eğitim sorusu
# =================================================================
def _ask_retrain(model_name: str, path: str) -> bool:
    """Model dosyası varsa kullanıcıya sorar, yoksa direkt True döner."""
    if not os.path.exists(path):
        print(f"[{model_name}] Model bulunamadı, sıfırdan eğitilecek.")
        return True
    ans = input(
        f"\n[{model_name}] Mevcut model: {path}\n"
        f"  Yeniden eğitilsin mi? (E/H): "
    ).strip().upper()
    return ans == "E"


# =================================================================
# Yardımcı: eğitim geçmişini JSON olarak kaydet
# =================================================================
def _save_history(history: tf.keras.callbacks.History, path: str, name: str) -> None:
    hist_dict = {k: [float(v) for v in vals] for k, vals in history.history.items()}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(hist_dict, f, indent=2, ensure_ascii=False)
    print(f"  [{name}] Eğitim geçmişi kaydedildi: {path}")


# =================================================================
# Yardımcı: metrikleri terminale yazdır
# =================================================================
def _print_metrics(history: tf.keras.callbacks.History, name: str) -> None:
    h = history.history
    epoch = len(h.get("loss", []))
    print(f"\n  ── {name} EĞİTİM METRİKLERİ (Son Epoch: {epoch}) ──")
    for key in sorted(h.keys()):
        vals = h[key]
        print(f"    {key:<40s}: son={vals[-1]:.4f}  en iyi={min(vals) if 'loss' in key else max(vals):.4f}")


# =================================================================
# MIMO MODELİ — Keras Mimarisi
# =================================================================
def _build_mimo_model(n_lookback: int, n_time_feat: int = 2,
                      n_static_feat: int = 5) -> Model:
    """
    İki girdi dalı:
      - X_Time   : (n_lookback, n_time_feat) → LSTM(32)
      - X_Static : (n_static_feat,)          → Dense(16)
    Üç çıktı: y_risk (sigmoid), y_grade (linear), y_segment (softmax-4)
    """
    # Zaman serisi dalı — LSTM
    inp_time = Input(shape=(n_lookback, n_time_feat), name="X_Time")
    x_t = LSTM(32, return_sequences=False, name="lstm_time")(inp_time)
    x_t = Dropout(0.2)(x_t)

    # Statik özellik dalı — Dense
    inp_static = Input(shape=(n_static_feat,), name="X_Static")
    x_s = Dense(16, activation="relu", name="dense_static")(inp_static)
    x_s = BatchNormalization()(x_s)

    # Birleştirme
    merged = Concatenate(name="merge")([x_t, x_s])
    shared = Dense(32, activation="relu", name="shared")(merged)
    shared = Dropout(0.2)(shared)

    # Çıktı 1: Risk skoru (0–1)
    out_risk = Dense(1, activation="sigmoid", name="y_risk")(shared)

    # Çıktı 2: Tahmin notu (0–100, lineer)
    out_grade = Dense(1, activation="linear", name="y_grade")(shared)

    # Çıktı 3: Segment sınıfı (S1–S4, softmax)
    out_seg = Dense(4, activation="softmax", name="y_segment")(shared)

    model = Model(
        inputs=[inp_time, inp_static],
        outputs=[out_risk, out_grade, out_seg],
        name="mimo_model",
    )
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss={
            "y_risk":    "binary_crossentropy",
            "y_grade":   "mse",
            "y_segment": "sparse_categorical_crossentropy",
        },
        loss_weights={"y_risk": 1.0, "y_grade": 0.01, "y_segment": 1.0},
        metrics={
            "y_risk":    ["mae"],
            "y_grade":   ["mae"],
            "y_segment": ["accuracy"],
        },
    )
    return model


# =================================================================
# MIMO — Eğitim
# =================================================================
def train_mimo(mimo_ds: dict) -> dict:
    """
    mimo_ds: build_mimo_dataset() çıktısı.
    Döner: scaler metadata dict  →  saved_models/mimo_meta.pkl
    """
    print("\n  [MIMO] Veriler hazırlanıyor...")

    X_time   = mimo_ds["X_Time"].astype(np.float32)    # (N, lookback, 2)
    X_static = mimo_ds["X_Static"].astype(np.float32)  # (N, 6) — current_week dahil
    y_risk   = mimo_ds["y_risk"].astype(np.float32)    # (N,)
    y_grade  = mimo_ds["y_grade"].astype(np.float32)   # (N,)
    y_seg    = mimo_ds["y_segment"].astype(np.int32)   # (N,) — feature_mimo'dan

    N = X_time.shape[0]
    print(f"  [MIMO] Toplam örnek: {N}  |  X_Time: {X_time.shape}  |  X_Static: {X_static.shape}")

    # StandardScaler — sadece X_Static üzerinde
    scaler = StandardScaler()
    X_static_norm = scaler.fit_transform(X_static).astype(np.float32)

    # y_grade'i 0–1 aralığına normalize et (lineer çıktı için)
    grade_min, grade_max = float(y_grade.min()), float(y_grade.max())
    y_grade_norm = ((y_grade - grade_min) / (grade_max - grade_min + 1e-8)).astype(np.float32)

    # Train / validation ayrımı
    split = int(N * (1 - VAL_SPLIT))
    idx   = np.random.permutation(N)
    tr, vl = idx[:split], idx[split:]

    train_data = (
        [X_time[tr], X_static_norm[tr]],
        {"y_risk": y_risk[tr], "y_grade": y_grade_norm[tr], "y_segment": y_seg[tr]},
    )
    val_data = (
        [X_time[vl], X_static_norm[vl]],
        {"y_risk": y_risk[vl], "y_grade": y_grade_norm[vl], "y_segment": y_seg[vl]},
    )

    # Model inşa et
    n_lookback  = X_time.shape[1]
    n_time_feat = X_time.shape[2]
    model = _build_mimo_model(n_lookback, n_time_feat, X_static.shape[1])
    model.summary(print_fn=lambda x: print("    " + x))

    # Callbacks
    callbacks = [
        EarlyStopping(monitor="val_loss", patience=8, restore_best_weights=True, verbose=1),
        ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=4, verbose=1),
    ]

    print(f"\n  [MIMO] Eğitim başlıyor... ({EPOCHS} epoch, batch={BATCH_SIZE})")
    history = model.fit(
        train_data[0], train_data[1],
        validation_data=val_data,
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        callbacks=callbacks,
        verbose=1,
    )

    _print_metrics(history, "MIMO")

    # Modeli kaydet
    model.save(MIMO_MODEL_PATH)
    print(f"  [MIMO] Keras modeli kaydedildi: {MIMO_MODEL_PATH}")

    # Eğitim geçmişini kaydet
    _save_history(history, MIMO_HISTORY_PATH, "MIMO")

    # Scaler metadata
    meta = {
        "scaler_mean":  scaler.mean_.astype(np.float32),
        "scaler_scale": scaler.scale_.astype(np.float32),
        "grade_min":    grade_min,
        "grade_max":    grade_max,
        "seg_map":      _SEG_MAP,
    }
    with open(MIMO_META_PATH, "wb") as f:
        pickle.dump(meta, f, protocol=4)
    print(f"  [MIMO] Metadata kaydedildi: {MIMO_META_PATH}")

    # Örnek tahmin üret ve CSV'ye yaz
    _write_mimo_predictions(model, X_time, X_static_norm, y_risk, y_grade, y_seg,
                            grade_min, grade_max)

    return meta


# =================================================================
# MIMO — Örnek Tahminler CSV
# =================================================================
def _write_mimo_predictions(model, X_time, X_static_norm,
                             y_risk, y_grade, y_seg,
                             grade_min, grade_max) -> None:
    preds = model.predict([X_time, X_static_norm], verbose=0)
    pred_risk  = preds[0].flatten()
    pred_grade = (preds[1].flatten() * (grade_max - grade_min) + grade_min).clip(0, 100)
    pred_seg   = np.argmax(preds[2], axis=1)

    _SEG_LABEL = {0: "S1", 1: "S2", 2: "S3", 3: "S4"}
    df = pd.DataFrame({
        "true_risk":    y_risk,
        "pred_risk":    pred_risk.round(4),
        "true_grade":   y_grade,
        "pred_grade":   pred_grade.round(2),
        "true_segment": y_seg,
        "pred_segment": pred_seg,
    })
    df.to_csv(MIMO_PRED_PATH, index=False)
    print(f"  [MIMO] Tahmin CSV kaydedildi: {MIMO_PRED_PATH}")

    records = [
        {
            "student_id":     int(i),
            "true_risk":      round(float(y_risk[i]), 4),
            "pred_risk":      round(float(pred_risk[i]), 4),
            "true_grade":     round(float(y_grade[i]), 2),
            "pred_grade":     round(float(pred_grade[i]), 2),
            "true_segment":   _SEG_LABEL[int(y_seg[i])],
            "pred_segment":   _SEG_LABEL[int(pred_seg[i])],
        }
        for i in range(len(y_seg))
    ]
    with open(MIMO_PRED_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"  [MIMO] Tahmin JSON kaydedildi: {MIMO_PRED_JSON_PATH}")


# =================================================================
# HKAR MODELİ — Keras Mimarisi
# =================================================================
def _build_hkar_model(top_k: int, n_seq_feat: int = 3,
                      n_habit_feat: int = 5) -> Model:
    """
    İki girdi dalı:
      - X_Sequence : (top_k, n_seq_feat) → LSTM(16)
      - X_UserHabit: (n_habit_feat,)      → Dense(16)
    Tek çıktı: y_segment (softmax-4)
    """
    # Sıralı soru denemesi dalı — LSTM (DKT benzeri)
    inp_seq = Input(shape=(top_k, n_seq_feat), name="X_Sequence")
    x_q = LSTM(16, return_sequences=False, name="lstm_seq")(inp_seq)
    x_q = Dropout(0.2)(x_q)

    # Kullanıcı alışkanlığı dalı — Dense
    inp_habit = Input(shape=(n_habit_feat,), name="X_UserHabit")
    x_h = Dense(16, activation="relu", name="dense_habit")(inp_habit)
    x_h = BatchNormalization()(x_h)

    # Birleştirme
    merged = Concatenate(name="merge")([x_q, x_h])
    hidden = Dense(32, activation="relu", name="hidden")(merged)
    hidden = Dropout(0.2)(hidden)

    # Çıktı: Segment (S1–S4)
    out_seg = Dense(4, activation="softmax", name="y_segment")(hidden)

    model = Model(
        inputs=[inp_seq, inp_habit],
        outputs=out_seg,
        name="hkar_model",
    )
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


# =================================================================
# HKAR — Eğitim
# =================================================================
def train_hkar(hkar_ds: dict) -> dict:
    """
    hkar_ds: build_hkar_dataset() çıktısı.
    Döner: konu/durum indeks haritaları dict  →  saved_models/hkar_meta.pkl
    """
    print("\n  [HKAR] Veriler hazırlanıyor...")

    X_seq   = hkar_ds["X_Sequence"].astype(np.float32)   # (N, TOP_K, 3)
    X_habit = hkar_ds["X_UserHabit"].astype(np.float32)  # (N, 5)

    # Segment etiketleri
    y_seg = (
        STUDENT_REGISTRY["segment"]
        .map(_SEG_MAP)
        .fillna(0)
        .astype(np.int32)
        .values
    )  # (N,)

    N = X_seq.shape[0]
    print(f"  [HKAR] Toplam örnek: {N}  |  X_Sequence: {X_seq.shape}  |  X_UserHabit: {X_habit.shape}")

    # X_UserHabit standardize et
    scaler = StandardScaler()
    X_habit_norm = scaler.fit_transform(X_habit).astype(np.float32)

    # Train / validation ayrımı
    split = int(N * (1 - VAL_SPLIT))
    idx   = np.random.permutation(N)
    tr, vl = idx[:split], idx[split:]

    train_data = ([X_seq[tr], X_habit_norm[tr]], y_seg[tr])
    val_data   = ([X_seq[vl], X_habit_norm[vl]], y_seg[vl])

    # Model inşa et
    top_k      = X_seq.shape[1]
    n_seq_feat = X_seq.shape[2]
    model = _build_hkar_model(top_k, n_seq_feat, X_habit.shape[1])
    model.summary(print_fn=lambda x: print("    " + x))

    # Callbacks
    callbacks = [
        EarlyStopping(monitor="val_loss", patience=8, restore_best_weights=True, verbose=1),
        ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=4, verbose=1),
    ]

    print(f"\n  [HKAR] Eğitim başlıyor... ({EPOCHS} epoch, batch={BATCH_SIZE})")
    history = model.fit(
        train_data[0], train_data[1],
        validation_data=val_data,
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        callbacks=callbacks,
        verbose=1,
    )

    _print_metrics(history, "HKAR")

    # Modeli kaydet
    model.save(HKAR_MODEL_PATH)
    print(f"  [HKAR] Keras modeli kaydedildi: {HKAR_MODEL_PATH}")

    # Eğitim geçmişini kaydet
    _save_history(history, HKAR_HISTORY_PATH, "HKAR")

    # Konu ve durum indeks haritaları
    topic_list   = list(CFG.topics)
    topic_to_idx = {t: i for i, t in enumerate(topic_list)}
    state_to_idx = {s: i for i, s in enumerate(CFG.step_states)}

    meta = {
        "topic_list":         topic_list,
        "topic_to_idx":       topic_to_idx,
        "state_to_idx":       state_to_idx,
        "content_thresholds": dict(CFG.content_thresholds),
        "component_type_map": dict(COMPONENT_TYPE_MAP),
        "seg_map":            _SEG_MAP,
        "scaler_mean":        scaler.mean_.astype(np.float32),
        "scaler_scale":       scaler.scale_.astype(np.float32),
    }
    with open(HKAR_META_PATH, "wb") as f:
        pickle.dump(meta, f, protocol=4)
    print(f"  [HKAR] Metadata kaydedildi: {HKAR_META_PATH}")

    # Örnek tahmin üret ve CSV'ye yaz
    _write_hkar_predictions(model, X_seq, X_habit_norm, y_seg)

    return meta


# =================================================================
# HKAR — Örnek Tahminler CSV
# =================================================================
def _write_hkar_predictions(model, X_seq, X_habit_norm, y_seg) -> None:
    n_sample = len(y_seg)
    preds    = model.predict([X_seq[:n_sample], X_habit_norm[:n_sample]], verbose=0)
    pred_seg = np.argmax(preds, axis=1)

    _SEG_LABEL = {0: "S1", 1: "S2", 2: "S3", 3: "S4"}
    df = pd.DataFrame({
        "true_segment": y_seg[:n_sample],
        "pred_segment": pred_seg,
        "conf_S1": preds[:, 0].round(4),
        "conf_S2": preds[:, 1].round(4),
        "conf_S3": preds[:, 2].round(4),
        "conf_S4": preds[:, 3].round(4),
    })
    df.to_csv(HKAR_PRED_PATH, index=False)
    print(f"  [HKAR] Tahmin CSV kaydedildi: {HKAR_PRED_PATH}")

    records = [
        {
            "student_id":   int(i),
            "true_segment": _SEG_LABEL[int(y_seg[i])],
            "pred_segment": _SEG_LABEL[int(pred_seg[i])],
            "confidence":   {
                "S1": round(float(preds[i, 0]), 4),
                "S2": round(float(preds[i, 1]), 4),
                "S3": round(float(preds[i, 2]), 4),
                "S4": round(float(preds[i, 3]), 4),
            },
        }
        for i in range(n_sample)
    ]
    with open(HKAR_PRED_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"  [HKAR] Tahmin JSON kaydedildi: {HKAR_PRED_JSON_PATH}")


# =================================================================
# Ana akış
# =================================================================
def main() -> None:
    print("=" * 65)
    print("  LOCAL DERİN ÖĞRENME EĞİTİM MOTORU")
    print("  Lokal ortam — Render'a gitmez")
    print(f"  TensorFlow: {tf.__version__}")
    print("=" * 65)

    _ensure_dirs()

    # ── 1. Veri üret veya yükle ────────────────────────────────────
    _TRAIN_DATA_DIR = "output/train"
    _data_missing   = not os.path.isdir(os.path.join(_TRAIN_DATA_DIR, "raw_tables"))

    if _data_missing:
        print("[Veri] output/train/raw_tables/ bulunamadi -- simulasyon zorunlu.")
        _gen = True
    else:
        ans  = input("\nYeni egitim verisi uretilsin mi? (E/H): ").strip().upper()
        _gen = (ans == "E")

    if _gen:
        print("\n[1/4] Simulasyon baslatiliyor...")
        eng    = SimulationEngine()
        tables = eng.simulate_full_semester(weeks=CFG.general.n_weeks)
        print(f"  Uretilen tablo sayisi: {len(tables)}")
        save_tables(tables, _TRAIN_DATA_DIR)
    else:
        print("\n[1/4] Mevcut veriler yukleniyor...")
        tables = load_tables(_TRAIN_DATA_DIR)
        print(f"  {len(tables)} tablo yuklendi.")

    # ── 2. MIMO — Multi-Cutoff Eğitim ─────────────────────────────
    print("\n[2/4] MIMO özellikleri hesaplanıyor (multi-cutoff)...")
    _TRAIN_CUTOFFS = [4, 6, 8, 10, 12]
    all_x_time, all_x_static = [], []
    all_y_risk, all_y_grade, all_y_seg = [], [], []
    for cw in _TRAIN_CUTOFFS:
        ds = build_mimo_dataset(tables, cutoff_week=cw)
        all_x_time.append(ds["X_Time"])
        all_x_static.append(ds["X_Static"])
        all_y_risk.append(ds["y_risk"])
        all_y_grade.append(ds["y_grade"])
        all_y_seg.append(ds["y_segment"])
    mimo_ds = {
        "X_Time":    np.concatenate(all_x_time),
        "X_Static":  np.concatenate(all_x_static),
        "y_risk":    np.concatenate(all_y_risk),
        "y_grade":   np.concatenate(all_y_grade),
        "y_segment": np.concatenate(all_y_seg),
    }
    print(f"  X_Time   : {mimo_ds['X_Time'].shape}")
    print(f"  X_Static : {mimo_ds['X_Static'].shape}")

    if _ask_retrain("MIMO", MIMO_MODEL_PATH):
        train_mimo(mimo_ds)
    else:
        print("  [MIMO] Eğitim atlandı — mevcut model yükleniyor ve prediction üretiliyor...")
        model = tf.keras.models.load_model(MIMO_MODEL_PATH)
        with open(MIMO_META_PATH, "rb") as f:
            meta = pickle.load(f)
        scaler    = StandardScaler()
        scaler.mean_  = meta["scaler_mean"]
        scaler.scale_ = meta["scaler_scale"]
        scaler.n_features_in_ = len(meta["scaler_mean"])
        X_time        = mimo_ds["X_Time"].astype(np.float32)
        X_static_norm = scaler.transform(mimo_ds["X_Static"]).astype(np.float32)
        y_risk        = mimo_ds["y_risk"].astype(np.float32)
        y_grade       = mimo_ds["y_grade"].astype(np.float32)
        y_seg         = mimo_ds["y_segment"].astype(np.int32)
        _write_mimo_predictions(model, X_time, X_static_norm, y_risk, y_grade, y_seg,
                                meta["grade_min"], meta["grade_max"])

    # ── 3. HKAR ────────────────────────────────────────────────────
    print("\n[3/4] HKAR özellikleri hesaplanıyor...")
    hkar_ds = build_hkar_dataset(tables)
    print(f"  X_Sequence  : {hkar_ds['X_Sequence'].shape}")
    print(f"  X_UserHabit : {hkar_ds['X_UserHabit'].shape}")

    if _ask_retrain("HKAR", HKAR_MODEL_PATH):
        train_hkar(hkar_ds)
    else:
        print("  [HKAR] Eğitim atlandı — mevcut model yükleniyor ve prediction üretiliyor...")
        model = tf.keras.models.load_model(HKAR_MODEL_PATH)
        with open(HKAR_META_PATH, "rb") as f:
            meta = pickle.load(f)
        scaler    = StandardScaler()
        scaler.mean_  = meta["scaler_mean"]
        scaler.scale_ = meta["scaler_scale"]
        scaler.n_features_in_ = len(meta["scaler_mean"])
        X_seq        = hkar_ds["X_Sequence"].astype(np.float32)
        X_habit_norm = scaler.transform(hkar_ds["X_UserHabit"]).astype(np.float32)
        y_seg        = (STUDENT_REGISTRY["segment"].map(_SEG_MAP).fillna(0).astype(np.int32).values)
        _write_hkar_predictions(model, X_seq, X_habit_norm, y_seg)

    # ── 4. Özet ────────────────────────────────────────────────────
    print("\n[4/4] Eğitim tamamlandı.")
    print("\n  Kaydedilen dosyalar:")
    files = [
        MIMO_MODEL_PATH, HKAR_MODEL_PATH,
        MIMO_META_PATH,  HKAR_META_PATH,
        MIMO_HISTORY_PATH, HKAR_HISTORY_PATH,
        MIMO_PRED_PATH,  HKAR_PRED_PATH,
    ]
    for p in files:
        exists = "✓" if os.path.exists(p) else "✗"
        size   = f"({os.path.getsize(p)/1024:.1f} KB)" if os.path.exists(p) else ""
        print(f"  {exists}  {p}  {size}")

    print("\n  Sonraki adım: saved_models/ klasörünü Render'a deploy edin.")
    print("  Render ortamında sadece features/predict.py kullanın.")
    print("=" * 65)


if __name__ == "__main__":
    main()
