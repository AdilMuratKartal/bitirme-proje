# -*- coding: utf-8 -*-
"""05 — HAYALET NOT (not var, aktivite yok) ve KAYIP NOT (aktivite var, not yok)
Kanit zinciri: grade_items(itemmodule, iteminstance) -> assign/quiz tablolari
+ modules/course_modules uzerinden cmid -> ESKI mdl_log.cmid eslesmesi.
0 ile NULL ayrimi: 0 girilmis nottur; 'gecerli not' = finalgrade > 0 (hayalet testinde),
KAYIP testinde ise satir-yok ve finalgrade-NULL ayri ayri sayilir.
"""
from common import *
L = []
def say(s=""):
    s = str(s); print(s); L.append(s)

say("="*70); say("05 HAYALET / KAYIP NOT KONTROLU"); say("="*70)
mods = load("modules"); cm = load("course_modules")
gi = load("grade_items"); gg = load("grade_grades")
asub = load("assign_submission"); qa = load("quiz_attempts")
lname, log, lm = get_log()
say(f"Log tablosu: mdl_{lname} (cmid kolonu: {'VAR' if lm.get('cmid') else 'YOK'})\n")

mid = dict(zip(mods[col(mods, "name", table="modules")].astype(str),
               num(mods[col(mods, "id", table="modules")])))
cmidc = col(cm, "id", table="course_modules")
cmod  = col(cm, "module", table="course_modules")
cins  = col(cm, "instance", table="course_modules")
def inst2cmid(t):
    sel = cm[num(cm[cmod]) == mid.get(t, -1)]
    return dict(zip(num(sel[cins]).astype("Int64"), num(sel[cmidc]).astype("Int64")))

logpairs = set()
if lm.get("cmid"):
    lp = pd.DataFrame({"c": num(log[lm["cmid"]]), "u": num(log[lm["userid"]])}).dropna()
    lp = lp[lp["c"] > 0]
    logpairs = set(zip(lp["c"].astype("int64"), lp["u"].astype("int64")))

gid  = col(gi, "id", table="grade_items")
gim  = col(gi, "itemmodule", table="grade_items", zorunlu=False)
gins = col(gi, "iteminstance", table="grade_items", zorunlu=False)
fg   = col(gg, "finalgrade", table="grade_grades")
guid = col(gg, "userid", table="grade_grades")
giid = col(gg, "itemid", table="grade_grades")
if not (gim and gins):
    raise SystemExit("grade_items'ta itemmodule/iteminstance yok -> bu test yapilamaz.")

ozet = []
for typ, evt, k1, fin in [("assign", asub, "assignment", None),
                          ("quiz",   qa,   "quiz",       "timefinish")]:
    if evt is None:
        say(f"[{typ}] kanit tablosu yok, atlandi."); continue
    it = gi[gi[gim].astype(str) == typ][[gid, gins]].copy(); it.columns = ["gid", "inst"]
    rows = gg[[giid, guid, fg]].merge(it, left_on=giid, right_on="gid", how="inner")
    rows["inst"] = num(rows["inst"]); rows["u"] = num(rows[guid]); rows["g"] = num(rows[fg])
    rows = rows.dropna(subset=["inst", "u"])

    ev = evt.copy()
    ev["i"] = num(ev[col(evt, k1, table=typ)])
    ev["u"] = num(ev[col(evt, "userid", table=typ)])
    if fin:
        ev = ev[num(ev[col(evt, fin, table=typ)]) > 0]   # sadece BITMIS denemeler
    ev = ev.dropna(subset=["i", "u"])
    evset = set(zip(ev["i"].astype("int64"), ev["u"].astype("int64")))
    c2cm = inst2cmid(typ)

    # --- HAYALET: finalgrade > 0 ama hicbir teslim/deneme/log yok ---
    pos = rows[rows["g"] > 0]
    keys = list(zip(pos["inst"].astype("int64"), pos["u"].astype("int64")))
    flags = []
    for k in keys:
        ok = k in evset
        if not ok and logpairs:
            cmid = c2cm.get(k[0])
            ok = (cmid is not None) and ((int(cmid), k[1]) in logpairs)
        flags.append(ok)
    gh = len(keys) - sum(flags)
    say(f"[{typ}] HAYALET not (not>0, kanit YOK): {gh}/{len(keys)} (%{yuzde(gh, len(keys)):.2f})")
    if gh:
        kaydet(f"05_hayalet_{typ}.csv",
               pos.loc[[not f for f in flags], ["inst", "u", "g"]]
                  .rename(columns={"inst": "iteminstance", "u": "userid", "g": "finalgrade"}).head(5000))

    # --- KAYIP: kanit var ama not satiri yok / NULL ---
    rowset  = set(zip(rows["inst"].astype("int64"), rows["u"].astype("int64")))
    nullset = set(zip(rows.loc[rows["g"].isna(), "inst"].astype("int64"),
                      rows.loc[rows["g"].isna(), "u"].astype("int64")))
    yok = sum(1 for k in evset if k not in rowset)
    nul = sum(1 for k in evset if k in nullset)
    say(f"[{typ}] KAYIP not — kanitli cift: {len(evset)} | not satiri HIC ACILMAMIS: {yok} "
        f"(%{yuzde(yok, len(evset)):.2f}) | satir var ama finalgrade NULL: {nul} (%{yuzde(nul, len(evset)):.2f})")
    ozet.append((typ, yuzde(gh, len(keys)), yuzde(yok + nul, len(evset))))

say("\n--- ESIK YORUMU (sizin kriteriniz) ---")
for typ, a, b in ozet:
    durum = "TEMIZ" if max(a, b) < 1 else ("INCELENMELI" if max(a, b) < 15 else "CIDDI MANIPULASYON SUPHESI")
    say(f"  {typ:<7} hayalet %{a:.2f} | kayip %{b:.2f}  -> {durum}")
say("Not: quiz'de 'inprogress' (bitmemis) denemeler kanit sayilmadi; assign'da her teslim sayildi.")
rapor("05_hayalet_kayip_not_rapor.txt", L)
