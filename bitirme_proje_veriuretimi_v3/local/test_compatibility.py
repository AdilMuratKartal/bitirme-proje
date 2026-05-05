"""
test_compatibility.py — GPU Eğitim ↔ CPU Inference Uyumluluk Testi
====================================================================
KULLANIM:
  GPU ortamında (eğitim + kaydetme):
    .venv_gpu\\Scripts\\python.exe test_compatibility.py --mode train

  CPU ortamında (yükleme + inference):
    .venv_cpu\\Scripts\\python.exe test_compatibility.py --mode infer

Her iki mod da saved_models/ klasörünü kullanır.
Klasörü her iki ortamdan da erişilebilir tutmak yeterlidir.
"""

import os
import sys
import argparse
import numpy as np

# ── Sabitler ──────────────────────────────────────────────────────
ROOT             = os.path.dirname(os.path.abspath(__file__))
SAVED_DIR        = os.path.join(ROOT, "saved_models")
MODEL_PATH       = os.path.join(SAVED_DIR, "dummy_model.keras")
SCALER_PATH      = os.path.join(SAVED_DIR, "dummy_scaler.pkl")

# Dummy veri boyutları
N_SAMPLES   = 200
N_LOOKBACK  = 5
N_FEATURES  = 3
N_STATIC    = 4
N_CLASSES   = 4

SEPARATOR = "=" * 62


def _header(title: str) -> None:
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)


def _check_versions() -> None:
    """Ortam bilgilerini ekrana yazar."""
    import tensorflow as tf
    import sklearn
    import pandas as pd

    print(f"\n  Python     : {sys.version.split()[0]}")
    print(f"  TensorFlow : {tf.__version__}")
    print(f"  Keras      : {tf.keras.__version__}")
    print(f"  NumPy      : {np.__version__}")
    print(f"  Pandas     : {pd.__version__}")
    print(f"  sklearn    : {sklearn.__version__}")

    gpus = tf.config.list_physical_devices("GPU")
    cpus = tf.config.list_physical_devices("CPU")
    print(f"  GPU cihaz  : {gpus if gpus else 'YOK (CPU modu)'}")
    print(f"  CPU cihaz  : {cpus}")


# =================================================================
# TRAIN MODU — GPU ortamında çalıştırılır
# =================================================================
def run_train() -> None:
    _header("MOD: TRAIN  |  GPU ortamı simülasyonu")
    _check_versions()

    import tensorflow as tf
    import joblib
    from sklearn.preprocessing import StandardScaler
    from tensorflow.keras import Input, Model
    from tensorflow.keras.layers import LSTM, Dense, Concatenate, Dropout

    # GPU bellek büyüme modunu aktifleştir (GTX 1650 için zorunlu)
    gpus = tf.config.list_physical_devices("GPU")
    if gpus:
        tf.config.experimental.set_memory_growth(gpus[0], True)
        print(f"\n  [GPU] Bellek büyüme modu aktif: {gpus[0].name}")
    else:
        print("\n  [UYARI] GPU bulunamadı — CPU üzerinde eğitim yapılacak.")
        print("          CUDA 11.2 + cuDNN 8.1 kurulu olmayabilir.")

    os.makedirs(SAVED_DIR, exist_ok=True)

    # ── Dummy veri üret ───────────────────────────────────────────
    print("\n  [1/5] Dummy veri üretiliyor...")
    np.random.seed(42)
    X_seq    = np.random.rand(N_SAMPLES, N_LOOKBACK, N_FEATURES).astype(np.float32)
    X_static = np.random.rand(N_SAMPLES, N_STATIC).astype(np.float32)
    y_seg    = np.random.randint(0, N_CLASSES, size=(N_SAMPLES,)).astype(np.int32)

    print(f"     X_seq    : {X_seq.shape}  dtype={X_seq.dtype}")
    print(f"     X_static : {X_static.shape}  dtype={X_static.dtype}")
    print(f"     y_seg    : {y_seg.shape}  dtype={y_seg.dtype}")

    # ── Scaler fit + kaydet ───────────────────────────────────────
    print("\n  [2/5] StandardScaler eğitiliyor ve .pkl olarak kaydediliyor...")
    scaler = StandardScaler()
    X_static_norm = scaler.fit_transform(X_static).astype(np.float32)

    joblib.dump(scaler, SCALER_PATH)
    print(f"     Kaydedildi: {SCALER_PATH}")
    print(f"     scaler.mean_ dtype : {scaler.mean_.dtype}")
    print(f"     scaler.scale_ dtype: {scaler.scale_.dtype}")

    # ── Model mimarisi ────────────────────────────────────────────
    print("\n  [3/5] Keras modeli inşa ediliyor...")
    inp_seq    = Input(shape=(N_LOOKBACK, N_FEATURES), name="X_Sequence")
    inp_static = Input(shape=(N_STATIC,),              name="X_Static")

    x_s = LSTM(16, name="lstm_seq")(inp_seq)
    x_s = Dropout(0.1)(x_s)
    x_d = Dense(8, activation="relu", name="dense_static")(inp_static)

    merged  = Concatenate(name="merge")([x_s, x_d])
    hidden  = Dense(16, activation="relu", name="hidden")(merged)
    out_seg = Dense(N_CLASSES, activation="softmax", name="y_segment")(hidden)

    model = Model(inputs=[inp_seq, inp_static], outputs=out_seg, name="dummy_model")
    model.compile(
        optimizer="adam",
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    model.summary(print_fn=lambda x: print("     " + x))

    # ── Eğitim ───────────────────────────────────────────────────
    print("\n  [4/5] Model eğitiliyor (5 epoch, sadece uyumluluk için)...")
    history = model.fit(
        [X_seq, X_static_norm], y_seg,
        epochs=5,
        batch_size=32,
        validation_split=0.15,
        verbose=1,
    )
    final_acc  = history.history["accuracy"][-1]
    final_loss = history.history["loss"][-1]
    print(f"\n     Son epoch — loss: {final_loss:.4f}  acc: {final_acc:.4f}")

    # ── Modeli kaydet ─────────────────────────────────────────────
    print(f"\n  [5/5] Model .keras olarak kaydediliyor...")
    model.save(MODEL_PATH)
    size_kb = os.path.getsize(MODEL_PATH) / 1024
    print(f"     Kaydedildi: {MODEL_PATH}  ({size_kb:.1f} KB)")

    print(f"\n  TRAIN MODU TAMAMLANDI.")
    print(f"  Şimdi CPU ortamında şunu çalıştır:")
    print(f"  .venv_cpu\\Scripts\\python.exe test_compatibility.py --mode infer")


# =================================================================
# INFER MODU — CPU ortamında çalıştırılır
# =================================================================
def run_infer() -> None:
    _header("MOD: INFER  |  CPU ortamı simülasyonu (Render prod)")
    _check_versions()

    import tensorflow as tf
    import joblib

    # ── Dosya varlık kontrolü ─────────────────────────────────────
    print("\n  [1/5] Artifacat dosyaları kontrol ediliyor...")
    missing = []
    for path, name in [(MODEL_PATH, "dummy_model.keras"), (SCALER_PATH, "dummy_scaler.pkl")]:
        if os.path.exists(path):
            size_kb = os.path.getsize(path) / 1024
            print(f"     [OK]  {name}  ({size_kb:.1f} KB)")
        else:
            print(f"     [!!]  {name}  -- BULUNAMADI")
            missing.append(name)

    if missing:
        print("\n  [HATA] Eksik dosya var. Önce GPU ortamında --mode train çalıştır.")
        sys.exit(1)

    # ── Scaler yükle ──────────────────────────────────────────────
    print("\n  [2/5] Scaler (.pkl) yükleniyor...")
    scaler = joblib.load(SCALER_PATH)
    print(f"     Tür           : {type(scaler).__name__}")
    print(f"     mean_ shape   : {scaler.mean_.shape}  dtype={scaler.mean_.dtype}")
    print(f"     scale_ shape  : {scaler.scale_.shape}  dtype={scaler.scale_.dtype}")
    # Pickle uyumluluk kontrolü: numpy dtype beklentisi
    assert scaler.mean_.dtype in [np.float32, np.float64], \
        f"[UYUMSUZLUK] Scaler mean_ dtype beklenmedik: {scaler.mean_.dtype}"
    print("     Pickle uyumluluk: OK")

    # ── Keras modeli yükle ────────────────────────────────────────
    print("\n  [3/5] Keras modeli (.keras) yükleniyor...")
    model = tf.keras.models.load_model(MODEL_PATH)
    print(f"     Model adı     : {model.name}")
    print(f"     Giriş katmanı : {[i.shape for i in model.inputs]}")
    print(f"     Çıkış katmanı : {[o.shape for o in model.outputs]}")

    # Keras versiyon uyumsuzluğu burada fırlatırdı —
    # TF 2.10 ↔ TF 2.10 aynı sürüm olduğundan bu kontrolden geçer.
    print("     Keras versiyon uyumluluk: OK")

    # ── Dummy inference verisi ────────────────────────────────────
    print("\n  [4/5] Dummy inference verisi hazırlanıyor...")
    np.random.seed(99)
    X_seq_new    = np.random.rand(10, N_LOOKBACK, N_FEATURES).astype(np.float32)
    X_static_new = np.random.rand(10, N_STATIC).astype(np.float32)

    # Scaler ile normalize et (train ile aynı dönüşüm)
    X_static_norm = scaler.transform(X_static_new).astype(np.float32)

    print(f"     X_seq_new    : {X_seq_new.shape}")
    print(f"     X_static_norm: {X_static_norm.shape}")

    # ── Tahmin ───────────────────────────────────────────────────
    print("\n  [5/5] model.predict() çalıştırılıyor...")
    preds = model.predict([X_seq_new, X_static_norm], verbose=0)

    print(f"     Çıktı shape   : {preds.shape}")
    print(f"     Çıktı dtype   : {preds.dtype}")
    pred_classes = np.argmax(preds, axis=1)

    for i, (cls, probs) in enumerate(zip(pred_classes, preds)):
        bar = "".join(["█" * int(p * 20) for p in probs])
        print(f"     Örnek {i+1:2d} → Segment S{cls+1}  [{bar:<20s}]  "
              f"güven={probs[cls]:.2f}")

    # ── Tensor shape uyumluluk kontrolü ──────────────────────────
    assert preds.shape == (10, N_CLASSES), \
        f"[UYUMSUZLUK] Beklenen (10,{N_CLASSES}), gelen {preds.shape}"
    assert preds.dtype == np.float32, \
        f"[UYUMSUZLUK] Beklenen float32, gelen {preds.dtype}"

    print(f"\n  Tensor shape uyumluluk : OK  {preds.shape}")
    print(f"  Pickle uyumluluk       : OK")
    print(f"  Keras versiyon         : OK  (TF {tf.__version__})")

    print(f"\n  INFER MODU TAMAMLANDI.")
    print(f"  Sonuç: GPU'da eğitilen .keras modeli CPU ortamında")
    print(f"         sorunsuz yüklendi ve tahmin üretti.")


# =================================================================
# Ana giriş noktası
# =================================================================
def main() -> None:
    parser = argparse.ArgumentParser(
        description="GPU eğitim ↔ CPU inference uyumluluk testi"
    )
    parser.add_argument(
        "--mode",
        choices=["train", "infer"],
        required=True,
        help="train: GPU ortamında eğit+kaydet | infer: CPU ortamında yükle+tahmin yap",
    )
    args = parser.parse_args()

    if args.mode == "train":
        run_train()
    else:
        run_infer()


if __name__ == "__main__":
    main()
