"""
tests/test_data_semantics.py
════════════════════════════════════════════════════════════════════
Black-Box Data Semantic Test Suite
Moodle sentetik veri üretim motoru — kapalı kutu semantik testler.

Tasarım İlkeleri:
  • SIFIR tautological test: hiçbir assert engine.py iç değişkenini
    doğrudan okumaz. Yalnızca üretilen DataFrame'lerin semantiği test edilir.
  • Motor küçük ölçekte (50 öğrenci / 3 kurs / 6 hafta) bir kez çalıştırılır;
    tüm testler aynı session-scoped tables fixture'ını paylaşır.
  • Başarısız olması gereken testler kasıtlı olarak yazılmıştır.
    Başarısızlık = gerçek hata; susturulmaz.

Test Grupları:
  1. TestTimeMonotonicity      — 5 test  (Moodle 4.0 zaman kısıtları)
  2. TestGradeIntegrity        — 3 test  (hayalet not + puan sınırları)
  3. TestModulePrerequisite    — 2 test  (hiyerarşik modül kilidi + dropout)
  4. TestMLModelCompatibility  — 4 test  (MIMO / HKAR model girdi bütünlüğü)

Çalıştırma:
  cd <proje_koku>
  pytest tests/test_data_semantics.py -v
"""

import sys
import os
import pytest
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from config import CFG  # conftest.py zaten patch'ledi (50 öğrenci / 3 kurs / 6 hafta)


# ════════════════════════════════════════════════════════════════════
# SESSION FİXTURE'LARI
# Motor bir kez çalışır; her test sınıfı aynı verileri denetler.
# ════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def tables():
    """
    SimulationEngine'i patch'li CFG ile çalıştırır.
    conftest.py önce modül önbelleğini temizlediği için
    engine + student_registry yeni n_students değeriyle yüklenir.
    """
    from engine import SimulationEngine
    eng = SimulationEngine()
    return eng.simulate_full_semester(weeks=CFG.general.n_weeks)


@pytest.fixture(scope="session")
def mimo_targets(tables):
    """
    MIMO hedef vektörlerini (risk skoru + tahmin notu) üretir.
    feature_mimo.build_mimo_targets doğrudan çağrılır — pipeline sarmalayıcısı
    kullanılmaz; böylece ML katmanının kendisi de test kapsamına girer.
    """
    from feature_mimo import build_mimo_targets
    return build_mimo_targets(
        grade_df      = tables["mdl_grade_grades"],
        assign_sub_df = tables["mdl_assign_submission"],
        completion_df = tables["mdl_course_modules_completion"],
        quiz_att_df   = tables["mdl_quiz_attempts"],
        course_mod_df = tables["mdl_course_modules"],
    )


# ════════════════════════════════════════════════════════════════════
# TEST GRUBU 1 — ZAMAN MONOTONLUĞU (Time Monotonicity)
# Moodle 4.0: log kayıtları tek yönlü ilerler, geri gitmez.
# ════════════════════════════════════════════════════════════════════

class TestTimeMonotonicity:

    def test_question_step_strict_monotonicity(self, tables):
        """
        NEYİ: mdl_question_attempt_steps — aynı quiz attempt'e ait
        adımların timecreated değerleri kesinlikle artan sırada olmalı
        VE son adımın timecreated değeri timefinish'i aşmamalı.

        NEDEN: DKT modeli adım sırasını zaman damgasına göre sıralar.
        Ters sıra → modelin geçmiş bilgiyi "gelecek" olarak öğrenmesi
        (data leakage). timefinish aşımı BUG-1 regresyon testi.

        ZINCIR: steps.questionattemptid
                  → question_attempts.id
                  → question_attempts.questionusageid
                  → quiz_attempts.uniqueid (timefinish için)
        """
        steps = tables.get("mdl_question_attempt_steps", pd.DataFrame())
        qa    = tables.get("mdl_question_attempts",      pd.DataFrame())
        atts  = tables.get("mdl_quiz_attempts",          pd.DataFrame())

        if any(df.empty for df in [steps, qa, atts]):
            pytest.skip("Sınav adım verisi yok — segment dağılımı bu çalışmada sınav üretmedi")

        merged = (
            steps
            .merge(
                qa[["id", "questionusageid"]].rename(columns={"id": "qa_id"}),
                left_on="questionattemptid", right_on="qa_id", how="inner",
            )
            .merge(
                atts[["uniqueid", "timefinish"]],
                left_on="questionusageid", right_on="uniqueid", how="inner",
            )
        )

        if merged.empty:
            pytest.skip("Zincir birleştirmesi boş sonuç verdi")

        monoton_violations = []
        finish_violations  = []

        for quiz_uid, grp in merged.groupby("questionusageid"):
            ts_list   = grp.sort_values("timecreated")["timecreated"].tolist()
            timefinish = int(grp["timefinish"].iloc[0])

            # Her adım kendinden sonrakinden KÜÇÜK olmalı (strict)
            for i in range(len(ts_list) - 1):
                if ts_list[i] >= ts_list[i + 1]:
                    monoton_violations.append(
                        f"quiz_uid={quiz_uid}: "
                        f"step[{i}]={ts_list[i]} >= step[{i+1}]={ts_list[i+1]}"
                    )

            # Son adım quiz bitiş zamanını aşmamalı
            if ts_list and ts_list[-1] > timefinish:
                finish_violations.append(
                    f"quiz_uid={quiz_uid}: "
                    f"son_adım={ts_list[-1]} > timefinish={timefinish} "
                    f"(fark={ts_list[-1] - timefinish}s)"
                )

        assert not monoton_violations, (
            f"{len(monoton_violations)} adım monotonluk ihlali (ilk 10):\n"
            + "\n".join(monoton_violations[:10])
        )
        assert not finish_violations, (
            f"{len(finish_violations)} adım timefinish aşımı — BUG-1 REGRESYON (ilk 10):\n"
            + "\n".join(finish_violations[:10])
        )

    def test_quiz_attempt_within_open_window(self, tables):
        """
        NEYİ: Her quiz attempt için:
          • timestart  >= mdl_quiz.timeopen   (quiz açılmadan başlanamaz)
          • timefinish <= mdl_quiz.timeclose  (quiz kapandıktan sonra bitirilemez)

        NEDEN: Moodle quiz motoru bu sınırları DB düzeyinde uygular.
        timefinish > timeclose → BUG-1 regresyon senaryosu.
        timestart < timeopen  → imkânsız Moodle eylemi, ML zaman özelliğini bozar.
        """
        atts  = tables.get("mdl_quiz_attempts", pd.DataFrame())
        quizz = tables.get("mdl_quiz",          pd.DataFrame())

        if atts.empty or quizz.empty:
            pytest.skip("Quiz verisi yok")

        merged = atts.merge(
            quizz[["id", "timeopen", "timeclose"]].rename(columns={"id": "qid"}),
            left_on="quiz", right_on="qid", how="inner",
        )

        early_start = merged[merged["timestart"]  < merged["timeopen"]]
        late_finish = merged[merged["timefinish"] > merged["timeclose"]]

        assert early_start.empty, (
            f"{len(early_start)} attempt quiz açılmadan başlamış "
            f"(timestart < timeopen):\n"
            f"{early_start[['id','userid','timestart','timeopen']].to_string(index=False)}"
        )
        assert late_finish.empty, (
            f"{len(late_finish)} attempt quiz kapandıktan sonra bitmiş "
            f"(timefinish > timeclose) — BUG-1 REGRESYON:\n"
            f"{late_finish[['id','userid','timefinish','timeclose']].to_string(index=False)}"
        )

    def test_quiz_attempt_positive_duration(self, tables):
        """
        NEYİ: Her quiz attempt'te timestart < timefinish (süre kesinlikle > 0).

        NEDEN: Moodle quiz motoru attempt süresini puanlamaya dahil eder.
        Sıfır veya negatif süre → DB tutarsızlığı + MIMO duration_minutes
        özelliği NaN/negatif üretir → ML modeli bozulur.
        """
        atts = tables.get("mdl_quiz_attempts", pd.DataFrame())
        if atts.empty:
            pytest.skip("Quiz attempt yok")

        invalid = atts[atts["timestart"] >= atts["timefinish"]]
        assert invalid.empty, (
            f"{len(invalid)} attempt'te timestart >= timefinish:\n"
            f"{invalid[['id','userid','timestart','timefinish']].to_string(index=False)}"
        )

    def test_assignment_submission_within_window(self, tables):
        """
        NEYİ: Her ödev teslimi için:
          • timemodified >= allowsubmissionsfromdate  (ödev açılmadan teslim yok)
          • timemodified <= duedate                   (geç teslim kabul edilmez)

        NEDEN: Kural 4 gereği timeclose sonrası teslim kabul edilmez.
        Bu test aynı zamanda panic_or_miss stratejisinin sınır koşullarını
        (due_dt - 0..300s) da denetler.
        """
        subs   = tables.get("mdl_assign_submission", pd.DataFrame())
        assign = tables.get("mdl_assign",            pd.DataFrame())

        if subs.empty or assign.empty:
            pytest.skip("Ödev teslimi verisi yok")

        merged = subs.merge(
            assign[["id", "allowsubmissionsfromdate", "duedate"]].rename(
                columns={"id": "aid"}
            ),
            left_on="assignment", right_on="aid", how="inner",
        )

        before_open = merged[merged["timemodified"] < merged["allowsubmissionsfromdate"]]
        after_due   = merged[merged["timemodified"] > merged["duedate"]]

        assert before_open.empty, (
            f"{len(before_open)} teslim ödev açılmadan yapılmış "
            f"(timemodified < allowsubmissionsfromdate)"
        )
        assert after_due.empty, (
            f"{len(after_due)} geç teslim (timemodified > duedate) — "
            f"Kural 4 ihlali:\n"
            f"{after_due[['id','userid','timemodified','duedate']].to_string(index=False)}"
        )

    def test_grade_recorded_after_quiz_closes(self, tables):
        """
        NEYİ: Quiz kaynaklı (itemtype='quiz') notların timemodified değeri,
        simülasyondaki en erken quiz kapanma zamanından BÜYÜK olmalı (Kural 6).

        NEDEN: Eğitmen notları ancak quiz kapandıktan 3-10 gün sonra girilebilir.
        Erken not → Kural 6 ihlali + ML özelliği olarak kullanılan
        timemodified sütunu yanlış sıra bilgisi taşır.

        NOT: Karmaşık quiz→grade_item FK join'i yerine kural seviyesinde
        test edilir: en erken quiz kapanma zamanından önceki hiçbir not
        geçerli olamaz (3 gün minimum gecikme nedeniyle).
        """
        grades      = tables.get("mdl_grade_grades", pd.DataFrame())
        grade_items = tables.get("mdl_grade_items",  pd.DataFrame())
        quizz       = tables.get("mdl_quiz",         pd.DataFrame())

        if grades.empty or grade_items.empty or quizz.empty:
            pytest.skip("Not veya quiz verisi yok")

        quiz_item_ids = set(
            grade_items[grade_items["itemtype"] == "quiz"]["id"].tolist()
        )
        quiz_grades = grades[grades["itemid"].isin(quiz_item_ids)]

        if quiz_grades.empty:
            pytest.skip("Quiz kaynaklı not yok")

        # Simülasyondaki en erken quiz kapanma zamanı
        # Herhangi bir quiz notu bu zamandan önce girilmiş olamaz.
        earliest_close = int(quizz["timeclose"].min())

        too_early = quiz_grades[quiz_grades["timemodified"] <= earliest_close]
        assert too_early.empty, (
            f"{len(too_early)} quiz notu, quizin kapanma zamanından önce veya "
            f"eş zamanlı girilmiş (timemodified <= earliest_close={earliest_close}) "
            f"— Kural 6 ihlali:\n"
            f"{too_early[['id','userid','itemid','timemodified']].to_string(index=False)}"
        )


# ════════════════════════════════════════════════════════════════════
# TEST GRUBU 2 — HAYALET NOT VE PUAN BÜTÜNLÜĞÜ (Grade Integrity)
# ════════════════════════════════════════════════════════════════════

class TestGradeIntegrity:

    def test_grade_finalgrade_bounds(self, tables):
        """
        NEYİ: mdl_grade_grades.finalgrade değerlerinin tamamı [0.0, 100.0]
        sınırı içinde olmalı; hiçbiri negatif veya 100'ün üzerinde olamaz.

        NEDEN: Moodle grade_items tanımında grademin=0, grademax=100.
        Bu sınır dışındaki değer:
          • DB kısıtını (grademax constraint) ihlal eder.
          • MIMO modeli için [0,1] normalizasyonunu bozar.
          • risk_score sigmoid fonksiyonunu tutarsız kılar.
        """
        grades = tables.get("mdl_grade_grades", pd.DataFrame())
        if grades.empty:
            pytest.skip("Not verisi yok")

        out_of_bounds = grades[
            (grades["finalgrade"] < 0.0) | (grades["finalgrade"] > 100.0)
        ]
        assert out_of_bounds.empty, (
            f"{len(out_of_bounds)} not [0, 100] aralığı dışında:\n"
            f"{out_of_bounds[['id','userid','itemid','finalgrade']].to_string(index=False)}"
        )

    def test_no_quiz_grade_without_attempt(self, tables):
        """
        NEYİ: Quiz kaynaklı notu (grade_items.itemtype == 'quiz') olan
        her öğrencinin mdl_quiz_attempts tablosunda en az bir kaydı olmalı.

        NEDEN: Attempt'i olmayan öğrenciye verilen not "hayalet not" (ghost grade)
        üretir. ML modeli sıfır etkileşim için pozitif label öğrenir;
        bu bir label leakage senaryosudur ve model genellemesini yok eder.

        İLİŞKİ: mdl_grade_grades.itemid → mdl_grade_items(itemtype='quiz')
        """
        grades      = tables.get("mdl_grade_grades",  pd.DataFrame())
        grade_items = tables.get("mdl_grade_items",   pd.DataFrame())
        atts        = tables.get("mdl_quiz_attempts", pd.DataFrame())

        if grades.empty or grade_items.empty:
            pytest.skip("Not verisi yok")

        quiz_item_ids = set(
            grade_items[grade_items["itemtype"] == "quiz"]["id"].tolist()
        )
        quiz_grades = grades[grades["itemid"].isin(quiz_item_ids)]

        if quiz_grades.empty:
            pytest.skip("Quiz kaynaklı not yok")

        graded_uids   = set(quiz_grades["userid"].unique())
        attempted_uids = set(atts["userid"].unique()) if not atts.empty else set()

        ghost_uids = graded_uids - attempted_uids
        assert not ghost_uids, (
            f"{len(ghost_uids)} öğrenci quiz attempt'i olmadan quiz notu almış "
            f"(HAYALET NOT):\n"
            f"userid'ler: {sorted(ghost_uids)[:15]}"
        )

    def test_no_null_in_critical_grade_columns(self, tables):
        """
        NEYİ: mdl_grade_grades'de userid, itemid ve finalgrade sütunları
        hiç NULL / NaN içermemeli.

        NEDEN: ML pipeline'ı NaN satırı ile karşılaştığında ya siler
        (öğrenciyi görmezden gelir) ya da yanlış doldurur (fill_value).
        Her iki senaryo model kalitesini etkiler. Kritik sütunlarda
        NULL = veri üretim hatasının doğrudan göstergesidir.
        """
        grades = tables.get("mdl_grade_grades", pd.DataFrame())
        if grades.empty:
            pytest.skip("Not verisi yok")

        for col in ["userid", "itemid", "finalgrade"]:
            if col not in grades.columns:
                pytest.fail(f"mdl_grade_grades'de beklenen sütun eksik: '{col}'")
            null_count = int(grades[col].isna().sum())
            assert null_count == 0, (
                f"mdl_grade_grades.{col} sütununda {null_count} NULL değer var — "
                f"ML normalizasyonu çökecek"
            )


# ════════════════════════════════════════════════════════════════════
# TEST GRUBU 3 — ÖNKOŞUL İHLAL TESTİ (Prerequisite)
# Kural 5: hiyerarşik modül sırası + dropout sonrası kayıt yasağı
# ════════════════════════════════════════════════════════════════════

class TestModulePrerequisite:

    def test_completion_timestamps_respect_sequence(self, tables):
        """
        NEYİ: Bir öğrencinin bir kursta tamamladığı modüller için
        timemodified(seq N+1) >= timemodified(seq N) olmalı.

        NEDEN: Kural 5 — Modül N tamamlanmadan Modül N+1 kilidi açılmaz.
        Bu test BUG-2 (S2 profil kayması, miss_count sıfırlanmama) ve
        Zaman Paradoksu yamasının regresyonunu da yakalar:
        aynı haftada birden fazla modül tamamlandığında 1s gap garantisi
        ihlal edilirse sıra bozulur.

        NOT: Tamamlanmamış modüller (eksik satırlar) test kapsamı dışıdır;
        yalnızca mevcut completion çiftleri karşılaştırılır.
        """
        comps   = tables.get("mdl_course_modules_completion", pd.DataFrame())
        modules = tables.get("mdl_course_modules",            pd.DataFrame())

        if comps.empty or modules.empty:
            pytest.skip("Tamamlama verisi yok")

        merged = comps.merge(
            modules[["id", "course", "sequence"]].rename(columns={"id": "mod_id"}),
            left_on="coursemoduleid", right_on="mod_id", how="inner",
        )

        violations = []
        for (uid, course_id), grp in merged.groupby(["userid", "course"]):
            if len(grp) < 2:
                continue  # Tek modül: karşılaştırma yapılamaz
            sorted_grp = grp.sort_values("sequence")
            seqs  = sorted_grp["sequence"].tolist()
            times = sorted_grp["timemodified"].tolist()

            for i in range(len(times) - 1):
                if times[i + 1] < times[i]:
                    violations.append(
                        f"uid={uid} course={course_id}: "
                        f"seq {seqs[i+1]} (t={times[i+1]}) < "
                        f"seq {seqs[i]}  (t={times[i]}) "
                        f"— {times[i] - times[i+1]}s geri gidiş"
                    )

        assert not violations, (
            f"{len(violations)} önkoşul sırası ihlali (ilk 10):\n"
            + "\n".join(violations[:10])
        )

    def test_no_completion_after_dropout_cutoff(self, tables):
        """
        NEYİ: Dropout olan öğrencilerin modül tamamlama zaman damgaları
        (timemodified) dropout haftasının bitiş anını (week_end) aşmamalıdır.

        NEDEN: Kural 5 — dropout_week sonrası HİÇBİR kayıt üretilmez.
        Kayıt üretme durur (is_active_in_week koruması ✓), ancak zaman
        damgası üretim mekanizması bağımsız çalışır.

        ⚠ KASITLI REGRESYON TESTİ: S4 profili module_gap_days=(10, 25)
        tanımlar; 7 günlük bir haftada 10-25 günlük gap olanaksız.
        dropout_week=5 için week_start(5)+10 gün = week 7'ye sızar.
        Bu test bu yapısal sızıntıyı BULURSA başarısız olur → gerçek hata.

        CUTOFF: week_start(dropout_week + 1) = sem_start + dropout_week × 7gün
        """
        comps    = tables.get("mdl_course_modules_completion", pd.DataFrame())
        registry = tables.get("student_registry",              pd.DataFrame())

        if comps.empty or registry.empty:
            pytest.skip("Tamamlama veya kayıt defteri verisi yok")

        dropouts = registry.dropna(subset=["dropout_week"])
        if dropouts.empty:
            pytest.skip("Bu seed + n_students kombinasyonunda dropout öğrenci yok")

        sem_start_ts = int(CFG.general.semester_start.timestamp())
        week_secs    = 7 * 24 * 3600   # 604800

        violations = []
        for _, row in dropouts.iterrows():
            uid          = int(row["userid"])
            dropout_week = int(row["dropout_week"])
            # Hafta dropout_week'te aktif; hafta dropout_week+1'in başı = cutoff
            cutoff_ts = sem_start_ts + dropout_week * week_secs

            user_comps   = comps[comps["userid"] == uid]
            after_cutoff = user_comps[user_comps["timemodified"] >= cutoff_ts]

            if not after_cutoff.empty:
                violations.append(
                    f"uid={uid} dropout_week={dropout_week} "
                    f"cutoff_ts={cutoff_ts}: "
                    f"{len(after_cutoff)} tamamlama cutoff sonrası "
                    f"(max_ts={int(after_cutoff['timemodified'].max())})"
                )

        assert not violations, (
            f"{len(violations)} dropout sonrası zaman damgası ihlali:\n"
            f"Bu hata S4 module_gap_days=(10,25) ile dropout cutoff'un\n"
            f"sistematik olarak aşıldığını gösterir.\n"
            + "\n".join(violations[:10])
        )


# ════════════════════════════════════════════════════════════════════
# TEST GRUBU 4 — ML MODEL UYUMLULUĞU (MIMO / HKAR)
# ════════════════════════════════════════════════════════════════════

class TestMLModelCompatibility:

    def test_mimo_targets_no_duplicate_userid(self, mimo_targets):
        """
        NEYİ: MIMO hedef veri setinde (build_mimo_targets çıktısı) her
        userid yalnızca BİR KEZ bulunmalı.

        NEDEN: Duplicate satır ML eğitiminde o öğrenciye orantısız ağırlık
        verir (implicit oversampling). BUG-3 regresyon testi:
        grade_df.set_index("userid") non-unique iken crash veriyordu;
        groupby().mean() yamasının ardından bu test duplicate satır
        üretilmediğini garanti eder.
        """
        dups = mimo_targets[mimo_targets.duplicated("userid")]["userid"].tolist()
        assert not dups, (
            f"MIMO targets'ta {len(dups)} duplicate userid — BUG-3 REGRESYON:\n"
            f"{dups[:10]}"
        )

    def test_mimo_risk_score_bounds(self, mimo_targets):
        """
        NEYİ: y_risk_score sütunundaki tüm değerler [0.0, 1.0] aralığında
        olmalı (sigmoid çıktısı).

        NEDEN: Downstream sistemler eşik karşılaştırması yapar (örn. > 0.7
        ise uyarı). Sınır dışı değer → yanlış alarm veya gizli alarm.
        Sigmoid formülü matematiksel olarak bu sınırı garanti eder;
        test bu garantinin üretim çıktısında da geçerli olduğunu doğrular.
        """
        col = CFG.mimo_target.risk_score_col
        assert col in mimo_targets.columns, f"Beklenen sütun eksik: '{col}'"

        out = mimo_targets[
            (mimo_targets[col] < 0.0) | (mimo_targets[col] > 1.0)
        ]
        assert out.empty, (
            f"{len(out)} öğrencinin risk skoru [0, 1] dışında:\n"
            f"{out[['userid', col]].to_string(index=False)}"
        )

    def test_mimo_predicted_grade_bounds(self, mimo_targets):
        """
        NEYİ: y_predicted_grade sütunundaki tüm değerler [0.0, 100.0]
        aralığında olmalı.

        NEDEN: feature_mimo.py içindeki np.clip(p_grad, 0, 100) garantisinin
        üretim verisinde de geçerli olduğunu doğrular. Sınır dışı tahmin
        not → regresyon modelinin loss fonksiyonunu bozar.
        """
        col = CFG.mimo_target.predicted_grade_col
        assert col in mimo_targets.columns, f"Beklenen sütun eksik: '{col}'"

        out = mimo_targets[
            (mimo_targets[col] < 0.0) | (mimo_targets[col] > 100.0)
        ]
        assert out.empty, (
            f"{len(out)} öğrencinin tahmin notu [0, 100] dışında:\n"
            f"{out[['userid', col]].to_string(index=False)}"
        )

    def test_hkar_fk_no_orphan_question_attempts(self, tables):
        """
        NEYİ: mdl_question_attempts.questionusageid değerlerinin tamamı
        mdl_quiz_attempts.uniqueid kümesinde bulunmalı (FK bütünlüğü).

        NEDEN: HKAR zinciri:
          quiz_attempts.uniqueid → question_attempts.questionusageid
        Kırık halka → feature_hkar._build_enriched_attempts() sessiz LEFT JOIN
        kaybı → topic_status bazı öğrenciler için boş kalır →
        X_Sequence DKT vektörü sıfır matrisine döner.

        Bu test Moodle 4.0'da "hard relation" olan bu bağlantıyı
        (her quiz_attempt mutlaka question_attempt içerir) doğrular.
        """
        qa   = tables.get("mdl_question_attempts", pd.DataFrame())
        atts = tables.get("mdl_quiz_attempts",     pd.DataFrame())

        if qa.empty or atts.empty:
            pytest.skip("Soru denemesi veya quiz attempt verisi yok")

        valid_uniqueids  = set(atts["uniqueid"].astype(int).tolist())
        orphan_qa = qa[~qa["questionusageid"].astype(int).isin(valid_uniqueids)]

        assert orphan_qa.empty, (
            f"{len(orphan_qa)} mdl_question_attempts satırının "
            f"mdl_quiz_attempts'te karşılığı yok (orphan FK):\n"
            f"Geçersiz questionusageid'ler: "
            f"{orphan_qa['questionusageid'].unique()[:5].tolist()}"
        )
