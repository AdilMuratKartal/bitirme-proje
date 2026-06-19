# -*- coding: utf-8 -*-
"""Azaltilmis-Feature Model Karsilastirma — K=15 / K=20 vs 33-feature baseline

Amac: feature_importance konsensusu (XGBoost gain + Permutation + SHAP ortalama sira)
ile en onemli K feature'i secip, ayni 3 modeli (XGBoost/RandomForest/LightGBM) bu daraltilmis
feature setiyle egitmek ve 33-feature baseline ile metrik karsilastirmasi yapmak.

Karar VERMEZ — sadece karsilastirma tablosu + grafik uretir. Kullanici sayilari gorup
hangi feature setini benimseyecegine karar verir. (--adopt K ile secilen set kaydedilir.)

Girdi : cikti/01_cohort_dataset.csv   (student_success_prediction.py ile ayni)
Cikti : cikti/ml/feature_reduction_comparison.txt
        cikti/ml/12_feature_reduction_karsilastirma.png
        (--adopt verilirse) ../saved_models/  PKL+ONNX+meta yeniden yazilir
"""
import sys, os, argparse, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))  # localv2/ (convert modulu)
from common import rapor

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import accuracy_score, roc_auc_score, f1_score
import xgboost as xgb
import lightgbm as lgb
import pickle, datetime as _dt

# --------------------------------------------------------------------------- #
# Dizinler + sabitler (student_success_prediction.py ile ayni)                #
# --------------------------------------------------------------------------- #
CIKTI_DIR = os.path.join(os.path.dirname(__file__), "cikti")
ML_DIR    = os.path.join(CIKTI_DIR, "ml")
os.makedirs(ML_DIR, exist_ok=True)

SAVED_MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "saved_models")
MODEL_PKL  = os.path.join(SAVED_MODELS_DIR, "student_success_model.pkl")
MODEL_ONNX = os.path.join(SAVED_MODELS_DIR, "student_success_model.onnx")
META_JSON  = os.path.join(SAVED_MODELS_DIR, "student_success_meta.json")

DATASET = os.path.join(CIKTI_DIR, "01_cohort_dataset.csv")

# student_success_prediction.py ile birebir ayni leakage seti
LEAKAGE = {
    "norm_pct", "grade_margin", "grade_margin_pct",
    "finalgrade", "gradepass", "grademax", "grademin",
    "userid", "courseid", "label", "kurs_tier", "teslim_per_gun", "quiz_act_pct",
    "n_quiz_deneme_log1p", "n_teslim_log1p", "quiz_act", "forum_view", "forum_submit",
    "n_quiz_deneme", "n_teslim", "teslim_var",
}

RANDOM_STATE = 42
TOP_KS = [20, 15]   # karsilastirilacak daraltilmis feature sayilari


def build_models():
    """student_success_prediction.py ile ayni hiperparametreler."""
    return {
        "XGBoost": xgb.XGBClassifier(
            n_estimators=300, max_depth=5, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, min_child_weight=3,
            random_state=RANDOM_STATE, verbosity=0,
        ),
        "RandomForest": RandomForestClassifier(
            n_estimators=300, max_depth=8, min_samples_leaf=5,
            random_state=RANDOM_STATE, n_jobs=-1,
        ),
        "LightGBM": lgb.LGBMClassifier(
            n_estimators=300, max_depth=5, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, min_child_samples=10,
            random_state=RANDOM_STATE, verbose=-1,
        ),
    }


def train_eval(features, X_train, X_test, y_train, y_test, cv):
    """Verilen feature seti ile 3 modeli egit; her model icin metrik dondur."""
    Xtr, Xte = X_train[features], X_test[features]
    out, trained = {}, {}
    for name, model in build_models().items():
        model.fit(Xtr, y_train)
        trained[name] = model
        y_pred = model.predict(Xte)
        y_prob = model.predict_proba(Xte)[:, 1]
        cv_auc = cross_val_score(
            build_models()[name], Xtr, y_train,
            cv=cv, scoring="roc_auc", n_jobs=-1,
        ).mean()
        out[name] = {
            "acc": accuracy_score(y_test, y_pred),
            "auc": roc_auc_score(y_test, y_prob),
            "f1":  f1_score(y_test, y_pred),
            "cv_auc": cv_auc,
        }
    best = max(out, key=lambda n: out[n]["auc"])
    return out, trained, best


def consensus_ranking(features, trained, best_name, X_test, y_test):
    """XGBoost gain + Permutation(best) + SHAP(LightGBM) -> ortalama sira (kucuk=onemli)."""
    # 1) XGBoost gain
    gain = pd.Series(
        trained["XGBoost"].get_booster().get_score(importance_type="gain")
    )
    gain = gain.reindex(features).fillna(0.0)
    xgb_rank = gain.rank(ascending=False, method="first")

    # 2) Permutation (best model, test seti, AUC)
    perm = permutation_importance(
        trained[best_name], X_test[features], y_test,
        n_repeats=20, random_state=RANDOM_STATE, n_jobs=-1, scoring="roc_auc",
    )
    perm_s = pd.Series(perm.importances_mean, index=features)
    perm_rank = perm_s.rank(ascending=False, method="first")

    # 3) SHAP (LightGBM) — basarisiz olursa gain+perm konsensusu
    ranks = [xgb_rank, perm_rank]
    try:
        import shap
        lgb_model = trained["LightGBM"]
        explainer = shap.TreeExplainer(lgb_model, data=None, model_output="raw")
        sv = explainer(X_test[features])
        vals = sv.values[:, :, 1] if sv.values.ndim == 3 else sv.values
        shap_s = pd.Series(np.abs(vals).mean(axis=0), index=features)
        ranks.append(shap_s.rank(ascending=False, method="first"))
        method = "gain+perm+shap"
    except Exception as exc:
        print(f"  [UYARI] SHAP atlandi ({exc}) — gain+perm konsensusu kullanildi.")
        method = "gain+perm"

    avg_rank = pd.concat(ranks, axis=1).mean(axis=1).sort_values()
    return avg_rank, method


def main():
    ap = argparse.ArgumentParser(description="Azaltilmis-feature model karsilastirma")
    ap.add_argument("--adopt", type=int, choices=TOP_KS, default=None,
                    help="Verilen K ile final modeli kaydet (PKL/ONNX/meta yeniden yazilir).")
    args = ap.parse_args()

    if not os.path.exists(DATASET):
        raise SystemExit(f"HATA: {DATASET} yok. Once 01_hazirla.py calistirin.")

    print("=== AZALTILMIS-FEATURE MODEL KARSILASTIRMA ===\n")
    df = pd.read_csv(DATASET)
    all_feats = sorted([c for c in df.columns if c not in LEAKAGE])
    X = df[all_feats].fillna(0).astype(float)
    y = df["label"].astype(int)
    print(f"Dataset : {len(df):,} satir  |  {len(all_feats)} feature (baseline)")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y,
    )
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)

    # 1) Baseline (tum feature) — ayni zamanda importance konsensusu icin
    print("\n[1] Baseline egitiliyor (tum feature)...")
    base_res, base_trained, base_best = train_eval(all_feats, X_train, X_test, y_train, y_test, cv)
    print(f"    En iyi: {base_best}  AUC={base_res[base_best]['auc']:.4f}")

    print("[2] Feature importance konsensusu hesaplaniyor...")
    avg_rank, method = consensus_ranking(all_feats, base_trained, base_best, X_test, y_test)
    print(f"    Yontem: {method}")

    # 3) Her K icin daraltilmis set egit
    feature_sets = {f"ALL ({len(all_feats)})": all_feats}
    selected = {}
    for k in TOP_KS:
        feats_k = avg_rank.head(k).index.tolist()
        selected[k] = feats_k
        feature_sets[f"TOP-{k}"] = feats_k

    comparison = {}
    for label, feats in feature_sets.items():
        print(f"[3] Egitiliyor: {label}  ({len(feats)} feature)...")
        res, _, best = train_eval(feats, X_train, X_test, y_train, y_test, cv)
        comparison[label] = {"best": best, "res": res, "n": len(feats)}

    # 4) Rapor
    lines = [
        "=== FEATURE AZALTMA KARSILASTIRMASI ===",
        "",
        f"Dataset    : {len(df):,} satir",
        f"Baseline   : {len(all_feats)} feature",
        f"Secim      : feature_importance konsensusu ({method}), ortalama sira",
        "",
        "--- EN IYI MODEL (her feature seti icin, AUC'ye gore) ---",
        f"  {'Feature Seti':<14s} {'Model':<13s} {'AUC':>8s} {'F1':>8s} {'Acc':>8s} {'CV-AUC':>8s}",
    ]
    for label, c in comparison.items():
        b = c["res"][c["best"]]
        lines.append(
            f"  {label:<14s} {c['best']:<13s} "
            f"{b['auc']:>8.4f} {b['f1']:>8.4f} {b['acc']:>8.4f} {b['cv_auc']:>8.4f}"
        )

    # AUC kaybi (baseline en iyiye gore)
    base_label = f"ALL ({len(all_feats)})"
    base_auc = comparison[base_label]["res"][comparison[base_label]["best"]]["auc"]
    lines += ["", "--- BASELINE'A GORE AUC FARKI ---"]
    for k in TOP_KS:
        c = comparison[f"TOP-{k}"]
        auc_k = c["res"][c["best"]]["auc"]
        lines.append(f"  TOP-{k:<3d}: dAUC = {auc_k - base_auc:+.4f}  ({auc_k:.4f} vs {base_auc:.4f})")

    lines += ["", "--- HER FEATURE SETI: 3 MODEL DETAY ---"]
    for label, c in comparison.items():
        lines.append(f"  [{label}]")
        for nm, r in c["res"].items():
            mark = " <<<" if nm == c["best"] else ""
            lines.append(f"     {nm:<13s} AUC={r['auc']:.4f} F1={r['f1']:.4f} "
                         f"Acc={r['acc']:.4f} CV-AUC={r['cv_auc']:.4f}{mark}")

    for k in TOP_KS:
        lines += ["", f"--- TOP-{k} SECILEN FEATURE'LAR (onem sirasi) ---"]
        for i, f in enumerate(selected[k], 1):
            lines.append(f"  {i:2d}. {f}")

    rapor(CIKTI_DIR, "feature_reduction_comparison.txt", lines)
    print("\n[Rapor] cikti/feature_reduction_comparison.txt")

    # 5) Grafik — AUC karsilastirma
    labels = list(comparison.keys())
    aucs = [comparison[l]["res"][comparison[l]["best"]]["auc"] for l in labels]
    f1s  = [comparison[l]["res"][comparison[l]["best"]]["f1"] for l in labels]
    xpos = np.arange(len(labels)); w = 0.38
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(xpos - w/2, aucs, w, label="AUC", color="#4CAF50")
    ax.bar(xpos + w/2, f1s,  w, label="F1",  color="#2196F3")
    for i, (a, f) in enumerate(zip(aucs, f1s)):
        ax.text(i - w/2, a + 0.005, f"{a:.3f}", ha="center", fontsize=8)
        ax.text(i + w/2, f + 0.005, f"{f:.3f}", ha="center", fontsize=8)
    ax.set_xticks(xpos); ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.05); ax.set_ylabel("Skor")
    ax.set_title("Feature Azaltma — En Iyi Model AUC/F1 Karsilastirma")
    ax.legend(); ax.axhline(base_auc, color="gray", ls="--", lw=0.8, alpha=0.6)
    plt.tight_layout()
    plt.savefig(os.path.join(ML_DIR, "12_feature_reduction_karsilastirma.png"), dpi=150)
    plt.close()
    print("[Grafik] cikti/ml/12_feature_reduction_karsilastirma.png")

    # 6) (Opsiyonel) benimse: secilen K ile final modeli kaydet
    if args.adopt:
        k = args.adopt
        feats = selected[k]
        print(f"\n[ADOPT] TOP-{k} ile final model kaydediliyor ({len(feats)} feature)...")
        res, trained, best = train_eval(feats, X_train, X_test, y_train, y_test, cv)
        _save = {
            "trained": trained, "best_name": best, "features": feats,
            "metrics": {nm: {kk: r[kk] for kk in ("acc", "auc", "f1", "cv_auc")}
                        for nm, r in res.items()},
            "saved_at": _dt.datetime.now().isoformat(),
        }
        with open(MODEL_PKL, "wb") as ffp:
            pickle.dump(_save, ffp)
        print(f"  PKL : {MODEL_PKL}")
        try:
            from convert_student_success_to_onnx import export_to_onnx
            export_to_onnx(trained[best], best, feats, MODEL_ONNX)
            print(f"  ONNX: {MODEL_ONNX}")
        except Exception as exc:
            print(f"  [UYARI] ONNX export basarisiz: {exc}")
        meta = {
            "model_name": best, "features": feats, "n_features": len(feats),
            "auc": res[best]["auc"], "f1": res[best]["f1"],
            "accuracy": res[best]["acc"], "cv_auc": res[best]["cv_auc"],
            "saved_at": _dt.datetime.now().isoformat(),
        }
        with open(META_JSON, "w", encoding="utf-8") as ffp:
            json.dump(meta, ffp, ensure_ascii=False, indent=2)
        print(f"  Meta: {META_JSON}")

    print("\n=== TAMAMLANDI ===")


if __name__ == "__main__":
    main()
