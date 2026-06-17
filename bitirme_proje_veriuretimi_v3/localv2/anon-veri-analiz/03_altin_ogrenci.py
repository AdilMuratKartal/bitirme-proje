# -*- coding: utf-8 -*-
"""03 — ALTIN OGRENCI KUMESI (eksiksiz profil)
ONEMLI UYARLAMA: Bu sette mdl_course_completions ve course_modules_completion YOK.
'Tamamlama' kosulu yerine SOMUT KANIT kullanildi: odev teslimi VEYA bitmis quiz denemesi.
Kume tanimi: kayitli (enrolment) + >=1 log + >=1 dolu finalgrade + >=1 teslim/deneme.
"""
from common import *
L = []
def say(s=""):
    s = str(s); print(s); L.append(s)

say("="*70); say("03 ALTIN OGRENCI KUMESI"); say("="*70)
say("NOT: course_completions tablosu bu dokumde yok -> kriter teslim/deneme kanitiyla degistirildi.\n")

ue = load("user_enrolments"); u = load("user"); gg = load("grade_grades")
asub = load("assign_submission"); qa = load("quiz_attempts"); enr = load("enrol")
lname, log, lm = get_log()

def S(s): return set(num(s).dropna().astype("int64"))

uid_all = S(u[col(u, "id", table="user")])
uid_enr = S(ue[col(ue, "userid", table="user_enrolments")])
uid_log = S(log[lm["userid"]])
gmask = num(gg[col(gg, "finalgrade", table="grade_grades")]).notna()
uid_gr = S(gg.loc[gmask, col(gg, "userid", table="grade_grades")])
uid_sub = S(asub[col(asub, "userid", table="assign_submission")]) if asub is not None else set()
uid_att = set()
if qa is not None:
    fin = num(qa[col(qa, "timefinish", table="quiz_attempts")]) > 0
    uid_att = S(qa.loc[fin, col(qa, "userid", table="quiz_attempts")])
uid_act = uid_sub | uid_att

s1 = uid_enr & uid_log
s2 = s1 & uid_gr
golden = s2 & uid_act
say(f"Toplam kullanici (mdl_user)        : {len(uid_all)}")
say(f"Kayitli kullanici (enrolment)      : {len(uid_enr)}  (%{yuzde(len(uid_enr), len(uid_all)):.1f})")
say(f"  + en az 1 log kaydi              : {len(s1)}  (kayitlilarin %{yuzde(len(s1), len(uid_enr)):.1f})")
say(f"  + en az 1 dolu finalgrade        : {len(s2)}  (kayitlilarin %{yuzde(len(s2), len(uid_enr)):.1f})")
say(f"  + teslim/bitmis-quiz kaniti      : {len(golden)}")
say("")
say(f">>> ALTIN KUME: {len(golden)} ogrenci")
say(f">>> Kayitli ogrencilere orani : %{yuzde(len(golden), len(uid_enr)):.1f}")
say(f">>> Tum kullanicilara orani   : %{yuzde(len(golden), len(uid_all)):.1f}")
say("    (Ogretmen/yonetici hesaplari da 'kullanici' sayildigi icin kayitli-oran daha anlamlidir.)")
kaydet("03_altin_ogrenci_listesi.csv", pd.DataFrame({"userid": sorted(golden)}))

# Eksiklik profili: hangi katman kac kisi kaybettiriyor?
say("\nKayip analizi (kayitli olup kumeden dusenler):")
say(f"  log'u hic olmayan kayitli        : {len(uid_enr - uid_log)}")
say(f"  dolu notu hic olmayan kayitli    : {len(uid_enr - uid_gr)}")
say(f"  teslim/deneme kaniti olmayan     : {len(uid_enr - uid_act)}")

# Kurs bazinda (yaklasik: kanitlar kullanici duzeyinde esleniyor)
if enr is not None:
    e = ue[[col(ue, "enrolid", table="user_enrolments"), col(ue, "userid")]].copy()
    e.columns = ["eid", "uid"]
    em = enr[[col(enr, "id", table="enrol"), col(enr, "courseid", table="enrol")]].copy()
    em.columns = ["eid", "cid"]
    uc = e.merge(em, on="eid", how="left").dropna()
    uc["uid"] = num(uc["uid"]); uc["cid"] = num(uc["cid"])
    uc["golden"] = uc["uid"].isin(golden)
    per = uc.groupby("cid").agg(kayitli=("uid", "nunique"),
                                altin=("golden", "sum")).reset_index()
    per["oran_pct"] = (100 * per["altin"] / per["kayitli"]).round(1)
    kaydet("03_kurs_bazinda_altin_kume.csv", per.sort_values("kayitli", ascending=False))
    say(f"\nKurs bazinda dagilim CSV'ye yazildi. Medyan kurs-ici altin oran: %{per['oran_pct'].median():.1f}")
    say("ML ICIN: modeli once bu kume uzerinde egitip sonra eksik-veri stratejisiyle genisletin.")
rapor("03_altin_ogrenci_rapor.txt", L)
