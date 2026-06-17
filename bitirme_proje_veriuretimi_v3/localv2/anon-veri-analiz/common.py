# -*- coding: utf-8 -*-
"""Ortak yardimcilar — 2014-2015 anonim Moodle CSV seti.

BU SETIN BILINEN OZELLIKLERI (on denetimden):
- Dosya on eki: anon_  (or. anon_log.csv); ayrac: ","; basliklar mevcut
- ESKI log tablosu var: mdl_log  (mdl_logstore_standard_log YOK -> kod otomatik secer)
- mdl_course_completions / course_modules_completion YOK (kod alternatif kanit kullanir)
- mdl_course.enddate buyuk olasilikla YOK (Moodle <3.2) -> pencere varsayimi yapilir
- Zamanlar 10 haneli Unix epoch (SANIYE). Moodle milisaniye TUTMAZ.
Kullanim: her script tek basina calisir:  python 01_sentetiklik.py [VERI_KLASORU]
"""
import os, sys, glob, time
import pandas as pd

DATA_DIR = r"C:\Users\2025\Desktop\proje-veri-seçimi-araştırma\proje-için-toplanılan-veriler\anonim-data"
if len(sys.argv) > 1:
    DATA_DIR = sys.argv[1]
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cikti")
os.makedirs(OUT_DIR, exist_ok=True)

COURSE_SURESI_AY = 6      # course.enddate yoksa: startdate + bu kadar ay
NOW = int(time.time())
TS_LO = 1_000_000_000     # 2001-09 oncesi epoch'lar gecersiz sayilir

_pref = None
def prefix():
    global _pref
    if _pref is None:
        for p in ("anon_mdl_", "mdl_", ""):
            newpath = os.path.join(DATA_DIR, p + "course.csv")
            print(newpath)
            if glob.glob(os.path.join(DATA_DIR, p + "course.csv")):
                _pref = p
                break
        else:
            raise SystemExit(f"HATA: course.csv bulunamadi -> {DATA_DIR}\n"
                             "Yolu kontrol edin veya scripti calistirirken arguman verin.")
    return _pref

_cache = {}
def load(table):
    """anon_<table>.csv dosyasini okur; yoksa None doner. Kolon adlari kucultulur."""
    if table in _cache:
        return _cache[table]
    path = os.path.join(DATA_DIR, prefix() + table + ".csv")
    if not os.path.exists(path):
        _cache[table] = None
        return None
    df = pd.read_csv(path, sep=",", low_memory=False,
                     encoding="utf-8-sig", encoding_errors="replace",
                     on_bad_lines="skip")
    df.columns = [str(c).strip().lower() for c in df.columns]
    _cache[table] = df
    return df

def col(df, *cands, table="?", zorunlu=True):
    """Aday adlardan ilk var olan kolonu dondurur; yoksa bilgilendirici hata."""
    for c in cands:
        if c in df.columns:
            return c
    if zorunlu:
        raise SystemExit(f"[{table}] beklenen kolon bulunamadi: {cands}\n"
                         f"  Mevcut kolonlar: {list(df.columns)}\n"
                         "  -> Basliklar standart Moodle adlarinda degilse bu listeyi bana gonderin.")
    return None

def num(s):
    return pd.to_numeric(s, errors="coerce")

def ts_ok(s):
    """Sadece gecerli epoch'lari (2001..simdi) birakir, digerleri NaN."""
    v = num(s)
    return v.where((v >= TS_LO) & (v <= NOW))

def get_log():
    """(ad, df, kolon_haritasi). Yeni logstore varsa onu, yoksa ESKI mdl_log'u kullanir."""
    new = load("logstore_standard_log")
    if new is not None and len(new):
        m = dict(time=col(new, "timecreated", table="logstore_standard_log"),
                 userid=col(new, "userid", table="logstore_standard_log"),
                 courseid=col(new, "courseid", table="logstore_standard_log"),
                 cmid=col(new, "contextinstanceid", "cmid", table="logstore_standard_log", zorunlu=False),
                 action=col(new, "action", table="logstore_standard_log", zorunlu=False))
        return "logstore_standard_log", new, m
    old = load("log")
    if old is None:
        raise SystemExit("HATA: ne logstore_standard_log ne de log tablosu var.")
    m = dict(time=col(old, "time", table="log"),
             userid=col(old, "userid", table="log"),
             courseid=col(old, "course", "courseid", table="log"),
             cmid=col(old, "cmid", table="log", zorunlu=False),
             action=col(old, "action", table="log", zorunlu=False))
    return "log", old, m

def rapor(ad, satirlar):
    p = os.path.join(OUT_DIR, ad)
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(map(str, satirlar)))
    print(f"\n>>> rapor kaydedildi: {p}")

def kaydet(ad, df):
    p = os.path.join(OUT_DIR, ad)
    df.to_csv(p, index=False, encoding="utf-8-sig")
    print(f">>> csv kaydedildi: {p}  ({len(df)} satir)")

def yuzde(a, b):
    return 100.0 * a / b if b else float("nan")
