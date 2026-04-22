"""
engine.py — SimulationEngine v5.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Lokal kullanım:
    from engine import SimulationEngine
    engine = SimulationEngine()
    tables = engine.simulate_full_semester(weeks=14)

İleride cron job / webhook:
    engine.dispatch(QuizOpenEvent(week=8, course_id=3, quiz_id=12))

Tasarım prensipleri:
  - Her event handler bağımsız; yan etki = self._rows[tablo] listesine ekleme
  - Kural 3: Quiz giriş penceresi 18:00-20:00, max 60 dk attempt
  - Kural 4: Segment bazlı submit stratejisi
  - Kural 5: is_active_in_week() her event handler'da kontrol edilir
  - Kural 6: Not girişi duedate + 3-10 gün
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config import (
    CFG, COURSE_NAMES, TOPICS, COMPONENT_TYPE_MAP,
    QUESTION_STEP_STATES, SegmentProfile,
)
from events import (
    AssignmentOpenEvent, DropoutCheckEvent,
    GradingEvent, QuizOpenEvent, WeeklyActivityEvent,
)
from student_registry import (
    STUDENT_REGISTRY, get_profile, get_segment,
    is_active_in_week,
)

try:
    from faker import Faker as _Faker
    _fi = _Faker("tr_TR")
    _Faker.seed(CFG.general.seed)
    class _FW:
        def first_name(self):  return _fi.first_name()
        def last_name(self):   return _fi.last_name()
        def email(self):       return _fi.email()
    fake = _FW()
except ImportError:
    from faker_lite import FakerLite
    fake = FakerLite(seed=CFG.general.seed)


# ═════════════════════════════════════════════════════════════════
# YARDIMCI SINIFLAR
# ═════════════════════════════════════════════════════════════════

class TimeCalc:
    """
    Tüm zaman hesaplamaları bu sınıfta toplanır.
    Bağımsız static metotlar -> test edilmesi kolay, cron'a taşınabilir.
    """

    BASE = CFG.general.semester_start

    @staticmethod
    def week_start(week: int) -> datetime:
        """1-tabanlı hafta -> o haftanın Pazartesi 08:00."""
        return TimeCalc.BASE + timedelta(weeks=week - 1)

    @staticmethod
    def week_end(week: int) -> datetime:
        return TimeCalc.week_start(week) + timedelta(days=6, hours=23, minutes=59)

    @staticmethod
    def ts(dt: datetime) -> int:
        return int(dt.timestamp())

    @staticmethod
    def clamp(dt: datetime, lo: datetime, hi: datetime) -> datetime:
        return max(lo, min(dt, hi))

    # ── Kural 3: Quiz zamanlama ────────────────────────────────────
    @staticmethod
    def quiz_open_close(week: int, rng: np.random.Generator) -> Tuple[datetime, datetime]:
        """
        Quiz timeopen: o haftanın Salı–Perşembe arası rastgele bir saat.
        timeclose: timeopen + 24-48 saat (max 48h — Kural 3).
        """
        wstart     = TimeCalc.week_start(week)
        day_offset = rng.integers(1, 4)          # 1=Salı, 2=Çarş, 3=Perş
        hour_open  = rng.integers(8, 16)
        open_dt    = wstart + timedelta(days=int(day_offset), hours=int(hour_open))
        open_hours = rng.integers(24, 49)        # 24-48 saat açık
        close_dt   = open_dt + timedelta(hours=int(open_hours))
        return open_dt, close_dt

    @staticmethod
    def quiz_attempt_window(
        close_dt: datetime,
        profile: SegmentProfile,
        rng: np.random.Generator,
    ) -> Tuple[datetime, datetime]:
        """
        Kural 3: Öğrenci close_dt günü 18:00-20:00 arasında giriş yapar.
        Attempt süresi: profile.quiz_duration_range ile sınırlı, max 60 dk.
        timestart + duration <= timeclose zorunlu.
        """
        entry_day   = close_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        win_start   = entry_day + timedelta(hours=CFG.quiz.entry_window_start_h)
        win_end     = entry_day + timedelta(hours=CFG.quiz.entry_window_end_h)
        win_start   = TimeCalc.clamp(win_start, close_dt - timedelta(hours=2), close_dt - timedelta(minutes=5))
        win_end     = TimeCalc.clamp(win_end,   win_start + timedelta(minutes=1), close_dt - timedelta(minutes=1))

        start_ts    = win_start.timestamp()
        end_ts      = win_end.timestamp()
        start_dt    = datetime.fromtimestamp(float(rng.uniform(start_ts, end_ts)))

        lo, hi      = profile.quiz_duration_range
        desired_min = float(rng.uniform(lo, hi))
        max_by_close = (close_dt - start_dt).total_seconds() / 60
        dur_min     = min(desired_min, max_by_close, CFG.quiz.max_attempt_minutes)
        dur_min     = max(dur_min, 1.0)

        finish_dt   = start_dt + timedelta(minutes=dur_min)
        return start_dt, finish_dt, dur_min

    # ── Kural 4: Ödev teslim zamanlama ───────────────────────────
    @staticmethod
    def submit_time(
        strategy: str,
        open_dt:  datetime,
        due_dt:   datetime,
        rng:      np.random.Generator,
    ) -> Optional[datetime]:
        """
        Segment bazlı teslim zamanı. None = teslim etmedi.
        Kural 4:
          early        -> due_dt - (3-7 gün)
          last24h      -> due_dt - (0-24h), %70 son 2h
          panic        -> due_dt - (1-60 dk)
          panic_or_miss-> %50 None, yoksa due_dt - (1-5 dk)
        """
        if strategy == "early":
            days_before = float(rng.uniform(3, 8))
            dt = due_dt - timedelta(days=days_before)
            return TimeCalc.clamp(dt, open_dt, due_dt)

        if strategy == "last24h":
            if rng.random() < 0.70:   # %70 son 2 saat
                secs = float(rng.uniform(0, 7200))
            else:
                secs = float(rng.uniform(0, 86400))
            dt = due_dt - timedelta(seconds=secs)
            return TimeCalc.clamp(dt, open_dt, due_dt)

        if strategy == "panic":
            secs = float(rng.uniform(60, 3600))
            dt   = due_dt - timedelta(seconds=secs)
            return TimeCalc.clamp(dt, open_dt, due_dt)

        if strategy == "panic_or_miss":
            if rng.random() < 0.50:
                return None
            secs = float(rng.uniform(0, 300))
            dt   = due_dt - timedelta(seconds=secs)
            return TimeCalc.clamp(dt, open_dt, due_dt)

        return None   # bilinmeyen strateji -> teslim yok

    # ── Kural 6: Not gecikme tarihi ──────────────────────────────
    @staticmethod
    def grading_time(due_dt: datetime, rng: np.random.Generator) -> datetime:
        delay_days = int(rng.integers(3, 11))
        return due_dt + timedelta(days=delay_days)

    # ── Dirichlet zaman bütçesi (Kural 3: sorular) ────────────────
    @staticmethod
    def dirichlet_budget(
        n: int,
        total_seconds: float,
        rng: np.random.Generator,
    ) -> List[float]:
        """n parçaya toplam_seconds'u Dirichlet ile böl."""
        alpha = np.ones(n)
        fracs = rng.dirichlet(alpha)
        return (fracs * total_seconds).tolist()


class SegmentBehavior:
    """
    Segment profili + RNG -> davranışsal karar noktaları.
    Tek bir yerde toplandığı için test ve ayar kolaylaşır.
    """

    @staticmethod
    def should_skip_week(profile: SegmentProfile, rng: np.random.Generator) -> bool:
        return rng.random() < profile.missing_week_prob

    @staticmethod
    def weekly_click_count(profile: SegmentProfile, week: int, rng: np.random.Generator) -> int:
        mu, sigma  = profile.weekly_clicks_base
        decay      = profile.click_decay_per_week * (week - 1)
        adjusted   = max(mu - decay, 1.0)
        n          = int(rng.normal(adjusted, sigma))
        return max(n, 0)

    @staticmethod
    def random_action(profile: SegmentProfile, rng: np.random.Generator) -> str:
        actions = list(profile.action_weights.keys())
        weights = [profile.action_weights[a] for a in actions]
        idx     = int(rng.choice(len(actions), p=np.array(weights) / sum(weights)))
        return actions[idx]

    @staticmethod
    def random_component(rng: np.random.Generator) -> str:
        components = list(COMPONENT_TYPE_MAP.keys())
        return str(rng.choice(components))

    @staticmethod
    def complete_module(profile: SegmentProfile, rng: np.random.Generator) -> bool:
        return rng.random() < profile.completion_prob

    @staticmethod
    def quiz_score(profile: SegmentProfile, rng: np.random.Generator) -> float:
        mu, sigma = profile.quiz_score
        return float(np.clip(rng.normal(mu, sigma), 0, 100))

    @staticmethod
    def grade_value(profile: SegmentProfile, week: int, rng: np.random.Generator) -> float:
        mu, sigma  = profile.base_grade
        trend_mu, trend_sigma = profile.grade_trend_per_week
        trend      = trend_mu + float(rng.normal(0, trend_sigma))
        raw        = mu + trend * (week - 1)
        noisy      = float(rng.normal(raw, sigma))
        return float(np.clip(noisy, 0, 100))


# ═════════════════════════════════════════════════════════════════
# DÖNEM TAKVİMİ
# ═════════════════════════════════════════════════════════════════

@dataclass
class CourseSchedule:
    """Bir kursun dönem boyunca olay takvimi."""
    course_id:       int
    quiz_weeks:      List[int]       # Hangi haftalarda quiz var
    assign_weeks:    List[int]       # Hangi haftalarda ödev açılıyor
    assign_durations: List[int]      # Karşılık gelen açık kalma haftası (1-3)


def build_semester_schedule(n_courses: int, n_weeks: int) -> List[CourseSchedule]:
    """
    Her kurs için haftalık olay takvimi üretir.
    Quiz haftaları: tüm kurslar için Hafta 4, 8, 13 (±1 stagger).
    Ödev haftaları: Hafta 2, 6, 10 (±1 stagger), açık 2-3 hafta.
    Bu liste ileride config.py'ye taşınabilir.
    """
    schedules = []
    base_quiz_weeks   = [4, 8, 13]
    base_assign_weeks = [2, 6, 10]

    for cid in range(1, n_courses + 1):
        # Kurslar arası ±1 hafta kayma — aynı hafta tüm kursların aynı anda
        # sınav/ödev açması yerine doğal dağılım sağlar
        stagger = (cid - 1) % 2   # 0 veya 1

        q_weeks = [min(w + stagger, n_weeks) for w in base_quiz_weeks]
        a_weeks = [min(w + stagger, n_weeks - 2) for w in base_assign_weeks]
        a_durs  = [2, 2, 3]        # Açık kalma hafta sayısı

        schedules.append(CourseSchedule(
            course_id        = cid,
            quiz_weeks       = q_weeks,
            assign_weeks     = a_weeks,
            assign_durations = a_durs,
        ))

    return schedules


# ═════════════════════════════════════════════════════════════════
# ANA MOTOR
# ═════════════════════════════════════════════════════════════════

class SimulationEngine:
    """
    Event-based simülasyon motoru.

    Yerel kullanım:
        engine = SimulationEngine()
        tables = engine.simulate_full_semester(weeks=14)

    Tek event dispatch (cron/webhook için):
        engine.dispatch(QuizOpenEvent(week=8, course_id=3, quiz_id=12))
    """

    # Tablolar ve id sayaçları
    _TABLE_NAMES = [
        "mdl_user", "mdl_course", "mdl_grade_items",
        "mdl_assign", "mdl_assign_submission",
        "mdl_quiz", "mdl_quiz_attempts",
        "mdl_course_modules", "mdl_course_modules_completion",
        "mdl_logstore_standard_log",
        "mdl_grade_grades", "mdl_grade_grades_history",
        "mdl_question_categories", "mdl_question",
        "mdl_question_attempts", "mdl_question_attempt_steps",
        "student_registry",
    ]

    def __init__(self, seed: Optional[int] = None):
        self._rng    = np.random.default_rng(seed or CFG.general.seed)
        self._rows:  Dict[str, List[dict]] = {t: [] for t in self._TABLE_NAMES}
        self._ids:   Dict[str, int]        = {t: 0  for t in self._TABLE_NAMES}
        self._ids["_quiz_uniqueid_counter"] = 0
        self._ids["_assign_counter"]        = 0
        self._ids["_quiz_counter"]          = 0

        # Referans nesnelerin idleri (setup sonrası dolar)
        self._course_modules: Dict[int, List[dict]] = {}   # course_id -> modül listesi
        self._questions:      Dict[int, List[dict]] = {}   # quiz_id -> soru listesi
        self._assign_meta:    Dict[int, dict]       = {}   # assign_id -> {due_dt, ...}
        self._quiz_meta:      Dict[int, dict]       = {}   # quiz_id -> {open_dt, close_dt}
        self._pending_grading: List[GradingEvent]   = []   # Gelecek grading eventleri

        # Event handler kayıt tablosu
        self._handlers: Dict[type, Callable] = {
            WeeklyActivityEvent:  self._handle_weekly_activity,
            QuizOpenEvent:        self._handle_quiz_event,
            AssignmentOpenEvent:  self._handle_assignment_event,
            GradingEvent:         self._handle_grading_event,
            DropoutCheckEvent:    self._handle_dropout_check,
        }

        # ── S2/S3 modül tamamlama state (Faz 2 sürekliliği için) ────
        # Anahtar: (uid, course_id)
        # Değer: {'miss_count': int, 'prev_missed': bool}
        self._completion_state: Dict[Tuple[int, int], Dict] = {}

        # S3 kurs-başı tamamlama sayacı (her kurs bağımsız, raw_tables mantığıyla aynı)
        # Anahtar: (uid, course_id)  Değer: int
        self._s3_course_done: Dict[Tuple[int, int], int] = {}

        self._schedule = build_semester_schedule(
            CFG.general.n_courses, CFG.general.n_weeks
        )
        self._setup_reference_tables()

    # ─────────────────────────────────────────────────────────────
    # ID YÖNETİMİ
    # ─────────────────────────────────────────────────────────────
    def _next_id(self, table: str) -> int:
        self._ids[table] += 1
        return self._ids[table]

    def _add(self, table: str, row: dict) -> None:
        row.setdefault("id", self._next_id(table))
        self._rows[table].append(row)

    # ─────────────────────────────────────────────────────────────
    # REFERANS TABLOLARI KURULUMU  (bir kez çalışır)
    # ─────────────────────────────────────────────────────────────
    def _setup_reference_tables(self) -> None:
        """
        Statik referans tablolarını üret ve _rows'a kaydet.
        Bunlar Faz 2 / cron çalışmalarında dokunulmaz.
        """
        self._setup_users()
        self._setup_courses()
        self._setup_course_modules()
        self._setup_question_bank()
        self._setup_student_registry()
        print(f"   Referans tabloları hazır: "
              f"{CFG.general.n_students} öğrenci | "
              f"{CFG.general.n_courses} kurs | "
              f"{CFG.general.n_courses * CFG.general.n_modules_per_course} modül")

    def _setup_users(self) -> None:
        for _, row in STUDENT_REGISTRY.iterrows():
            uid     = int(row["userid"])
            profile = get_profile(uid)
            la_mu, la_sigma = profile.lastaccess_days_ago
            days_ago = abs(float(self._rng.normal(la_mu, la_sigma)))
            now_dt   = TimeCalc.BASE + timedelta(weeks=CFG.general.n_weeks)
            self._add("mdl_user", {
                "id":          uid,
                "username":    f"user{uid:05d}",
                "firstname":   fake.first_name(),
                "lastname":    fake.last_name(),
                "email":       fake.email(),
                "lastaccess":  TimeCalc.ts(now_dt - timedelta(days=days_ago)),
                "timecreated": TimeCalc.ts(TimeCalc.BASE - timedelta(days=30)),
            })

    def _setup_courses(self) -> None:
        start_ts = TimeCalc.ts(TimeCalc.BASE)
        end_ts   = TimeCalc.ts(TimeCalc.BASE + timedelta(weeks=CFG.general.n_weeks))
        for i, name in enumerate(COURSE_NAMES, start=1):
            tag = "".join(w[0] for w in name.split()[:3]).upper()
            self._add("mdl_course", {
                "id":          i,
                "shortname":   f"{tag}-{i:02d}",
                "fullname":    name,
                "startdate":   start_ts,
                "enddate":     end_ts,
                "timecreated": start_ts,
            })
            # grade item (kurs genel notu)
            self._add("mdl_grade_items", {
                "courseid":    i,
                "itemname":    f"{name} — Genel Not",
                "itemtype":    "course",
                "grademax":    100.0,
                "grademin":    0.0,
                "timecreated": start_ts,
            })

    def _setup_course_modules(self) -> None:
        # BUG-6 FIX: lokal mod_id=0 sayacı kaldırıldı; _add->_next_id ile
        # _ids["mdl_course_modules"] doğru tutulur → save/load_state ID çakışması olmaz.
        components = list(COMPONENT_TYPE_MAP.keys())
        for course_id in range(1, CFG.general.n_courses + 1):
            modules = []
            for seq, topic in enumerate(TOPICS, start=1):
                comp  = str(self._rng.choice(components))
                ctype = COMPONENT_TYPE_MAP[comp]
                row   = {           # "id" yok → _add, _next_id ile atar
                    "course":       course_id,
                    "module":       seq,
                    "instance":     0,          # _add sonrası row["id"] ile eşitlenir
                    "completion":   1,
                    "added":        TimeCalc.ts(TimeCalc.BASE),
                    "sequence":     seq,
                    "component":    comp,
                    "content_type": ctype,
                    "topic":        topic,
                }
                self._add("mdl_course_modules", row)   # _ids["mdl_course_modules"] burada artar
                row["instance"] = row["id"]            # instance = atanan mod id
                modules.append(row)
            self._course_modules[course_id] = modules

    def _setup_question_bank(self) -> None:
        """
        Her kurs için bir soru kategorisi ve N soru oluştur.
        Sorular tüm quizler arasında paylaşılır.
        BUG-6 FIX: Lokal q_id/cat_id sayaçları kaldırıldı; _add->_next_id kullanılıyor.
        cat_id, course_id sırası ile 1-1 örtüşür (_handle_quiz_event'teki cat_id=course_id varsayımı korunur).
        """
        qtypes = ["multichoice", "truefalse", "shortanswer"]
        for course_id in range(1, CFG.general.n_courses + 1):
            topic_name = TOPICS[(course_id - 1) % len(TOPICS)]
            cat_row = {        # "id" yok → _add atar (1'den başlayıp artar)
                "name":   f"{COURSE_NAMES[course_id-1]} — Soru Bankası",
                "parent": 0,
                "info":   topic_name,
            }
            self._add("mdl_question_categories", cat_row)
            cat_id = cat_row["id"]   # _add'in atadığı id; course_id ile örtüşür

            for q_seq in range(1, CFG.quiz.questions_per_quiz + 1):
                self._add("mdl_question", {   # "id" yok → _add atar
                    "category":    cat_id,
                    "name":        f"Soru {q_seq} — {topic_name}",
                    "qtype":       qtypes[q_seq % len(qtypes)],
                    "timecreated": TimeCalc.ts(TimeCalc.BASE),
                })

    def _setup_student_registry(self) -> None:
        for _, row in STUDENT_REGISTRY.iterrows():
            self._add("student_registry", {
                "userid":       int(row["userid"]),
                "segment":      row["segment"],
                "label":        row["label"],
                "dropout_week": row["dropout_week"],
            })

    # ─────────────────────────────────────────────────────────────
    # ANA SİMÜLASYON DÖNGÜSÜ
    # ─────────────────────────────────────────────────────────────
    def simulate_full_semester(self, weeks: int = 14) -> Dict[str, pd.DataFrame]:
        """
        14 haftalık dönemin tamamını sırayla simüle eder.
        Her hafta için uygun event'ler oluşturulup dispatch edilir.
        """
        print("=" * 68)
        print("  SimulationEngine — Tam Dönem Simülasyonu")
        print(f"  {CFG.general.n_students} öğrenci | "
              f"{CFG.general.n_courses} kurs | {weeks} hafta")
        print("=" * 68)

        for week in range(1, weeks + 1):
            print(f"\n  -- Hafta {week:02d} ----------------------------------")
            self.simulate_week(week)

        print("\n" + "=" * 68)
        print("  Simülasyon tamamlandı. Tablolar oluşturuluyor...")
        tables = self.to_dataframes()
        self._print_stats(tables)
        print("=" * 68)
        return tables

    def simulate_week(self, week: int) -> None:
        """
        Belirli bir haftanın tüm event'lerini işler.
        Cron modunda sadece bu metot çağrılır.
        """
        # 1. Haftalık aktivite (log + modül tamamlama)
        self.dispatch(WeeklyActivityEvent(week=week))

        # 2. Kurs bazlı quiz ve ödev event'leri
        for cs in self._schedule:
            if week in cs.quiz_weeks:
                self._ids["_quiz_counter"] += 1
                qid = self._ids["_quiz_counter"]
                open_dt, close_dt = TimeCalc.quiz_open_close(week, self._rng)
                evt = QuizOpenEvent(
                    week=week, course_id=cs.course_id,
                    quiz_id=qid, open_dt=open_dt, close_dt=close_dt,
                )
                self.dispatch(evt)

            idx = cs.assign_weeks.index(week) if week in cs.assign_weeks else -1
            if idx >= 0:
                self._ids["_assign_counter"] += 1
                aid = self._ids["_assign_counter"]
                open_weeks = cs.assign_durations[idx]
                open_dt    = TimeCalc.week_start(week)
                due_dt     = TimeCalc.week_start(week + open_weeks) - timedelta(hours=1)
                evt = AssignmentOpenEvent(
                    week=week, course_id=cs.course_id,
                    assign_id=aid, open_weeks=open_weeks,
                    open_dt=open_dt, due_dt=due_dt,
                )
                self.dispatch(evt)

        # 3. Bu hafta için tetiklenecek bekleyen grading event'leri
        # BUG-2 FIX: g.due_dt (ödev kapanış tarihi) değil, g.week (not girme haftası)
        # karşılaştırılır. Eski kod notları ödev kapanışıyla aynı anda giriyordu (Kural 6 ihlali).
        due_now = [g for g in self._pending_grading if g.week == week]
        for g_evt in due_now:
            self.dispatch(g_evt)
            self._pending_grading.remove(g_evt)

    def dispatch(self, event: Any) -> None:
        handler = self._handlers.get(type(event))
        if handler is None:
            raise ValueError(f"Bilinmeyen event tipi: {type(event)}")
        handler(event)

    # ─────────────────────────────────────────────────────────────
    # EVENT HANDLER'LAR
    # ─────────────────────────────────────────────────────────────

    def _handle_weekly_activity(self, evt: WeeklyActivityEvent) -> None:
        """
        Her hafta: log kayıtları + sıralı modül tamamlama.
        Kural 5: dropout kontrolü, hiyerarşik completion.
        Fix S2/S3: completion_state ile segment-aware tamamlama.
        Fix Log  : action->component eşleşmesi; objectid ve courseid anlamlı.
        """
        _S2_MAX_MISS = 4
        _S3_HARD_CAP = 7

        week = evt.week
        uids = STUDENT_REGISTRY["userid"].tolist()

        log_count = 0
        cmp_count = 0

        # ── Log için component havuzlarını bir kez oluştur ───────────
        # (Bu haftaya kadar oluşturulmuş assign/quiz var; module ise her zaman hazır)
        _VIEW_TYPES = {"İzleme", "Okuma"}
        view_pool: List[tuple]    = []  # (comp, obj_id, course_id)
        submit_pool: List[tuple]  = []
        attempt_pool: List[tuple] = []

        for cid_m, mods in self._course_modules.items():
            for m in mods:
                if COMPONENT_TYPE_MAP.get(m["component"], "") in _VIEW_TYPES:
                    view_pool.append((m["component"], m["id"], cid_m))
        for r in self._rows["mdl_assign"]:
            submit_pool.append(("mod_assign", r["id"], r["course"]))
        for r in self._rows["mdl_quiz"]:
            attempt_pool.append(("mod_quiz", r["id"], r["course"]))

        _fallback = view_pool or [
            (m["component"], m["id"], cid_m)
            for cid_m, mods in self._course_modules.items()
            for m in mods
        ]
        action_pool: Dict[str, List[tuple]] = {
            "view":    view_pool    or _fallback,
            "submit":  submit_pool  or _fallback,
            "attempt": attempt_pool or _fallback,
        }

        # RISK-1 FIX: Döngü dışında tek O(n) geçiş; döngü içi O(N²) lineer tarama yerine O(1)
        # Yeni tamamlamalar da döngü içinde cache'e eklenir (intra-week tutarlılık).
        _all_completions: Dict[int, set] = {}
        for _cr in self._rows["mdl_course_modules_completion"]:
            _all_completions.setdefault(_cr["userid"], set()).add(_cr["coursemoduleid"])

        for uid in uids:
            if not is_active_in_week(uid, week):
                continue

            profile   = get_profile(uid)
            seg       = get_segment(uid)
            # Fix 2: skip_week sadece LOG üretimini engeller.
            # Modül tamamlama (Kural 5) her zaman işletilir; aksi hâlde
            # should_skip_week=True olan haftalar hiyerarşiyi kırıp S1 dahil
            # tüm segmentleri bir sonraki modülde önkoşul bariyerine sürükler.
            skip_week = SegmentBehavior.should_skip_week(profile, self._rng)

            # ── Log kayıtları (action->component->objectid->courseid zinciri) ──
            # Yalnızca öğrenci o hafta sisteme girmişse üretilir.
            if not skip_week:
                n_clicks   = SegmentBehavior.weekly_click_count(profile, week, self._rng)
                week_start = TimeCalc.week_start(week)

                for _ in range(n_clicks):
                    day_off = float(self._rng.uniform(0, 7))
                    hour    = (
                        float(self._rng.choice([22, 23, 0, 1]))
                        if self._rng.random() < profile.late_night_ratio
                        else float(self._rng.uniform(8, 22))
                    )
                    log_dt = week_start + timedelta(days=day_off, hours=hour)

                    action = SegmentBehavior.random_action(profile, self._rng)
                    pool   = action_pool.get(action, _fallback)

                    if pool:
                        idx = int(self._rng.integers(0, len(pool)))
                        comp, objectid, log_course_id = pool[idx]
                    else:
                        comp          = SegmentBehavior.random_component(self._rng)
                        objectid      = None
                        log_course_id = int(self._rng.integers(1, CFG.general.n_courses + 1))

                    self._add("mdl_logstore_standard_log", {
                        "userid":      uid,
                        "courseid":    log_course_id,
                        "component":   comp,
                        "action":      action,
                        "objectid":    objectid,
                        "timecreated": TimeCalc.ts(log_dt),
                        "_week":       week,
                    })
                    log_count += 1

            # ── Modül tamamlama — her kurs için sıralı (Kural 5) ─────────
            # skip_week'ten BAĞIMSIZ: asenkron okuma modeli.
            for course_id, modules in self._course_modules.items():
                # BUG-1 FIX: raw_tables.py ile aynı formül kullanılarak bu haftanın
                # hedef modül listesi hesaplanır.
                # Formül: expected_week(seq) = max(1, int(seq * n_weeks / n_mods))
                # round() KULLANILMADI — round(7.5)=8 (banker's rounding) modül 7'yi atlardı.
                # n_mods(15) > n_weeks(14): hafta 1 → [1,2]; hafta 2-14 → [3]..[15].
                # Tüm 15 modül 14 haftada eksiksiz kapsanır, hiçbir modül atlanmaz.
                n_mods = len(modules)
                n_wks  = CFG.general.n_weeks
                target_seqs = [
                    s for s in range(1, n_mods + 1)
                    if max(1, int(s * n_wks / n_mods)) == week
                ]
                if not target_seqs:
                    continue

                # ZAMAN PARADOKSU YAMASI: Aynı haftada birden fazla modül düştüğünde
                # (örn. hafta 1 → [1,2]), her modül için bağımsız rastgele gap_days
                # üretilirse Modül 2'nin Modül 1'den önce timestamp alması mümkündür.
                # last_comp_dt tracker'ı hafta içi monotonluğu garanti eder:
                # her modülün comp_dt'si en az 1 saniye öncekinden büyük olur.
                last_comp_dt = TimeCalc.week_start(week)

                for target_seq in target_seqs:
                    mod    = modules[target_seq - 1]
                    mod_id = mod["id"]

                    # S3: Kurs başına hard cap — break ile kalan seqleri de atla
                    s3_key = (uid, course_id)
                    if seg == "S3" and self._s3_course_done.get(s3_key, 0) >= _S3_HARD_CAP:
                        break

                    # S2: per-(uid, course_id) state
                    cs_key = (uid, course_id)
                    cs = self._completion_state.setdefault(cs_key, {
                        "miss_count": 0, "prev_missed": False
                    })

                    # Hiyerarşik önkoşul (Kural 5) — RISK-1 FIX: O(1) cache araması
                    if target_seq > 1:
                        prev_mod_id = modules[target_seq - 2]["id"]
                        if prev_mod_id not in _all_completions.get(uid, set()):
                            continue  # Önkoşul yok -> atla (miss sayılmaz)

                    # Segment bazlı tamamlama kararı
                    if seg == "S1":
                        should_complete = True
                    elif seg == "S2":
                        # Kural S2: ardışık atlamadan sonra veya toplam 4 atlamaya
                        # ulaşınca bir sonraki modül ZORLA tamamlanır.
                        must_complete   = cs["prev_missed"] or cs["miss_count"] >= _S2_MAX_MISS
                        should_complete = must_complete or SegmentBehavior.complete_module(profile, self._rng)
                    else:
                        should_complete = SegmentBehavior.complete_module(profile, self._rng)

                    if not should_complete:
                        if seg == "S2":
                            cs["miss_count"]  += 1
                            cs["prev_missed"]  = True
                        continue

                    cs["prev_missed"] = False
                    if seg == "S2":
                        cs["miss_count"] = 0   # BUG-2 FIX: zorla tamamlama sonrası sayaç sıfırla → S2 karakteri korunur
                    if seg == "S3":
                        self._s3_course_done[s3_key] = self._s3_course_done.get(s3_key, 0) + 1

                    # Zaman sıkışması + monotonluk önlemi:
                    # candidate_dt: hafta başından rastgele gap_days ilerisi
                    # comp_dt: candidate ve (last_comp_dt + 1s) arasından büyük olan
                    # → Aynı haftada birden fazla modül tamamlanınca sıra bozulmaz.
                    gap_days     = float(self._rng.uniform(*profile.module_gap_days))
                    candidate_dt = TimeCalc.week_start(week) + timedelta(days=gap_days)
                    comp_dt      = max(last_comp_dt + timedelta(seconds=1), candidate_dt)
                    last_comp_dt = comp_dt

                    # RISK-1 FIX: Tamamlanan modülü anında cache'e ekle.
                    # Aynı hafta içinde ilerleyen iterasyonlar (farklı kurs / farklı uid)
                    # bu hafta tamamlananları prereq olarak görebilir.
                    _all_completions.setdefault(uid, set()).add(mod_id)

                    self._add("mdl_course_modules_completion", {
                        "coursemoduleid":  mod_id,
                        "userid":          uid,
                        "completionstate": 1,
                        "timemodified":    TimeCalc.ts(comp_dt),
                    })
                    cmp_count += 1

        print(f"     WeeklyActivity -> {log_count} log | {cmp_count} completion")

    def _handle_quiz_event(self, evt: QuizOpenEvent) -> None:
        """
        Kural 3: Quiz tanımı + attempt + soru adımları.
        Tüm zamanlama kısıtları TimeCalc.quiz_attempt_window() içinde uygulanır.
        """
        quiz_id   = evt.quiz_id
        course_id = evt.course_id
        open_dt   = evt.open_dt
        close_dt  = evt.close_dt

        # Quiz tanımı
        quiz_name = (
            f"Quiz {evt.quiz_id} — "
            f"{COURSE_NAMES[course_id - 1]} Hafta {evt.week}"
        )
        self._add("mdl_quiz", {
            "id":        quiz_id,
            "course":    course_id,
            "name":      quiz_name,
            "timeopen":  TimeCalc.ts(open_dt),
            "timeclose": TimeCalc.ts(close_dt),
            "timelimit": CFG.quiz.max_attempt_minutes * 60,
        })
        # Grade item (quiz)
        self._add("mdl_grade_items", {
            "courseid":    course_id,
            "itemname":    quiz_name,
            "itemtype":    "quiz",
            "grademax":    100.0,
            "grademin":    0.0,
            "timecreated": TimeCalc.ts(open_dt),
        })
        grade_item_id = self._ids["mdl_grade_items"]   # Fix: sonraki notta kullanılır

        # Sorular: course_id'e göre soru bankasından seç
        q_rows = self._rows["mdl_question"]
        # Her kurs için ayrı kategoride sorular var; basit index ile eşle
        cat_id  = course_id   # _setup_question_bank'ta cat_id = course_id sırasıyla
        q_pool  = [q for q in q_rows if q["category"] == cat_id]
        if len(q_pool) < CFG.quiz.questions_per_quiz:
            q_pool = q_pool * math.ceil(CFG.quiz.questions_per_quiz / max(len(q_pool), 1))
        questions = q_pool[: CFG.quiz.questions_per_quiz]

        attempt_count = 0
        qa_count      = 0

        # Fix 1: Quiz için de modül önkoşul önbelleği (assignment ile aynı mantık).
        # Döngü dışında O(n) tek geçiş; her uid için O(1) küme kesişimi.
        _quiz_course_mod_ids: set = {m["id"] for m in self._course_modules.get(course_id, [])}
        _quiz_uid_completed: Dict[int, set] = {}
        for _r in self._rows["mdl_course_modules_completion"]:
            _quiz_uid_completed.setdefault(_r["userid"], set()).add(_r["coursemoduleid"])

        for uid in STUDENT_REGISTRY["userid"].tolist():
            if not is_active_in_week(uid, evt.week):
                continue

            # Fix 1: Önkoşul — sınava girecek kurstan en az bir modül tamamlanmali
            if not (_quiz_uid_completed.get(uid, set()) & _quiz_course_mod_ids):
                continue  # Modül tamamlamadi -> sinava giremez

            profile = get_profile(uid)
            if self._rng.random() < profile.quiz_missing_prob:
                continue

            # Kural 3: Attempt zamanlaması
            try:
                start_dt, finish_dt, dur_min = TimeCalc.quiz_attempt_window(
                    close_dt, profile, self._rng
                )
            except Exception:
                continue

            # ── Fix: answered_ratio — kişisel cevaplama olasılığı ────
            ans_lo, ans_hi        = profile.answered_ratio
            personal_answer_prob  = float(self._rng.uniform(ans_lo, ans_hi))
            correct_lo, correct_hi = profile.correct_answer_prob

            # ── Fix: Fractions ÖNCE üretilir, sumgrades ondan hesaplanır ──
            total_secs = (finish_dt - start_dt).total_seconds()
            q_budgets  = TimeCalc.dirichlet_budget(len(questions), total_secs, self._rng)

            qa_buffer: List[tuple] = []  # (q, fraction, is_correct, q_budget)
            total_fraction = 0.0

            for q, q_budget in zip(questions, q_budgets):
                # answered_ratio: bu soruyu boş bırakma kontrolü
                if self._rng.random() > personal_answer_prob:
                    continue  # Boş bıraktı — attempt satırı üretilmez
                is_correct = self._rng.random() < float(self._rng.uniform(correct_lo, correct_hi))
                fraction   = 1.0 if is_correct else round(float(self._rng.uniform(0, 0.5)), 2)
                total_fraction += fraction
                qa_buffer.append((q, fraction, is_correct, q_budget))

            # sumgrades = (toplam_fraction / questions_per_quiz) * 100
            sumgrades = round((total_fraction / CFG.quiz.questions_per_quiz) * 100, 2)

            # BUG-4 FIX: Tüm sorular atlandıysa (answered_ratio çok düşük segmentlerde)
            # attempt kaydı oluşturma — sıfır question_attempt'li bir quiz_attempt
            # HKAR zincirini kırar ve mdl_grade_grades'e hayalet 0 notu yazar.
            if not qa_buffer:
                continue

            uniqueid   = self._next_id("_quiz_uniqueid_counter")
            attempt_id = self._next_id("mdl_quiz_attempts")
            self._rows["mdl_quiz_attempts"].append({
                "id":               attempt_id,
                "quiz":             quiz_id,
                "userid":           uid,
                "uniqueid":         uniqueid,
                "timestart":        TimeCalc.ts(start_dt),
                "timefinish":       TimeCalc.ts(finish_dt),
                "sumgrades":        sumgrades,
                "state":            "finished",
                "duration_minutes": round(dur_min, 2),
            })
            attempt_count += 1

            # ── Soru denemeleri + adımlar ────────────────────────────
            current_dt = start_dt
            for q, fraction, is_correct, q_budget in qa_buffer:
                qa_id = self._next_id("mdl_question_attempts")
                qa_dt = TimeCalc.clamp(
                    current_dt + timedelta(seconds=q_budget * 0.1),
                    current_dt,
                    finish_dt - timedelta(seconds=1),
                )
                self._rows["mdl_question_attempts"].append({
                    "id":                qa_id,
                    "questionusageid":   uniqueid,
                    "questionid":        q["id"],
                    "userid":            uid,
                    "responsesummary":   "Yanıt" if is_correct else "",
                    "rightanswer":       "Doğru",
                    "fraction":          fraction,
                    "timecreated":       TimeCalc.ts(qa_dt),
                })
                qa_count += 1

                # BUG-3 FIX ek: n_steps, mevcut q_budget'ın izin verdiği
                # maksimum tam-saniyeye kırpılır. Böylece Dirichlet fraksiyonları
                # ne kadar küçük olursa olsun her adım en az 1 tam saniye alır.
                n_steps_raw = int(self._rng.integers(*profile.steps_per_question))
                max_steps   = max(1, int(q_budget * 0.9))
                n_steps     = min(n_steps_raw, max_steps)
                s_budgets   = TimeCalc.dirichlet_budget(n_steps, q_budget * 0.9, self._rng)

                for s_idx, s_sec in enumerate(s_budgets):
                    is_final    = (s_idx == n_steps - 1)
                    state_label = (
                        "gradedright" if (is_final and is_correct)
                        else "gradedwrong" if is_final
                        else str(self._rng.choice(QUESTION_STEP_STATES[:-2]))
                    )
                    # BUG-3 FIX ek: alt sınır 500ms → 1s.
                    # int(timestamp) dönüşümünde 500ms sıfıra iner; iki ardışık
                    # adım aynı int-saniyeye düşer ve monotonluk ihlal edilir.
                    step_dt = TimeCalc.clamp(
                        current_dt + timedelta(seconds=s_sec),
                        current_dt + timedelta(seconds=1),
                        finish_dt  - timedelta(seconds=1),
                    )
                    self._add("mdl_question_attempt_steps", {
                        "questionattemptid": qa_id,
                        "state":             state_label,
                        "timecreated":       TimeCalc.ts(step_dt),
                    })
                    current_dt = step_dt

                # BUG-3 FIX: q_budget tekrar eklenmez.
                # Step döngüsü current_dt'yi zaten ilerletmiştir (toplam ~q_budget*0.9).
                # Buraya q_budget daha eklenmesi çift sayıma yol açar; tüm sonraki
                # adımlar finish_dt-1s'e sıkışır ve timecreated monotonluğu bozulur.

            # ── Fix: Quiz notunu grade_grades + grade_grades_history'e ekle ──
            # Kural 6: not girişi quiz kapandıktan 3-10 gün sonra
            if self._rng.random() >= profile.grade_missing_prob:
                note_dt    = TimeCalc.grading_time(close_dt, self._rng)
                grade_base = {
                    "userid":       uid,
                    "itemid":       grade_item_id,
                    "finalgrade":   sumgrades,
                    "timemodified": TimeCalc.ts(note_dt),
                }
                self._add("mdl_grade_grades", grade_base)
                self._add("mdl_grade_grades_history", {**grade_base, "source": "teacher"})

        print(f"     QuizEvent(course={course_id}, quiz={quiz_id}) -> "
              f"{attempt_count} attempt | {qa_count} soru denemesi")

    def _handle_assignment_event(self, evt: AssignmentOpenEvent) -> None:
        """
        Kural 4: Ödev tanımı + segment bazlı teslimler.
        Kural 5: dropout kontrolü.
        Kural 6: GradingEvent planlanır -> _pending_grading.
        """
        assign_id = evt.assign_id
        course_id = evt.course_id
        open_dt   = evt.open_dt
        due_dt    = evt.due_dt

        assign_name = (
            f"Ödev {assign_id} — "
            f"{COURSE_NAMES[course_id - 1]} Hafta {evt.week}"
        )
        self._add("mdl_assign", {
            "id":                          assign_id,
            "course":                      course_id,
            "name":                        assign_name,
            "duedate":                     TimeCalc.ts(due_dt),
            "allowsubmissionsfromdate":    TimeCalc.ts(open_dt),
            "timeclose":                   TimeCalc.ts(due_dt),
        })
        # grade item (ödev)
        self._add("mdl_grade_items", {
            "courseid":    course_id,
            "itemname":    assign_name,
            "itemtype":    "assign",
            "grademax":    100.0,
            "grademin":    0.0,
            "timecreated": TimeCalc.ts(open_dt),
        })
        # BUG-5 FIX: grade_item_id'yi string eşleşmesi yerine doğrudan kaydet.
        # "Ödev 1" substring'i "Ödev 10"u da yakalar — FK yanlış tabloya bağlanırdı.
        _grade_item_id = self._ids["mdl_grade_items"]

        # Fix 3: Döngü dışında uid -> tamamlanan modül id seti önbelleği
        # O(n) tek geçiş; döngü içi her uid için O(|completion_table|) taramadan kaçınır.
        _course_mod_ids: set = {m["id"] for m in self._course_modules.get(course_id, [])}
        _uid_completed: Dict[int, set] = {}
        for _r in self._rows["mdl_course_modules_completion"]:
            _uid_completed.setdefault(_r["userid"], set()).add(_r["coursemoduleid"])

        sub_count = 0
        for uid in STUDENT_REGISTRY["userid"].tolist():
            if not is_active_in_week(uid, evt.week):
                continue
            if not is_active_in_week(uid, evt.week + evt.open_weeks):
                continue  # Dropout teslim penceresinin ortasında gerçekleşebilir

            # Fix 3: Önkoşul — öğrenci bu kursta en az bir modül tamamlamış olmalı
            if not (_uid_completed.get(uid, set()) & _course_mod_ids):
                continue  # Hiç modül tamamlanmamış -> teslim yapamaz

            profile = get_profile(uid)
            sub_dt  = TimeCalc.submit_time(
                profile.submit_strategy, open_dt, due_dt, self._rng
            )
            if sub_dt is None:
                continue   # Kural 4: panic_or_miss -> teslim yok

            # Kural 4: timeclose'u geç teslim KABUL EDİLMEZ
            if sub_dt > due_dt:
                continue

            delay_h = (sub_dt - open_dt).total_seconds() / 3600

            self._add("mdl_assign_submission", {
                "userid":       uid,
                "assignment":   assign_id,
                "timemodified": TimeCalc.ts(sub_dt),
                "status":       "submitted",
                "delay_hours":  round(delay_h, 2),
            })
            sub_count += 1

        # BUG-5 FIX: item_id -> _assign_meta'ya kaydet (string lookup yerine O(1) sözlük).
        # BUG-7 FIX: grading_dt tek seferlik hesaplanır ve GradingEvent'e gömülür;
        #            _handle_grading_event farklı RNG state'iyle ikinci kez hesaplamaz.
        grading_dt = TimeCalc.grading_time(due_dt, self._rng)
        self._assign_meta[assign_id] = {
            "item_id":    _grade_item_id,
            "due_dt":     due_dt,
        }
        self._pending_grading.append(GradingEvent(
            week       = self._week_of(grading_dt),
            assign_id  = assign_id,
            due_dt     = due_dt,
            grading_dt = grading_dt,   # BUG-7: artık event içinde taşınıyor
        ))

        print(f"     AssignEvent(course={course_id}, assign={assign_id}) -> "
              f"{sub_count} teslim | grading Hafta {self._week_of(grading_dt)}")

    def _handle_grading_event(self, evt: GradingEvent) -> None:
        """
        Kural 6: Teslim yapan öğrencilerin notlarını duedate + 3-10 gün sonra gir.
        BUG-5 FIX: item_id artık _assign_meta'dan O(1) alınır; "Ödev 1" substring'i
                   "Ödev 10" ile eşleşip yanlış FK'ye bağlanma riski ortadan kalktı.
        BUG-7 FIX: note_dt, evt.grading_dt'den gelir — ikinci RNG çağrısı yok,
                   zaman paradoksu imkânsız.
        """
        # BUG-5 FIX: _assign_meta sözlüğünden doğrudan lookup
        meta = self._assign_meta.get(evt.assign_id)
        if meta is None:
            return   # Assign event henüz işlenmemişse (cron ilk çalışma) sessizce atla

        item_id    = meta["item_id"]
        graded     = 0
        # BUG-7 FIX: grading_dt event'te taşınıyor, burada yeniden hesaplanmıyor
        note_dt_ts = TimeCalc.ts(evt.grading_dt)

        # O ödevi teslim eden öğrenciler
        subs = [
            r for r in self._rows["mdl_assign_submission"]
            if r["assignment"] == evt.assign_id
        ]

        for sub in subs:
            uid     = sub["userid"]
            profile = get_profile(uid)
            if self._rng.random() < profile.grade_missing_prob:
                continue

            grade = SegmentBehavior.grade_value(profile, evt.week, self._rng)
            base  = {
                "userid":       uid,
                "itemid":       item_id,
                "finalgrade":   round(grade, 2),
                "timemodified": note_dt_ts,
            }
            self._add("mdl_grade_grades", base)
            self._add("mdl_grade_grades_history", {**base, "source": "teacher"})
            graded += 1

        print(f"     GradingEvent(assign={evt.assign_id}) -> {graded} not girildi")

    def _handle_dropout_check(self, evt: DropoutCheckEvent) -> None:
        dropped = STUDENT_REGISTRY[
            STUDENT_REGISTRY["dropout_week"] == evt.week
        ]
        print(f"     DropoutCheck Hafta {evt.week}: {len(dropped)} öğrenci ayrıldı")

    # ─────────────────────────────────────────────────────────────
    # YARDIMCILAR
    # ─────────────────────────────────────────────────────────────
    def _week_of(self, dt: datetime) -> int:
        diff = (dt - TimeCalc.BASE).days
        return max(1, min(int(diff // 7) + 1, CFG.general.n_weeks))

    def _print_stats(self, tables: Dict[str, pd.DataFrame]) -> None:
        total = 0
        print(f"\n   {'Tablo':<48}  {'Satır':>10}")
        print(f"   {'-'*48}  {'-'*10}")
        for name in sorted(tables):
            n = len(tables[name])
            total += n
            print(f"   {name:<48}  {n:>10,}")
        print(f"   {'-'*48}  {'-'*10}")
        print(f"   {'TOPLAM':<48}  {total:>10,}")

    # ─────────────────────────────────────────────────────────────
    # ÇIKTI
    # ─────────────────────────────────────────────────────────────
    def to_dataframes(self) -> Dict[str, pd.DataFrame]:
        """
        İç liste yapısını pandas DataFrame'lere çevirir.
        pipeline.py bu metodu çağırarak CSV'lere yazar.
        """
        frames: Dict[str, pd.DataFrame] = {}
        for name in self._TABLE_NAMES:
            rows = self._rows.get(name, [])
            if rows:
                df = pd.DataFrame(rows)
                # id sütununu ilk sıraya getir
                if "id" in df.columns:
                    cols = ["id"] + [c for c in df.columns if c != "id"]
                    df   = df[cols]
                frames[name] = df
            else:
                frames[name] = pd.DataFrame()
        return frames

    # ─────────────────────────────────────────────────────────────
    # STATE PERSISTENCE  (Faz 2 / cron sürekliliği)
    # ─────────────────────────────────────────────────────────────
    def save_state(self, path: str = "output/engine_state.json") -> None:
        """
        Motor durumunu JSON dosyasına yazar.
        Faz 2: Render.com cron job'lar arası süreklilik için.
        Kaydedilen alanlar:
          - _ids          : tablo id sayaçları
          - _completion_state : S2 miss sayaçları ve prev_missed bayrakları
          - _s3_course_done   : S3 kurs bazı tamamlama sayaçları
          - _pending_grading  : henüz işlenmemiş GradingEvent kuyruğu
        """
        import json
        from pathlib import Path

        _FMT = "%Y-%m-%dT%H:%M:%S"   # RISK-4 FIX: explicit format, TZ-agnostic
        state = {
            "ids": self._ids,
            "completion_state": {
                f"{k[0]},{k[1]}": v
                for k, v in self._completion_state.items()
            },
            "s3_course_done": {
                f"{k[0]},{k[1]}": v
                for k, v in self._s3_course_done.items()
            },
            # RISK-2 FIX: _assign_meta kayıt altına alınıyor.
            # Cron restart sonrası _handle_grading_event item_id'yi burada bulur.
            "assign_meta": {
                str(aid): {
                    "item_id": v["item_id"],
                    "due_dt":  v["due_dt"].strftime(_FMT),
                }
                for aid, v in self._assign_meta.items()
            },
            "pending_grading": [
                {
                    "week":       g.week,
                    "assign_id":  g.assign_id,
                    "due_dt":     g.due_dt.strftime(_FMT),       # RISK-4 FIX
                    "grading_dt": g.grading_dt.strftime(_FMT),   # BUG-7: yeni alan
                }
                for g in self._pending_grading
            ],
        }
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        print(f"   State kaydedildi -> {p}")

    def load_state(self, path: str = "output/engine_state.json") -> None:
        """
        Önceki cron çalışmasından motor durumunu yükler.
        Dosya yoksa sessizce devam eder (ilk çalışmada güvenli).
        Faz 2: simulate_week() çağrılmadan önce çağrılmalı.
        """
        import json
        from pathlib import Path

        p = Path(path)
        if not p.exists():
            return

        with open(p, encoding="utf-8") as f:
            state = json.load(f)

        _FMT = "%Y-%m-%dT%H:%M:%S"   # RISK-4 FIX: explicit format, TZ-safe

        # id sayaçlarını geri yükle
        self._ids.update({k: int(v) for k, v in state.get("ids", {}).items()})

        # S2 completion state
        for k_str, v in state.get("completion_state", {}).items():
            uid, cid = map(int, k_str.split(","))
            self._completion_state[(uid, cid)] = {
                "miss_count":  int(v.get("miss_count", 0)),
                "prev_missed": bool(v.get("prev_missed", False)),
            }

        # S3 kurs bazı sayaçlar
        for k_str, v in state.get("s3_course_done", {}).items():
            uid, cid = map(int, k_str.split(","))
            self._s3_course_done[(uid, cid)] = int(v)

        # RISK-2 FIX: _assign_meta geri yükle
        for k_str, v in state.get("assign_meta", {}).items():
            self._assign_meta[int(k_str)] = {
                "item_id": int(v["item_id"]),
                "due_dt":  datetime.strptime(v["due_dt"], _FMT),
            }

        # Bekleyen GradingEvent kuyruğu — RISK-4 + BUG-7 FIX
        for g_dict in state.get("pending_grading", []):
            self._pending_grading.append(GradingEvent(
                week       = int(g_dict["week"]),
                assign_id  = int(g_dict["assign_id"]),
                due_dt     = datetime.strptime(g_dict["due_dt"],     _FMT),
                grading_dt = datetime.strptime(g_dict["grading_dt"], _FMT),
            ))

        print(f"   State yüklendi <- {p}")

    def load_rows_from_csv(self, out_dir: str = "output") -> None:
        """
        RISK-2 FIX: Cron restart sonrası transaction tablolarını CSV'den _rows'a yükler.
        Faz 2'de load_state() ile birlikte çağrılmalıdır; aksi takdirde
        _uid_completed / _all_completions önbellekleri boş kalır ve tüm öğrenciler
        "modül tamamlamadı" sayılarak quiz/ödev önkoşulunu geçemez.

        Cron kullanımı:
            engine = SimulationEngine()
            engine.load_state("output/engine_state.json")
            engine.load_rows_from_csv("output")
            engine.simulate_week(current_week)
            engine.save_state("output/engine_state.json")
        """
        import pandas as pd
        from pathlib import Path

        # Yalnızca önkoşul kontrolü ve not hesabını etkileyen tablolar yüklenir.
        # Referans tablolar (_setup_reference_tables tarafından zaten kurulur) atlanır.
        _TRANSACTION_TABLES = [
            "mdl_course_modules_completion",   # onkosul kontrolleri icin okumasi GEREKIYOR
            "mdl_assign_submission",           # GradingEvent not hesabi icin okumasi GEREKIYOR
            # Asagidaki tablolar hicbir handler tarafindan OKUNMUYOR (sadece yaziliyor).
            # Render.com'da 14 hafta sonra onlari yeniden yuklemek OOM'a sebep olur.
            # Cron modunda sadece yeni haftanin verisi self._rows'a yazilir, gecmis satira gerek yok.
            # "mdl_quiz_attempts",
            # "mdl_question_attempts",
            # "mdl_question_attempt_steps",
            # "mdl_logstore_standard_log",
            # "mdl_grade_grades",
            # "mdl_grade_grades_history",
        ]
        raw     = Path(out_dir) / "raw_tables"
        loaded  = 0
        skipped = 0
        for tname in _TRANSACTION_TABLES:
            path = raw / f"{tname}.csv"
            if path.exists():
                df = pd.read_csv(path)
                # NaN içeren satırları dict'e çevirince None kalır — bu kabul edilebilir
                self._rows[tname] = df.where(pd.notna(df), other=None).to_dict("records")
                loaded += 1
            else:
                skipped += 1
        print(f"   load_rows_from_csv: {loaded} tablo yuklendi, {skipped} atland <- {raw}")
