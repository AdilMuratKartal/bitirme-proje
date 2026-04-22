"""
tests/conftest.py
─────────────────
Pytest başlamadan önce CFG singleton'ını küçük ölçeğe patch'ler ve
bağımlı modüllerin önbelleğini temizletiyorum. Böylece her modül, patch'li
CFG (50 öğrenci / 3 kurs / 6 hafta) ile sıfırdan yüklettirip yük bindirmemeye çalıştım.

Bu dosya test_data_semantics.py'deki hiçbir mantığa dokunmaz;
yalnızca fixture ortamını hazırlar.
"""

import sys
import os

# Proje kökü ve local/ dizinini path'e ekle (dosyalar local/ altına taşındı)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL = os.path.join(PROJECT_ROOT, 'local')
sys.path.insert(0, LOCAL)        # config, engine, feature_mimo vb. düz import için
sys.path.insert(0, PROJECT_ROOT) # render_backend ve local paketi için

# ── CFG'yi MODÜL YÜKLENMESİNDEN ÖNCE patch'le ───────────────────
from config import CFG

CFG.general.n_students = 50   # ~12 S1, ~17 S2, ~12 S3, ~8 S4 — istatistik için yeterli
CFG.general.n_courses  = 3    # FK zincirini test etmeye yeterli, hızlı çalışır
CFG.general.n_weeks    = 6    # Quiz hafta 4+5+6, ödev hafta 2+3+4 tetiklenir

# ── Bağımlı modülleri önbellekten temizle ────────────────────────
# Bu modüller CFG'yi modül seviyesinde (import-time) okur.
# Önbellek temizlenmezse eski n_students=2000 ile oluşturulmuş
# STUDENT_REGISTRY singleton'ı kullanılır → fixture yanlış çalışır.
for _mod in [
    "student_registry",
    "engine",
    "feature_mimo",
    "feature_hkar",
]:
    sys.modules.pop(_mod, None)
