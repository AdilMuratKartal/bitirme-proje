# -*- coding: utf-8 -*-
"""04 — KURS TARIH PENCERESI ile LOG UYUMU
ONEMLI: Moodle <3.2'de mdl_course'ta 'enddate' YOKTUR. Bu sette de buyuk olasilikla yok.
Strateji: enddate varsa kullan; yoksa pencere = [startdate, startdate + COURSE_SURESI_AY ay].
Ek olarak verinin kendisinden 'gozlenen aktiflik araligi' da raporlanir.
"""
from common import *
L = []
def say(s=""):
    s = str(s); print(s); L.append(s)

say("="*70); say("04 KURS PENCERESI - LOG UYUMU"); say("="*70)
c = load("course"); lname, log, lm = get_log()
cid = col(c, "id", table="course"); sd = col(c, "startdate", table="course")
edc = col(c, "enddate", table="course", zorunlu=False)

start = ts_ok(c[sd])
n0 = int((num(c[sd]).fillna(0) <= 0).sum())
say(f"Kurs sayisi: {len(c)} | startdate gecersiz/0 olan: {n0} (bunlar pencere analizinden haric)")
if edc:
    end = ts_ok(c[edc]); end = end.where(end > start)
    kay = "enddate kolonu"
else:
    end = pd.Series([float("nan")] * len(c))
    kay = None
if kay is None or end.notna().sum() == 0:
    end = start + COURSE_SURESI_AY * 30 * 86400
    kay = f"VARSAYIM: startdate + {COURSE_SURESI_AY} ay (enddate kolonu yok / bos)"
say(f"Bitis tarihi kaynagi: {kay}")

win = pd.DataFrame({"cid": num(c[cid]), "start": start, "end": end}).dropna(subset=["cid", "start"])
win = win[win["start"] > 0]
lj = pd.DataFrame({"cid": num(log[lm["courseid"]]),
                   "t": ts_ok(log[lm["time"]])}).dropna()
m = lj.merge(win, on="cid", how="inner")
say(f"\nPencereli kursa eslesen log: {len(m)} / toplam log {len(lj)}")
once  = (m["t"] < m["start"]).mean() * 100
sonra = (m["t"] > m["end"]).mean() * 100
icin  = 100 - once - sonra
say(f"  pencere ICINDE : %{icin:.2f}")
say(f"  baslangictan ONCE: %{once:.2f}   <- bu oran enddate varsayimindan ETKILENMEZ, en guvenilir sinyaldir")
say(f"  bitisten SONRA  : %{sonra:.2f}   <- enddate varsayimsa ihtiyatla yorumlayin")

per = m.assign(once=(m["t"] < m["start"]), sonra=(m["t"] > m["end"])) \
       .groupby("cid").agg(n_log=("t", "size"),
                           once_pct=("once", lambda s: 100 * s.mean()),
                           sonra_pct=("sonra", lambda s: 100 * s.mean())).reset_index()
kaydet("04_kurs_bazinda_pencere_uyumu.csv", per.sort_values("once_pct", ascending=False))
kotu = per[(per["n_log"] >= 100) & (per["once_pct"] > 20)]
say(f"\n'Baslamadan once' logu %20'yi asan yogun kurs (n_log>=100): {len(kotu)}")
for _, r in kotu.head(10).iterrows():
    say(f"  kurs {int(r['cid'])}: n={int(r['n_log'])} once %{r['once_pct']:.1f}")

g = m.groupby("cid")["t"].agg(["min", "max"])
g = g.join(win.set_index("cid")[["start"]])
say("\nGozlenen aktiflik (loglardan): kurs basina ilk-son log araligi medyani: "
    f"{((g['max']-g['min'])/86400).median():.0f} gun")
say("YORUM: 'once' orani yuksekse ya startdate'ler yanlis/anonimlestirilmis ya da loglar")
say("kurs takviminden bagimsiz uretilmis demektir. %1 alti idealdir.")
rapor("04_kurs_log_penceresi_rapor.txt", L)
