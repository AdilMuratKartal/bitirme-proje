"""
engine_pkg/setup.py — Statik referans tablolarının kurulumu (ReferenceBuilder).
Service pattern: tek sorumluluğu referans tabloları oluşturmak.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Dict, Optional

import numpy as np

from config import (
    CFG, COURSE_NAMES, TOPICS, COMPONENT_TYPE_MAP,
    COURSE_GRADE_SCHEMAS,
)
from enrollment_plan import build_enrollment_plan, enrollment_summary
import student_registry as _sr

from .context import SimContext
from .schedule import TimeCalc

try:
    from faker import Faker as _Faker
    _fi = _Faker("tr_TR")
    _Faker.seed(CFG.general.seed)

    class _FW:
        def first_name(self): return _fi.first_name()
        def last_name(self):  return _fi.last_name()
        def email(self):      return _fi.email()

    _fake = _FW()
except ImportError:
    from faker_lite import FakerLite
    _fake = FakerLite(seed=CFG.general.seed)


class ReferenceBuilder:
    """
    SimulationEngine başlatılırken çağrılan statik referans tablolarını kurar.
    Tüm _setup_* metotları bu sınıfta toplanır; SimulationEngine sadece build() çağırır.
    """

    def __init__(self, ctx: SimContext) -> None:
        self._ctx   = ctx
        self._store = ctx.store
        self._rng   = ctx.rng

    # ── Ortak kısayol ─────────────────────────────────────────────────
    def _add(self, table: str, row: dict) -> None:
        self._store.add(table, row)

    # ── Ana giriş ─────────────────────────────────────────────────────
    def build(self) -> None:
        """Tüm referans tablolarını sırayla kurar."""
        self._setup_users()
        self._setup_grade_categories()   # courses'dan önce: root id'leri hazırlanır
        self._setup_courses()
        self._setup_enrolments()
        self._setup_course_modules()
        self._setup_question_bank()
        self._setup_content_activity_types()
        self._setup_student_registry()
        print(
            f"   Referans tablolari hazir: "
            f"{CFG.general.n_students} ogrenci | "
            f"{CFG.general.n_courses} kurs | "
            f"{CFG.general.n_courses * CFG.general.n_modules_per_course} modul"
        )

    # ─────────────────────────────────────────────────────────────────
    # KULLANICI
    # ─────────────────────────────────────────────────────────────────
    def _setup_users(self) -> None:
        now_dt = TimeCalc.BASE + timedelta(weeks=CFG.general.n_weeks)
        for _, row in _sr.STUDENT_REGISTRY.iterrows():
            uid     = int(row["userid"])
            profile = _sr.get_profile(uid)
            la_mu, la_sigma = profile.lastaccess_days_ago
            days_ago = abs(float(self._rng.normal(la_mu, la_sigma)))
            self._add("mdl_user", {
                "id":          uid,
                "username":    f"user{uid:05d}",
                "firstname":   _fake.first_name(),
                "lastname":    _fake.last_name(),
                "email":       _fake.email(),
                "lastaccess":  TimeCalc.ts(now_dt - timedelta(days=days_ago)),
                "timecreated": TimeCalc.ts(TimeCalc.BASE - timedelta(days=30)),
            })

    # ─────────────────────────────────────────────────────────────────
    # NOT KATEGORİLERİ
    # ─────────────────────────────────────────────────────────────────
    def _setup_grade_categories(self) -> None:
        start_ts = TimeCalc.ts(TimeCalc.BASE)
        for course_id in range(1, CFG.general.n_courses + 1):
            schema = COURSE_GRADE_SCHEMAS.get(course_id, {})
            cats   = schema.get("categories", [])

            root_row = {
                "courseid":    course_id,
                "parent":      None,
                "depth":       1,
                "fullname":    "?",
                "aggregation": 13,
                "timecreated": start_ts,
            }
            self._add("mdl_grade_categories", root_row)
            root_id = root_row["id"]

            cat_map:      Dict[str, int] = {}
            cat_item_map: Dict[str, int] = {}
            for cat in cats:
                cat_row = {
                    "courseid":    course_id,
                    "parent":      root_id,
                    "depth":       2,
                    "fullname":    cat["name"],
                    "aggregation": cat["aggregation"],
                    "timecreated": start_ts,
                }
                self._add("mdl_grade_categories", cat_row)
                cat_map[cat["name"]] = cat_row["id"]

                # Her alt kategori için "category total" grade_item
                cat_item_row = {
                    "courseid":         course_id,
                    "categoryid":       root_id,
                    "itemname":         f"{cat['name']} Toplami",
                    "itemtype":         "category",
                    "itemmodule":       None,
                    "grademax":         float(cat["grademax"]),
                    "grademin":         0.0,
                    "gradepass":        float(cat["grademax"]) * 0.5,
                    "aggregationcoef":  cat["coef"],
                    "aggregationcoef2": 0.0,
                    "timecreated":      start_ts,
                }
                self._add("mdl_grade_items", cat_item_row)
                cat_item_map[cat["name"]] = cat_item_row["id"]

            self._ctx.grade_cat_ids[course_id]      = cat_map
            self._ctx.grade_cat_item_ids[course_id] = cat_item_map

    # ─────────────────────────────────────────────────────────────────
    # KURSLAR
    # ─────────────────────────────────────────────────────────────────
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
            self._add("mdl_grade_items", {
                "courseid":         i,
                "categoryid":       None,
                "itemname":         f"{name} - Genel Not",
                "itemtype":         "course",
                "itemmodule":       None,
                "grademax":         100.0,
                "grademin":         0.0,
                "gradepass":        50.0,
                "aggregationcoef":  0.0,
                "aggregationcoef2": 0.0,
                "timecreated":      start_ts,
            })
            self._ctx.quiz_index[i] = 0

    # ─────────────────────────────────────────────────────────────────
    # KAYIT SİSTEMİ (Enrollment)
    # ─────────────────────────────────────────────────────────────────
    def _setup_enrolments(self) -> None:
        start_ts = TimeCalc.ts(TimeCalc.BASE)
        end_ts   = TimeCalc.ts(TimeCalc.BASE + timedelta(weeks=CFG.general.n_weeks))

        enrol_ids: Dict[int, int] = {}
        for course_id in range(1, CFG.general.n_courses + 1):
            enrol_row = {
                "enrol": "manual", "courseid": course_id,
                "status": 0, "timecreated": start_ts,
            }
            self._add("mdl_enrol", enrol_row)
            enrol_ids[course_id] = enrol_row["id"]

        plan = build_enrollment_plan(_sr.STUDENT_REGISTRY, self._rng)
        for uid, course_ids in plan.items():
            for cid in course_ids:
                self._add("mdl_user_enrolments", {
                    "enrolid": enrol_ids[cid], "userid": uid,
                    "status": 0, "timestart": start_ts, "timeend": end_ts,
                })
        print(f"   {enrollment_summary(plan)}")

    # ─────────────────────────────────────────────────────────────────
    # KURS MODÜLLERİ
    # ─────────────────────────────────────────────────────────────────
    def _setup_course_modules(self) -> None:
        components = list(COMPONENT_TYPE_MAP.keys())
        for course_id in range(1, CFG.general.n_courses + 1):
            modules = []
            for seq, topic in enumerate(TOPICS, start=1):
                comp  = str(self._rng.choice(components))
                ctype = COMPONENT_TYPE_MAP[comp]
                row   = {
                    "course": course_id, "module": seq, "instance": 0,
                    "completion": 1, "added": TimeCalc.ts(TimeCalc.BASE),
                    "sequence": seq, "component": comp,
                    "content_type": ctype, "topic": topic,
                }
                self._add("mdl_course_modules", row)
                row["instance"] = row["id"]
                modules.append(row)
            self._ctx.course_modules[course_id] = modules

    # ─────────────────────────────────────────────────────────────────
    # SORU BANKASI
    # ─────────────────────────────────────────────────────────────────
    def _setup_question_bank(self) -> None:
        qtypes = ["multichoice", "truefalse", "shortanswer"]
        for course_id in range(1, CFG.general.n_courses + 1):
            topic_name = TOPICS[(course_id - 1) % len(TOPICS)]
            cat_row = {
                "name":   f"{COURSE_NAMES[course_id-1]} - Soru Bankasi",
                "parent": 0,
                "info":   topic_name,
            }
            self._add("mdl_question_categories", cat_row)
            cat_id = cat_row["id"]
            for q_seq in range(1, CFG.quiz.questions_per_quiz + 1):
                self._add("mdl_question", {
                    "category":    cat_id,
                    "name":        f"Soru {q_seq} - {topic_name}",
                    "qtype":       qtypes[q_seq % len(qtypes)],
                    "timecreated": TimeCalc.ts(TimeCalc.BASE),
                })

    # ─────────────────────────────────────────────────────────────────
    # ÖĞRENCİ KAYIT DEFTERİ
    # ─────────────────────────────────────────────────────────────────
    def _setup_student_registry(self) -> None:
        for _, row in _sr.STUDENT_REGISTRY.iterrows():
            self._add("student_registry", {
                "userid":       int(row["userid"]),
                "segment":      row["segment"],
                "label":        row["label"],
                "dropout_week": row["dropout_week"],
            })

    # ─────────────────────────────────────────────────────────────────
    # İÇERİK AKTİVİTE TİPLERİ + GRADE ITEMS + DERS TAKVİMİ
    # ─────────────────────────────────────────────────────────────────
    def _setup_content_activity_types(self) -> None:
        """
        Her kurs için lesson/scorm/h5p/forum/badge tabloları oluşturur.
        Tüm non-SCORM kurslar için lesson grade_item yaratılır:
          - lesson_category varsa → graded (kategori ile ilişkili)
          - lesson_category yoksa → ungraded (categoryid=None, aggregationcoef=0)
        mdl_event: lecture_days'den ders takvimi olayları eklenir.
        """
        start_ts      = TimeCalc.ts(TimeCalc.BASE)
        SCORM_COURSES = {4, 13}
        H5P_COURSES   = {5, 9, 14}

        for course_id in range(1, CFG.general.n_courses + 1):
            name   = COURSE_NAMES[course_id - 1]
            schema = COURSE_GRADE_SCHEMAS.get(course_id, {})
            cats   = schema.get("categories", [])

            def _cat_id(cat_name: Optional[str]) -> Optional[int]:
                if not cat_name:
                    return None
                return self._ctx.grade_cat_ids.get(course_id, {}).get(cat_name)

            def _coef(cat_name: Optional[str]) -> float:
                if not cat_name:
                    return 0.0
                return next((c["coef"] for c in cats if c["name"] == cat_name), 0.0)

            # ── Forum ─────────────────────────────────────────────────
            self._add("mdl_forum", {
                "course": course_id,
                "name":   f"{name} - Tartisma Forumu",
                "type":   "general", "timecreated": start_ts,
            })
            forum_cat_name = schema.get("forum_category")
            if forum_cat_name:
                f_gmax = float(schema.get("forum_grademax", 20.0))
                self._add("mdl_grade_items", {
                    "courseid": course_id, "categoryid": _cat_id(forum_cat_name),
                    "itemname": f"{name} - Forum Katilimi",
                    "itemtype": "mod", "itemmodule": "forum",
                    "grademax": f_gmax, "grademin": 0.0,
                    "gradepass": round(f_gmax * 0.5, 2),
                    "aggregationcoef": round(_coef(forum_cat_name), 5),
                    "aggregationcoef2": 0.0, "timecreated": start_ts,
                })

            # ── Lesson — SCORM kursları dışında tümüne; graded veya ungraded ──
            if course_id not in SCORM_COURSES:
                self._add("mdl_lesson", {
                    "course": course_id,
                    "name":   f"{name} - Ders Icerigi",
                    "timecreated": start_ts, "available": start_ts,
                })
                lesson_cat_name = schema.get("lesson_category")
                l_gmax = float(schema.get("lesson_grademax", 10.0))
                self._add("mdl_grade_items", {
                    "courseid":   course_id,
                    "categoryid": _cat_id(lesson_cat_name),   # None → ungraded
                    "itemname":   f"{name} - Ders Icerigi",
                    "itemtype":   "mod", "itemmodule": "lesson",
                    "grademax":   l_gmax, "grademin": 0.0,
                    "gradepass":  round(l_gmax * 0.5, 2),
                    "aggregationcoef":  round(_coef(lesson_cat_name), 5),
                    "aggregationcoef2": 0.0, "timecreated": start_ts,
                })

            # ── SCORM — sadece kurs 4 ve 13 ───────────────────────────
            if course_id in SCORM_COURSES:
                self._add("mdl_scorm", {
                    "course": course_id,
                    "name":   f"{name} - SCORM Paketi",
                    "timecreated": start_ts, "completionscorerequired": 70,
                })
                scorm_cat_name = schema.get("scorm_category")
                if scorm_cat_name:
                    s_gmax = float(schema.get("scorm_grademax", 40.0))
                    self._add("mdl_grade_items", {
                        "courseid": course_id, "categoryid": _cat_id(scorm_cat_name),
                        "itemname": f"{name} - SCORM Paketi",
                        "itemtype": "mod", "itemmodule": "scorm",
                        "grademax": s_gmax, "grademin": 0.0,
                        "gradepass": round(s_gmax * 0.5, 2),
                        "aggregationcoef": round(_coef(scorm_cat_name), 5),
                        "aggregationcoef2": 0.0, "timecreated": start_ts,
                    })

            # ── H5P — sadece kurs 5, 9, 14 ────────────────────────────
            if course_id in H5P_COURSES:
                self._add("mdl_h5pactivity", {
                    "course": course_id,
                    "name":   f"{name} - H5P Aktivitesi",
                    "timecreated": start_ts, "grademethod": 1,
                })
                h5p_cat_name = schema.get("h5p_category")
                if h5p_cat_name:
                    h_gmax = float(schema.get("h5p_grademax", 20.0))
                    self._add("mdl_grade_items", {
                        "courseid": course_id, "categoryid": _cat_id(h5p_cat_name),
                        "itemname": f"{name} - H5P Aktivitesi",
                        "itemtype": "mod", "itemmodule": "h5pactivity",
                        "grademax": h_gmax, "grademin": 0.0,
                        "gradepass": round(h_gmax * 0.5, 2),
                        "aggregationcoef": round(_coef(h5p_cat_name), 5),
                        "aggregationcoef2": 0.0, "timecreated": start_ts,
                    })

            # ── Badge ─────────────────────────────────────────────────
            self._add("mdl_badge", {
                "courseid": course_id,
                "name":     f"{name} - Tamamlama Rozeti",
                "status": 1, "timecreated": start_ts,
            })

            # ── Ders takvim olayları (lecture_days) ───────────────────
            sched_def = schema.get("schedule", {})
            for lday in sched_def.get("lecture_days", []):
                for week in range(1, CFG.general.n_weeks + 1):
                    lecture_dt = TimeCalc.week_start(week) + timedelta(days=int(lday), hours=9)
                    self._add("mdl_event", {
                        "userid":       0,
                        "courseid":     course_id,
                        "name":         f"{name} - Hafta {week} Ders",
                        "eventtype":    "course",
                        "timestart":    TimeCalc.ts(lecture_dt),
                        "timeduration": 5400,
                        "instance":     0,
                        "modulename":   "course",
                    })
