# -*- coding: utf-8 -*-
"""clean_df_10_2_5.csv gercekten anonim Moodle setinden mi uretilmis? KESIN test.
Mantik: turetilmisse UID'lerin ~%100'u anon_user.id icinde, COURSE'larin ~%100'u
anon_course.id icinde ve (UID,COURSE) ciftleri kayit (enrolment) ciftleri icinde olmali.
Kullanim:  python eslesme_kontrol.py
(yollari asagida gerekirse duzenleyin)
"""
import os
import pandas as pd

ANON = r"C:\Users\2025\Desktop\proje-veri-seçimi-araştırma\proje-için-toplanılan-veriler\anonim-data"
CLEAN = r"C:\Users\2025\Desktop\proje-veri-seçimi-araştırma\proje-için-toplanılan-veriler\clean_df_10_2.5.csv"   # dosya neredeyse o yolu yazin

num = lambda s: pd.to_numeric(s, errors="coerce")
A = lambda t: pd.read_csv(os.path.join(ANON, "anon_mdl_" + t + ".csv"),
                          low_memory=False, encoding="utf-8-sig")

cd = pd.read_csv(CLEAN, sep=";", low_memory=False)
uid = set(num(cd["UID"]).dropna().astype("int64"))
crs = set(num(cd["COURSE"]).dropna().astype("int64"))
print(f"clean_df: {len(cd)} satir | {len(uid)} UID | {len(crs)} kurs")

u = A("user"); c = A("course")
uset = set(num(u["id"]).dropna().astype("int64"))
cset = set(num(c["id"]).dropna().astype("int64"))
p1 = 100 * len(uid & uset) / len(uid)
p2 = 100 * len(crs & cset) / len(crs)
print(f"\nTEST 1  UID'ler anon_user icinde      : %{p1:.2f}")
print(f"TEST 2  COURSE'lar anon_course icinde : %{p2:.2f}")

ue = A("user_enrolments"); en = A("enrol")
e = ue.merge(en, left_on="enrolid", right_on="id", suffixes=("", "_e"))
pairs = set(zip(num(e["userid"]).astype("int64"), num(e["courseid"]).astype("int64")))
cdp = list(zip(num(cd["UID"]).astype("int64"), num(cd["COURSE"]).astype("int64")))
p3 = 100 * sum(1 for k in cdp if k in pairs) / len(cdp)
print(f"TEST 3  (UID,COURSE) ciftleri kayit ciftleri icinde: %{p3:.2f}")

print("\nHUKUM:")
if min(p1, p2, p3) >= 99:
    print("  KESIN: clean_df bu anonim veritabanindan uretilmis.")
elif min(p1, p2) >= 95:
    print("  BUYUK OLASILIKLA ayni kaynak (kucuk farklar filtre/temizlikten olabilir).")
else:
    print("  Dusuk ortusme: farkli bir kaynaktan/versiyondan uretilmis olabilir.")
