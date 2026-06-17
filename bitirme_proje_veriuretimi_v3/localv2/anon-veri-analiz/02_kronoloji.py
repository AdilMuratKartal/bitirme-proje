# -*- coding: utf-8 -*-
"""02 — KRONOLOJIK TUTARLILIK / ZAMAN MONOTONLUGU
Bu sette tamamlama tablolari YOK -> 'tamamlama' yerine bitmis quiz denemesi ve
odev teslimi kullanilir. Tum oranlar icin hedef: %1 alti.
"""
from common import *
L = []
def say(s=""):
    s = str(s); print(s); L.append(s)
TOL = 3600  # saat dilimi / kucuk saat kaymasi toleransi (sn)

say("="*70); say("02 KRONOLOJI / ZAMAN TUTARLILIGI"); say("="*70)
u = load("user"); lname, log, lm = get_log()
say(f"Log tablosu: mdl_{lname}")
uidc = col(u, "id", table="user")
fa = col(u, "firstaccess", table="user", zorunlu=False)
la = col(u, "lastaccess",  table="user", zorunlu=False)

if fa and la:
    f = ts_ok(u[fa]); l = ts_ok(u[la])
    m = f.notna() & l.notna() & (f > 0) & (l > 0)
    v = int(((l < f) & m).sum())
    say(f"\n2A) user.lastaccess < firstaccess : {v}/{int(m.sum())} (%{yuzde(v, int(m.sum())):.3f})")

lt = ts_ok(log[lm["time"]]); lu = num(log[lm["userid"]])
if fa:
    minlog = pd.DataFrame({"u": lu, "t": lt}).dropna().groupby("u")["t"].min()
    fmap = pd.Series(ts_ok(u[fa]).values, index=num(u[uidc]).values)
    j = pd.DataFrame({"minlog": minlog}); j["fa"] = j.index.map(fmap)
    j = j.dropna(); j = j[j["fa"] > 0]
    v = int((j["minlog"] < j["fa"] - TOL).sum())
    say(f"2B) ilk log < user.firstaccess    : {v}/{len(j)} (%{yuzde(v, len(j)):.3f})  [tolerans {TOL}s]")
    say("    Sifira yakin olmali; yuksekse log ve user tablolari farkli kaynaktan uretilmis olabilir.")

qa = load("quiz_attempts")
if qa is not None and len(qa):
    ts = ts_ok(qa[col(qa, "timestart", table="quiz_attempts")])
    tf = ts_ok(qa[col(qa, "timefinish", table="quiz_attempts")])
    fin = (num(qa[col(qa, "timefinish")]) > 0) & ts.notna() & tf.notna()
    v = int(((tf < ts) & fin).sum())
    say(f"\n2C) quiz: timefinish < timestart (bitenlerde): {v}/{int(fin.sum())} (%{yuzde(v, int(fin.sum())):.3f})")
    d = (tf - ts)[fin & (tf >= ts)]
    if len(d):
        say(f"    deneme suresi: medyan {d.median()/60:.1f} dk | p99 {d.quantile(.99)/60:.0f} dk | >24 saat: %{100*(d>86400).mean():.2f}")
        say("    (>24 saatlik denemeler acik birakilan oturumlardir; ML'de sure feature'i icin kirpin)")

asub = load("assign_submission")
if asub is not None and len(asub):
    tc = ts_ok(asub[col(asub, "timecreated", table="assign_submission")])
    tm = ts_ok(asub[col(asub, "timemodified", table="assign_submission")])
    m = tc.notna() & tm.notna() & (tc > 0) & (tm > 0)
    v = int(((tm < tc) & m).sum())
    say(f"\n2D) teslim: timemodified < timecreated: {v}/{int(m.sum())} (%{yuzde(v, int(m.sum())):.3f})")

gg = load("grade_grades"); gi = load("grade_items")
gtm = col(gg, "timemodified", table="grade_grades", zorunlu=False)
gim = col(gi, "itemmodule", table="grade_items", zorunlu=False) if gi is not None else None
if asub is not None and gim and gtm:
    gid = col(gi, "id", table="grade_items"); ins = col(gi, "iteminstance", table="grade_items")
    it = gi[gi[gim].astype(str) == "assign"][[gid, ins]]
    gsel = gg.merge(it, left_on=col(gg, "itemid"), right_on=gid, how="inner")
    gsel = gsel[num(gsel[col(gg, "finalgrade")]) > 0].copy()
    sub = asub.copy()
    sub["k1"] = num(sub[col(asub, "assignment", table="assign_submission")])
    sub["k2"] = num(sub[col(asub, "userid", table="assign_submission")])
    smin = sub.dropna(subset=["k1", "k2"]).groupby(["k1", "k2"])[col(asub, "timecreated")].min().rename("sub_tc")
    gsel["k1"] = num(gsel[ins]); gsel["k2"] = num(gsel[col(gg, "userid")])
    j = gsel.dropna(subset=["k1", "k2"]).set_index(["k1", "k2"]).join(smin, how="inner")
    j["g"] = ts_ok(j[gtm]); j["s"] = ts_ok(j["sub_tc"]); j = j.dropna(subset=["g", "s"])
    v = int((j["g"] < j["s"] - 86400).sum())
    say(f"\n2E) Odev NOTU teslimden >1 gun ONCE girilmis: {v}/{len(j)} (%{yuzde(v, len(j)):.3f})")
    say("    Yuksek oran = notlar aktiviteden bagimsiz basilmis (sentetik/iceri aktarim) isareti.")

c = load("course")
sd = col(c, "startdate", table="course", zorunlu=False)
if sd:
    cw = pd.DataFrame({"cid": num(c[col(c, "id", table="course")]), "start": ts_ok(c[sd])}).dropna()
    cw = cw[cw["start"] > 0]
    lj = pd.DataFrame({"cid": num(log[lm["courseid"]]), "t": lt}).dropna().merge(cw, on="cid", how="inner")
    v = int((lj["t"] < lj["start"] - TOL).sum())
    say(f"\n2F) Kurs baslangicindan ONCE atilmis log: {v}/{len(lj)} (%{yuzde(v, len(lj)):.2f})  [ayrinti: 04]")

say("\nGENEL ESIK: her madde %1 altinda ise zaman akisi TUTARLI kabul edilir;")
say("%15-20 ustu maddeler ciddi manipulasyon/bozulma isaretidir (kendi kriteriniz).")
rapor("02_kronoloji_rapor.txt", L)
