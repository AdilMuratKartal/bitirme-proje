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
    ax.set_title(f"{model_name} — Loss Eğrisi")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Loss")
    ax.legend()

    # ── İkincil metrik grafiği ────────────────────────────────────
    if secondary_key:
        ax2 = axes[1]
        ax2.plot(epochs, history[secondary_key], label=f"Train {secondary_key.upper()}", linewidth=2)
        if secondary_val_key:
            ax2.plot(epochs, history[secondary_val_key],
                     label=f"Val {secondary_key.upper()}", linewidth=2, linestyle="--")
        ax2.set_title(f"{model_name} — {secondary_key.upper()} Eğrisi")
        ax2.set_xlabel("Epoch")
        ax2.set_ylabel(secondary_key.upper())
        ax2.legend()

    fig.suptitle(f"Öğrenme Eğrileri — {model_name}", fontsize=13, fontweight="bold")
    plt.tight_layout()
    path = os.path.join(output_dir, "loss_curve.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
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
    ax1.plot(lims, lims, "r--", linewidth=1.5, label="Mükemmel Tahmin")
    ax1.set_xlim(lims); ax1.set_ylim(lims)
    ax1.set_xlabel("Gerçek Değer"); ax1.set_ylabel("Tahmin Edilen")
    ax1.set_title("Actual vs Predicted")
    ax1.legend(fontsize=8)

    # Hata histogram
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.hist(errors, bins=30, edgecolor="white", color="steelblue", alpha=0.8)
    ax2.axvline(0, color="red", linestyle="--", linewidth=1.5)
    ax2.set_xlabel("Hata (Pred − True)"); ax2.set_ylabel("Frekans")
    ax2.set_title("Hata Dağılımı")

    # Residuals vs Predicted
    ax3 = fig.add_subplot(gs[0, 2])
    ax3.scatter(y_pred, errors, alpha=0.4, edgecolors="none", s=25)
    ax3.axhline(0, color="red", linestyle="--", linewidth=1.5)
    ax3.set_xlabel("Tahmin Edilen"); ax3.set_ylabel("Rezidüel")
    ax3.set_title("Rezidüel Grafiği")

    fig.suptitle(f"Tahmin Analizi — {model_name}", fontsize=13, fontweight="bold")
    plt.tight_layout()
    path = os.path.join(output_dir, "prediction_analysis.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  [OK] prediction_analysis.png ->{path}")


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
        ax.set_xlabel("Tahmin Edilen Sınıf")
        ax.set_ylabel("Gerçek Sınıf")

    fig.suptitle(f"Sınıflandırma Analizi — {model_name}", fontsize=13, fontweight="bold")
    plt.tight_layout()
    path = os.path.join(output_dir, "prediction_analysis.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  [OK] prediction_analysis.png ->{path}")


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

    # 1. Öğrenme eğrileri
    if history:
        plot_learning_curves(history, out, model_name)
    else:
        print("  [INFO] history=None -- loss_curve.png atlandi.")

    # 2. Tahmin analizi + 3. Metrik raporu
    if task == "regression":
        metrics = _regression_metrics(y_true, y_pred)
        _plot_regression(y_true, y_pred, out, model_name)
    else:
        metrics = _classification_metrics(y_true, y_pred, class_labels)
        _plot_confusion_matrix(y_true, y_pred, out, model_name, class_labels)

    _write_metrics_report(metrics, out, model_name, task, len(y_true))

    print(f"\n  Tum ciktilar kaydedildi -> {out}\n")
    return out


# ═════════════════════════════════════════════════════════════════
# Demo (python analyze_models.py ile doğrudan çalıştırma)
# ═════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    rng = np.random.default_rng(42)
    N   = 200

    # ── Demo 1: MIMO Risk Skoru (Regresyon) ───────────────────────
    y_true_reg  = rng.uniform(0.1, 0.9, N).astype(np.float32)
    noise       = rng.normal(0, 0.07, N).astype(np.float32)
    y_pred_reg  = np.clip(y_true_reg + noise, 0, 1)

    fake_history_reg = {
        "loss":     list(np.exp(-np.linspace(0.5, 3.0, 50)) + rng.uniform(0, 0.02, 50)),
        "val_loss": list(np.exp(-np.linspace(0.4, 2.5, 50)) + rng.uniform(0, 0.04, 50)),
        "mae":      list(np.linspace(0.25, 0.04, 50) + rng.uniform(0, 0.01, 50)),
        "val_mae":  list(np.linspace(0.28, 0.07, 50) + rng.uniform(0, 0.02, 50)),
    }

    run_analysis(
        model_name = "MIMO_RiskScore",
        task       = "regression",
        y_true     = y_true_reg,
        y_pred     = y_pred_reg,
        history    = fake_history_reg,
    )

    # ── Demo 2: HKAR Konu Başarısı (Sınıflandırma) ───────────────
    y_true_cls = rng.integers(0, 4, N)
    probs      = rng.dirichlet([3, 2, 2, 1], N)
    y_pred_cls = np.argmax(probs, axis=1)
    y_pred_cls = np.where(rng.random(N) < 0.75, y_true_cls, y_pred_cls)

    fake_history_cls = {
        "loss":         list(np.exp(-np.linspace(0.4, 2.8, 60)) + rng.uniform(0, 0.03, 60)),
        "val_loss":     list(np.exp(-np.linspace(0.3, 2.2, 60)) + rng.uniform(0, 0.05, 60)),
        "accuracy":     list(np.linspace(0.3, 0.88, 60) + rng.uniform(0, 0.02, 60)),
        "val_accuracy": list(np.linspace(0.28, 0.82, 60) + rng.uniform(0, 0.03, 60)),
    }

    run_analysis(
        model_name   = "HKAR_TopicSuccess",
        task         = "classification",
        y_true       = y_true_cls,
        y_pred       = y_pred_cls,
        history      = fake_history_cls,
        class_labels = ["S1_Başarılı", "S2_Orta", "S3_İstikrarsız", "S4_Terk"],
    )
