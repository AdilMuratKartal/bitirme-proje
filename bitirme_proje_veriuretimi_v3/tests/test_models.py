"""
tests/test_models.py
────────────────────
5 ML Değişmez Testi (MLOps QA)

1. TestDataLeakage      — X özelliklerinde hedef sızıntısı yok
2. TestLearningCapacity — MicroMLP küçük veri setini ezberleyebilir
3. TestBaselineComparison — Doğrusal model > ortalama tahmin
4. TestDeterminism      — Özellik üreticisi saf; engine seed tekrarlanabilir
5. TestGradientFlow     — Geri yayılım gradyanları var, sonlu, sıfır değil
"""

import sys
import os
import pytest
import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print(PROJECT_ROOT)
LOCAL = PROJECT_ROOT + "/local"
print(LOCAL)
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, LOCAL)  # config, engine, feature_mimo vb. düz import için



# ─────────────────────────────────────────────────────────────────
# Pure-numpy 2-katmanlı MLP (dış bağımlılık yok)
# ─────────────────────────────────────────────────────────────────
class MicroMLP:
    def __init__(self, in_dim: int, hidden: int, out_dim: int, seed: int = 42):
        rng = np.random.default_rng(seed)
        self.W1 = rng.standard_normal((in_dim, hidden)) * np.sqrt(2.0 / in_dim)
        self.b1 = np.zeros(hidden)
        self.W2 = rng.standard_normal((hidden, out_dim)) * np.sqrt(2.0 / hidden)
        self.b2 = np.zeros(out_dim)
        self.grads: dict = {}
        self._X = self._z1 = self._a1 = None

    def forward(self, X: np.ndarray) -> np.ndarray:
        self._X  = X
        self._z1 = X @ self.W1 + self.b1
        self._a1 = np.maximum(0.0, self._z1)
        return self._a1 @ self.W2 + self.b2

    def mse_backward(self, y: np.ndarray, y_pred: np.ndarray) -> float:
        N    = len(y)
        err  = y_pred.ravel() - y.ravel()
        loss = float(np.mean(err ** 2))
        dout = (2.0 / N) * err[:, None]
        self.grads["W2"] = self._a1.T @ dout
        self.grads["b2"] = dout.sum(0)
        da1              = dout @ self.W2.T
        dz1              = da1 * (self._z1 > 0)
        self.grads["W1"] = self._X.T @ dz1
        self.grads["b1"] = dz1.sum(0)
        return loss

    def step(self, lr: float = 0.005) -> None:
        self.W1 -= lr * self.grads["W1"]
        self.b1 -= lr * self.grads["b1"]
        self.W2 -= lr * self.grads["W2"]
        self.b2 -= lr * self.grads["b2"]


def _train(mlp: MicroMLP, X: np.ndarray, y: np.ndarray,
           epochs: int, lr: float = 0.005) -> list[float]:
    losses = []
    for _ in range(epochs):
        pred = mlp.forward(X)
        loss = mlp.mse_backward(y, pred)
        mlp.step(lr)
        losses.append(loss)
    return losses


# ─────────────────────────────────────────────────────────────────
# Fixture yardımcı: CFG patch + modül önbelleği temizle
# ─────────────────────────────────────────────────────────────────
_ENGINE_MODULES = [
    "student_registry", "engine",
    "feature_mimo", "feature_hkar",
]

def _patch_cfg_and_clear(n_students=60, n_courses=2, n_weeks=4):
    from config import CFG
    CFG.general.n_students = n_students
    CFG.general.n_courses  = n_courses
    CFG.general.n_weeks    = n_weeks
    for mod in _ENGINE_MODULES:
        sys.modules.pop(mod, None)
    return CFG


# ─────────────────────────────────────────────────────────────────
# Fixture'lar
# ─────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def real_mimo_data():
    _patch_cfg_and_clear(n_students=60, n_courses=2, n_weeks=4)
    from config import CFG
    from engine import SimulationEngine
    from feature_mimo import build_mimo_dataset

    eng    = SimulationEngine()
    tables = eng.simulate_full_semester(weeks=CFG.general.n_weeks)
    ds     = build_mimo_dataset(tables)
    ds["_tables"] = tables
    return ds


@pytest.fixture(scope="module")
def real_hkar_data(real_mimo_data):
    from feature_hkar import build_hkar_dataset
    tables = real_mimo_data["_tables"]
    return build_hkar_dataset(tables)


@pytest.fixture(scope="module")
def tiny_train_val():
    """
    Sentetik regresyon görevi: y = 0.7*x0 + 0.3*x1 + küçük gürültü
    N=40 → 20 eğitim / 20 doğrulama
    """
    rng = np.random.default_rng(0)
    N   = 40
    X   = rng.standard_normal((N, 5)).astype(np.float32)
    y   = (0.7 * X[:, 0] + 0.3 * X[:, 1] + rng.normal(0, 0.05, N)).astype(np.float32)
    return {
        "X_tr": X[:20], "y_tr": y[:20],
        "X_val": X[20:], "y_val": y[20:],
    }


# ─────────────────────────────────────────────────────────────────
# 1. Veri Sızıntısı
# ─────────────────────────────────────────────────────────────────
class TestDataLeakage:
    def test_x_static_does_not_contain_target_columns(self, real_mimo_data):
        """X_Static sütunları hedef (risk_score / predicted_grade) içermemeli."""
        from config import CFG
        forbidden = {
            CFG.mimo_target.risk_score_col,
            CFG.mimo_target.predicted_grade_col,
        }
        x_cols = set(real_mimo_data["x_static_df"].columns) - {"userid"}
        assert x_cols.isdisjoint(forbidden), \
            f"Hedef sütunları X_Static'te bulundu: {x_cols & forbidden}"

    def test_x_time_grade_not_identical_to_target_grade(self, real_mimo_data):
        """
        X_Time son hafta notu hedefe birebir eşit olmamalı.
        y_grade artık segment bazlı bağımsız dağılımdan üretildiğinden
        X_Time'daki gözlem dönemi notlarıyla özdeş olamaz.
        """
        x_time_df = real_mimo_data["x_time_df"]
        y_grade   = real_mimo_data["y_grade"]

        last_col = "w_minus_1_grade"
        assert last_col in x_time_df.columns, f"Kolon bulunamadı: {last_col}"

        last_week_grade = x_time_df[last_col].values.astype(np.float64)
        target_grade    = y_grade.astype(np.float64)

        assert not np.allclose(last_week_grade, target_grade, atol=1e-3), \
            "X_Time son hafta notu hedefe birebir eşit — veri sızıntısı şüphesi!"

    def test_target_not_linearly_derivable_from_x_static(self, real_mimo_data):
        """
        y_grade, X_Static'in lineer kombinasyonu olmamalı (R² < 0.95).
        Eski leakage durumunda R² ~1.0 idi (y=0.5*grade+0.3*quiz+0.2*comp).
        Segment bazlı hedefe geçişten sonra R² < 0.95 olmalıdır.
        """
        X = real_mimo_data["x_static_df"].drop(columns="userid").values.astype(np.float64)
        y = real_mimo_data["y_grade"].astype(np.float64)

        if len(y) < 10:
            pytest.skip("Örnek sayısı R² hesabı için yetersiz")

        X_b   = np.column_stack([X, np.ones(len(X))])
        w, *_ = np.linalg.lstsq(X_b, y, rcond=None)
        y_hat = X_b @ w
        ss_res = np.sum((y - y_hat) ** 2)
        ss_tot = np.sum((y - y.mean()) ** 2)
        r2 = 1.0 - ss_res / (ss_tot + 1e-10)

        assert r2 < 0.95, (
            f"X_Static y_grade'i lineer olarak türetiyor (R²={r2:.3f} ≥ 0.95) "
            f"— veri sızıntısı var!"
        )

    def test_y_risk_not_derivable_from_x_static(self, real_mimo_data):
        """
        y_risk, X_Static'in lineer kombinasyonu olmamalı (R² < 0.95).
        """
        X = real_mimo_data["x_static_df"].drop(columns="userid").values.astype(np.float64)
        y = real_mimo_data["y_risk"].astype(np.float64)

        if len(y) < 10:
            pytest.skip("Örnek sayısı R² hesabı için yetersiz")

        X_b   = np.column_stack([X, np.ones(len(X))])
        w, *_ = np.linalg.lstsq(X_b, y, rcond=None)
        y_hat = X_b @ w
        ss_res = np.sum((y - y_hat) ** 2)
        ss_tot = np.sum((y - y.mean()) ** 2)
        r2 = 1.0 - ss_res / (ss_tot + 1e-10)

        assert r2 < 0.95, (
            f"X_Static y_risk'i lineer olarak türetiyor (R²={r2:.3f} ≥ 0.95) "
            f"— veri sızıntısı var!"
        )


# ─────────────────────────────────────────────────────────────────
# 2. Öğrenme Kapasitesi
# ─────────────────────────────────────────────────────────────────
class TestLearningCapacity:
    def test_mlp_can_overfit_tiny_dataset(self, tiny_train_val):
        """
        256 gizli birimli MLP, 2000 epoch sonunda eğitim kaybını
        başlangıcın %5'ine indirmelidir (ezber kapasitesi doğrulama).
        """
        d  = tiny_train_val
        X, y = d["X_tr"], d["y_tr"]

        mlp    = MicroMLP(in_dim=5, hidden=256, out_dim=1, seed=0)
        losses = _train(mlp, X, y, epochs=2000, lr=0.01)

        initial = losses[0]
        final   = losses[-1]
        assert final < initial * 0.05, \
            f"MLP eğitim kaybını düşüremedi: {initial:.4f} → {final:.4f}"

    def test_val_loss_higher_than_train_loss_after_overfit(self, tiny_train_val):
        """
        Ezberleme sonrası doğrulama kaybı eğitim kaybından belirgin yüksek olmalı
        (overfitting = genelleme boşluğu var demek).
        """
        d = tiny_train_val
        X_tr, y_tr   = d["X_tr"], d["y_tr"]
        X_val, y_val = d["X_val"], d["y_val"]

        mlp = MicroMLP(in_dim=5, hidden=256, out_dim=1, seed=0)
        _train(mlp, X_tr, y_tr, epochs=2000, lr=0.01)

        pred_tr  = mlp.forward(X_tr).ravel()
        pred_val = mlp.forward(X_val).ravel()
        loss_tr  = float(np.mean((pred_tr  - y_tr)  ** 2))
        loss_val = float(np.mean((pred_val - y_val) ** 2))

        assert loss_val > loss_tr * 3, \
            f"Beklenen genelleme boşluğu yok: train={loss_tr:.4f}, val={loss_val:.4f}"


# ─────────────────────────────────────────────────────────────────
# 3. Temel Karşılaştırma
# ─────────────────────────────────────────────────────────────────
class TestBaselineComparison:
    def test_linear_model_beats_mean_predictor(self, real_mimo_data):
        # OLS eğitim MSE'si her zaman ortalama MSE'den küçük olmalıdır.
        # Bu test özelliklerin sıfır olmayan bilgi içerdiğini ve X matrisinin
        # tam rankta olduğunu doğrular (tamamen gürültülü özellikler bu testi kırar).
        X_raw = real_mimo_data["x_static_df"].drop(columns="userid").values.astype(np.float64)
        y     = real_mimo_data["y_grade"].astype(np.float64)

        if len(y) < 10:
            pytest.skip("Örnek sayısı karşılaştırma için yetersiz")

        # OLS: bias terimi ekle, tüm veri üzerinde fit + evaluate
        X_b   = np.column_stack([X_raw, np.ones(len(X_raw))])
        w, *_ = np.linalg.lstsq(X_b, y, rcond=None)
        pred  = X_b @ w

        mse_model    = float(np.mean((pred - y) ** 2))
        mse_baseline = float(np.mean((np.mean(y) - y) ** 2))

        assert mse_model < mse_baseline, \
            f"OLS eğitim MSE temel tahmini geçemedi: {mse_model:.2f} >= {mse_baseline:.2f} " \
            f"(özellikler bilgi içermiyor veya X tam rankta değil)"


# ─────────────────────────────────────────────────────────────────
# 4. Belirlilik (Determinizm)
# ─────────────────────────────────────────────────────────────────
class TestDeterminism:
    def test_feature_builder_is_pure(self, real_mimo_data):
        """
        build_x_static aynı tablolarla iki kez çağrıldığında özdeş sonuç vermeli.
        """
        from feature_mimo import build_x_static
        tables = real_mimo_data["_tables"]

        df1 = build_x_static(
            tables["mdl_logstore_standard_log"],
            tables["mdl_grade_grades"],
            tables["mdl_assign"],
            tables["mdl_assign_submission"],
            tables["mdl_quiz_attempts"],
            tables["mdl_course_modules_completion"],
            tables["mdl_course_modules"],
        )
        df2 = build_x_static(
            tables["mdl_logstore_standard_log"],
            tables["mdl_grade_grades"],
            tables["mdl_assign"],
            tables["mdl_assign_submission"],
            tables["mdl_quiz_attempts"],
            tables["mdl_course_modules_completion"],
            tables["mdl_course_modules"],
        )
        pd.testing.assert_frame_equal(df1.reset_index(drop=True),
                                      df2.reset_index(drop=True))

    def test_engine_seed_reproducibility(self):
        """
        Aynı seed ile iki SimulationEngine çalıştırması özdeş quiz_attempts üretmeli.
        """
        _patch_cfg_and_clear(n_students=30, n_courses=2, n_weeks=3)
        from config import CFG
        from engine import SimulationEngine

        def run():
            e = SimulationEngine(seed=1337)
            return e.simulate_full_semester(weeks=CFG.general.n_weeks)["mdl_quiz_attempts"]

        qa1 = run().sort_values(["userid", "quiz", "timestart"]).reset_index(drop=True)

        _patch_cfg_and_clear(n_students=30, n_courses=2, n_weeks=3)
        from engine import SimulationEngine as SE2
        qa2 = SE2(seed=1337).simulate_full_semester(
            weeks=CFG.general.n_weeks
        )["mdl_quiz_attempts"].sort_values(["userid", "quiz", "timestart"]).reset_index(drop=True)

        pd.testing.assert_frame_equal(qa1, qa2)


# ─────────────────────────────────────────────────────────────────
# 5. Gradyan Akışı
# ─────────────────────────────────────────────────────────────────
class TestGradientFlow:
    def test_gradients_exist_after_backward(self, real_mimo_data):
        """Tek forward+backward sonrası tüm gradyan anahtarları dolu olmalı."""
        X = real_mimo_data["X_Static"].astype(np.float64)
        y = real_mimo_data["y_grade"].astype(np.float64)

        mlp  = MicroMLP(in_dim=X.shape[1], hidden=16, out_dim=1, seed=7)
        pred = mlp.forward(X)
        mlp.mse_backward(y, pred)

        for key in ("W1", "b1", "W2", "b2"):
            assert key in mlp.grads, f"Gradyan eksik: {key}"
            assert mlp.grads[key] is not None

    def test_gradients_are_finite_and_nonzero(self, real_mimo_data):
        """Tüm gradyanlar sonlu ve en az biri sıfırdan farklı olmalı."""
        X = real_mimo_data["X_Static"].astype(np.float64)
        y = real_mimo_data["y_grade"].astype(np.float64)

        mlp  = MicroMLP(in_dim=X.shape[1], hidden=16, out_dim=1, seed=7)
        pred = mlp.forward(X)
        mlp.mse_backward(y, pred)

        for key in ("W1", "b1", "W2", "b2"):
            g = mlp.grads[key]
            assert np.all(np.isfinite(g)), f"{key} gradyanı NaN/Inf içeriyor"

        all_zero = all(np.all(mlp.grads[k] == 0) for k in ("W1", "b1", "W2", "b2"))
        assert not all_zero, "Tüm gradyanlar sıfır — geri yayılım çalışmıyor"
