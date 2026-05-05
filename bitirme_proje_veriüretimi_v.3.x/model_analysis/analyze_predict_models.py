"""
analyze_predict_models.py — Tahmin Dağılımı Analizörü
══════════════════════════════════════════════════════
outputs/predict/ içindeki tahmin dosyalarını okur.
y_true YOKTUR — başarı metrikleri hesaplanmaz.
Yalnızca dağılım istatistikleri ve görseller üretilir.

Çıktı (model_analysis/<Model>_Predict/):
    prediction_summary.txt      — istatistiksel özet
    prediction_distribution.png — histogram / bar grafikleri

Kullanım:
    python analyze_predict_models.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np

# ── Stil ────────────────────────────────────────────────────────
plt.rcParams.update({
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "font.size":         10,
    "axes.titlesize":    11,
    "figure.facecolor":  "white",
})

_SEP         = "=" * 62
_DPI         = 150
_COLORS      = ["#4C72B0", "#DD8452", "#55A868", "#C44E52"]  # S1/S2/S3/S4
_SEG_ORDER   = ["S1", "S2", "S3", "S4"]
_SEG_LABELS  = ["S1_Başarılı", "S2_Orta", "S3_İstikrarsız", "S4_Terk"]

_SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR    = os.path.dirname(_SCRIPT_DIR)
_PREDICT_DIR = os.path.join(_ROOT_DIR, "outputs", "predict")
_OUT_BASE    = os.path.join(_ROOT_DIR, "model_analysis")


# ════════════════════════════════════════════════════════════════
# Yardımcılar
# ════════════════════════════════════════════════════════════════

def _make_dir(model_name: str) -> str:
    path = os.path.join(_OUT_BASE, model_name)
    os.makedirs(path, exist_ok=True)
    return path


def _continuous_stats(values: np.ndarray) -> dict:
    return dict(
        n      = int(len(values)),
        min    = float(np.min(values)),
        max    = float(np.max(values)),
        mean   = float(np.mean(values)),
        std    = float(np.std(values)),
        p25    = float(np.percentile(values, 25)),
        median = float(np.median(values)),
        p75    = float(np.percentile(values, 75)),
    )


def _freq_stats(labels: List[str]) -> dict:
    total  = len(labels)
    counts = {s: labels.count(s) for s in _SEG_ORDER}
    ratios = {s: counts[s] / total if total else 0.0 for s in _SEG_ORDER}
    return dict(total=total, counts=counts, ratios=ratios)


# ════════════════════════════════════════════════════════════════
# MIMO: pred_risk + pred_grade + pred_segment
# ════════════════════════════════════════════════════════════════

def _analyze_mimo(preds: List[dict]) -> str:
    out_dir = _make_dir("MIMO_Predict")

    risk   = np.array([p["pred_risk"]  for p in preds], dtype=float)
    grade  = np.array([p["pred_grade"] for p in preds], dtype=float)
    segs   = [p["pred_segment"] for p in preds]

    rs  = _continuous_stats(risk)
    gs  = _continuous_stats(grade)
    sf  = _freq_stats(segs)

    # ── Grafik: 2 satır × 3 sütun ───────────────────────────────
    fig = plt.figure(figsize=(16, 10))
    gridsp = gridspec.GridSpec(2, 3, figure=fig, hspace=0.45, wspace=0.35)

    # [0,0] pred_risk histogram
    ax = fig.add_subplot(gridsp[0, 0])
    ax.hist(risk, bins=35, color=_COLORS[0], edgecolor="white", alpha=0.85)
    ax.axvline(rs["mean"],   color="red",    linestyle="--", linewidth=1.5,
               label=f"Ort: {rs['mean']:.3f}")
    ax.axvline(rs["median"], color="orange", linestyle=":",  linewidth=1.5,
               label=f"Med: {rs['median']:.3f}")
    ax.set_title("Risk Skoru Dağılımı")
    ax.set_xlabel("pred_risk")
    ax.set_ylabel("Frekans")
    ax.legend(fontsize=8)

    # [0,1] pred_grade histogram
    ax = fig.add_subplot(gridsp[0, 1])
    ax.hist(grade, bins=35, color=_COLORS[1], edgecolor="white", alpha=0.85)
    ax.axvline(gs["mean"],   color="red",    linestyle="--", linewidth=1.5,
               label=f"Ort: {gs['mean']:.1f}")
    ax.axvline(gs["median"], color="orange", linestyle=":",  linewidth=1.5,
               label=f"Med: {gs['median']:.1f}")
    ax.set_title("Not Tahmini Dağılımı")
    ax.set_xlabel("pred_grade")
    ax.set_ylabel("Frekans")
    ax.legend(fontsize=8)

    # [0,2] box plots yan yana
    ax = fig.add_subplot(gridsp[0, 2])
    bp = ax.boxplot(
        [risk, grade / 100],  # grade'i 0-1'e normalize et karşılaştırma için
        labels=["pred_risk", "pred_grade\n(÷100)"],
        patch_artist=True,
        widths=0.5,
    )
    for patch, color in zip(bp["boxes"], _COLORS[:2]):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_title("Box Plot Karşılaştırması")
    ax.set_ylabel("Değer (normalize)")

    # [1,0] segment frekans bar
    ax = fig.add_subplot(gridsp[1, 0])
    counts = [sf["counts"][s] for s in _SEG_ORDER]
    bars   = ax.bar(_SEG_LABELS, counts, color=_COLORS, edgecolor="white", alpha=0.85)
    ax.bar_label(bars, fmt="%d", padding=3, fontsize=8)
    ax.set_title("Tahmin Edilen Segment Frekansları")
    ax.set_ylabel("Öğrenci Sayısı")
    ax.tick_params(axis="x", rotation=12)

    # [1,1] segment oran bar
    ax = fig.add_subplot(gridsp[1, 1])
    ratios = [sf["ratios"][s] * 100 for s in _SEG_ORDER]
    bars   = ax.bar(_SEG_LABELS, ratios, color=_COLORS, edgecolor="white", alpha=0.85)
    ax.bar_label(bars, labels=[f"{r:.1f}%" for r in ratios], padding=3, fontsize=8)
    ax.set_title("Tahmin Edilen Segment Oranları")
    ax.set_ylabel("Yüzde (%)")
    ax.set_ylim(0, max(ratios) * 1.18)
    ax.tick_params(axis="x", rotation=12)

    # [1,2] risk vs grade scatter (sample 300 nokta — okunabilirlik)
    ax = fig.add_subplot(gridsp[1, 2])
    idx = np.random.default_rng(0).choice(len(risk), size=min(300, len(risk)), replace=False)
    ax.scatter(risk[idx], grade[idx], alpha=0.45, s=20,
               c=[_COLORS[_SEG_ORDER.index(segs[i])] for i in idx])
    ax.set_title("Risk ↔ Not İlişkisi  (örneklem)")
    ax.set_xlabel("pred_risk")
    ax.set_ylabel("pred_grade")

    fig.suptitle(
        f"MIMO — Tahmin Dağılımı Analizi  (n={len(preds)})",
        fontsize=13, fontweight="bold",
    )
    plot_path = os.path.join(out_dir, "prediction_distribution.png")
    fig.savefig(plot_path, dpi=_DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  [OK] prediction_distribution.png -> {plot_path}")

    # ── Özet metin ───────────────────────────────────────────────
    ts    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        _SEP,
        "  MIMO TAHMİN DAĞILIMI ÖZETİ",
        f"  Kaynak  : outputs/predict/mimo_predictions.json",
        f"  N       : {len(preds)}",
        f"  Tarih   : {ts}",
        _SEP,
        "",
        "── pred_risk  (sürekli, 0–1) ────────────────────────",
        f"  min    : {rs['min']:.4f}",
        f"  max    : {rs['max']:.4f}",
        f"  mean   : {rs['mean']:.4f}",
        f"  std    : {rs['std']:.4f}",
        f"  %25    : {rs['p25']:.4f}",
        f"  median : {rs['median']:.4f}",
        f"  %75    : {rs['p75']:.4f}",
        "",
        "── pred_grade  (sürekli, 0–100) ─────────────────────",
        f"  min    : {gs['min']:.2f}",
        f"  max    : {gs['max']:.2f}",
        f"  mean   : {gs['mean']:.2f}",
        f"  std    : {gs['std']:.2f}",
        f"  %25    : {gs['p25']:.2f}",
        f"  median : {gs['median']:.2f}",
        f"  %75    : {gs['p75']:.2f}",
        "",
        "── pred_segment  (kategorik) ────────────────────────",
    ]
    for s, label in zip(_SEG_ORDER, _SEG_LABELS):
        lines.append(
            f"  {label:<22s}: {sf['counts'][s]:>5d}  ({sf['ratios'][s]*100:>5.1f}%)"
        )
    lines += ["", _SEP]

    txt_path = os.path.join(out_dir, "prediction_summary.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  [OK] prediction_summary.txt      -> {txt_path}")

    return out_dir


# ════════════════════════════════════════════════════════════════
# HKAR: pred_segment + confidence per class
# ════════════════════════════════════════════════════════════════

def _analyze_hkar(preds: List[dict]) -> str:
    out_dir = _make_dir("HKAR_Predict")

    segs = [p["pred_segment"] for p in preds]
    sf   = _freq_stats(segs)

    # Confidence toplama: her segment → tahmin edildiğinde ortalama güven
    conf_all: Dict[str, List[float]] = {s: [] for s in _SEG_ORDER}
    for p in preds:
        conf = p.get("confidence", {})
        for s in _SEG_ORDER:
            val = conf.get(s)
            if val is not None:
                conf_all[s].append(float(val))

    conf_avg = {
        s: float(np.mean(v)) if v else 0.0
        for s, v in conf_all.items()
    }
    conf_std = {
        s: float(np.std(v)) if v else 0.0
        for s, v in conf_all.items()
    }

    # ── Grafik: 1 satır × 3 sütun ───────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    # [0] segment frekans
    counts = [sf["counts"][s] for s in _SEG_ORDER]
    bars   = axes[0].bar(_SEG_LABELS, counts, color=_COLORS, edgecolor="white", alpha=0.85)
    axes[0].bar_label(bars, fmt="%d", padding=3, fontsize=8)
    axes[0].set_title("Tahmin Edilen Segment Frekansları")
    axes[0].set_ylabel("Öğrenci Sayısı")
    axes[0].tick_params(axis="x", rotation=12)

    # [1] segment oran
    ratios = [sf["ratios"][s] * 100 for s in _SEG_ORDER]
    bars   = axes[1].bar(_SEG_LABELS, ratios, color=_COLORS, edgecolor="white", alpha=0.85)
    axes[1].bar_label(bars, labels=[f"{r:.1f}%" for r in ratios], padding=3, fontsize=8)
    axes[1].set_title("Tahmin Edilen Segment Oranları")
    axes[1].set_ylabel("Yüzde (%)")
    axes[1].set_ylim(0, max(ratios) * 1.18)
    axes[1].tick_params(axis="x", rotation=12)

    # [2] ortalama confidence (hata çubuklarıyla)
    avg_vals = [conf_avg[s] * 100 for s in _SEG_ORDER]
    std_vals = [conf_std[s] * 100 for s in _SEG_ORDER]
    bars = axes[2].bar(
        _SEG_LABELS, avg_vals,
        yerr=std_vals, capsize=5,
        color=_COLORS, edgecolor="white", alpha=0.85,
        error_kw=dict(elinewidth=1.2, ecolor="gray"),
    )
    axes[2].bar_label(bars, labels=[f"{v:.1f}%" for v in avg_vals], padding=6, fontsize=8)
    axes[2].set_title("Ortalama Tahmin Güveni (±std)")
    axes[2].set_ylabel("Confidence (%)")
    axes[2].set_ylim(0, 115)
    axes[2].tick_params(axis="x", rotation=12)

    fig.suptitle(
        f"HKAR — Tahmin Dağılımı Analizi  (n={len(preds)})",
        fontsize=13, fontweight="bold",
    )
    plt.tight_layout()
    plot_path = os.path.join(out_dir, "prediction_distribution.png")
    fig.savefig(plot_path, dpi=_DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  [OK] prediction_distribution.png -> {plot_path}")

    # ── Özet metin ───────────────────────────────────────────────
    ts    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        _SEP,
        "  HKAR TAHMİN DAĞILIMI ÖZETİ",
        f"  Kaynak  : outputs/predict/hkar_predictions.json",
        f"  N       : {len(preds)}",
        f"  Tarih   : {ts}",
        _SEP,
        "",
        "── pred_segment  (kategorik) ────────────────────────",
    ]
    for s, label in zip(_SEG_ORDER, _SEG_LABELS):
        lines.append(
            f"  {label:<22s}: {sf['counts'][s]:>5d}  ({sf['ratios'][s]*100:>5.1f}%)"
        )
    lines += [
        "",
        "── Ortalama Confidence (tüm öğrenciler üzerinden) ───",
    ]
    for s, label in zip(_SEG_ORDER, _SEG_LABELS):
        lines.append(
            f"  {label:<22s}: ort={conf_avg[s]*100:>5.1f}%  std={conf_std[s]*100:>5.1f}%"
        )
    lines += ["", _SEP]

    txt_path = os.path.join(out_dir, "prediction_summary.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  [OK] prediction_summary.txt      -> {txt_path}")

    return out_dir


# ════════════════════════════════════════════════════════════════
# ANA GİRİŞ NOKTASI
# ════════════════════════════════════════════════════════════════

def main() -> None:
    print(_SEP)
    print("  Tahmin Dağılımı Analizörü")
    print(f"  Kaynak : {_PREDICT_DIR}")
    print(_SEP)

    candidates = {
        "MIMO": os.path.join(_PREDICT_DIR, "mimo_predictions.json"),
        "HKAR": os.path.join(_PREDICT_DIR, "hkar_predictions.json"),
    }

    found = {k: v for k, v in candidates.items() if os.path.isfile(v)}

    if not found:
        print("[HATA] outputs/predict/ içinde tahmin dosyası bulunamadı.")
        print(f"       Beklenen klasör: {_PREDICT_DIR}")
        print("       Lütfen önce predict_models.py çalıştırın.")
        sys.exit(1)

    print(f"  Bulunan dosyalar: {list(found.keys())}\n")

    if "MIMO" in found:
        print("--- MIMO ---------------------------------------------------")
        with open(found["MIMO"], encoding="utf-8") as f:
            mimo_preds = json.load(f)
        out = _analyze_mimo(mimo_preds)
        print(f"  Cikti: {out}\n")

    if "HKAR" in found:
        print("--- HKAR ---------------------------------------------------")
        with open(found["HKAR"], encoding="utf-8") as f:
            hkar_preds = json.load(f)
        out = _analyze_hkar(hkar_preds)
        print(f"  Cikti: {out}\n")

    print(_SEP)
    print("  Tamamlandi.")
    print(_SEP)


if __name__ == "__main__":
    main()
