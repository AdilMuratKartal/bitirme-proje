# -*- coding: utf-8 -*-
"""07 — REFERANS BUTUNLUGU (FK) + ML FEATURE PROTOTIPI
1) ML join yollarinda yetim (orphan) oranlari
2) (userid, courseid) duzeyinde ornek ozellik tablosu uretir: cikti/07_features.csv
Hedef degisken adayi: kurs toplam notu (grade_items.itemtype='course') yuzdesi.
"""
from common import *
L = []
def say(s=""):
    s = str(s); print(s); L.append(s)

say("="*70); say("07 FK BUTUNLUGU + FEATURE PROTOTIPI"); say("="*70)

def orphan(ct, cc, pt, pc="id"):
    c = load(ct); p = load(pt)
    if c is None or p is None:
        say(f"  {ct} -> {pt}: tablo yok, atlandi"); return
    cc2 = col(c, cc, table=ct, zorunlu=False)
    pc2 = col(p, pc, table=pt, zorunlu=False)
    if not cc2 or not pc2:
        say(f"  {ct}.{cc} -> {pt}: kolon yok, atlandi"); return
    v = num(c[cc2]).dropna(); v = v[v > 0].astype("int64")
    s = set(num(p[pc2]).dropna().astype("int64"))
    o = int((~v.isin(s)).sum())
    isaret = "OK " if o == 0 else ("!  " if 100*o/len(v) < 1 else "!!!")
    say(f"  {isaret} {ct}.{cc2:<12} -> {pt:<13}: {o:>7} yetim / {len(v)} (%{yuzde(o, len(v)):.2f})")

say("\n-- FK / yetim kayit kontrolleri --")
lname, log, lm = get_log()
orphan("grade_grades", "itemid", "grade_items")
orphan("grade_grades", "userid", "user")
orphan("grade_items", "courseid", "course")
orphan("course_modules", "course", "course")
orphan("course_modules", "module", "modules")
orphan("assign_submission", "assignment", "assign")
orphan("assign_submission", "userid", "user")
orphan("quiz_attempts", "quiz", "quiz")
orphan("quiz_attempts", "userid", "user")
orphan("user_enrolments", "enrolid", "enrol")
orphan("user_enrolments", "userid", "user")
orphan("enrol", "courseid", "course")
orphan(lname, lm["userid"], "user")
orphan(lname, lm["courseid"], "course")
say("  %1 alti yetim genelde zararsizdir (silinmis kayit artigi); %5+ ise join'ler veri kaybettirir.")

say("\n-- (userid, courseid) feature tablosu uretiliyor --")
lt = ts_ok(log[lm["time"]])
lg = pd.DataFrame({"u": num(log[lm["userid"]]), "c": num(log[lm["courseid"]]),
                   "t": lt, "gun": lt // 86400}).dropna(subset=["u", "c", "t"])
ac = lm.get("action")
if ac:
    lg["view"] = log.loc[lg.index, ac].astype(str).str.startswith("view") if len(lg) > 0 else False
agg = {"n_log": ("t", "size"), "n_aktif_gun": ("gun", "nunique"),
       "ilk_log": ("t", "min"), "son_log": ("t", "max")}
if ac and "view" in lg.columns:
    agg["n_view"] = ("view", "sum")
F = lg.groupby(["u", "c"]).agg(**agg).reset_index()
F["aktif_sure_gun"] = ((F["son_log"] - F["ilk_log"]) / 86400).round(1)
F["log_per_gun"] = (F["n_log"] / F["n_aktif_gun"].clip(lower=1)).round(2)

a = load("assign"); asub = load("assign_submission")
if a is not None and asub is not None:
    amap = dict(zip(num(a[col(a, "id", table="assign")]),
                    num(a[col(a, "course", table="assign")])))
    s = pd.DataFrame({"i": num(asub[col(asub, "assignment")]),
                      "u": num(asub[col(asub, "userid")])}).dropna()
    s["c"] = s["i"].map(amap)
    F = F.merge(s.dropna().groupby(["u", "c"]).size().rename("n_teslim").reset_index(),
                on=["u", "c"], how="left")

q = load("quiz"); qa = load("quiz_attempts")
if q is not None and qa is not None:
    qmap = dict(zip(num(q[col(q, "id", table="quiz")]),
                    num(q[col(q, "course", table="quiz")])))
    s = pd.DataFrame({"i": num(qa[col(qa, "quiz")]),
                      "u": num(qa[col(qa, "userid")]),
                      "f": num(qa[col(qa, "timefinish")])}).dropna()
    s = s[s["f"] > 0]; s["c"] = s["i"].map(qmap)
    F = F.merge(s.dropna(subset=["c"]).groupby(["u", "c"]).size().rename("n_quiz_deneme").reset_index(),
                on=["u", "c"], how="left")

gi = load("grade_items"); gg = load("grade_grades")
ity = col(gi, "itemtype", table="grade_items", zorunlu=False)
gmx = col(gi, "grademax", table="grade_items", zorunlu=False)
if ity and gmx:
    crs = gi[gi[ity].astype(str) == "course"]
    imap = dict(zip(num(crs[col(gi, "id")]),
                    zip(num(crs[col(gi, "courseid")]), num(crs[gmx]))))
    t = gg[[col(gg, "itemid"), col(gg, "userid"), col(gg, "finalgrade")]].copy()
    t.columns = ["i", "u", "g"]
    t["i"] = num(t["i"]); t["u"] = num(t["u"]); t["g"] = num(t["g"])
    t["cm"] = t["i"].map(imap)
    t = t.dropna(subset=["cm"])
    t["c"] = t["cm"].map(lambda x: x[0]); t["mx"] = t["cm"].map(lambda x: x[1])
    t["hedef_kurs_not_pct"] = (100 * t["g"] / t["mx"]).clip(0, 100)
    F = F.merge(t.groupby(["u", "c"])["hedef_kurs_not_pct"].mean().reset_index(),
                on=["u", "c"], how="left")

gim = col(gi, "itemmodule", table="grade_items", zorunlu=False)
if gim and gmx:
    md = gi[gi[gim].notna() & (num(gi[gmx]) > 0)]
    imap2 = dict(zip(num(md[col(gi, "id")]),
                     zip(num(md[col(gi, "courseid")]), num(md[gmx]))))
    t = gg[[col(gg, "itemid"), col(gg, "userid"), col(gg, "finalgrade")]].copy()
    t.columns = ["i", "u", "g"]
    t["i"] = num(t["i"]); t["u"] = num(t["u"]); t["g"] = num(t["g"])
    t["cm"] = t["i"].map(imap2); t = t.dropna(subset=["cm", "g"])
    t["c"] = t["cm"].map(lambda x: x[0]); t["mx"] = t["cm"].map(lambda x: x[1])
    t["pct"] = (100 * t["g"] / t["mx"]).clip(0, 100)
    F = F.merge(t.groupby(["u", "c"])["pct"].agg(
                    modul_not_ort="mean",
                    modul_not_std="std",
                    n_dolu_not="size").reset_index(),
                on=["u", "c"], how="left")

for cc in ["n_teslim", "n_quiz_deneme", "n_dolu_not"]:
    if cc in F.columns:
        F[cc] = F[cc].fillna(0).astype(int)
F = F.rename(columns={"u": "userid", "c": "courseid"})
kaydet("07_features.csv", F)
say(f"Feature tablosu: {F.shape[0]} satir x {F.shape[1]} kolon")
say("Bos oranlar (%):")
for cc in F.columns:
    say(f"  {cc:<22} %{100*F[cc].isna().mean():.1f}")

if "hedef_kurs_not_pct" in F.columns:
    smp = F.dropna(subset=["hedef_kurs_not_pct"])
    if len(smp) > 100:
        r = smp["n_log"].corr(smp["hedef_kurs_not_pct"])
        say(f"\nHizli tutarlilik: corr(n_log, kurs notu) = {r:.3f}")
        say("  Gercek egitim verisinde tipik olarak POZITIF (0.1-0.4) cikar;")
        say("  ~0 veya negatifse loglar ile notlar BIRBIRINDEN BAGIMSIZ uretilmis olabilir.")

say("\n-- ML icin onerilen turetilmis ozellikler --")
for s in [
    "n_log, n_view, n_aktif_gun, log_per_gun (katilim yogunlugu)",
    "aktif_sure_gun ve son_log-kurs_baslangici (erken birakma / dropout sinyali)",
    "n_teslim / kursdaki toplam odev sayisi (teslim orani)",
    "n_quiz_deneme, ort. deneme suresi (02C'deki sure dagilimi ile)",
    "modul_not_ort, modul_not_std (performans seviyesi ve istikrari)",
    "ilk 2-4 haftadaki log/teslim sayisi (erken uyari modeli icin)",
    "gece/hafta sonu aktivite orani (calisma aliskanligi)",
    "HEDEF onerileri: hedef_kurs_not_pct (regresyon) | gecti/kaldi esigi (siniflandirma)",
    "  'terk' = kurs penceresinin son %40'inda hic log yok VE kurs notu bos (04 ile birlikte)"
]:
    say("  * " + s)
say("\nUYARI: 04 ve 06 bulgularina gore toplu-girilen kalemler ve pencere-disi loglar")
say("zamansal ozellikleri bozar; bu satirlari filtreleyin veya isaretleyin.")
rapor("07_fk_ve_features_rapor.txt", L)
