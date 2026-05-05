"""
engine_pkg/finalize.py — Dönem sonu işlemleri.
CourseCompletionFinalizer, BadgeIssuer, GradeAggregator.
"""
from __future__ import annotations

import time
from typing import Dict, List, Tuple

from config import CFG
from student_registry import get_segment

from .context import SimContext


class CourseCompletionFinalizer:
    """
    14. hafta bitiminde mdl_course_completions tablosunu doldurur.
    Eşik: modüllerin >= %40'ı tamamlanmış öğrenciler kurs tamamladı sayılır.
    """
    _THRESHOLD = 0.40

    def finalize(self, ctx: SimContext) -> None:
        store     = ctx.store
        end_ts    = int((CFG.general.semester_start).timestamp()) + CFG.general.n_weeks * 7 * 86400
        enroll_ts = int((CFG.general.semester_start).timestamp()) - 7 * 86400
        n_mods    = CFG.general.n_modules_per_course

        _mod_to_course: Dict[int, int] = {}
        for course_id, mods in ctx.course_modules.items():
            for m in mods:
                _mod_to_course[m["id"]] = course_id

        comp_counts: Dict[Tuple[int, int], int] = {}
        for r in store._rows["mdl_course_modules_completion"]:
            course_id = _mod_to_course.get(r["coursemoduleid"])
            if course_id is not None:
                key = (r["userid"], course_id)
                comp_counts[key] = comp_counts.get(key, 0) + 1

        added = 0
        for (uid, course_id), cnt in comp_counts.items():
            if cnt / max(n_mods, 1) >= self._THRESHOLD:
                store.add("mdl_course_completions", {
                    "userid":        uid,
                    "course":        course_id,
                    "timeenrolled":  enroll_ts,
                    "timecompleted": end_ts,
                    "reaggregate":   0,
                })
                added += 1
        print(f"   CourseCompletionFinalizer: {added} tamamlama kaydi eklendi")


class BadgeIssuer:
    """
    Kurs tamamlayan öğrencilere rozet verir.
    Segment bazlı olasılık: S1->%95, S2->%60, S3->%20, S4->%5.
    """
    _BADGE_PROB = {"S1": 0.95, "S2": 0.60, "S3": 0.20, "S4": 0.05}

    def issue(self, ctx: SimContext) -> None:
        store     = ctx.store
        rng       = ctx.rng
        badge_map = {r["courseid"]: r["id"] for r in store._rows["mdl_badge"]}
        issued    = 0
        issued_set: set = set()

        for comp in store._rows["mdl_course_completions"]:
            uid       = comp["userid"]
            course_id = comp["course"]
            key       = (uid, course_id)
            if key in issued_set:
                continue
            seg      = get_segment(uid)
            prob     = self._BADGE_PROB.get(seg, 0.05)
            if rng.random() < prob:
                badge_id = badge_map.get(course_id)
                if badge_id:
                    store.add("mdl_badge_issued", {
                        "badgeid":    badge_id,
                        "userid":     uid,
                        "uniquehash": f"{uid}_{course_id}_{comp['timecompleted']}",
                        "dateissued": comp["timecompleted"],
                    })
                    issued += 1
                    issued_set.add(key)
        print(f"   BadgeIssuer: {issued} rozet verildi")


class GradeAggregator:
    """
    Moodle grade_regrade_final_grades mantığıyla kategori ve kurs not toplamlarını hesaplar.
    Kategori toplamı: child mod item'larının normalize ortalaması × cat_grademax.
    Kurs toplamı: kategori toplamlarının doğal toplamı (Natural sum).
    """

    def aggregate(self, ctx: SimContext) -> None:
        store  = ctx.store
        now_ts = int(time.time())

        items_by_id: Dict[int, dict] = {r["id"]: r for r in store._rows["mdl_grade_items"]}

        grades_lkp: Dict[Tuple[int, int], float] = {
            (r["userid"], r["itemid"]): r["finalgrade"]
            for r in store._rows["mdl_grade_grades"]
        }

        enrol_map: Dict[int, int] = {r["id"]: r["courseid"] for r in store._rows["mdl_enrol"]}
        enrolled:  Dict[int, set] = {}
        for r in store._rows["mdl_user_enrolments"]:
            cid = enrol_map.get(r["enrolid"])
            if cid:
                enrolled.setdefault(cid, set()).add(r["userid"])

        course_item_map: Dict[int, int] = {
            r["courseid"]: r["id"]
            for r in store._rows["mdl_grade_items"]
            if r["itemtype"] == "course"
        }

        for course_id in range(1, CFG.general.n_courses + 1):
            user_ids  = enrolled.get(course_id, set())
            cat_names = ctx.grade_cat_ids.get(course_id, {})
            cat_items = ctx.grade_cat_item_ids.get(course_id, {})

            child_items_map: Dict[int, List[dict]] = {}
            for r in store._rows["mdl_grade_items"]:
                if r["courseid"] == course_id and r["itemtype"] == "mod":
                    cid_val = r.get("categoryid")
                    if cid_val is not None:
                        child_items_map.setdefault(cid_val, []).append(r)

            for uid in user_ids:
                cat_finals: Dict[int, float] = {}

                for cat_name, grade_cat_id in cat_names.items():
                    cat_item_id = cat_items.get(cat_name)
                    if cat_item_id is None:
                        continue
                    cat_item = items_by_id.get(cat_item_id)
                    if cat_item is None:
                        continue

                    children = child_items_map.get(grade_cat_id, [])
                    normals  = []
                    for item in children:
                        g  = grades_lkp.get((uid, item["id"]))
                        mx = item.get("grademax") or 100.0
                        if g is not None and mx > 0:
                            normals.append(g / mx)

                    if not normals:
                        continue

                    cat_pct   = sum(normals) / len(normals)
                    cat_final = round(
                        min(max(cat_pct * cat_item["grademax"], 0.0), cat_item["grademax"]), 4
                    )
                    cat_finals[cat_item_id] = cat_final
                    store.add("mdl_grade_grades", {
                        "userid":       uid,
                        "itemid":       cat_item_id,
                        "finalgrade":   cat_final,
                        "timemodified": now_ts,
                    })
                    store.add("mdl_grade_grades_history", {
                        "userid":       uid,
                        "itemid":       cat_item_id,
                        "finalgrade":   cat_final,
                        "timemodified": now_ts,
                        "source":       "system",
                    })

                if not cat_finals:
                    continue
                course_item_id = course_item_map.get(course_id)
                if course_item_id is None:
                    continue
                course_item  = items_by_id[course_item_id]
                course_final = round(
                    min(max(sum(cat_finals.values()), 0.0), course_item["grademax"]), 4
                )
                store.add("mdl_grade_grades", {
                    "userid":       uid,
                    "itemid":       course_item_id,
                    "finalgrade":   course_final,
                    "timemodified": now_ts,
                })
                store.add("mdl_grade_grades_history", {
                    "userid":       uid,
                    "itemid":       course_item_id,
                    "finalgrade":   course_final,
                    "timemodified": now_ts,
                    "source":       "system",
                })

            print(
                f"   [Grade Aggregation] Kurs {course_id}: "
                f"{len(user_ids)} ogrenci icin category+course notlari hesaplandi"
            )
