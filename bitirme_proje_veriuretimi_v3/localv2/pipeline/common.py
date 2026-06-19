# -*- coding: utf-8 -*-
"""Pipeline ortak yardimcilar — Moodle 2014 anonim veri seti.

Veri ozellikleri:
- Dosya oneki: anon_mdl_  (or. anon_mdl_course.csv)
- Aylik log dosyalari: log-olarak-aylar/ (anon_enero.csv ... anon_diciembre.csv)
- Eski mdl_log formati (logstore_standard_log YOK)
- mdl_log kolonlari: id, time, userid, ip, course, module, cmid, action, url, info
- course.enddate YOK (Moodle <3.2)
- Zamanlar 10 haneli Unix epoch (saniye)

Zaman kaydirma (TIME_OFFSET_S):
  Ham veri 2014-2015 donemini kapsiyor. Dashboard'un anlamli gozukmesi icin
  tum timestamp'ler +12 yil (378,691,200 saniye) kaydiriliyor.
  2014-01-01 (1388534400) → 2026-01-01 (1767225600)
  Kural: sadece > 0 olan degerler kaydiriliyor (0 = Moodle'da "belirsiz/yok").
"""
import os, sys, glob, time
import pandas as pd

# Ham anon veri dizini. Oncelik: ANON_DATA_DIR env -> eski Desktop yolu -> Documents yolu.
# (Veri tasinabildigi icin var olan ilk dizin otomatik secilir.)
_CANDIDATE_DATA_DIRS = [
    os.environ.get("ANON_DATA_DIR"),
    r"C:\Users\2025\Desktop\proje-veri-seçimi-araştırma\proje-için-toplanılan-veriler\anonim-data",
    r"C:\Users\2025\Documents\ML-Project\anonim-data",
]
DATA_DIR = next((d for d in _CANDIDATE_DATA_DIRS if d and os.path.isdir(d)),
                _CANDIDATE_DATA_DIRS[1])
LOG_AYLAR_DIR = os.path.join(DATA_DIR, "log-olarak-aylar")
PREFIX = "anon_mdl_"

NOW = int(time.time())
TS_LO = 1_000_000_000  # 2001-09 oncesi epoch gecersiz

# 2014-01-01 → 2026-01-01: tam 4383 gun (2016 + 2020 + 2024 artik yillari dahil)
TIME_OFFSET_S = 378_691_200

MONTHLY_LOG_FILES = sorted(glob.glob(os.path.join(LOG_AYLAR_DIR, "anon_*.csv")))

_cache = {}

def load(table, usecols=None, dtype=None):
    """anon_mdl_<table>.csv dosyasini okur; yoksa None doner."""
    cache_key = (table, tuple(usecols) if usecols else None)
    if cache_key in _cache:
        return _cache[cache_key]
    path = os.path.join(DATA_DIR, PREFIX + table + ".csv")
    if not os.path.exists(path):
        _cache[cache_key] = None
        return None
    df = pd.read_csv(
        path, sep=",", low_memory=False,
        encoding="utf-8-sig", encoding_errors="replace",
        on_bad_lines="skip", usecols=usecols, dtype=dtype
    )
    df.columns = [str(c).strip().lower() for c in df.columns]
    _cache[cache_key] = df
    return df


def col(df, *cands, table="?", zorunlu=True):
    """Aday adlardan ilk var olan kolonu dondurur."""
    for c in cands:
        if c in df.columns:
            return c
    if zorunlu:
        raise SystemExit(
            f"[{table}] beklenen kolon bulunamadi: {cands}\n"
            f"  Mevcut: {list(df.columns)}"
        )
    return None


def num(s):
    return pd.to_numeric(s, errors="coerce")


def load_monthly_logs(usecols=None, filtered_users=None, filtered_courses=None,
                      chunk_size=500_000):
    """12 aylik log dosyalarini birlestirir.

    filtered_users/filtered_courses verilirse erken filtreleme yapar (RAM tasarrufu).
    Doner: DataFrame(id, time, userid, course, module, cmid, action)
    """
    LOG_COLS = list(usecols) if usecols else ["id", "time", "userid", "course", "module", "cmid", "action"]

    # filtered_courses varsa course kolonu LOG_COLS'ta olmak zorunda
    _course_col_added = False
    if filtered_courses is not None and "course" not in LOG_COLS and "courseid" not in LOG_COLS:
        LOG_COLS.append("course")
        _course_col_added = True

    parts = []

    for fpath in MONTHLY_LOG_FILES:
        month = os.path.basename(fpath).replace("anon_", "").replace(".csv", "")
        print(f"  Yukleniyor: {month} ...", end=" ")

        for chunk in pd.read_csv(
            fpath, sep=",", low_memory=False,
            encoding="utf-8-sig", encoding_errors="replace",
            on_bad_lines="skip", usecols=LOG_COLS,
            chunksize=chunk_size
        ):
            chunk.columns = [str(c).strip().lower() for c in chunk.columns]
            courseid_col = col(chunk, "course", "courseid", table="log", zorunlu=(filtered_courses is not None))
            if filtered_users is not None:
                chunk = chunk[chunk["userid"].isin(filtered_users)]
            if filtered_courses is not None and courseid_col is not None:
                chunk = chunk[chunk[courseid_col].isin(filtered_courses)]
            if len(chunk):
                parts.append(chunk)

        print(f"{sum(len(p) for p in parts):,} satir (toplam)")

    if not parts:
        return pd.DataFrame(columns=LOG_COLS)

    log_df = pd.concat(parts, ignore_index=True)

    # Kolon adi normalizasyonu: 'course' -> courseid icin alias ekle
    if "course" in log_df.columns and "courseid" not in log_df.columns:
        log_df = log_df.rename(columns={"course": "courseid"})

    # Caller usecols'a dahil etmediyse gecici ekledigimiz course kolonunu dusur
    if _course_col_added and "courseid" in log_df.columns:
        log_df = log_df.drop(columns=["courseid"])

    # Zaman kaydirma: ham log 2014-2015, dashboard icin +12 yil (2026-2027)
    if "time" in log_df.columns:
        log_df["time"] = pd.to_numeric(log_df["time"], errors="coerce")
        _mask = log_df["time"].notna() & (log_df["time"] > 0)
        log_df.loc[_mask, "time"] += TIME_OFFSET_S

    return log_df


def kaydet(cikti_dir, ad, df):
    os.makedirs(cikti_dir, exist_ok=True)
    p = os.path.join(cikti_dir, ad)
    df.to_csv(p, index=False, encoding="utf-8-sig")
    print(f">>> Kaydedildi: {p}  ({len(df):,} satir, {len(df.columns)} kolon)")
    return p


def rapor(cikti_dir, ad, satirlar):
    os.makedirs(cikti_dir, exist_ok=True)
    p = os.path.join(cikti_dir, ad)
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(map(str, satirlar)))
    print(f">>> Rapor: {p}")
    return p


def yuzde(a, b):
    return 100.0 * a / b if b else float("nan")
