# -*- coding: utf-8 -*-
"""07 — REFERANS BUTUNLUGU (FK) + ML FEATURE PROTOTIPI
Korelasyon Paradoksu Çözümü ve Performans Ağırlıklı Feature Geliştirme
"""
from common import *
L = []
def say(s=""):
    s = str(s); print(s); L.append(s)

say("="*70); say("07 FK BUTUNLUGU + FEATURE PROTOTIPI (KORELASYON PARADOKSU ANALIZI)"); say("="*70)

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

say("\n-- (userid, courseid) feature tablosu uretiliyor --")
lt = ts_ok(log[lm["time"]])

# Eski Moodle şeması kolon kontrolleri (module ve action tespiti)
mod_col = "module" if "module" in log.columns else (lm.get("module") if lm.get("module") in log.columns else None)
act_col = "action" if "action" in log.columns else (lm.get("action") if lm.get("action") in log.columns else None)

lg = pd.DataFrame({
    "u": num(log[lm["userid"]]), 
    "c": num(log[lm["courseid"]]),
    "t": lt, 
    "gun": lt // 86400
}).dropna(subset=["u", "c", "t"])

# Paradoks Çözümü: Resource View ve Performans Log Ayrımı
if mod_col and act_col:
    lg["is_resource"] = (log[mod_col].astype(str) == "resource") & (log[act_col].astype(str) == "view")
    lg["is_perf_action"] = log[mod_col].astype(str).isin(["assign", "quiz", "assignment", "workshop"])
    lg["view"] = log[act_col].astype(str).str.startswith("view")
else:
    lg["is_resource"] = False
    lg["is_perf_action"] = False
    lg["view"] = False

# Agregasyon matrisini genişletiyoruz
agg = {
    "n_log": ("t", "size"), 
    "n_aktif_gun": ("gun", "nunique"),
    "ilk_log": ("t", "min"), 
    "son_log": ("t", "max"),
    "n_view": ("view", "sum"),
    "n_resource_view": ("is_resource", "sum"),
    "n_perf_log": ("is_perf_action", "sum")
}

F = lg.groupby(["u", "c"]).agg(**agg).reset_index()
F["aktif_sure_gun"] = ((F["son_log"] - F["ilk_log"]) / 86400).round(1)
F["log_per_gun"] = (F["n_log"] / F["n_aktif_gun"].clip(lower=1)).round(2)

# Saf log gürültüsünü (resource indirmelerini) temizleyen 'net katılım' feature'ı
F["n_pure_log"] = F["n_log"] - F["n_resource_view"]

# --- ASSIGNMENT DATA ---
a = load("assign"); asub = load("assign_submission")
if a is not None and asub is not None:
    amap = dict(zip(num(a[col(a, "id", table="assign")]), num(a[col(a, "course", table="assign")])))
    s = pd.DataFrame({"i": num(asub[col(asub, "assignment")]), "u": num(asub[col(asub, "userid")])}).dropna()
    s["c"] = s["i"].map(amap)
    F = F.merge(s.dropna().groupby(["u", "c"]).size().rename("n_teslim").reset_index(), on=["u", "c"], how="left")

# --- QUIZ DATA ---
q = load("quiz"); qa = load("quiz_attempts")
if q is not None and qa is not None:
    qmap = dict(zip(num(q[col(q, "id", table="quiz")]), num(q[col(q, "course", table="quiz")])))
    s = pd.DataFrame({"i": num(qa[col(qa, "quiz")]), "u": num(qa[col(qa, "userid")]), "f": num(qa[col(qa, "timefinish")])}).dropna()
    s = s[s["f"] > 0]; s["c"] = s["i"].map(qmap)
    F = F.merge(s.dropna(subset=["c"]).groupby(["u", "c"]).size().rename("n_quiz_deneme").reset_index(), on=["u", "c"], how="left")

# --- TARGET COURSE GRADE ---
gi = load("grade_items"); gg = load("grade_grades")
ity = col(gi, "itemtype", table="grade_items", zorunlu=False)
gmx = col(gi, "grademax", table="grade_items", zorunlu=False)
if ity and gmx:
    crs = gi[gi[ity].astype(str) == "course"]
    imap = dict(zip(num(crs[col(gi, "id")]), zip(num(crs[col(gi, "courseid")]), num(crs[gmx]))))
    t = gg[[col(gg, "itemid"), col(gg, "userid"), col(gg, "finalgrade")]].copy()
    t.columns = ["i", "u", "g"]
    t["i"] = num(t["i"]); t["u"] = num(t["u"]); t["g"] = num(t["g"])
    t["cm"] = t["i"].map(imap)
    t = t.dropna(subset=["cm"])
    t["c"] = t["cm"].map(lambda x: x[0]); t["mx"] = t["cm"].map(lambda x: x[1])
    t["hedef_kurs_not_pct"] = (100 * t["g"] / t["mx"]).clip(0, 100)
    F = F.merge(t.groupby(["u", "c"])["hedef_kurs_not_pct"].mean().reset_index(), on=["u", "c"], how="left")

# --- COMPONENT GRADES ---
gim = col(gi, "itemmodule", table="grade_items", zorunlu=False)
if gim and gmx:
    md = gi[gi[gim].notna() & (num(gi[gmx]) > 0)]
    imap2 = dict(zip(num(md[col(gi, "id")]), zip(num(md[col(gi, "courseid")]), num(md[gmx]))))
    t = gg[[col(gg, "itemid"), col(gg, "userid"), col(gg, "finalgrade")]].copy()
    t.columns = ["i", "u", "g"]
    t["i"] = num(t["i"]); t["u"] = num(t["u"]); t["g"] = num(t["g"])
    t["cm"] = t["i"].map(imap2); t = t.dropna(subset=["cm", "g"])
    t["c"] = t["cm"].map(lambda x: x[0]); t["mx"] = t["cm"].map(lambda x: x[1])
    t["pct"] = (100 * t["g"] / t["mx"]).clip(0, 100)
    F = F.merge(t.groupby(["u", "c"])["pct"].agg(modul_not_ort="mean", modul_not_std="std", n_dolu_not="size").reset_index(), on=["u", "c"], how="left")

for cc in ["n_teslim", "n_quiz_deneme", "n_dolu_not"]:
    if cc in F.columns:
        F[cc] = F[cc].fillna(0).astype(int)
F = F.rename(columns={"u": "userid", "c": "courseid"})

# --- ML ALTERNATIF STRATEJI: PERFORMANS AGIRLIKLI INDEKS (Sıfır Korelasyon B planı) ---
# Eğer loglar tamamen bağımsız/sentetik üretildiyse, modelin bel bağlayacağı yeni sentetik-olmayan ana feature:
F["performans_katilim_skoru"] = (F["n_teslim"] * 2.0) + (F["n_quiz_deneme"] * 1.5)

kaydet("07_features.csv", F)
say(f"Feature tablosu: {F.shape[0]} satir x {F.shape[1]} kolon")

# --- KORELASYON PARADOKSU DOGRULAMA TESTLERI ---
if "hedef_kurs_not_pct" in F.columns:
    smp = F.dropna(subset=["hedef_kurs_not_pct"])
    if len(smp) > 100:
        r_raw = smp["n_log"].corr(smp["hedef_kurs_not_pct"])
        r_pure = smp["n_pure_log"].corr(smp["hedef_kurs_not_pct"])
        r_resource = smp["n_resource_view"].corr(smp["hedef_kurs_not_pct"])
        r_perf_log = smp["n_perf_log"].corr(smp["hedef_kurs_not_pct"])
        r_activity = smp["performans_katilim_skoru"].corr(smp["hedef_kurs_not_pct"])
        
        say("\n" + "!"*40 + "\nPARADOKS DOGRULAMA ANALIZ SONUCLARI\n" + "!"*40)
        say(f" Ham Log Korelasyonu corr(n_log, kurs_notu)             : {r_raw:.3f}")
        say(f" Kaynak İndirme Korelasyonu corr(n_resource, kurs_notu)   : {r_resource:.3f}")
        say(f" Temizlenmiş Saf Log Korelasyonu corr(n_pure_log, kurs_notu): {r_pure:.3f}")
        say(f" Aktif Modül Log Korelasyonu corr(n_perf_log, kurs_notu)  : {r_perf_log:.3f}")
        say(f" Performans Katılım İndeksi corr(akt_skor, kurs_notu)     : {r_activity:.3f}")
        
        say("\n--- PARADOKS TEŞHİSİ VE STRATEJİK YOL HARİTASI ---")
        if abs(r_resource) > 0.1 and r_pure > r_raw:
            say(" -> TEŞHİS: HIPOTEZ DOGRULANDI! Korelasyonu bozan unsur 'Resource View' gürültüsü.")
            say("    ML MODEL STRATEJİSİ: 'n_log' yerine 'n_pure_log' veya 'n_perf_log' kullanın.")
        elif abs(r_raw) <= 0.05 and abs(r_perf_log) <= 0.05:
            say(" -> TEŞHİS: VERI TABLOLARI TAMAMEN BAGIMSIZ (Güçlü Sentetik/Manipülasyon Belirtisi).")
            say("    ML MODEL STRATEJİSİ: Log tabanlı tüm feature'ları drop edin! Modelde tamamen")
            say("    ['n_teslim', 'modul_not_ort', 'performans_katilim_skoru'] özelliklerine ağırlık verin.")
        else:
            say(" -> TEŞHİS: Beklenmeyen yapısal dağılım. Korelasyon eğilimleri karmaşık.")

rapor("07_fk_ve_features_rapor.txt", L)