# -*- coding: utf-8 -*-
"""
verify_lineage.py  (v2 - aylik loglar dahil)
============================================
clean_df'teki 10 (UID, COURSE) ornegini, ham anon_mdl tablolarina ve AYLIK LOG
dosyalarina kadar GERI IZLER. Her olayi HANGI DOSYADA buldugunu raporlar.

Taranan log kaynaklari:
  - anon_log.csv                (eski mdl_log; varsa)
  - log-olarak-aylar/*.csv       (anon_enero, anon_febrero, ... aylik loglar)
Iki log SEMASI da otomatik taninir:
  - ESKI mdl_log      : kolonlar module + action
  - YENI logstore     : kolonlar eventname + component + action + target + courseid
Her kaynak dosya icin: tanidigi kolonlar + en sik gecen olay turleri basilir,
boylece esleme senin export'unla birebir degilse buradan duzeltebilirsin.

Ne test eder:
  1) VARLIK  : UID-COURSE cifti HANGI dosyalarda kac olayla geciyor.
  2) LOG     : clean_df'te bir feature>0 ise, ham log'ta o olay GERCEKTEN var mi
               (kaynak dosya kirilimiyla). feature>0 <=> ham olay VAR olmali.
  3) GRADE   : ACCOMPLISH_* ile anon_grade_items + anon_grade_grades uyumu.
  4) ACCOMPLISH-BUG: ders-ici notlar ham veride farkliyken clean_df'te ayni mi.

Calistirma:
    pip install pandas
    python verify_lineage.py

NOT: aylik loglar toplam ~5GB. Script hepsini PARCA PARCA (chunk) okur, sadece
10 ornegin satirlarini tutar; bellek sismez ama disk okumasi birkac dakika surer.
"""

import os
import sys
import glob
import pandas as pd
import numpy as np
from collections import Counter, defaultdict

# ============================== CONFIG =====================================
CLEAN_DF = r"C:\Users\2025\Desktop\proje-veri-seçimi-araştırma\clean_df_10_2.5.csv"    # <-- clean_df yolu
DATA_DIR = r"C:\Users\2025\Desktop\proje-veri-seçimi-araştırma\proje-için-toplanılan-veriler\anonim-data"  # <-- anon_*.csv klasoru
MONTHLY_LOG_DIR = os.path.join(DATA_DIR, "log-olarak-aylar")   # <-- aylik loglar klasoru
INCLUDE_ANON_LOG = True   # ana klasordeki anon_log.csv'yi de tara
CLEAN_SEP = ";"           # clean_df ayraci
ANON_SEP  = ","           # anon_*.csv ayraci
LOG_CHUNK = 300_000       # log'u kac satirlik parcalarla okuyacagiz

# Bos birakirsan otomatik cesitli 10 ornek secilir. Kendin vermek istersen:
SAMPLE_PAIRS = [
    # (69994, 580), (52507, 1363), (4, 4949),
]
# ===========================================================================

LOG_GROUPS = ["COURSE_VIEW", "RESOURCE_VIEW", "URL_VIEW", "ASSIGN_VIEW",
              "QUIZ_VIEW", "ASSIGN_SUBMIT", "QUIZ_ATTEMPT", "QUIZ_CLOSE_ATTEMPT",
              "FORUM_VIEW_FORUM", "FORUM_VIEW_DISCUSSION"]


def low(x):
    return str(x).strip().lower()


def read_csv_smart(path, sep_hint=None):
    seps = [sep_hint] if sep_hint else []
    seps += [",", ";", "\t"]
    last = None
    for s in dict.fromkeys(seps):
        try:
            df = pd.read_csv(path, sep=s, low_memory=False)
            if df.shape[1] > 1:
                df.columns = [low(c).lstrip("\ufeff") for c in df.columns]
                return df
        except Exception as e:
            last = e
    raise RuntimeError(f"Okunamadi: {path} ({last})")


def col(cols, *cands):
    cset = list(cols)
    for c in cands:
        if c in cset:
            return c
    for c in cands:
        for real in cset:
            if c in real:
                return real
    return None


def classify(mod, action, target, ev):
    """Bir log satirini 10 feature grubundan birine atar; yoksa None."""
    m, a, t, e = low(mod), low(action), low(target), low(ev)
    # ---- YENI logstore: eventname dolu ----
    if e and e != "nan":
        comp = None
        for c in ("resource", "url", "assign", "quiz", "forum"):
            if "mod_" + c in e:
                comp = c
                break
        if comp is None and "course_viewed" in e:
            return "COURSE_VIEW"
        if comp == "resource" and "viewed" in e:
            return "RESOURCE_VIEW"
        if comp == "url" and "viewed" in e:
            return "URL_VIEW"
        if comp == "assign":
            if "submitted" in e or "submission_created" in e:
                return "ASSIGN_SUBMIT"
            if "viewed" in e:
                return "ASSIGN_VIEW"
        if comp == "quiz":
            if "attempt_started" in e:
                return "QUIZ_ATTEMPT"
            if "attempt_submitted" in e or "attempt_reviewed" in e:
                return "QUIZ_CLOSE_ATTEMPT"
            if "viewed" in e:
                return "QUIZ_VIEW"
        if comp == "forum":
            if "discussion_viewed" in e:
                return "FORUM_VIEW_DISCUSSION"
            if "viewed" in e:
                return "FORUM_VIEW_FORUM"
        return None
    # ---- ESKI mdl_log: module + action ----
    if m == "course" and "view" in a:
        return "COURSE_VIEW"
    if m == "resource" and "view" in a:
        return "RESOURCE_VIEW"
    if m == "url" and "view" in a:
        return "URL_VIEW"
    if m == "assign":
        if "submit" in a or "upload" in a:
            return "ASSIGN_SUBMIT"
        if "view" in a:
            return "ASSIGN_VIEW"
    if m == "quiz":
        if "close" in a:
            return "QUIZ_CLOSE_ATTEMPT"
        if "attempt" in a:
            return "QUIZ_ATTEMPT"
        if "view" in a:
            return "QUIZ_VIEW"
    if m == "forum":
        if "discussion" in a:
            return "FORUM_VIEW_DISCUSSION"
        if "view" in a:
            return "FORUM_VIEW_FORUM"
    return None


def anon(name):
    return os.path.join(DATA_DIR, name)


def list_log_sources():
    src = []
    if INCLUDE_ANON_LOG and os.path.exists(anon("anon_log.csv")):
        src.append(anon("anon_log.csv"))
    if os.path.isdir(MONTHLY_LOG_DIR):
        src += sorted(glob.glob(os.path.join(MONTHLY_LOG_DIR, "*.csv")))
    return src


def pick_samples(clean):
    if SAMPLE_PAIRS:
        idx = clean.set_index(["uid", "course"]).index
        return [(u, c) for (u, c) in SAMPLE_PAIRS if (u, c) in idx][:10]
    acc = [c for c in clean.columns if c.startswith("accomplish")]
    g = clean.groupby("course")
    varies = (g[acc].nunique() > 1).any(axis=1)
    cl = clean.copy()
    cl["_v"] = cl["course"].map(varies)
    vp = [c for c in cl.columns if c.endswith("_pct") and "view" in c]
    cl["_act"] = cl[vp].sum(axis=1)
    idx = []
    for v in (True, False):
        for t in (True, False):
            sub = cl[(cl["_v"] == v) & (cl["bin_target"] == t)].sort_values("_act")
            if len(sub):
                idx += [sub.index[0], sub.index[-1]]
    idx = list(dict.fromkeys(idx))[:10]
    return [(int(cl.loc[i, "uid"]), int(cl.loc[i, "course"])) for i in idx]


def scan_sources(sample, sources):
    """
    Tum log kaynaklarini tarar.
    Donen:
      counts[(u,c)][group][srcname] = sayi    (siniflanmis olaylar)
      rows[(u,c)][srcname]          = sayi    (toplam ham satir; VARLIK icin)
      vocab[srcname]                = Counter (en sik olay turleri)
      colmap[srcname]               = tanidigi kolon adlari
    """
    want = set(sample)
    counts = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    rows = defaultdict(lambda: defaultdict(int))
    vocab = {}
    colmap = {}

    for path in sources:
        srcname = os.path.basename(path)
        print(f"  > taraniyor: {srcname}")
        try:
            reader = pd.read_csv(path, sep=ANON_SEP, chunksize=LOG_CHUNK, low_memory=False)
        except Exception as e:
            print(f"    ! acilamadi: {e}")
            continue
        cu = cc = cmod = ca = ct = ce = None
        first = True
        vc = Counter()
        for ch in reader:
            ch.columns = [low(x).lstrip("\ufeff") for x in ch.columns]
            if first:
                cu = col(ch.columns, "userid", "user", "user_id")
                cc = col(ch.columns, "courseid", "course", "course_id")
                cmod = col(ch.columns, "module", "component")
                ca = col(ch.columns, "action")
                ct = col(ch.columns, "target")
                ce = col(ch.columns, "eventname", "event")
                colmap[srcname] = {"userid": cu, "course": cc, "module/component": cmod,
                                   "action": ca, "target": ct, "eventname": ce}
                first = False
                if not cu or not cc:
                    print(f"    ! userid/course kolonu bulunamadi -> {list(ch.columns)[:12]}")
                    break
            # ilk parcadan genel olay-turu dagilimini topla (kaynak vokabuleri)
            if sum(vc.values()) < LOG_CHUNK:
                if ce:
                    vc.update(ch[ce].astype(str).str.lower().head(20000).tolist())
                elif cmod and ca:
                    vc.update((ch[cmod].astype(str).str.lower() + "/" +
                               ch[ca].astype(str).str.lower()).head(20000).tolist())
            # userid/course'a gore filtrele
            cu_num = pd.to_numeric(ch[cu], errors="coerce")
            cc_num = pd.to_numeric(ch[cc], errors="coerce")
            mask = cu_num.notna() & cc_num.notna()
            sub = ch[mask].copy()
            sub["_u"] = cu_num[mask].astype(int)
            sub["_c"] = cc_num[mask].astype(int)
            sub["_k"] = list(zip(sub["_u"], sub["_c"]))
            sub = sub[sub["_k"].isin(want)]
            if sub.empty:
                continue
            for k, grp in sub.groupby("_k"):
                rows[k][srcname] += len(grp)
                for _, r in grp.iterrows():
                    g = classify(r[cmod] if cmod else "", r[ca] if ca else "",
                                 r[ct] if ct else "", r[ce] if ce else "")
                    if g:
                        counts[k][g][srcname] += 1
        vocab[srcname] = vc
    return counts, rows, vocab, colmap


def main():
    print("=" * 80)
    print(" clean_df  ->  ham anon_mdl + AYLIK LOG  KOKEN DOGRULAMA (v2)")
    print("=" * 80)
    if not os.path.exists(CLEAN_DF):
        sys.exit(f"clean_df yok: {CLEAN_DF}")
    if not os.path.isdir(DATA_DIR):
        sys.exit(f"anon klasoru yok: {DATA_DIR}")

    clean = read_csv_smart(CLEAN_DF, CLEAN_SEP)
    print(f"clean_df: {clean.shape[0]} satir, {clean.shape[1]} kolon")

    sources = list_log_sources()
    print(f"Log kaynagi sayisi: {len(sources)}")
    for s in sources:
        print("   -", os.path.basename(s))
    print()

    sample = pick_samples(clean)
    print(f"Dogrulanacak {len(sample)} ornek:")
    for u, c in sample:
        print(f"   UID={u:<7} COURSE={c}")
    print()

    print("Loglar taraniyor (parca parca, birkac dakika surebilir)...")
    counts, rows, vocab, colmap = scan_sources(sample, sources)
    print("Tarama bitti.\n")

    # ---- kaynak dosya raporu: kolonlar + en sik olay turleri ----
    print("=" * 80)
    print(" KAYNAK DOSYALAR: taninan kolonlar + en sik olay turleri")
    print("=" * 80)
    for s in sources:
        sn = os.path.basename(s)
        cm = colmap.get(sn, {})
        sema = "YENI logstore" if cm.get("eventname") else ("ESKI mdl_log" if cm.get("module/component") else "?")
        print(f"\n[{sn}]  sema={sema}")
        print("   kolonlar:", {k: v for k, v in cm.items() if v})
        top = vocab.get(sn, Counter()).most_common(8)
        if top:
            print("   en sik olaylar:", "; ".join(f"{k}={v}" for k, v in top))

    # ---- grade tablolari ----
    gi = gg = None
    gi_course = gi_id = gi_max = gg_item = gg_user = gg_final = None
    try:
        gi = read_csv_smart(anon("anon_mdl_grade_items.csv"), ANON_SEP)
        gg = read_csv_smart(anon("anon_mdl_grade_grades.csv"), ANON_SEP)
        gi_course = col(gi.columns, "courseid", "course")
        gi_id = col(gi.columns, "id", "itemid")
        gi_max = col(gi.columns, "grademax", "grade_max")
        gg_item = col(gg.columns, "itemid", "gradeitemid")
        gg_user = col(gg.columns, "userid", "user")
        gg_final = col(gg.columns, "finalgrade", "rawgrade", "grade")
    except Exception as e:
        print(f"\n  ! grade tablolari okunamadi: {e}")

    clean_idx = clean.set_index(["uid", "course"])

    # ---- ornek ornek ----
    print("\n" + "=" * 80)
    print(" ORNEK ORNEK DOGRULAMA")
    print("=" * 80)
    for (u, c) in sample:
        print("-" * 80)
        print(f"UID={u}  COURSE={c}   clean_df.BIN_TARGET={bool(clean_idx.loc[(u,c),'bin_target'])}")
        row = clean_idx.loc[(u, c)]

        # VARLIK: hangi dosyalarda
        rdict = rows.get((u, c), {})
        if rdict:
            print("  [VARLIK] log dosyalarinda:",
                  "; ".join(f"{k}={v} olay" for k, v in sorted(rdict.items(), key=lambda x: -x[1])))
        else:
            print("  [VARLIK] HICBIR log dosyasinda bulunamadi  <-- bu cift loglardan gelmiyor!")

        # LOG yapisal tutarlilik (kaynak kirilimiyla)
        print("  [LOG] feature              clean>0  ham_say  kaynak(lar)            durum")
        cdict = counts.get((u, c), {})
        for g in LOG_GROUPS:
            cl = g.lower() + "_pct"
            cval = float(row[cl]) if cl in row.index else np.nan
            cpos = (not np.isnan(cval)) and cval > 0
            srcs = cdict.get(g, {})
            tot = sum(srcs.values())
            src_txt = ",".join(f"{os.path.splitext(k)[0]}:{v}" for k, v in sorted(srcs.items(), key=lambda x: -x[1])[:3]) or "-"
            ok = (cpos == (tot > 0))
            print(f"        {g:<22} {str(cpos):<7} {tot:>7}  {src_txt:<22} {'OK' if ok else '!! CELISKI'}")

        # GRADE plausibilite
        if gi is not None and gg is not None and gi_course and gg_user:
            items = gi[gi[gi_course] == c]
            ids = set(items[gi_id])
            gmax = dict(zip(items[gi_id], pd.to_numeric(items[gi_max], errors="coerce")))
            stu = gg[(gg[gg_user] == u) & (gg[gg_item].isin(ids))]
            fg = pd.to_numeric(stu[gg_final], errors="coerce")
            norm = [v / gmax[i] for i, v in zip(stu[gg_item], fg)
                    if pd.notna(v) and gmax.get(i, 0) and gmax[i] > 0]
            avg = np.mean(norm) if norm else float("nan")
            print(f"  [GRADE] ham: kalem={len(ids)} notlu={fg.notna().sum()} ort.norm.not={avg:.3f}"
                  f"  | clean ACC_MAND_GRADE={float(row.get('accomplish_mandatory_grade', np.nan)):.3f}"
                  f" ACC_MAND_PCT_GRADED={float(row.get('accomplish_mandatory_pct_graded', np.nan)):.3f}")
        print()

    # ---- ACCOMPLISH-BUG: ham notlar ders-icinde gercekten ayni mi ----
    print("=" * 80)
    print(" ACCOMPLISH-BUG TESTI (ham grade_grades ile)")
    print("=" * 80)
    if gi is not None and gg is not None and gi_course and gg_user:
        for c in sorted({p[1] for p in sample}):
            items = gi[gi[gi_course] == c]
            ids = set(items[gi_id])
            gmax = dict(zip(items[gi_id], pd.to_numeric(items[gi_max], errors="coerce")))
            sub = gg[gg[gg_item].isin(ids)].copy()
            sub["_fg"] = pd.to_numeric(sub[gg_final], errors="coerce")
            sub["_mx"] = sub[gg_item].map(gmax)
            sub = sub[(sub["_mx"] > 0)]
            sub["_n"] = sub["_fg"] / sub["_mx"]
            per = sub.groupby(gg_user)["_n"].mean().dropna()
            if len(per) >= 2:
                sp = per.max() - per.min()
                print(f"  COURSE={c}: {len(per)} ogr. ham ort.not min={per.min():.3f} "
                      f"max={per.max():.3f} fark={sp:.3f}  "
                      + ("(ham FARKLI -> clean ayniysa ETL HATASI)" if sp > 1e-6 else "(ham da ayni)"))
    print("\nBitti. 'CELISKI', 'bulunamadi' ve buyuk 'fark' satirlarina odaklan.")


if __name__ == "__main__":
    main()
