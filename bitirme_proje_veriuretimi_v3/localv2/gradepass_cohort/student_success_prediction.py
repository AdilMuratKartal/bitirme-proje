# -*- coding: utf-8 -*-
"""Ogrenci Basari Tahmini — ML Modelleri + Feature Importance + SHAP Analizi

Modeller: XGBoost (ana), RandomForest, LightGBM
Feature Importance:
  1. XGBoost built-in (gain bazli)
  2. Permutation Importance (model-agnostic)
SHAP:
  3. Beeswarm (ozet — hangi feature hangi yonde etkiliyor)
  4. Bar (ortalama |SHAP| — global onem sirasi)
  5. Waterfall (tek tahmin aciklamasi — en belirsiz ornek)
  6. Dependence (top-2 feature icin SHAP vs deger iliskisi)

Leakage kontrolu:
  norm_pct, grade_margin, grade_margin_pct -> DISLANIR (not bazli, saf leakage)
  finalgrade, gradepass, grademax, grademin -> DISLANIR (label kaynagi)

Girdi : cikti/01_cohort_dataset.csv
Cikti : cikti/ml/
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))  # localv2/ (convert modulu)
from common import rapor, yuzde
from convert_student_success_to_onnx import export_to_onnx

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.model_selection import (
    train_test_split, StratifiedKFold, cross_val_score
)
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    accuracy_score, roc_auc_score, f1_score,
    classification_report, confusion_matrix, ConfusionMatrixDisplay,
    roc_curve
)
import xgboost as xgb
import lightgbm as lgb
import shap
import pickle, json, datetime as _dt

# --------------------------------------------------------------------------- #
# Dizinler                                                                     #
# --------------------------------------------------------------------------- #
CIKTI_DIR = os.path.join(os.path.dirname(__file__), "cikti")
ML_DIR    = os.path.join(CIKTI_DIR, "ml")
os.makedirs(ML_DIR, exist_ok=True)

SAVED_MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "saved_models")
os.makedirs(SAVED_MODELS_DIR, exist_ok=True)

# Interaktif soru atlanip her zaman yeniden egitmek icin True yapin (otomasyon).
# False → kayitli model varsa kullaniciya SORULUR (kullan / yeniden egit).
FORCE_RETRAIN = False

MODEL_PKL  = os.path.join(SAVED_MODELS_DIR, "student_success_model.pkl")
MODEL_ONNX = os.path.join(SAVED_MODELS_DIR, "student_success_model.onnx")
META_JSON  = os.path.join(SAVED_MODELS_DIR, "student_success_meta.json")

DATASET = os.path.join(CIKTI_DIR, "01_cohort_dataset.csv")

print("=== OGRENCI BASARI TAHMINI ===\n")

# --------------------------------------------------------------------------- #
# 1. Veri + Feature Tanimi                                                     #
# --------------------------------------------------------------------------- #
if not os.path.exists(DATASET):
    raise SystemExit(f"HATA: {DATASET} bulunamadi. Once 01_hazirla.py calistirin.")

df = pd.read_csv(DATASET)
df["userid"]   = df["userid"].astype(int)
df["courseid"] = df["courseid"].astype(int)

# Leakage: not kaynakli (r=+0.88 / +0.78) + label kaynagi + kimlik
LEAKAGE = {
    "norm_pct", "grade_margin", "grade_margin_pct",
    "finalgrade", "gradepass", "grademax", "grademin",
    "userid", "courseid", "label" ,"kurs_tier"
}

ML_FEATURES = sorted([c for c in df.columns if c not in LEAKAGE])
X = df[ML_FEATURES].fillna(0).astype(float)
y = df["label"].astype(int)

n_feat = len(ML_FEATURES)
n_pos  = int(y.sum())
n_neg  = int((y == 0).sum())
print(f"Dataset : {len(df):,} satir  |  {n_feat} feature  (leakage haric)")
print(f"Label   : Gecti={n_pos:,}  Kaldi={n_neg:,}  Denge=%{y.mean()*100:.1f}")
print(f"Features: {ML_FEATURES}\n")

# --------------------------------------------------------------------------- #
# 2. Train-Test Split (%80/%20, stratified)                                   #
# --------------------------------------------------------------------------- #
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
print(f"Train : {len(X_train)}  |  Test : {len(X_test)}")
print(f"Train label: 0={int((y_train==0).sum())}  1={int((y_train==1).sum())}")
print(f"Test  label: 0={int((y_test==0).sum())}  1={int((y_test==1).sum())}\n")

# --------------------------------------------------------------------------- #
# 3. Modeller                                                                  #
# --------------------------------------------------------------------------- #
MODELS = {
    "XGBoost": xgb.XGBClassifier(
        n_estimators=300, max_depth=5, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        min_child_weight=3,
        random_state=42, verbosity=0,
    ),
    "RandomForest": RandomForestClassifier(
        n_estimators=300, max_depth=8, min_samples_leaf=5,
        random_state=42, n_jobs=-1,
    ),
    "LightGBM": lgb.LGBMClassifier(
        n_estimators=300, max_depth=5, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        min_child_samples=10,
        random_state=42, verbose=-1,
    ),
}

results  = {}
trained  = {}

# --------------------------------------------------------------------------- #
# 3a. Egitim karari — kayitli model varsa kullaniciya SOR                      #
# --------------------------------------------------------------------------- #
def _ask_retrain() -> bool:
    """True → yeniden egit; False → kayitli modeli yukle."""
    if FORCE_RETRAIN:
        print("[Bilgi] FORCE_RETRAIN=True → model yeniden egitiliyor.\n")
        return True
    if not os.path.exists(MODEL_PKL):
        print("[Bilgi] Kayitli model bulunamadi → egitim yapilacak.\n")
        return True
    if not sys.stdin.isatty():
        print("[Bilgi] Interaktif olmayan oturum → kayitli model kullanilacak.\n")
        return False
    print("\nKayitli model bulundu:")
    print(f"  {MODEL_PKL}")
    print("  [1] Var olan modeli kullan  (varsayilan)")
    print("  [2] Modeli yeniden egit")
    try:
        _ans = input("Seciminiz [1/2]: ").strip()
    except EOFError:
        _ans = "1"
    print()
    return _ans == "2"

_RETRAIN = _ask_retrain()

# --------------------------------------------------------------------------- #
# 3b. Kayitli model yukle                                                      #
# --------------------------------------------------------------------------- #
if not _RETRAIN:
    print(f"[Model yukleniyor] {MODEL_PKL}")
    try:
        with open(MODEL_PKL, "rb") as _f:
            _saved = pickle.load(_f)
        # Ozellik listesi tutarsizsa yeniden egit
        if set(_saved.get("features", [])) != set(ML_FEATURES):
            raise ValueError("Feature mismatch — dataset degisti, yeniden egitiliyor.")
        trained    = _saved["trained"]        # {"XGBoost": ..., "RandomForest": ..., "LightGBM": ...}
        best_name  = _saved["best_name"]
        best_model = trained[best_name]
        for _nm, _m in trained.items():
            _yp  = _m.predict(X_test)
            _ypr = _m.predict_proba(X_test)[:, 1]
            results[_nm] = {
                "acc":    accuracy_score(y_test, _yp),
                "auc":    roc_auc_score(y_test, _ypr),
                "f1":     f1_score(y_test, _yp),
                "cv_auc": _saved.get("metrics", {}).get(_nm, {}).get("cv_auc", 0.0),
                "y_pred": _yp, "y_prob": _ypr,
                "cm":     confusion_matrix(y_test, _yp),
                "report": classification_report(y_test, _yp,
                              target_names=["Kaldi(0)", "Gecti(1)"], digits=4),
            }
        print(f">>> Yuklendi: {best_name}  AUC={results[best_name]['auc']:.4f}")
    except Exception as _load_err:
        print(f"  [UYARI] Yukleme hatasi: {_load_err}")
        print("  → Yeniden egitime geciliyor.\n")
        results, trained = {}, {}
        _RETRAIN = True

# --------------------------------------------------------------------------- #
# 3b. Egit (kayitli model yoksa veya FORCE_RETRAIN=True)                      #
# --------------------------------------------------------------------------- #
if _RETRAIN:
    CV_FOLDS = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    for name, model in MODELS.items():
        print(f"[Egitim] {name} ...")
        model.fit(X_train, y_train)
        trained[name] = model

        y_pred = model.predict(X_test)
        y_prob = model.predict_proba(X_test)[:, 1]

        acc    = accuracy_score(y_test, y_pred)
        auc    = roc_auc_score(y_test, y_prob)
        f1     = f1_score(y_test, y_pred)
        cv_auc = cross_val_score(
            MODELS[name].__class__(**model.get_params()),
            X_train, y_train,
            cv=CV_FOLDS, scoring="roc_auc", n_jobs=-1
        ).mean()

        results[name] = {
            "acc": acc, "auc": auc, "f1": f1, "cv_auc": cv_auc,
            "y_pred": y_pred, "y_prob": y_prob,
            "cm": confusion_matrix(y_test, y_pred),
            "report": classification_report(y_test, y_pred,
                                            target_names=["Kaldi(0)", "Gecti(1)"],
                                            digits=4),
        }
        print(f"  Accuracy={acc:.4f}  AUC={auc:.4f}  F1={f1:.4f}  5-CV AUC={cv_auc:.4f}")

    best_name  = max(results, key=lambda n: results[n]["auc"])
    best_model = trained[best_name]

    # -------- PKL kaydet (3 model birlikte) --------
    print(f"\n[Kaydediliyor] {MODEL_PKL}")
    _save = {
        "trained":   trained,
        "best_name": best_name,
        "features":  ML_FEATURES,
        "metrics":   {nm: {k: r[k] for k in ("acc","auc","f1","cv_auc")}
                      for nm, r in results.items()},
        "saved_at":  _dt.datetime.now().isoformat(),
    }
    with open(MODEL_PKL, "wb") as _f:
        pickle.dump(_save, _f)
    print(f"  PKL : {MODEL_PKL}")

print(f"\n>>> En iyi model: {best_name}  (AUC={results[best_name]['auc']:.4f})")

# --------------------------------------------------------------------------- #
# 3c. GERCEK ONNX export + Meta JSON  (hem yukleme hem egitim yolundan sonra)  #
#     NOT: xgb.save_model(...onnx) ONNX uretmez; export_to_onnx gercek ONNX    #
#     uretir (label + probabilities[N,2], zipmap=False).                       #
# --------------------------------------------------------------------------- #
try:
    export_to_onnx(best_model, best_name, ML_FEATURES, MODEL_ONNX)
    print(f"[ONNX] yazildi: {MODEL_ONNX}")
except Exception as _onnx_err:
    print(f"[UYARI] ONNX export basarisiz: {_onnx_err}")

_meta = {
    "model_name": best_name,
    "features":   ML_FEATURES,
    "n_features": len(ML_FEATURES),
    "auc":        results[best_name]["auc"],
    "f1":         results[best_name]["f1"],
    "accuracy":   results[best_name]["acc"],
    "cv_auc":     results[best_name]["cv_auc"],
    "saved_at":   _dt.datetime.now().isoformat(),
}
with open(META_JSON, "w", encoding="utf-8") as _f:
    json.dump(_meta, _f, ensure_ascii=False, indent=2)
print(f"[Meta] yazildi: {META_JSON}")

# --------------------------------------------------------------------------- #
# 4. Grafikler — Model Karsilastirma                                          #
# --------------------------------------------------------------------------- #
print("\n[Grafik] Model karsilastirma...")

metrics = ["acc", "auc", "f1", "cv_auc"]
metric_labels = ["Accuracy", "AUC (test)", "F1", "5-CV AUC"]
x = np.arange(len(metrics))
width = 0.25
colors = ["#2196F3", "#4CAF50", "#FF9800"]

fig, ax = plt.subplots(figsize=(10, 5))
for i, (name, color) in enumerate(zip(MODELS.keys(), colors)):
    vals = [results[name][m] for m in metrics]
    bars = ax.bar(x + i * width, vals, width, label=name, color=color, alpha=0.85)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005,
                f"{v:.3f}", ha="center", va="bottom", fontsize=8)

ax.set_xticks(x + width)
ax.set_xticklabels(metric_labels, fontsize=11)
ax.set_ylim(0, 1.05)
ax.set_ylabel("Skor")
ax.set_title("Model Karsilastirma — XGBoost / RandomForest / LightGBM")
ax.legend()
ax.axhline(0.7, color="gray", linestyle="--", linewidth=0.8, alpha=0.5)
plt.tight_layout()
plt.savefig(os.path.join(ML_DIR, "01_model_karsilastirma.png"), dpi=150)
plt.close()
print("  01_model_karsilastirma.png")

# --------------------------------------------------------------------------- #
# 5. ROC Egrileri                                                             #
# --------------------------------------------------------------------------- #
print("[Grafik] ROC egrileri...")
fig, ax = plt.subplots(figsize=(7, 6))
colors_roc = ["#2196F3", "#4CAF50", "#FF9800"]
for (name, res), color in zip(results.items(), colors_roc):
    fpr, tpr, _ = roc_curve(y_test, res["y_prob"])
    ax.plot(fpr, tpr, color=color, lw=2,
            label=f"{name}  (AUC={res['auc']:.3f})")
ax.plot([0, 1], [0, 1], "k--", lw=1, alpha=0.5)
ax.set_xlabel("False Positive Rate")
ax.set_ylabel("True Positive Rate")
ax.set_title("ROC Egrisi — Tum Modeller")
ax.legend(fontsize=10)
plt.tight_layout()
plt.savefig(os.path.join(ML_DIR, "02_roc_egrisi.png"), dpi=150)
plt.close()
print("  02_roc_egrisi.png")

# --------------------------------------------------------------------------- #
# 6. Confusion Matrix (3 model yan yana)                                     #
# --------------------------------------------------------------------------- #
print("[Grafik] Confusion matrix...")
fig, axes = plt.subplots(1, 3, figsize=(14, 4))
for ax, (name, res) in zip(axes, results.items()):
    disp = ConfusionMatrixDisplay(res["cm"],
                                  display_labels=["Kaldi(0)", "Gecti(1)"])
    disp.plot(ax=ax, colorbar=False, cmap="Blues")
    ax.set_title(f"{name}\nAcc={res['acc']:.3f}  AUC={res['auc']:.3f}")
plt.suptitle("Confusion Matrix — Test Seti", y=1.01, fontsize=12)
plt.tight_layout()
plt.savefig(os.path.join(ML_DIR, "03_confusion_matrix.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  03_confusion_matrix.png")

# --------------------------------------------------------------------------- #
# 7. Feature Importance — XGBoost Built-in (Gain)                            #
# --------------------------------------------------------------------------- #
print("[Grafik] XGBoost feature importance (gain)...")

xgb_model = trained["XGBoost"]
fi_gain = pd.Series(
    xgb_model.get_booster().get_score(importance_type="gain"),
    name="gain"
).sort_values(ascending=False)

top_n = 20
fi_top = fi_gain.head(top_n)

fig, ax = plt.subplots(figsize=(9, 7))
colors_fi = ["#e74c3c" if i < 5 else "#3498db" for i in range(len(fi_top))]
bars = ax.barh(fi_top.index[::-1], fi_top.values[::-1], color=colors_fi[::-1])
ax.set_xlabel("Gain (XGBoost)")
ax.set_title(f"XGBoost Feature Importance — Top {top_n} (Gain Bazli)")
ax.axvline(fi_top.values.mean(), color="gray", linestyle="--",
           linewidth=1, label=f"Ort. gain={fi_top.values.mean():.1f}")
ax.legend()
for bar in bars:
    ax.text(bar.get_width() + fi_top.max() * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f"{bar.get_width():.1f}", va="center", fontsize=8)
plt.tight_layout()
plt.savefig(os.path.join(ML_DIR, "04_feature_importance_xgb_gain.png"), dpi=150)
plt.close()
print("  04_feature_importance_xgb_gain.png")

# --------------------------------------------------------------------------- #
# 8. Feature Importance — Permutation (model-agnostic, XGBoost test setinde) #
# --------------------------------------------------------------------------- #
print("[Grafik] Permutation importance...")

perm = permutation_importance(
    best_model, X_test, y_test,
    n_repeats=20, random_state=42, n_jobs=-1,
    scoring="roc_auc"
)
perm_df = pd.DataFrame({
    "feature": ML_FEATURES,
    "mean":    perm.importances_mean,
    "std":     perm.importances_std,
}).sort_values("mean", ascending=False)

top_perm = perm_df.head(top_n)

fig, ax = plt.subplots(figsize=(9, 7))
ax.barh(
    top_perm["feature"][::-1],
    top_perm["mean"][::-1],
    xerr=top_perm["std"][::-1],
    color=["#e74c3c" if m > 0 else "#95a5a6" for m in top_perm["mean"][::-1]],
    capsize=3, alpha=0.85
)
ax.axvline(0, color="black", linewidth=0.8)
ax.set_xlabel(f"AUC degisimi (permutasyon, n=20)  [{best_name}]")
ax.set_title(f"Permutation Feature Importance — Top {top_n}  [{best_name}]")
plt.tight_layout()
plt.savefig(os.path.join(ML_DIR, "05_feature_importance_permutation.png"), dpi=150)
plt.close()
print("  05_feature_importance_permutation.png")

# --------------------------------------------------------------------------- #
# 9. SHAP Analizi (LightGBM — TreeSHAP)                                      #
# Not: SHAP 0.49.x ile XGBoost 3.x base_score format uyumsuzlugu var;       #
#      LightGBM 4.6.0 tam uyumlu.                                             #
# --------------------------------------------------------------------------- #
print("\n[SHAP] Explainer hesaplaniyor...")

# LightGBM SHAP icin tercih edilir (XGBoost 3.x ile base_score uyumsuzlugu);
# model yuklemede LightGBM her zaman kaydedilir, dolayisiyla burada her zaman mevcut.
_shap_name  = "LightGBM" if "LightGBM" in trained else best_name
lgb_model   = trained[_shap_name]
explainer   = shap.TreeExplainer(lgb_model, data=None, model_output="raw")
shap_raw    = explainer(X_test)

# LightGBM binary siniflandirma: Explanation.values shape (n, features, 2) veya (n, features)
# Pozitif sinif (label=1) icin son boyuttan al
if shap_raw.values.ndim == 3:
    shap_vals_2d = shap_raw.values[:, :, 1]
    base_vals_1d = shap_raw.base_values[:, 1] if shap_raw.base_values.ndim == 2 else shap_raw.base_values
    shap_values  = shap.Explanation(
        values       = shap_vals_2d,
        base_values  = base_vals_1d,
        data         = shap_raw.data,
        feature_names= ML_FEATURES,
    )
else:
    shap_values = shap_raw
    shap_values.feature_names = ML_FEATURES

print(f"  SHAP degerleri hesaplandi: {shap_values.values.shape}")

# ---- 9a. SHAP Bar Plot (Global ortalama |SHAP|) ---- #
print("[SHAP] Bar plot (global onem)...")
shap.plots.bar(shap_values, max_display=top_n, show=False)
plt.title("SHAP — Global Feature Importance (Ort. |SHAP|)  [LightGBM]")
plt.tight_layout()
plt.savefig(os.path.join(ML_DIR, "06_shap_bar.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  06_shap_bar.png")

# ---- 9b. SHAP Beeswarm (Ozet — yön + dağılım) ---- #
print("[SHAP] Beeswarm plot...")
shap.plots.beeswarm(shap_values, max_display=top_n, show=False)
plt.title("SHAP Beeswarm — Feature Etkisi ve Yonu  [LightGBM]")
plt.tight_layout()
plt.savefig(os.path.join(ML_DIR, "07_shap_beeswarm.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  07_shap_beeswarm.png")

# ---- 9c. SHAP Waterfall (En belirsiz tahmin — 0.5'e en yakin prob) ---- #
print("[SHAP] Waterfall plot (tek ornek)...")
probs_lgb     = results[_shap_name]["y_prob"]
uncertain_idx = int(np.argmin(np.abs(probs_lgb - 0.5)))

shap.plots.waterfall(shap_values[uncertain_idx], max_display=15, show=False)
plt.title(
    f"SHAP Waterfall — En Belirsiz Tahmin  "
    f"[idx={uncertain_idx}, LGB prob={probs_lgb[uncertain_idx]:.3f}, "
    f"label={int(y_test.iloc[uncertain_idx])}]",
    fontsize=10
)
plt.tight_layout()
plt.savefig(os.path.join(ML_DIR, "08_shap_waterfall.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  08_shap_waterfall.png")

# ---- 9d. SHAP Dependence — Top 2 feature ---- #
print("[SHAP] Dependence plot (top-2 feature)...")
mean_abs_shap = np.abs(shap_values.values).mean(axis=0)
top2_idx      = np.argsort(mean_abs_shap)[::-1][:2]
top2_feats    = [ML_FEATURES[i] for i in top2_idx]

fig, axes = plt.subplots(1, 2, figsize=(14, 5))
for ax, feat in zip(axes, top2_feats):
    shap.dependence_plot(
        feat, shap_values.values, X_test,
        interaction_index="auto", ax=ax, show=False
    )
    ax.set_title(f"SHAP Dependence: {feat}")
plt.suptitle("SHAP Dependence — Top-2 Feature  [LightGBM]",
             fontsize=11, y=1.01)
plt.tight_layout()
plt.savefig(os.path.join(ML_DIR, "09_shap_dependence.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  09_shap_dependence.png")

# ---- 9e. SHAP Heatmap (Ornek x Feature matrisi) ---- #
print("[SHAP] Heatmap...")
shap_sum   = shap_values.values.sum(axis=1)
sort_order = np.argsort(shap_sum)

shap.plots.heatmap(
    shap_values[sort_order],
    max_display=15,
    show=False,
)
plt.title("SHAP Heatmap — Ornek x Feature  [LightGBM]")
plt.tight_layout()
plt.savefig(os.path.join(ML_DIR, "10_shap_heatmap.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  10_shap_heatmap.png")

# --------------------------------------------------------------------------- #
# 10. Ek Test: Feature Onem Tutarlilik Karsilastirmasi                       #
# --------------------------------------------------------------------------- #
print("\n[Ek Test] Feature onem tutarlilik karsilastirmasi (3 yontem)...")

# XGBoost gain sirasi
xgb_rank = {feat: rank for rank, feat in
             enumerate(fi_gain.index.tolist(), 1)}

# Permutation sirasi
perm_rank = {row["feature"]: rank for rank, (_, row) in
             enumerate(perm_df.iterrows(), 1)}

# SHAP sirasi
shap_rank = {ML_FEATURES[i]: rank for rank, i in
             enumerate(np.argsort(mean_abs_shap)[::-1], 1)}

# Ortak top-15 tablosu
common_feats = list(set(fi_gain.head(15).index) |
                    set(perm_df.head(15)["feature"]) |
                    set([ML_FEATURES[i] for i in np.argsort(mean_abs_shap)[::-1][:15]]))

rank_df = pd.DataFrame({
    "feature":    common_feats,
    "xgb_rank":  [xgb_rank.get(f, 999) for f in common_feats],
    "perm_rank": [perm_rank.get(f, 999) for f in common_feats],
    "shap_rank": [shap_rank.get(f, 999) for f in common_feats],
})
rank_df["avg_rank"] = rank_df[["xgb_rank", "perm_rank", "shap_rank"]].mean(axis=1)
rank_df = rank_df.sort_values("avg_rank").head(15)

fig, ax = plt.subplots(figsize=(10, 6))
x_pos = np.arange(len(rank_df))
ax.plot(x_pos, rank_df["xgb_rank"].values,  "o-", label="XGBoost Gain", color="#e74c3c", lw=2)
ax.plot(x_pos, rank_df["perm_rank"].values, "s-", label="Permutation",   color="#3498db", lw=2)
ax.plot(x_pos, rank_df["shap_rank"].values, "^-", label="SHAP |ortalama|", color="#27ae60", lw=2)
ax.set_xticks(x_pos)
ax.set_xticklabels(rank_df["feature"].values, rotation=45, ha="right", fontsize=9)
ax.set_ylabel("Sira (kucuk = daha onemli)")
ax.set_title("Feature Onem Tutarlilik: XGBoost Gain vs Permutation vs SHAP")
ax.legend()
ax.invert_yaxis()
plt.tight_layout()
plt.savefig(os.path.join(ML_DIR, "11_importance_tutarlilik.png"), dpi=150)
plt.close()
print("  11_importance_tutarlilik.png")

# --------------------------------------------------------------------------- #
# 11. Metin Raporu                                                            #
# --------------------------------------------------------------------------- #
print("\n[Rapor] ML raporu yaziliyor...")

shap_top10 = [(ML_FEATURES[i], float(mean_abs_shap[i]))
              for i in np.argsort(mean_abs_shap)[::-1][:10]]

lines = [
    "=== OGRENCI BASARI TAHMINI — ML RAPORU ===",
    "",
    f"Dataset   : {len(df):,} satir  |  {n_feat} feature",
    f"Train/Test: {len(X_train)}/{len(X_test)} (80/20 stratified)",
    f"Leakage   : norm_pct, grade_margin, grade_margin_pct DISLANMIS",
    "",
    "--- MODEL SONUCLARI ---",
]
for name, res in results.items():
    marker = " <<< EN IYI" if name == best_name else ""
    lines += [
        f"  {name}{marker}",
        f"    Accuracy : {res['acc']:.4f}",
        f"    AUC      : {res['auc']:.4f}",
        f"    F1       : {res['f1']:.4f}",
        f"    5-CV AUC : {res['cv_auc']:.4f}",
        "",
        f"    Classification Report:",
    ]
    for rline in res["report"].split("\n"):
        lines.append(f"      {rline}")
    lines.append("")

lines += [
    "--- XGBOOST FEATURE IMPORTANCE (Gain, Top 15) ---",
]
for feat, val in fi_gain.head(15).items():
    lines.append(f"  {feat:30s}: gain={val:.1f}  "
                 f"(xgb_rank={xgb_rank.get(feat,999)}, "
                 f"perm_rank={perm_rank.get(feat,999)}, "
                 f"shap_rank={shap_rank.get(feat,999)})")

lines += [
    "",
    "--- PERMUTATION IMPORTANCE (Top 15, AUC delta) ---",
]
for _, row in perm_df.head(15).iterrows():
    lines.append(f"  {row['feature']:30s}: delta_AUC={row['mean']:+.4f}  std={row['std']:.4f}")

lines += [
    "",
    "--- SHAP GLOBAL ONEM (Top 10, Ort. |SHAP|) ---",
    "  (TreeSHAP — XGBoost, test seti)",
]
for feat, val in shap_top10:
    lines.append(f"  {feat:30s}: {val:.4f}")

lines += [
    "",
    "--- TUTARLILIK OZETI (top-10 ortak sirasi) ---",
]
for _, row in rank_df.head(10).iterrows():
    lines.append(
        f"  {row['feature']:30s}: "
        f"xgb={int(row['xgb_rank']):3d}  "
        f"perm={int(row['perm_rank']):3d}  "
        f"shap={int(row['shap_rank']):3d}  "
        f"ort={row['avg_rank']:.1f}"
    )

lines += [
    "",
    "--- GRAFIKLER (cikti/ml/) ---",
    "  01_model_karsilastirma.png     — Accuracy/AUC/F1/CV-AUC karsilastirma",
    "  02_roc_egrisi.png              — ROC egrileri",
    "  03_confusion_matrix.png        — 3 model confusion matrix",
    "  04_feature_importance_xgb_gain.png — XGBoost gain bazli FI",
    "  05_feature_importance_permutation.png — Permutation FI",
    "  06_shap_bar.png                — SHAP global bar (ort. |SHAP|)",
    "  07_shap_beeswarm.png           — SHAP beeswarm (yon + dagilim)",
    "  08_shap_waterfall.png          — SHAP waterfall (tek belirsiz ornek)",
    "  09_shap_dependence.png         — SHAP dependence top-2 feature",
    "  10_shap_heatmap.png            — SHAP heatmap (ornek x feature)",
    "  11_importance_tutarlilik.png   — 3 yontem tutarlilik grafigi",
]

rapor(CIKTI_DIR, "ml_rapor.txt", lines)
print("\n=== TAMAMLANDI ===")
print(f"\n>>> Ciktilar: {ML_DIR}")
print(f">>> Rapor  : {os.path.join(CIKTI_DIR, 'ml_rapor.txt')}")
