# -*- coding: utf-8 -*-
"""01 — SENTETIKLIK / GERCEKLIK KONTROLU
Not dagilimi dogallik testleri + zaman damgasi (saniye duzeyi) dagilimi.
NOT: Moodle epoch'u SANIYE cinsindendir; milisaniye analizi bu yuzden imkansizdir,
saniye-ici dagilim ayni amaca hizmet eder.
"""
from common import *
L = []
def say(s=""):
    s = str(s); print(s); L.append(s)

say("="*70); say("01 SENTETIKLIK / GERCEKLIK KONTROLU"); say("="*70)
gg = load("grade_grades"); gi = load("grade_items")
if gg is None: raise SystemExit("grade_grades.csv yok")
fg  = col(gg, "finalgrade", table="grade_grades")
iid = col(gg, "itemid",     table="grade_grades")
uid = col(gg, "userid",     table="grade_grades")
g_all = num(gg[fg])
say(f"Not satiri: {len(gg)} | dolu finalgrade: {g_all.notna().sum()} "
    f"(%{yuzde(g_all.notna().sum(), len(gg)):.1f}) | NULL: {g_all.isna().sum()}")
say(f"finalgrade==0 olan: {(g_all==0).sum()}   [0 = GIRILMIS nottur; NULL = girilmemis/muaf]")
g = g_all.dropna(); gp = g[g > 0]

say(f"\n-- 1A) Yuvarlak-deger analizi (finalgrade>0, n={len(gp)}) --")
say(f"  tam sayi   : %{100*(gp%1==0).mean():.1f}")
say(f"  5'in kati  : %{100*(gp%5==0).mean():.1f}")
say(f"  10'un kati : %{100*(gp%10==0).mean():.1f}")
vc = gp.round(3).value_counts()
say("  En sik 12 deger:")
for v, c2 in vc.head(12).items():
    say(f"    {v:>10}: {c2:>7}  (%{100*c2/len(gp):.2f})")
say(f"  Tek bir degerin azami payi: %{100*vc.iloc[0]/len(gp):.2f}")

if gi is not None:
    gid = col(gi, "id", table="grade_items")
    gim = col(gi, "itemmodule", table="grade_items", zorunlu=False)
    if gim:
        mm = gg[[iid, fg]].merge(gi[[gid, gim]], left_on=iid, right_on=gid, how="left")
        mm["v"] = num(mm[fg]); mm = mm[mm["v"] > 0]
        agg = mm.groupby(gim)["v"].agg(n="size", tam=lambda s: 100*(s % 1 == 0).mean())
        say("\n  Modul bazinda tam-sayi orani (n'e gore ilk 10):")
        for ix, r in agg.sort_values("n", ascending=False).head(10).iterrows():
            say(f"    {str(ix):<14} n={int(r['n']):>7}  tam-sayi %{r['tam']:.1f}")
        say("  YORUM: quiz otomatik hesaplanir -> ondalik DOGAL; assign elle girilir -> 5/10 kati DOGAL.")
        say("         TUM modullerde %95+ tam sayi VE ayni degerlerin tekrarinda yigilma = sentetik suphesi.")

say("\n-- 1B) Son-hane (terminal digit) testi --")
ints = gp[(gp % 1 == 0) & (gp >= 10)].astype(int)
if len(ints):
    ld = (ints % 10).value_counts(normalize=True).sort_index() * 100
    say("  " + " ".join(f"{d}:%{ld.get(d,0):.1f}" for d in range(10)))
    say("  Elle girilen gercek notlarda 0/5 yigilmasi DOGALDIR; tum haneler ~%10 ise 'fazla duzgun'.")

say("\n-- 1C) Benford ilk-hane (REFERANS: 0-100 sinirli olcekte Benford zaten beklenmez) --")
fd = gp[gp >= 1].astype(str).str.replace(".", "", regex=False).str.lstrip("0").str[0]
fd = fd[fd.str.isdigit()].astype(int); fd = fd[fd > 0]
exp = {1:30.1,2:17.6,3:12.5,4:9.7,5:7.9,6:6.7,7:5.8,8:5.1,9:4.6}
obs = fd.value_counts(normalize=True) * 100
mad = sum(abs(float(obs.get(d, 0)) - exp[d]) for d in range(1, 10)) / 9
say("  " + " ".join(f"{d}:%{float(obs.get(d,0)):.1f}" for d in range(1, 10)))
say(f"  Benford'dan ort. mutlak sapma (MAD) = {mad:.2f}  (sinirli not olceginde yuksek cikmasi normaldir;")
say("  asil sinyal 1A/1B/1D/1E testleridir)")

say("\n-- 1D) Birebir kopyalanan not vektorleri --")
t1 = gg[[uid, iid, fg]].dropna(subset=[fg]).copy()
t1["p"] = t1[iid].astype(str) + ":" + num(t1[fg]).round(2).astype(str)
cnt = t1.groupby(uid)["p"].size()
coklu = set(cnt[cnt >= 3].index)
vec = t1[t1[uid].isin(coklu)].sort_values(iid).groupby(uid)["p"].agg("|".join)
vvc = vec.value_counts(); dups = vvc[vvc > 1]
n_dup = int(dups.sum()) if len(dups) else 0
say(f"  >=3 notu olan kullanici: {len(vec)} | TIPATIP ayni not vektorunu paylasan: {n_dup} "
    f"(%{yuzde(n_dup, len(vec)):.2f}) | en buyuk kopya grubu: {int(vvc.iloc[0]) if len(vvc) else 0}")
say("  YORUM: %1 alti temiz; yuksekse satir kopyalayan sentetik uretim suphesi.")
if len(dups):
    kaydet("01_kopya_not_vektorleri.csv",
           dups.head(20).rename("kullanici_sayisi").reset_index().rename(columns={"index": "vektor"}))

say("\n-- 1E) Zaman damgasi saniye/dakika dagilimi --")
lname, log, lm = get_log()
say(f"  Kullanilan log tablosu: mdl_{lname}" + ("  (ESKI format; logstore yok)" if lname=="log" else ""))
t = ts_ok(log[lm["time"]]).dropna().astype("int64")
def unif(x, n, label):
    c2 = x.value_counts().reindex(range(n), fill_value=0)
    e = len(x) / n
    chi = float(((c2 - e) ** 2 / e).sum())
    say(f"  {label}: n={len(x)} | chi2={chi:,.0f} (serbestlik={n-1}; ~{n-1} civari=tekduze) | "
        f"max pay %{100*c2.max()/len(x):.2f} (beklenen %{100/n:.2f}) | ':00' payi %{100*c2.iloc[0]/len(x):.2f}")
unif(t % 60, 60, "log saniye(0-59)")
unif((t // 60) % 60, 60, "log dakika(0-59)")
gtmc = col(gg, "timemodified", table="grade_grades", zorunlu=False)
if gtmc:
    gt = ts_ok(gg[gtmc]).dropna().astype("int64")
    if len(gt): unif(gt % 60, 60, "not timemodified saniye")
say("  YORUM: Gercek trafikte saniyeler ~tekduzedir. ':00'/tek saniyede yigilma = cron/toplu yazim.")
say("         Her sey 'kusursuz tekduze' + 1B'de haneler kusursuz + kopya vektor yoksa bile,")
say("         sentetiklik karari TEK teste degil testlerin TUTARLILIGINA dayanmalidir.")
d = t.sort_values().diff().dropna()
say(f"  Ardisik olay araligi: medyan {d.median():.0f}s | ayni-saniye orani %{100*(d==0).mean():.2f} | p99 {d.quantile(.99):.0f}s")

if "id" in log.columns:
    s2 = pd.DataFrame({"id": num(log["id"]), "t": ts_ok(log[lm["time"]])}).dropna().sort_values("id")
    inv = 100 * (s2["t"].diff() < 0).mean()
    smp = s2.sample(min(200000, len(s2)), random_state=1)
    sp = smp["id"].rank().corr(smp["t"].rank())
    say(f"\n-- 1F) log.id - zaman monotonlugu: geri giden zaman %{inv:.3f} | Spearman={sp:.4f}")
    say("  Gercek Moodle'da id otomatik artar -> Spearman ~1.000 beklenir.")
    say("  Belirgin dusukse satirlar sonradan uretilmis/karistirilmis demektir (guclu sentetiklik kaniti).")

rapor("01_sentetiklik_rapor.txt", L)
