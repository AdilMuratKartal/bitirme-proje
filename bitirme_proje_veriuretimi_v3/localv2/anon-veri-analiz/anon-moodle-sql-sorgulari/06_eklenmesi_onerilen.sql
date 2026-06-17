-- =====================================================================
-- 06 — EKLENMESI ONERILEN SORGULAR (yukledginiz scriptlerde YOKTU)
-- Projeniz (basari / terk tahmini) icin degerli ama elinizdeki setlerde
-- bulunmayan analizler. Hepsi bizim anon sema (eski log, completions yok) ile uyumlu.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 6.1  FORUM KATILIMI (forum_post + forum_discussions) — sosyal etkilesim feature'i
-- ---------------------------------------------------------------------
SELECT
    d.course AS courseid,
    p.userid,
    COUNT(DISTINCT p.id)         AS gonderi_sayisi,
    COUNT(DISTINCT d.id)         AS katildigi_tartisma,
    SUM(p.parent=0)              AS actigi_konu       -- parent=0 -> yeni konu
FROM mdl_forum_post p
JOIN mdl_forum_discussions d ON d.id = p.discussion
GROUP BY d.course, p.userid
ORDER BY d.course, gonderi_sayisi DESC;

-- ---------------------------------------------------------------------
-- 6.2  KAYNAK GORUNTULEME YOGUNLUGU (log uzerinden, modul tipine gore)
--   Eski log'da action='view', module='resource'/'url'/'page'/'book'...
-- ---------------------------------------------------------------------
SELECT
    l.course AS courseid, l.userid, l.module AS modul_tipi,
    COUNT(*) AS goruntuleme,
    COUNT(DISTINCT l.cmid) AS farkli_kaynak
FROM mdl_log l
WHERE l.action LIKE 'view%' AND l.module IN ('resource','url','page','book','folder')
GROUP BY l.course, l.userid, l.module;

-- ---------------------------------------------------------------------
-- 6.3  KURS ICI PERCENTILE / SIRALAMA (akrana gore basari feature'i)
--   Mutlak not yerine "kurs icinde nerede" daha guclu bir ML ozelligidir.
-- ---------------------------------------------------------------------
SELECT
    gi.courseid, gg.userid, gg.finalgrade,
    ROUND(PERCENT_RANK() OVER (PARTITION BY gi.courseid ORDER BY gg.finalgrade),3) AS kurs_ici_percentile
FROM mdl_grade_grades gg
JOIN mdl_grade_items gi ON gi.id=gg.itemid AND gi.itemtype='course'
WHERE gg.finalgrade IS NOT NULL;
-- NOT: PERCENT_RANK MySQL 8+/MariaDB 10.2+ gerektirir. Eski surumde alt-sorgu ile sayim yapin.

-- ---------------------------------------------------------------------
-- 6.4  ERKEN-UYARI FEATURE'I: kursun ilk 4 haftasindaki aktivite
--   Dropout modellerinde en guclu sinyallerden biri "erken katilim"dir.
-- ---------------------------------------------------------------------
SELECT
    l.course AS courseid, l.userid,
    SUM(l.time < c.startdate + 28*86400) AS ilk4hafta_log,
    COUNT(*) AS toplam_log,
    ROUND(100*SUM(l.time < c.startdate + 28*86400)/COUNT(*),1) AS ilk4hafta_pct
FROM mdl_log l
JOIN mdl_course c ON c.id = l.course
WHERE c.startdate>0 AND l.time>0
GROUP BY l.course, l.userid;

-- ---------------------------------------------------------------------
-- 6.5  CALISMA ALISKANLIGI: gece / hafta sonu aktivite orani
--   Hem davranissal feature hem de sentetiklik kontrolu (tekduze 7/24 = supheli).
-- ---------------------------------------------------------------------
SELECT
    l.userid,
    ROUND(100*AVG(HOUR(FROM_UNIXTIME(l.time)) < 6),1)              AS gece_pct,
    ROUND(100*AVG(DAYOFWEEK(FROM_UNIXTIME(l.time)) IN (1,7)),1)    AS hafta_sonu_pct,
    COUNT(*) AS n_log
FROM mdl_log l WHERE l.time>0
GROUP BY l.userid
HAVING n_log >= 20;

-- ---------------------------------------------------------------------
-- 6.6  KURS NOTU GECTI/KALDI OZETI (mdl_grade_letters esigi ile, varsa)
--   grade_letters kurs/baglam basina harf esiklerini tutar.
-- ---------------------------------------------------------------------
SELECT
    e.courseid,
    COUNT(*) AS notu_olan_ogrenci,
    SUM(100*cg.finalgrade/NULLIF(cgi.grademax,0) >= 50) AS gecen,   -- 50 esigi orektir
    ROUND(100*AVG(100*cg.finalgrade/NULLIF(cgi.grademax,0) >= 50),1) AS gecme_pct
FROM mdl_enrol e
JOIN mdl_grade_items cgi ON cgi.courseid=e.courseid AND cgi.itemtype='course'
JOIN mdl_grade_grades cg ON cg.itemid=cgi.id
WHERE cg.finalgrade IS NOT NULL AND cgi.grademax>0
GROUP BY e.courseid;

-- ---------------------------------------------------------------------
-- 6.7  GUNLUK PLATFORM NABZI (zaman serisi; sentetik 'duz' trafik tespiti)
-- ---------------------------------------------------------------------
SELECT
    DATE(FROM_UNIXTIME(l.time)) AS gun,
    COUNT(*) AS olay, COUNT(DISTINCT l.userid) AS aktif_kullanici
FROM mdl_log l WHERE l.time>0
GROUP BY gun ORDER BY gun;
-- Gercek akademik takvimde haftalik dalgalanma ve tatil dususleri gorulur;
-- kusursuz duz bir cizgi sentetik uretim isaretidir.
