"""
analyze_models.py — Model Analiz ve Görselleştirme Raporlayıcısı
════════════════════════════════════════════════════════════════
Bağımsız, izole betik. Mevcut hiçbir proje dosyasını import etmez.

Kullanım (MIMO Regresyon örneği):
─────────────────────────────────
    from analyze_models import run_analysis

    run_analysis(
        model_name  = "MIMO_RiskScore",
        task        = "regression",          # "regression" | "classification"
        y_true      = np.array([...]),
        y_pred      = np.array([...]),
        history     = {                      # None geçilebilir
            "loss":     [0.9, 0.7, ...],
            "val_loss": [0.95, 0.8, ...],
            "mae":      [...],
            "val_mae":  [...],
        },
        output_dir  = "model_analysis",      # varsayılan klasör
    )

Kayıtlar (model_analysis/<model_name>/):
    loss_curve.png          — Train vs Val Loss + ikincil metrik
    prediction_analysis.png — Actual vs Predicted scatter / Confusion Matrix heatmap
    metrics_report.txt      — Tüm sayısal metrikler
"""

from __future__ import annotations

import os
import textwrap
from datetime import datetime
from typing import Dict, List, Optional, Union

import matplotlib
matplotlib.use("Agg")  # GUI gerektirmez
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import seaborn as sns

from sklearn.metrics import (
    # Regresyon
    mean_squared_error,
    mean_absolute_error,
    r2_score,
    # Sınıflandırma
    confusion_matrix,
    classification_report,
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
)

# ─── Stil ayarları ────────────────────────────────────────────────
sns.set_theme(style="whitegrid", palette="muted", font_scale=1.1)
FIGSIZE_CURVE  = (12, 5)
FIGSIZE_PRED   = (8, 7)
DPI            = 150


# ═════════════════════════════════════════════════════════════════
# Yardımcı: çıktı klasörü
# ═════════════════════════════════════════════════════════════════
def _make_output_dir(base: str, model_name: str) -> str:
    safe_name = model_name.replace(" ", "_").replace("/", "-")
    path = os.path.join(base, safe_name)
    os.makedirs(path, exist_ok=True)
    return path


# ═════════════════════════════════════════════════════════════════
# 1. Öğrenme Eğrileri
# ═════════════════════════════════════════════════════════════════
def plot_learning_curves(
    history:    Dict[str, List[float]],
    output_dir: str,
    model_name: str,
) -> None:
    """
    history dict'inden loss + (varsa) ikincil metriği çizer.
    Beklenen anahtarlar: "loss", "val_loss" (zorunlu)
                         "mae" / "val_mae"  VEYA
                         "accuracy" / "val_accuracy"  (opsiyonel)
    """
    if not history or "loss" not in history:
        print(f"  [WARN] history bos ya da 'loss' anahtari yok -- loss_curve.png atlandi.")
        return

    epochs   = range(1, len(history["loss"]) + 1)
    has_val  = "val_loss" in history

    # İkincil metriği otomatik tespit et
    secondary_key     = None
    secondary_val_key = None
    for candidate in ("mae", "mse", "accuracy", "f1"):
        if candidate in history:
            secondary_key = candidate
            secondary_val_key = f"val_{candidate}" if f"val_{candidate}" in history else None
            break

    n_plots = 2 if secondary_key else 1
    fig, axes = plt.subplots(1, n_plots, figsize=(12 if n_plots == 2 else 7, 5))
    if n_plots == 1:
        axes = [axes]

    # ── Loss grafiği ──────────────────────────────────────────────
    ax = axes[0]
    ax.plot(epochs, history["loss"], label="Train Loss", linewidth=2)
    if has_val:
        ax.plot(epochs, history["val_loss"], label="Val Loss", linewidth=2, linestyle="--")
    ax.set_title(f"{model_name} - Loss Curve")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Loss")
    ax.legend()

    # Secondary metric
    if secondary_key:
        ax2 = axes[1]
        ax2.plot(epochs, history[secondary_key], label=f"Train {secondary_key.upper()}", linewidth=2)
        if secondary_val_key:
            ax2.plot(epochs, history[secondary_val_key],
                     label=f"Val {secondary_key.upper()}", linewidth=2, linestyle="--")
        ax2.set_title(f"{model_name} - {secondary_key.upper()} Curve")
        ax2.set_xlabel("Epoch")
        ax2.set_ylabel(secondary_key.upper())
        ax2.legend()

    fig.suptitle(f"Ogrenme Egrileri - {model_name}", fontsize=13, fontweight="bold")
    plt.tight_layout()
    path = os.path.join(output_dir, "loss_curve.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    if not os.path.isfile(path):
        raise RuntimeError(f"savefig sessiz basarisiz: dosya olusturulamadi -> {path}")
    print(f"  [OK] loss_curve.png  -> {path}")


# ═════════════════════════════════════════════════════════════════
# 2a. Regresyon: Metrikler + Hata Dağılımı
# ═════════════════════════════════════════════════════════════════
def _regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    mse  = mean_squared_error(y_true, y_pred)
    rmse = np.sqrt(mse)
    mae  = mean_absolute_error(y_true, y_pred)
    r2   = r2_score(y_true, y_pred)
    errors = y_pred - y_true
    return dict(mse=mse, rmse=rmse, mae=mae, r2=r2,
                error_mean=float(np.mean(errors)),
                error_std=float(np.std(errors)))


def _plot_regression(
    y_true:     np.ndarray,
    y_pred:     np.ndarray,
    output_dir: str,
    model_name: str,
) -> None:
    errors = y_pred - y_true
    fig = plt.figure(figsize=(14, 5))
    gs  = gridspec.GridSpec(1, 3, figure=fig)

    # Scatter: Actual vs Predicted
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.scatter(y_true, y_pred, alpha=0.45, edgecolors="none", s=30)
    lims = [min(y_true.min(), y_pred.min()) - 2,
            max(y_true.max(), y_pred.max()) + 2]
    ax1.plot(lims, lims, "r--", linewidth=1.5, label="Perfect Prediction")
    ax1.set_xlim(lims); ax1.set_ylim(lims)
    ax1.set_xlabel("True Value"); ax1.set_ylabel("Predicted")
    ax1.set_title("Actual vs Predicted")
    ax1.legend(fontsize=8)

    # Error histogram
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.hist(errors, bins=30, edgecolor="white", color="steelblue", alpha=0.8)
    ax2.axvline(0, color="red", linestyle="--", linewidth=1.5)
    ax2.set_xlabel("Error (Pred - True)"); ax2.set_ylabel("Frequency")
    ax2.set_title("Error Distribution")

    # Residuals vs Predicted
    ax3 = fig.add_subplot(gs[0, 2])
    ax3.scatter(y_pred, errors, alpha=0.4, edgecolors="none", s=25)
    ax3.axhline(0, color="red", linestyle="--", linewidth=1.5)
    ax3.set_xlabel("Predicted"); ax3.set_ylabel("Residual")
    ax3.set_title("Residual Plot")

    fig.suptitle(f"Tahmin Analizi - {model_name}", fontsize=13, fontweight="bold")
    plt.tight_layout()
    path = os.path.join(output_dir, "prediction_analysis.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    if not os.path.isfile(path):
        raise RuntimeError(f"savefig sessiz basarisiz: dosya olusturulamadi -> {path}")
    print(f"  [OK] prediction_analysis.png -> {path}")


# ═════════════════════════════════════════════════════════════════
# 2b. Sınıflandırma: Metrikler + Confusion Matrix
# ═════════════════════════════════════════════════════════════════
def _classification_metrics(
    y_true:        np.ndarray,
    y_pred:        np.ndarray,
    class_labels:  Optional[List[str]],
) -> dict:
    avg = "macro"
    return dict(
        accuracy  = accuracy_score(y_true, y_pred),
        f1        = f1_score(y_true, y_pred, average=avg, zero_division=0),
        precision = precision_score(y_true, y_pred, average=avg, zero_division=0),
        recall    = recall_score(y_true, y_pred, average=avg, zero_division=0),
        report    = classification_report(y_true, y_pred,
                                          target_names=class_labels, zero_division=0),
    )


def _plot_confusion_matrix(
    y_true:       np.ndarray,
    y_pred:       np.ndarray,
    output_dir:   str,
    model_name:   str,
    class_labels: Optional[List[str]],
) -> None:
    cm   = confusion_matrix(y_true, y_pred)
    norm = cm.astype(float) / cm.sum(axis=1, keepdims=True)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    for ax, data, title, fmt in [
        (axes[0], cm,   "Confusion Matrix (Sayım)", "d"),
        (axes[1], norm, "Confusion Matrix (Normalize)", ".2%"),
    ]:
        sns.heatmap(data, annot=True, fmt=fmt, cmap="Blues",
                    xticklabels=class_labels or "auto",
                    yticklabels=class_labels or "auto",
                    linewidths=0.5, ax=ax)
        ax.set_title(title)
        ax.set_xlabel("Predicted Class")
        ax.set_ylabel("True Class")

    fig.suptitle(f"Siniflandirma Analizi - {model_name}", fontsize=13, fontweight="bold")
    plt.tight_layout()
    path = os.path.join(output_dir, "prediction_analysis.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    if not os.path.isfile(path):
        raise RuntimeError(f"savefig sessiz basarisiz: dosya olusturulamadi -> {path}")
    print(f"  [OK] prediction_analysis.png -> {path}")


# ═════════════════════════════════════════════════════════════════
# 3. Metrik Raporu (TXT)
# ═════════════════════════════════════════════════════════════════
def _write_metrics_report(
    metrics:    dict,
    output_dir: str,
    model_name: str,
    task:       str,
    n_samples:  int,
) -> None:
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "=" * 60,
        f"  MODEL ANALİZ RAPORU",
        f"  Model     : {model_name}",
        f"  Görev     : {task.upper()}",
        f"  Örnekler  : {n_samples}",
        f"  Tarih     : {ts}",
        "=" * 60,
        "",
    ]

    if task == "regression":
        lines += [
            "── Regresyon Metrikleri ────────────────────────",
            f"  MSE            : {metrics['mse']:.4f}",
            f"  RMSE           : {metrics['rmse']:.4f}",
            f"  MAE            : {metrics['mae']:.4f}",
            f"  R²             : {metrics['r2']:.4f}",
            f"  Hata Ortalaması: {metrics['error_mean']:.4f}",
            f"  Hata Std       : {metrics['error_std']:.4f}",
        ]
    else:
        lines += [
            "── Sınıflandırma Metrikleri ────────────────────",
            f"  Accuracy  : {metrics['accuracy']:.4f}",
            f"  F1 (macro): {metrics['f1']:.4f}",
            f"  Precision : {metrics['precision']:.4f}",
            f"  Recall    : {metrics['recall']:.4f}",
            "",
            "── Sınıf Bazlı Rapor ───────────────────────────",
        ]
        for line in metrics["report"].splitlines():
            lines.append("  " + line)

    lines += ["", "=" * 60]

    path = os.path.join(output_dir, "metrics_report.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  [OK] metrics_report.txt      -> {path}")


# ═════════════════════════════════════════════════════════════════
# ANA GİRİŞ NOKTASI
# ═════════════════════════════════════════════════════════════════
def run_analysis(
    model_name:   str,
    task:         str,
    y_true:       Union[np.ndarray, list],
    y_pred:       Union[np.ndarray, list],
    history:      Optional[Dict[str, List[float]]] = None,
    output_dir:   str                              = "model_analysis",
    class_labels: Optional[List[str]]             = None,
) -> str:
    """
    Parametreler
    ─────────────
    model_name   : Rapor başlığı ve alt-klasör adı (örn. "MIMO_RiskScore")
    task         : "regression" veya "classification"
    y_true       : Gerçek etiketler (1-D array)
    y_pred       : Model tahminleri (1-D array)
    history      : Keras/manuel eğitim geçmişi dict'i. None → loss_curve.png üretilmez.
    output_dir   : Kök çıktı klasörü (varsayılan: "model_analysis/")
    class_labels : Sınıflandırma görevlerinde sınıf isimleri listesi (opsiyonel)

    Dönüş
    ──────
    Oluşturulan alt-klasör yolu (str)
    """
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)

    if task == "classification":
        y_true = y_true.astype(int)
        y_pred = y_pred.astype(int)

    assert y_true.shape == y_pred.shape, \
        f"y_true ({y_true.shape}) ve y_pred ({y_pred.shape}) boyutları eşleşmiyor."

    out = _make_output_dir(output_dir, model_name)
    print(f"\n{'='*55}")
    print(f"  Analiz basliyor: {model_name}  [{task.upper()}]")
    print(f"  Cikti klasoru  : {out}")
    print(f"{'='*55}")

    import traceback as _tb

    # 1. Öğrenme eğrileri
    if history:
        try:
            plot_learning_curves(history, out, model_name)
        except Exception:
            print("  [HATA] loss_curve.png kaydedilemedi:")
            _tb.print_exc()
    else:
        print("  [INFO] history=None -- loss_curve.png atlandi.")

    # 2. Tahmin analizi
    try:
        if task == "regression":
            metrics = _regression_metrics(y_true, y_pred)
            _plot_regression(y_true, y_pred, out, model_name)
        else:
            metrics = _classification_metrics(y_true, y_pred, class_labels)
            _plot_confusion_matrix(y_true, y_pred, out, model_name, class_labels)
    except Exception:
        print("  [HATA] prediction_analysis.png kaydedilemedi:")
        _tb.print_exc()
        metrics = {}

    # 3. Metrik raporu — plot başarısız olsa da yazılır
    if metrics:
        _write_metrics_report(metrics, out, model_name, task, len(y_true))

    print(f"\n  Tum ciktilar kaydedildi -> {out}\n")
    return out


# ═════════════════════════════════════════════════════════════════
# Doğrudan çalıştırma: outputs/train/ içindeki gerçek history'leri kullanır
# ═════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import json
    import sys

    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    _ROOT_DIR   = os.path.dirname(_SCRIPT_DIR)
    _TRAIN_DIR  = os.path.join(_ROOT_DIR, "outputs", "train")

    _SEG_MAP    = {"S1": 0, "S2": 1, "S3": 2, "S4": 3}
    _SEG_LABELS = ["S1_Başarılı", "S2_Orta", "S3_İstikrarsız", "S4_Terk"]

    _CANDIDATES = {
        "MIMO": {
            "history":     os.path.join(_TRAIN_DIR, "mimo_history.json"),
            "predictions": os.path.join(_TRAIN_DIR, "mimo_predictions.json"),
        },
        "HKAR": {
            "history":     os.path.join(_TRAIN_DIR, "hkar_history.json"),
            "predictions": os.path.join(_TRAIN_DIR, "hkar_predictions.json"),
        },
    }

    # ── History varlık kontrolü ───────────────────────────────────
    found = {k: v for k, v in _CANDIDATES.items() if os.path.isfile(v["history"])}

    if not found:
        print("[HATA] History bulunamadı.")
        print(f"       Beklenen klasör : {_TRAIN_DIR}")
        print("       Lütfen önce train_models.py çalıştırın.")
        sys.exit(1)

    print(f"  Bulunan modeller: {list(found.keys())}")

    # ── MIMO: Risk Skoru Regresyonu ───────────────────────────────
    if "MIMO" in found:
        paths = found["MIMO"]
        if not os.path.isfile(paths["predictions"]):
            print("  [WARN] MIMO predictions dosyası yok — MIMO atlanıyor.")
        else:
            with open(paths["history"],     encoding="utf-8") as f:
                mimo_hist = json.load(f)
            with open(paths["predictions"], encoding="utf-8") as f:
                mimo_preds = json.load(f)

            # Keras multi-output key'lerini plot_learning_curves formatına normalize et
            mimo_hist_plot = {
                "loss":    mimo_hist["loss"],
                "val_loss": mimo_hist["val_loss"],
                "mae":     mimo_hist.get("y_risk_mae"),
                "val_mae": mimo_hist.get("val_y_risk_mae"),
            }
            mimo_hist_plot = {k: v for k, v in mimo_hist_plot.items() if v is not None}

            run_analysis(
                model_name = "MIMO_RiskScore",
                task       = "regression",
                y_true     = np.array([p["true_risk"] for p in mimo_preds]),
                y_pred     = np.array([p["pred_risk"]  for p in mimo_preds]),
                history    = mimo_hist_plot,
                output_dir = os.path.join(_ROOT_DIR, "model_analysis"),
            )

    # ── HKAR: Segment Sınıflandırması ────────────────────────────
    if "HKAR" in found:
        paths = found["HKAR"]
        if not os.path.isfile(paths["predictions"]):
            print("  [WARN] HKAR predictions dosyası yok — HKAR atlanıyor.")
        else:
            with open(paths["history"],     encoding="utf-8") as f:
                hkar_hist = json.load(f)
            with open(paths["predictions"], encoding="utf-8") as f:
                hkar_preds = json.load(f)

            run_analysis(
                model_name   = "HKAR_SegmentClassification",
                task         = "classification",
                y_true       = np.array([_SEG_MAP[p["true_segment"]] for p in hkar_preds]),
                y_pred       = np.array([_SEG_MAP[p["pred_segment"]] for p in hkar_preds]),
                history      = hkar_hist,
                class_labels = _SEG_LABELS,
                output_dir   = os.path.join(_ROOT_DIR, "model_analysis"),
            )
