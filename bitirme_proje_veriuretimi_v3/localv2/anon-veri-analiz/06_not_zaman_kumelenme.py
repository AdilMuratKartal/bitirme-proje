# -*- coding: utf-8 -*-
"""06 — NOT GIRIS ZAMANLARININ KUMELENMESI ('toplu giris tuzagi')
grade_grades.timemodified: ayni gun/dakika/saniyede yigilma var mi?
Yorum: yigilma = ya hoca toplu yukleme yapti (gercek ama zamansal feature'lar zayiflar)
ya da uretici script topluca basti (sentetiklik isareti). Ayirt etmek icin
01'deki diger testlerle birlikte degerlendirin.
"""
from common import *
L = []
def say(s=""):
    s = str(s); print(s); L.append(s)

say("="*70); say("06 NOT ZAMAN DAMGASI KUMELENMESI"); say("="*70)
gg = load("grade_grades")
gtm = col(gg, "timemodified", table="grade_grades", zorunlu=False)
if not gtm:
    raise SystemExit("grade_grades.timemodified yok -> bu analiz yapilamaz.")
iid = col(gg, "itemid", table="grade_grades")
tm = ts_ok(gg[gtm]).dropna().astype("int64")
say(f"Gecerli timemodified: {len(tm)} / {len(gg)} (%{yuzde(len(tm), len(gg)):.1f})")
if len(tm) == 0:
    rapor("06_not_zaman_kumelenme_rapor.txt", L)
    raise SystemExit()

gun = pd.to_datetime(tm, unit="s").dt.normalize()
dvc = gun.value_counts()
say(f"\nKapsanan gun sayisi: {len(dvc)} | aralik: {gun.min().date()} -> {gun.max().date()}")
say(f"En yogun 10 gunun toplam payi: %{100*dvc.head(10).sum()/len(tm):.1f}")
say(f"En yogun TEK gunun payi      : %{100*dvc.iloc[0]/len(tm):.1f}  ({dvc.index[0].date()}, {int(dvc.iloc[0])} not)")
kaydet("06_gunluk_not_girisi.csv",
       dvc.rename("adet").rename_axis("gun").reset_index().sort_values("gun"))

dak = tm // 60
mvc = dak.value_counts()
say(f"\nEn buyuk TEK DAKIKA kumesi: {int(mvc.iloc[0])} not "
    f"({pd.to_datetime(int(mvc.index[0])*60, unit='s')})")
buyuk = mvc[mvc >= 100]
say(f">=100 notun ayni dakikada girildigi dakika sayisi: {len(buyuk)} | bu dakikalardaki not payi: %{100*buyuk.sum()/len(tm):.1f}")
sn = tm.value_counts()
say(f"En buyuk TEK SANIYE kumesi: {int(sn.iloc[0])} not")
kaydet("06_en_yogun_30_dakika.csv",
       mvc.head(30).rename("adet").rename_axis("epoch_dakika").reset_index()
          .assign(zaman=lambda d: pd.to_datetime(d["epoch_dakika"].astype("int64")*60, unit="s")))

# Kalem (grade_item) bazinda toplu giris
df2 = pd.DataFrame({"item": gg[iid], "dak": ts_ok(gg[gtm]) // 60}).dropna()
grp = df2.groupby("item")["dak"]
n = grp.size()
modal = grp.agg(lambda s: s.value_counts().iloc[0])
pay = (modal / n)[n >= 20]
say(f"\n>=20 notu olan kalem (grade_item): {len(pay)}")
say(f"  Notlarinin >=%80'i AYNI DAKIKADA girilen kalem: {(pay>=0.8).sum()} (%{100*(pay>=0.8).mean():.1f})")
say(f"  Ortalama 'modal dakika payi': %{100*pay.mean():.1f}")
say("  YORUM: Excel'den toplu aktarim ve 'notlari yeniden hesapla' islemleri bu deseni uretir;")
say("  bu kalemlerde timemodified'i ML'de ZAMANSAL ozellik olarak KULLANMAYIN, etiketleyip dislayin.")
kaydet("06_kalem_bazinda_toplu_giris.csv",
       pd.DataFrame({"n_not": n[n >= 20], "modal_dakika_pay": (pay*100).round(1)})
         .reset_index().sort_values("modal_dakika_pay", ascending=False))

saat = pd.to_datetime(tm, unit="s").dt.hour
hh = saat.value_counts(normalize=True).sort_index() * 100
say("\nSaat profili (UTC, %): " + " ".join(f"{h:02d}:{hh.get(h,0):.0f}" for h in range(0, 24, 2)))
gece = float(hh.reindex(range(0, 6)).fillna(0).sum())
hafta_sonu = (pd.to_datetime(tm, unit="s").dt.dayofweek >= 5).mean() * 100
say(f"Gece(00-06) payi: %{gece:.1f} | hafta sonu payi: %{hafta_sonu:.1f}")
say("Gercek kullanim gunduz+haftaici yogundur; tekduze 7/24 dagilim sentetiklik isaretidir.")
rapor("06_not_zaman_kumelenme_rapor.txt", L)
