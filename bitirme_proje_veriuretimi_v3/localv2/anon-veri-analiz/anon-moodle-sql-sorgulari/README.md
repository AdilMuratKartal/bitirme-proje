# Moodle 2014-2015 Anonim Set — SQL Sorgu Paketi

Bu paket, yüklediğiniz orijinal SQL scriptlerinden **işinize yarayanların**
sizin **anonim veri setinizin gerçek şemasına** uyarlanmış halidir + öğrenci
dashboard'u, veri kalitesi ve ML feature sorguları + eklenmesi önerilen sorgular.

Sözdizimi **MySQL/MariaDB** (Moodle'ın doğal veritabanı). PostgreSQL/DuckDB için aşağıya bakın.

## Kurulum (3 yol)
1. **MySQL/MariaDB**: Her `anon_X.csv` dosyasını `mdl_X` tablosu olarak içe aktarın
   (örn. `anon_course.csv` → `mdl_course`). Öneki `anon_` tutarsanız tüm dosyalarda
   `mdl_` → `anon_` değiştirin (toplu bul-değiştir).
2. **PostgreSQL**: `FROM_UNIXTIME(x)` → `TO_TIMESTAMP(x)`, `DATE_FORMAT(t,'%Y-%m-%d')`
   → `TO_CHAR(t,'YYYY-MM-DD')`, `MOD(a,b)` → `a % b`, `SUM(boolean)` → `SUM((cond)::int)`,
   `YEARWEEK(t,3)` → `TO_CHAR(t,'IYYYIW')`, `DATEDIFF` → tarih çıkarma. `IF/IFNULL` yok → `CASE`/`COALESCE`.
3. **DB kurmadan (DuckDB)**: `SELECT * FROM read_csv_auto('anon_course.csv')`.
   `FROM_UNIXTIME(x)` → `to_timestamp(x)`, `DATE(...)` → `CAST(... AS DATE)`. (Bu paket bu
   yöntemle test edildi.)

## Bu sete özgü KRİTİK uyarlamalar (orijinal scriptlerden farklar)
- **Eski log**: `mdl_logstore_standard_log` YOK → tüm log sorguları **eski `mdl_log`**
  (kolonlar: time, userid, course, module, cmid, action, url, info) üzerinden yazıldı.
- **Tamamlama yok**: `mdl_course_completions` / `course_modules_completion` YOK →
  "tamamladı" yerine **kanıt** (odev teslimi / bitmiş quiz denemesi) kullanıldı.
- **enddate yok**: `mdl_course.enddate` bu sürümde (Moodle <3.2) yok → kurs penceresinde
  "başlangıçtan önce log" oranı en güvenilir sinyaldir (varsayımdan etkilenmez).
- **İsimler placeholder**: `course.fullname` çoğunlukla sabit `nombre`; kullanıcı ad/eposta
  alanları anonim. **Gruplamayı ID ile yapın**; `course.shortname` koddur ve ayırt edicidir.
- **Çıkarılan tablolar** (orijinal scriptlerde vardı, sette YOK): `h5pactivity*`, `hvp`,
  `game`, `lti`, `assignsubmission_onlinetext`, `assignsubmission_file`,
  `assignfeedback_comments`, `grade_outcomes`.
- **Modül tipi**: sabit id (quiz=1, assign=6…) ile DEĞİL, daima `JOIN mdl_modules` ile çözülür.

## Dosyalar ve içerdikleri sorgular
**00_OKU_kurulum_ve_notlar.sql** — Yükleme, önek, şema notları (önce bunu okuyun).

**01_ogrenci_dashboard.sql** — Öğrenci tabanlı dashboard
- 1.1 Öğrenci özet kartı (platform geneli: kayıtlı kurs, log, aktif gün, teslim/quiz, ort. not)
- 1.2 Öğrenci × kurs satırı (asıl analiz granı; kurs notu dahil)
- 1.3 Haftalık katılım zaman serisi (katılım eğrisi/erken-uyarı grafiği)
- 1.4 Risk/terk adayı öğrenciler (completions olmadan, kanıt tabanlı)

**02_kurs_dashboard.sql** — Kurs tabanlı dashboard
- 2.1 Kurs özet tablosu (kayıt, aktiflik %, ort. kurs notu)
- 2.2 Kurs içi modül kompozisyonu + platform geneli modül dağılımı
- 2.3 Kurs not dağılımı (histogram kovaları)

**03_aktivite_detay_uyarlanmis.sql** — Sizin scriptlerinizden uyarlanmış
- 3.1 Odev teslimleri + not + geç/zamanında (Script.sql #1'in temizlenmiş hali)
- 3.2 Tüm modüllerde öğrenci notları (h5p/hvp/game/lti çıkarıldı, mdl_modules ile)
- 3.3 Lesson soru bazında doğru/yanlış oranı (Script-2.sql #3 uyarlaması)
- 3.4 Quiz deneme özeti (deneme sayısı, süre)

**04_veri_kalitesi.sql** — Sahtelik & tutarlılık (eşik: <%1 temiz, >%15-20 ciddi sorun)
- 4.1 Hayalet not (not var, aktivite yok) + 4.1b oran
- 4.2 Kayıp not (aktivite var, not yok/NULL) + oran
- 4.3 Not doğallığı (yuvarlaklık, en sık değerler)
- 4.4 Toplu giriş tuzağı (aynı dakikada girilen notlar)
- 4.5 Not teslimden önce mi girilmiş (güçlü sentetiklik işareti)
- 4.6 Kurs penceresi-log uyumu
- 4.7 FK yetim oranları (join'ler veri kaybettiriyor mu)
- 4.8 Altın öğrenci kümesi (eksiksiz profil)

**05_ml_feature_sorgulari.sql** — ML için (öğrenci × kurs granı)
- 5.1 Log tabanlı katılım feature'ları (view)
- 5.2 Teslim/quiz feature'ları (view)
- 5.3 Not feature'ları + hedef (view)
- 5.4 Nihai feature tablosu (ML'e beslenecek tek satır) + corr(log, not) tutarlılık testi

**06_eklenmesi_onerilen.sql** — Sizde olmayan ama değerli sorgular
- 6.1 Forum katılımı (gönderi/tartışma/konu) — sosyal etkileşim
- 6.2 Kaynak görüntüleme yoğunluğu (log üzerinden)
- 6.3 Kurs içi percentile/sıralama (akrana göre başarı)
- 6.4 Erken-uyarı: ilk 4 hafta aktivitesi (dropout için en güçlü sinyal)
- 6.5 Çalışma alışkanlığı: gece/hafta sonu oranı (+ sentetiklik kontrolü)
- 6.6 Geçti/kaldı özeti
- 6.7 Günlük platform nabzı (zaman serisi)

## Yorum rehberi
- 04'teki tutarsızlık oranları: **<%1 temiz**, **%1-15 incelenmeli**, **>%15-20 ciddi
  manipülasyon/bozulma**.
- Tek bir test sentetikliği KANITLAMAZ. Güçlü kanıt kombinasyonu: hayalet/kopya notlar +
  notların teslimden önce girilmesi (4.5) + corr(log, not) ≈ 0 (5.4) bir aradaysa.
- Toplu dakika yığılması (4.4) TEK başına genelde "hocanın Excel'den toplu yüklemesi"dir
  (gerçek veri ama zamansal feature'lar zayıflar) → 05'te o kalemlerin `timemodified`'ını kullanmayın.

> Bir kolon adı hata verirse (export'unuz standart Moodle adı kullanmıyorsa), o tablonun
> başlık satırını bana gönderin; eşlemeyi eklerim.
