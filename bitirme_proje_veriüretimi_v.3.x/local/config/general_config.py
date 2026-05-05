"""
config/general_config.py — Genel Parametreler, Tablo Şemaları, MasterConfig
"""

from dataclasses import dataclass, field
from typing import Dict, List
import datetime

from .segments import SegmentProfile, SEGMENT_PROFILES, SEGMENT_RATIOS, SEGMENT_LABELS


# ─────────────────────────────────────────────────────────────────
# GENEL PARAMETRELER
# ─────────────────────────────────────────────────────────────────
@dataclass
class GeneralConfig:
    seed:                  int  = 43
    n_students:            int  = 1000
    n_weeks:               int  = 14
    n_courses:             int  = 15
    n_modules_per_course:  int  = 15
    n_quizzes_per_course:  int  = 3
    n_assignments_per_course: int = 5
    n_lookback:            int  = 3
    output_dir:            str  = "output"
    db_path:               str  = "output/moodle_synthetic.db"
    locale:                str  = "tr_TR"
    semester_start: datetime.datetime = field(
        default_factory=lambda: datetime.datetime(2024, 2, 5, 8, 0, 0)
    )


@dataclass
class QuizConfig:
    max_open_hours:         int = 48
    entry_window_start_h:   int = 18
    entry_window_end_h:     int = 20
    max_attempt_minutes:    int = 60
    questions_per_quiz:     int = 10


@dataclass
class AssignmentConfig:
    min_open_weeks: int = 1
    max_open_weeks: int = 3


# ─────────────────────────────────────────────────────────────────
# KURS VE KONU LİSTELERİ
# ─────────────────────────────────────────────────────────────────
COURSE_NAMES: List[str] = [
    "Yazılım Geliştirme Temelleri",
    "Veri Yapıları ve Algoritmalar",
    "Nesne Yönelimli Programlama",
    "Veritabanı Yönetim Sistemleri",
    "Web Teknolojileri",
    "İşletim Sistemleri",
    "Bilgisayar Ağları",
    "Yazılım Mühendisliği",
    "Makine Öğrenmesi",
    "Yapay Zeka",
    "Siber Güvenlik",
    "Mobil Uygulama Geliştirme",
    "Bulut Bilişim",
    "Veri Analitiği",
    "İnsan-Bilgisayar Etkileşimi",
]

TOPICS: List[str] = [
    "Temel Kavramlar",
    "Değişkenler ve Veri Tipleri",
    "Kontrol Akışı",
    "Döngüler",
    "Fonksiyonlar",
    "Listeler ve Diziler",
    "Sözlükler ve Kümeler",
    "Nesne Yönelimli Programlama",
    "Hata Yönetimi",
    "Dosya İşlemleri",
    "Modüller ve Paketler",
    "Veritabanı Erişimi",
    "Web API Kullanımı",
    "Test ve Debugging",
    "Proje Uygulaması",
]

# ─────────────────────────────────────────────────────────────────
# TABLO ŞEMALARI  (ERD tam sütun listesi)
# ─────────────────────────────────────────────────────────────────
MDL_SCHEMA: Dict[str, List[str]] = {
    "mdl_user":                      ["id", "username", "firstname", "lastname",
                                      "email", "lastaccess", "timecreated"],
    "mdl_course":                    ["id", "shortname", "fullname", "startdate",
                                      "enddate", "timecreated"],
    "mdl_grade_items":               ["id", "courseid", "categoryid", "itemname",
                                      "itemtype", "itemmodule", "grademax", "grademin",
                                      "gradepass", "aggregationcoef", "aggregationcoef2",
                                      "timecreated"],
    "mdl_grade_categories":          ["id", "courseid", "parent", "depth",
                                      "fullname", "aggregation", "timecreated"],
    "mdl_course_completions":        ["id", "userid", "course",
                                      "timeenrolled", "timecompleted", "reaggregate"],
    "mdl_grade_grades":              ["id", "userid", "itemid", "finalgrade",
                                      "timemodified"],
    "mdl_grade_grades_history":      ["id", "userid", "itemid", "finalgrade",
                                      "timemodified", "source"],
    "mdl_assign":                    ["id", "course", "name", "duedate",
                                      "allowsubmissionsfromdate", "timeclose"],
    "mdl_assign_submission":         ["id", "userid", "assignment", "timemodified",
                                      "status", "delay_hours"],
    "mdl_logstore_standard_log":     ["id", "userid", "courseid", "component",
                                      "action", "objectid", "timecreated"],
    "mdl_quiz":                      ["id", "course", "name", "timeopen",
                                      "timeclose", "timelimit"],
    "mdl_quiz_attempts":             ["id", "quiz", "userid", "uniqueid",
                                      "timestart", "timefinish", "sumgrades",
                                      "state", "duration_minutes"],
    "mdl_course_modules":            ["id", "course", "module", "instance",
                                      "completion", "added", "sequence",
                                      "component", "content_type", "topic"],
    "mdl_course_modules_completion": ["id", "coursemoduleid", "userid",
                                      "completionstate", "timemodified"],
    "mdl_question_categories":       ["id", "name", "parent", "info"],
    "mdl_question":                  ["id", "category", "name", "qtype",
                                      "timecreated"],
    "mdl_question_attempts":         ["id", "questionusageid", "questionid",
                                      "userid", "responsesummary", "rightanswer",
                                      "fraction", "timecreated"],
    "mdl_question_attempt_steps":    ["id", "questionattemptid", "state",
                                      "timecreated"],
    "mdl_enrol":               ["id", "enrol", "courseid", "status", "timecreated"],
    "mdl_user_enrolments":     ["id", "enrolid", "userid", "status",
                                "timestart", "timeend"],
    "mdl_event":               ["id", "userid", "courseid", "name", "eventtype",
                                "timestart", "timeduration", "instance", "modulename"],
    "mdl_forum":               ["id", "course", "name", "type", "timecreated"],
    "mdl_forum_discussions":   ["id", "forum", "course", "userid", "name",
                                "timecreated"],
    "mdl_forum_posts":         ["id", "discussion", "userid", "message",
                                "timecreated", "wordcount"],
    "mdl_lesson":              ["id", "course", "name", "timecreated", "available"],
    "mdl_lesson_attempts":     ["id", "lessonid", "userid", "correct", "timeseen"],
    "mdl_scorm":               ["id", "course", "name", "timecreated",
                                "completionscorerequired"],
    "mdl_h5pactivity":         ["id", "course", "name", "timecreated", "grademethod"],
    "mdl_badge":               ["id", "courseid", "name", "status", "timecreated"],
    "mdl_badge_issued":        ["id", "badgeid", "userid", "uniquehash", "dateissued"],
}

COMPONENT_TYPE_MAP: Dict[str, str] = {
    "mod_url":             "İzleme",
    "mod_lesson":          "İzleme",
    "mod_bigbluebuttonbn": "İzleme",
    "mod_resource":        "Okuma",
    "mod_page":            "Okuma",
    "mod_book":            "Okuma",
    "mod_folder":          "Okuma",
    "mod_assign":          "Ödev",
    "mod_quiz":            "Ödev",
    "mod_workshop":        "Ödev",
    "mod_forum":           "Forum",
}

QUESTION_STEP_STATES: List[str] = [
    "todo", "invalid", "complete", "needsgrading",
    "gradedwrong", "gradedright", "gradedpartial",
]

CONTENT_TYPE_THRESHOLDS: Dict[str, float] = {
    "İzleme": 0.70,
    "Okuma":  0.55,
    "Ödev":   0.40,
    "Forum":  0.30,
}

# ─────────────────────────────────────────────────────────────────
# GEÇMİŞ / GELECEK EŞIK
# ─────────────────────────────────────────────────────────────────
FUTURE_CUTOFF_WEEK: int = 10

# ─────────────────────────────────────────────────────────────────
# ÇIKTI ŞEMALARI
# ─────────────────────────────────────────────────────────────────
@dataclass
class MIMOTargetSchema:
    risk_score_col:      str = "y_risk_score"
    predicted_grade_col: str = "y_predicted_grade"


@dataclass
class HKARTargetSchema:
    topic_status_col:        str = "topic_status"
    recommended_content_col: str = "recommended_content"


# ─────────────────────────────────────────────────────────────────
# ANA CONFIG
# ─────────────────────────────────────────────────────────────────
@dataclass
class MasterConfig:
    general:            GeneralConfig             = field(default_factory=GeneralConfig)
    quiz:               QuizConfig                = field(default_factory=QuizConfig)
    assignment:         AssignmentConfig          = field(default_factory=AssignmentConfig)
    mimo_target:        MIMOTargetSchema          = field(default_factory=MIMOTargetSchema)
    hkar_target:        HKARTargetSchema          = field(default_factory=HKARTargetSchema)
    schema:             Dict[str, List[str]]      = field(default_factory=lambda: MDL_SCHEMA)
    topics:             List[str]                 = field(default_factory=lambda: TOPICS)
    course_names:       List[str]                 = field(default_factory=lambda: COURSE_NAMES)
    component_map:      Dict[str, str]            = field(default_factory=lambda: COMPONENT_TYPE_MAP)
    content_thresholds: Dict[str, float]          = field(default_factory=lambda: CONTENT_TYPE_THRESHOLDS)
    segment_profiles:   Dict[str, SegmentProfile] = field(default_factory=lambda: SEGMENT_PROFILES)
    segment_ratios:     Dict[str, float]          = field(default_factory=lambda: SEGMENT_RATIOS)
    segment_labels:     Dict[str, str]            = field(default_factory=lambda: SEGMENT_LABELS)
    step_states:        List[str]                 = field(default_factory=lambda: QUESTION_STEP_STATES)


CFG = MasterConfig()
