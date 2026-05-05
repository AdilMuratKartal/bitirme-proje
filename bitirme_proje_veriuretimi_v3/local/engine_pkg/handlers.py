"""
engine_pkg/handlers.py — Event handler sınıfları.
Her sınıf tek bir event tipini işler; tüm durum ctx: SimContext üzerinden erişilir.
"""
from __future__ import annotations

import math
from datetime import timedelta
from typing import Any, Dict, List

import numpy as np

from config import (
    CFG, COURSE_NAMES, COMPONENT_TYPE_MAP,
    QUESTION_STEP_STATES, COURSE_GRADE_SCHEMAS,
)
from events import (
    AssignmentOpenEvent, DropoutCheckEvent,
    GradingEvent, QuizOpenEvent, WeeklyActivityEvent,
)
import student_registry as _sr
from student_registry import get_profile, get_segment, is_active_in_week

from .context import SimContext
from .schedule import TimeCalc, SegmentBehavior


# ─────────────────────────────────────────────────────────────────────
# HAFTALIK AKTİVİTE
# ─────────────────────────────────────────────────────────────────────

class WeeklyActivityHandler:
    _S2_MAX_MISS = 4
    _S3_HARD_CAP = 7

    _FORUM_PROB  = {"S1": 0.40, "S2": 0.25, "S3": 0.08, "S4": 0.02}
    _LESSON_PROB = {"S1": 0.70, "S2": 0.55, "S3": 0.30, "S4": 0.12}
    _LESSON_CORRECT = {"S1": 0.85, "S2": 0.65, "S3": 0.45, "S4": 0.25}

    def __init__(self, ctx: SimContext) -> None:
        self._ctx = ctx

    def handle(self, evt: WeeklyActivityEvent) -> None:
        ctx   = self._ctx
        store = ctx.store
        rng   = ctx.rng
        week  = evt.week
        uids  = _sr.STUDENT_REGISTRY["userid"].tolist()

        log_count = 0
        cmp_count = 0

        _VIEW_TYPES = {"Izleme", "Okuma"}
        view_pool:    List[tuple] = []
        submit_pool:  List[tuple] = []
        attempt_pool: List[tuple] = []

        for cid_m, mods in ctx.course_modules.items():
            for m in mods:
                if COMPONENT_TYPE_MAP.get(m["component"], "") in _VIEW_TYPES:
                    view_pool.append((m["component"], m["id"], cid_m))
        for r in store._rows["mdl_assign"]:
            submit_pool.append(("mod_assign", r["id"], r["course"]))
        for r in store._rows["mdl_quiz"]:
            attempt_pool.append(("mod_quiz", r["id"], r["course"]))

        _fallback = view_pool or [
            (m["component"], m["id"], cid_m)
            for cid_m, mods in ctx.course_modules.items()
            for m in mods
        ]
        action_pool: Dict[str, List[tuple]] = {
            "view":    view_pool    or _fallback,
            "submit":  submit_pool  or _fallback,
            "attempt": attempt_pool or _fallback,
        }

        # O(1) prereq cache — döngü öncesi tek geçiş
        _all_completions: Dict[int, set] = {}
        for _cr in store._rows["mdl_course_modules_completion"]:
            _all_completions.setdefault(_cr["userid"], set()).add(_cr["coursemoduleid"])

        for uid in uids:
            if not is_active_in_week(uid, week):
                continue

            profile   = get_profile(uid)
            seg       = get_segment(uid)
            skip_week = SegmentBehavior.should_skip_week(profile, rng)

            # ── Log kayıtları ──────────────────────────────────────────
            if not skip_week:
                n_clicks   = SegmentBehavior.weekly_click_count(profile, week, rng)
                week_start = TimeCalc.week_start(week)

                for _ in range(n_clicks):
                    day_off = float(rng.uniform(0, 7))
                    hour = (
                        float(rng.choice([22, 23, 0, 1]))
                        if rng.random() < profile.late_night_ratio
                        else float(rng.uniform(8, 22))
                    )
                    log_dt = week_start + timedelta(days=day_off, hours=hour)
                    action = SegmentBehavior.random_action(profile, rng)
                    pool   = action_pool.get(action, _fallback)

                    if pool:
                        idx = int(rng.integers(0, len(pool)))
                        comp, objectid, log_course_id = pool[idx]
                    else:
                        comp          = SegmentBehavior.random_component(rng)
                        objectid      = None
                        log_course_id = int(rng.integers(1, CFG.general.n_courses + 1))

                    store.add("mdl_logstore_standard_log", {
                        "userid":      uid,
                        "courseid":    log_course_id,
                        "component":   comp,
                        "action":      action,
                        "objectid":    objectid,
                        "timecreated": TimeCalc.ts(log_dt),
                        "_week":       week,
                    })
                    log_count += 1

            # ── Modül tamamlama — sıralı, önkoşul kontrollü ───────────
            for course_id, modules in ctx.course_modules.items():
                n_mods = len(modules)
                n_wks  = CFG.general.n_weeks
                target_seqs = [
                    s for s in range(1, n_mods + 1)
                    if max(1, int(s * n_wks / n_mods)) == week
                ]
                if not target_seqs:
                    continue

                last_comp_dt = TimeCalc.week_start(week)

                for target_seq in target_seqs:
                    mod    = modules[target_seq - 1]
                    mod_id = mod["id"]

                    s3_key = (uid, course_id)
                    if seg == "S3" and ctx.s3_course_done.get(s3_key, 0) >= self._S3_HARD_CAP:
                        break

                    cs_key = (uid, course_id)
                    cs = ctx.completion_state.setdefault(cs_key, {
                        "miss_count": 0, "prev_missed": False
                    })

                    if target_seq > 1:
                        prev_mod_id = modules[target_seq - 2]["id"]
                        if prev_mod_id not in _all_completions.get(uid, set()):
                            continue

                    if seg == "S1":
                        should_complete = True
                    elif seg == "S2":
                        must_complete   = cs["prev_missed"] or cs["miss_count"] >= self._S2_MAX_MISS
                        should_complete = must_complete or SegmentBehavior.complete_module(profile, rng)
                    else:
                        should_complete = SegmentBehavior.complete_module(profile, rng)

                    if not should_complete:
                        if seg == "S2":
                            cs["miss_count"]  += 1
                            cs["prev_missed"]  = True
                        continue

                    cs["prev_missed"] = False
                    if seg == "S2":
                        cs["miss_count"] = 0
                    if seg == "S3":
                        ctx.s3_course_done[s3_key] = ctx.s3_course_done.get(s3_key, 0) + 1

                    gap_days     = float(rng.uniform(*profile.module_gap_days))
                    candidate_dt = TimeCalc.week_start(week) + timedelta(days=gap_days)
                    comp_dt      = max(last_comp_dt + timedelta(seconds=1), candidate_dt)
                    last_comp_dt = comp_dt

                    _all_completions.setdefault(uid, set()).add(mod_id)

                    store.add("mdl_course_modules_completion", {
                        "coursemoduleid":  mod_id,
                        "userid":          uid,
                        "completionstate": 1,
                        "timemodified":    TimeCalc.ts(comp_dt),
                    })
                    cmp_count += 1

        # ── Forum + Lesson aktivitesi ──────────────────────────────────
        forum_count  = 0
        lesson_count = 0
        _forum_map:  Dict[int, int] = {r["course"]: r["id"] for r in store._rows["mdl_forum"]}
        _lesson_map: Dict[int, int] = {r["course"]: r["id"] for r in store._rows["mdl_lesson"]}

        for uid in uids:
            if not is_active_in_week(uid, week):
                continue
            seg    = get_segment(uid)
            wstart = TimeCalc.week_start(week)

            if rng.random() < self._FORUM_PROB.get(seg, 0.05):
                cid      = int(rng.integers(1, CFG.general.n_courses + 1))
                forum_id = _forum_map.get(cid)
                if forum_id is not None:
                    disc_dt = wstart + timedelta(
                        days=int(rng.integers(0, 5)),
                        hours=int(rng.integers(8, 22)),
                    )
                    disc_row = {
                        "forum":       forum_id,
                        "course":      cid,
                        "userid":      uid,
                        "name":        f"H{week} Tartisma {int(rng.integers(1, 50))}",
                        "timecreated": TimeCalc.ts(disc_dt),
                    }
                    store.add("mdl_forum_discussions", disc_row)
                    disc_id = disc_row["id"]
                    n_posts = int(rng.integers(1, 5))
                    for _ in range(n_posts):
                        post_dt = disc_dt + timedelta(hours=int(rng.integers(1, 72)))
                        store.add("mdl_forum_posts", {
                            "discussion":  disc_id,
                            "userid":      uid,
                            "message":     "...",
                            "timecreated": TimeCalc.ts(post_dt),
                            "wordcount":   int(rng.integers(20, 300)),
                        })
                    forum_count += 1

            for cid, lesson_id in _lesson_map.items():
                if rng.random() < self._LESSON_PROB.get(seg, 0.10):
                    is_correct = rng.random() < self._LESSON_CORRECT.get(seg, 0.50)
                    seen_dt = wstart + timedelta(
                        days=int(rng.integers(0, 7)),
                        hours=int(rng.integers(8, 22)),
                    )
                    store.add("mdl_lesson_attempts", {
                        "lessonid":  lesson_id,
                        "userid":    uid,
                        "correct":   int(is_correct),
                        "timeseen":  TimeCalc.ts(seen_dt),
                    })
                    lesson_count += 1

        print(
            f"     WeeklyActivity -> {log_count} log | {cmp_count} completion | "
            f"{forum_count} forum tartisma | {lesson_count} lesson attempt"
        )


# ─────────────────────────────────────────────────────────────────────
# QUIZ
# ─────────────────────────────────────────────────────────────────────

class QuizHandler:

    def __init__(self, ctx: SimContext) -> None:
        self._ctx = ctx

    def handle(self, evt: QuizOpenEvent) -> None:
        ctx       = self._ctx
        store     = ctx.store
        rng       = ctx.rng
        quiz_id   = evt.quiz_id
        course_id = evt.course_id
        open_dt   = evt.open_dt
        close_dt  = evt.close_dt

        quiz_name = f"Quiz {quiz_id} - {COURSE_NAMES[course_id - 1]} Hafta {evt.week}"
        store.add("mdl_quiz", {
            "id":        quiz_id,
            "course":    course_id,
            "name":      quiz_name,
            "timeopen":  TimeCalc.ts(open_dt),
            "timeclose": TimeCalc.ts(close_dt),
            "timelimit": CFG.quiz.max_attempt_minutes * 60,
        })

        schema     = COURSE_GRADE_SCHEMAS.get(course_id, {})
        quiz_gmaxes = schema.get("quiz_grademax", [100, 100])
        q_idx      = ctx.quiz_index.get(course_id, 0)
        q_grademax = float(quiz_gmaxes[min(q_idx, len(quiz_gmaxes) - 1)])
        quiz_cats  = schema.get("quiz_categories", [])
        q_cat_name = quiz_cats[min(q_idx, len(quiz_cats) - 1)] if quiz_cats else None
        q_cat_id   = ctx.grade_cat_ids.get(course_id, {}).get(q_cat_name)
        q_coef     = next(
            (c["coef"] for c in schema.get("categories", []) if c["name"] == q_cat_name),
            0.0,
        )
        ctx.quiz_index[course_id] = q_idx + 1

        store.add("mdl_grade_items", {
            "courseid":         course_id,
            "categoryid":       q_cat_id,
            "itemname":         quiz_name,
            "itemtype":         "mod",
            "itemmodule":       "quiz",
            "grademax":         q_grademax if q_grademax > 0 else 100.0,
            "grademin":         0.0,
            "gradepass":        round(q_grademax * 0.50, 2) if q_grademax > 0 else 50.0,
            "aggregationcoef":  round(q_coef, 5),
            "aggregationcoef2": 0.0,
            "timecreated":      TimeCalc.ts(open_dt),
        })
        grade_item_id = store._ids["mdl_grade_items"]

        # Soru havuzu
        cat_id = course_id
        q_pool = [q for q in store._rows["mdl_question"] if q["category"] == cat_id]
        if len(q_pool) < CFG.quiz.questions_per_quiz:
            q_pool = q_pool * math.ceil(CFG.quiz.questions_per_quiz / max(len(q_pool), 1))
        questions = q_pool[: CFG.quiz.questions_per_quiz]

        # Kayıtlı öğrenciler
        _enrol_ids: set = {
            e["id"] for e in store._rows["mdl_enrol"] if e["courseid"] == course_id
        }
        _enrolled_uids: set = {
            r["userid"] for r in store._rows["mdl_user_enrolments"]
            if r["enrolid"] in _enrol_ids
        }

        attempt_count = 0
        qa_count      = 0

        for uid in _sr.STUDENT_REGISTRY["userid"].tolist():
            if uid not in _enrolled_uids:
                continue
            if not is_active_in_week(uid, evt.week):
                continue

            profile = get_profile(uid)
            if rng.random() < profile.quiz_missing_prob:
                continue

            try:
                start_dt, finish_dt, dur_min = TimeCalc.quiz_attempt_window(
                    close_dt, profile, rng
                )
            except Exception:
                continue

            ans_lo, ans_hi         = profile.answered_ratio
            personal_answer_prob   = float(rng.uniform(ans_lo, ans_hi))
            correct_lo, correct_hi = profile.correct_answer_prob

            total_secs = (finish_dt - start_dt).total_seconds()
            q_budgets  = TimeCalc.dirichlet_budget(len(questions), total_secs, rng)

            qa_buffer: list = []
            total_fraction  = 0.0

            for q, q_budget in zip(questions, q_budgets):
                if rng.random() > personal_answer_prob:
                    continue
                is_correct = rng.random() < float(rng.uniform(correct_lo, correct_hi))
                fraction   = 1.0 if is_correct else round(float(rng.uniform(0, 0.5)), 2)
                total_fraction += fraction
                qa_buffer.append((q, fraction, is_correct, q_budget))

            if not qa_buffer:
                continue

            sumgrades  = round((total_fraction / CFG.quiz.questions_per_quiz) * 100, 2)
            uniqueid   = store.next_id("_quiz_uniqueid_counter")
            attempt_id = store.next_id("mdl_quiz_attempts")
            store._rows["mdl_quiz_attempts"].append({
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

            current_dt = start_dt
            for q, fraction, is_correct, q_budget in qa_buffer:
                qa_id = store.next_id("mdl_question_attempts")
                qa_dt = TimeCalc.clamp(
                    current_dt + timedelta(seconds=q_budget * 0.1),
                    current_dt,
                    finish_dt - timedelta(seconds=1),
                )
                store._rows["mdl_question_attempts"].append({
                    "id":              qa_id,
                    "questionusageid": uniqueid,
                    "questionid":      q["id"],
                    "userid":          uid,
                    "responsesummary": "Yanit" if is_correct else "",
                    "rightanswer":     "Dogru",
                    "fraction":        fraction,
                    "timecreated":     TimeCalc.ts(qa_dt),
                })
                qa_count += 1

                n_steps_raw = int(rng.integers(*profile.steps_per_question))
                max_steps   = max(1, int(q_budget * 0.9))
                n_steps     = min(n_steps_raw, max_steps)
                s_budgets   = TimeCalc.dirichlet_budget(n_steps, q_budget * 0.9, rng)

                for s_idx, s_sec in enumerate(s_budgets):
                    is_final    = (s_idx == n_steps - 1)
                    state_label = (
                        "gradedright" if (is_final and is_correct)
                        else "gradedwrong" if is_final
                        else str(rng.choice(QUESTION_STEP_STATES[:-2]))
                    )
                    step_dt = TimeCalc.clamp(
                        current_dt + timedelta(seconds=s_sec),
                        current_dt + timedelta(seconds=1),
                        finish_dt  - timedelta(seconds=1),
                    )
                    store.add("mdl_question_attempt_steps", {
                        "questionattemptid": qa_id,
                        "state":             state_label,
                        "timecreated":       TimeCalc.ts(step_dt),
                    })
                    current_dt = step_dt

            if rng.random() >= profile.grade_missing_prob:
                note_dt = TimeCalc.grading_time(close_dt, rng)
                grade_base = {
                    "userid":       uid,
                    "itemid":       grade_item_id,
                    "finalgrade":   sumgrades,
                    "timemodified": TimeCalc.ts(note_dt),
                }
                store.add("mdl_grade_grades", grade_base)
                store.add("mdl_grade_grades_history", {**grade_base, "source": "teacher"})

        store.add("mdl_event", {
            "userid":       0,
            "courseid":     course_id,
            "name":         quiz_name,
            "eventtype":    "open",
            "timestart":    TimeCalc.ts(open_dt),
            "timeduration": int((close_dt - open_dt).total_seconds()),
            "instance":     quiz_id,
            "modulename":   "quiz",
        })
        print(
            f"     QuizEvent(course={course_id}, quiz={quiz_id}) -> "
            f"{attempt_count} attempt | {qa_count} soru denemesi"
        )


# ─────────────────────────────────────────────────────────────────────
# ÖDEV
# ─────────────────────────────────────────────────────────────────────

class AssignmentHandler:

    def __init__(self, ctx: SimContext) -> None:
        self._ctx = ctx

    def handle(self, evt: AssignmentOpenEvent) -> None:
        ctx       = self._ctx
        store     = ctx.store
        rng       = ctx.rng
        assign_id = evt.assign_id
        course_id = evt.course_id
        open_dt   = evt.open_dt
        due_dt    = evt.due_dt

        assign_name = f"Odev {assign_id} - {COURSE_NAMES[course_id - 1]} Hafta {evt.week}"
        store.add("mdl_assign", {
            "id":                       assign_id,
            "course":                   course_id,
            "name":                     assign_name,
            "duedate":                  TimeCalc.ts(due_dt),
            "allowsubmissionsfromdate": TimeCalc.ts(open_dt),
            "timeclose":                TimeCalc.ts(due_dt),
        })

        a_schema        = COURSE_GRADE_SCHEMAS.get(course_id, {})
        a_grademax      = float(a_schema.get("assign_grademax", 100))
        a_cats          = a_schema.get("categories", [])
        assign_cat_name = a_schema.get("assign_category")
        a_cat_id        = ctx.grade_cat_ids.get(course_id, {}).get(assign_cat_name)
        a_coef          = next(
            (c["coef"] for c in a_cats if c["name"] == assign_cat_name), 0.0
        )

        store.add("mdl_grade_items", {
            "courseid":         course_id,
            "categoryid":       a_cat_id,
            "itemname":         assign_name,
            "itemtype":         "mod",
            "itemmodule":       "assign",
            "grademax":         a_grademax,
            "grademin":         0.0,
            "gradepass":        round(a_grademax * 0.50, 2),
            "aggregationcoef":  round(a_coef, 5),
            "aggregationcoef2": 0.0,
            "timecreated":      TimeCalc.ts(open_dt),
        })
        _grade_item_id = store._ids["mdl_grade_items"]

        _enrol_ids: set = {
            e["id"] for e in store._rows["mdl_enrol"] if e["courseid"] == course_id
        }
        _assign_enrolled_uids: set = {
            r["userid"] for r in store._rows["mdl_user_enrolments"]
            if r["enrolid"] in _enrol_ids
        }

        sub_count = 0
        for uid in _sr.STUDENT_REGISTRY["userid"].tolist():
            if uid not in _assign_enrolled_uids:
                continue
            if not is_active_in_week(uid, evt.week):
                continue
            if not is_active_in_week(uid, evt.week + evt.open_weeks):
                continue

            profile = get_profile(uid)
            sub_dt  = TimeCalc.submit_time(
                profile.submit_strategy, open_dt, due_dt, rng
            )
            if sub_dt is None:
                continue
            if sub_dt > due_dt:
                continue

            delay_h = (sub_dt - open_dt).total_seconds() / 3600
            store.add("mdl_assign_submission", {
                "userid":       uid,
                "assignment":   assign_id,
                "timemodified": TimeCalc.ts(sub_dt),
                "status":       "submitted",
                "delay_hours":  round(delay_h, 2),
            })
            sub_count += 1

        grading_dt = TimeCalc.grading_time(due_dt, rng)
        ctx.assign_meta[assign_id] = {
            "item_id": _grade_item_id,
            "due_dt":  due_dt,
        }
        ctx.pending_grading.append(GradingEvent(
            week       = TimeCalc.week_of(grading_dt),
            assign_id  = assign_id,
            due_dt     = due_dt,
            grading_dt = grading_dt,
        ))

        store.add("mdl_event", {
            "userid":       0,
            "courseid":     course_id,
            "name":         assign_name,
            "eventtype":    "due",
            "timestart":    TimeCalc.ts(due_dt),
            "timeduration": 0,
            "instance":     assign_id,
            "modulename":   "assign",
        })
        print(
            f"     AssignEvent(course={course_id}, assign={assign_id}) -> "
            f"{sub_count} teslim | grading Hafta {TimeCalc.week_of(grading_dt)}"
        )


# ─────────────────────────────────────────────────────────────────────
# NOT GİRİŞİ
# ─────────────────────────────────────────────────────────────────────

class GradingHandler:

    def __init__(self, ctx: SimContext) -> None:
        self._ctx = ctx

    def handle(self, evt: GradingEvent) -> None:
        ctx   = self._ctx
        store = ctx.store
        rng   = ctx.rng

        meta = ctx.assign_meta.get(evt.assign_id)
        if meta is None:
            return

        item_id    = meta["item_id"]
        note_dt_ts = TimeCalc.ts(evt.grading_dt)
        graded     = 0

        subs = [
            r for r in store._rows["mdl_assign_submission"]
            if r["assignment"] == evt.assign_id
        ]
        for sub in subs:
            uid     = sub["userid"]
            profile = get_profile(uid)
            if rng.random() < profile.grade_missing_prob:
                continue
            grade = SegmentBehavior.grade_value(profile, evt.week, rng)
            base  = {
                "userid":       uid,
                "itemid":       item_id,
                "finalgrade":   round(grade, 2),
                "timemodified": note_dt_ts,
            }
            store.add("mdl_grade_grades", base)
            store.add("mdl_grade_grades_history", {**base, "source": "teacher"})
            graded += 1

        print(f"     GradingEvent(assign={evt.assign_id}) -> {graded} not girildi")


# ─────────────────────────────────────────────────────────────────────
# DROPOUT KONTROLÜ
# ─────────────────────────────────────────────────────────────────────

class DropoutCheckHandler:

    def __init__(self, ctx: SimContext) -> None:
        self._ctx = ctx

    def handle(self, evt: DropoutCheckEvent) -> None:
        dropped = _sr.STUDENT_REGISTRY[_sr.STUDENT_REGISTRY["dropout_week"] == evt.week]
        print(f"     DropoutCheck Hafta {evt.week}: {len(dropped)} ogrenci ayrildi")
