"""
enrollment_plan.py — Stratified Weighted Enrollment Algoritması
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PARAMETRELER   → config/enrollment.py
ALGORİTMA      → bu dosya (sabit yoktur, config'den okur)

Farklı senaryo (tahmin verisi vb.) için:
    from config.enrollment import LOAD_GROUPS, SEG_LOAD_WEIGHTS, COURSE_TIERS
    # override istediğin sabiti
    plan = build_enrollment_plan(registry, rng,
                                  load_groups=my_groups,
                                  seg_weights=my_weights,
                                  tiers=my_tiers)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple

from config import (
    LOAD_GROUPS, LoadGroup,
    SEG_LOAD_WEIGHTS,
    COURSE_TIERS, CourseTier,
)


# ─────────────────────────────────────────────────────────────────
# YARDIMCI: Tier-ağırlıklı kurs havuzu
# ─────────────────────────────────────────────────────────────────
def _build_course_pool(
    tiers: Dict[str, CourseTier],
) -> Tuple[List[int], List[float]]:
    """
    Tüm kursları (tier ağırlığıyla) normalize edilmiş bir liste döner.
    rng.choice(..., p=weights, replace=False) için hazır.
    """
    courses: List[int]   = []
    raw_w:   List[float] = []
    for tier in tiers.values():
        courses.extend(tier.course_ids)
        raw_w.extend([tier.weight] * len(tier.course_ids))
    total = sum(raw_w)
    return courses, [w / total for w in raw_w]


# ─────────────────────────────────────────────────────────────────
# ADIM 1: Öğrencileri yük gruplarına ata (quota garantili)
# ─────────────────────────────────────────────────────────────────
def _assign_load_groups(
    registry:    pd.DataFrame,
    rng:         np.random.Generator,
    load_groups: Dict[str, LoadGroup],
    seg_weights: Dict[str, List[float]],
) -> Dict[int, str]:
    """
    Segment ağırlıklı stokastik ön-atama + quota overflow düzeltmesi.

    1. Her öğrenci için P(L|seg), P(M|seg), P(H|seg) ile grup çek
    2. Quota dolunca overflow → sonraki gruba taşı (L→M→H sırasıyla)
    3. Sonuç: kesin olarak LOAD_GROUPS[g].quota kadar öğrenci her grupta
    """
    groups  = list(load_groups.keys())
    quotas  = {g: load_groups[g].quota for g in groups}
    counts  = {g: 0 for g in groups}
    bucket: Dict[str, List[int]] = {g: [] for g in groups}

    for _, row in registry.iterrows():
        seg  = row["segment"]
        w    = seg_weights.get(seg, [1/len(groups)] * len(groups))
        g    = str(rng.choice(groups, p=w))
        bucket[g].append(int(row["userid"]))

    # Karıştır (sıraya bağlı önyargıyı kır)
    for g in groups:
        arr = bucket[g]
        rng.shuffle(arr)

    final:    Dict[int, str] = {}
    overflow: List[int]      = []

    for g in groups:
        take = min(len(bucket[g]), quotas[g])
        for uid in bucket[g][:take]:
            final[uid] = g
            counts[g] += 1
        overflow.extend(bucket[g][take:])

    # Overflow → dolu olmayan gruba sırayla doldur
    for uid in overflow:
        for g in groups:
            if counts[g] < quotas[g]:
                final[uid] = g
                counts[g] += 1
                break

    return final


# ─────────────────────────────────────────────────────────────────
# ANA FONKSİYON
# ─────────────────────────────────────────────────────────────────
def build_enrollment_plan(
    registry:    pd.DataFrame,
    rng:         np.random.Generator,
    load_groups: Optional[Dict[str, LoadGroup]]  = None,
    seg_weights: Optional[Dict[str, List[float]]] = None,
    tiers:       Optional[Dict[str, CourseTier]]  = None,
) -> Dict[int, List[int]]:
    """
    uid → kayıtlı kurs id listesi döner.

    Parametreler None ise config/enrollment.py varsayılanları kullanılır.
    Override için:
        from config.enrollment import LOAD_GROUPS
        my_groups = {**LOAD_GROUPS, "L": LoadGroup((3,4), 300)}
        plan = build_enrollment_plan(registry, rng, load_groups=my_groups)
    """
    lg  = load_groups if load_groups is not None else LOAD_GROUPS
    sw  = seg_weights if seg_weights is not None else SEG_LOAD_WEIGHTS
    tr  = tiers       if tiers       is not None else COURSE_TIERS

    pool, weights = _build_course_pool(tr)
    group_map     = _assign_load_groups(registry, rng, lg, sw)

    enrollment: Dict[int, List[int]] = {}
    for uid in registry["userid"].tolist():
        g_key     = group_map[uid]
        lo, hi    = lg[g_key].course_range
        n         = int(rng.integers(lo, hi + 1))
        chosen    = rng.choice(pool, size=n, replace=False, p=weights)
        enrollment[uid] = sorted(int(c) for c in chosen)

    return enrollment


# ─────────────────────────────────────────────────────────────────
# ÖZET İSTATİSTİK (debug / log için)
# ─────────────────────────────────────────────────────────────────
def enrollment_summary(plan: Dict[int, List[int]]) -> str:
    counts     = [len(v) for v in plan.values()]
    arr        = np.array(counts)
    total      = int(arr.sum())
    group_dist = {g: 0 for g in ("L", "M", "H")}
    for c in counts:
        if c <= 6:
            group_dist["L"] += 1
        elif c <= 8:
            group_dist["M"] += 1
        else:
            group_dist["H"] += 1
    return (
        f"Toplam kayıt: {total} | "
        f"Ort: {arr.mean():.1f} ders/öğrenci | "
        f"L={group_dist['L']} M={group_dist['M']} H={group_dist['H']}"
    )
