-- =====================================================================
-- 01 — OGRENCI TABANLI DASHBOARD SORGULARI
-- Amac: Her ogrencinin platform genelindeki ozet profili (katilim + basari).
-- Kaynak tablolar: mdl_user, mdl_user_enrolments, mdl_enrol, mdl_log,
--                  mdl_grade_grades, mdl_grade_items, mdl_assign_submission,
--                  mdl_quiz_attempts.
-- NOT: completions/enddate olmadigi icin "tamamlama" = teslim/bitmis-deneme kaniti.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1.1  OGRENCI OZET KARTI (platform geneli, tek satir/ogrenci)
--   Dashboard'un ust seridi: kac kursa kayitli, toplam etkinlik, aktif gun,
--   ilk/son hareket, teslim & quiz sayisi, ortalama modul notu.
-- ---------------------------------------------------------------------
SELECT
    u.id AS userid,
    u.username,                                  -- anonimlestirilmis olabilir
    COUNT(DISTINCT e.courseid)            AS kayitli_kurs,
    COUNT(DISTINCT l.id)                  AS toplam_log,
    COUNT(DISTINCT DATE(FROM_UNIXTIME(l.time))) AS aktif_gun,
    CASE WHEN MIN(NULLIF(l.time,0))>0
         THEN DATE_FORMAT(FROM_UNIXTIME(MIN(NULLIF(l.time,0))),'%Y-%m-%d') END AS ilk_hareket,
    CASE WHEN MAX(l.time)>0
         THEN DATE_FORMAT(FROM_UNIXTIME(MAX(l.time)),'%Y-%m-%d') END           AS son_hareket,
    CASE WHEN u.lastaccess>0
         THEN DATE_FORMAT(FROM_UNIXTIME(u.lastaccess),'%Y-%m-%d') END          AS son_giris,
    (SELECT COUNT(*) FROM mdl_assign_submission s WHERE s.userid=u.id)         AS odev_teslim,
    (SELECT COUNT(*) FROM mdl_quiz_attempts qa
        WHERE qa.userid=u.id AND qa.timefinish>0)                             AS bitmis_quiz,
    ROUND(AVG(CASE WHEN gg.finalgrade IS NOT NULL AND gi.grademax>0
              THEN 100*gg.finalgrade/gi.grademax END),1)                      AS ort_modul_not_pct
FROM mdl_user u
LEFT JOIN mdl_user_enrolments ue ON ue.userid = u.id
LEFT JOIN mdl_enrol e            ON e.id = ue.enrolid
LEFT JOIN mdl_log l              ON l.userid = u.id
LEFT JOIN mdl_grade_grades gg    ON gg.userid = u.id
LEFT JOIN mdl_grade_items gi     ON gi.id = gg.itemid AND gi.itemtype='mod'
GROUP BY u.id, u.username, u.lastaccess
HAVING kayitli_kurs > 0          -- sadece bir kursa kayitli (ogrenci adayi) hesaplar
ORDER BY toplam_log DESC;

-- ---------------------------------------------------------------------
-- 1.2  OGRENCI x KURS DASHBOARD SATIRI (asil ML/analiz grani)
--   Her (ogrenci, kurs) cifti icin katilim + kurs notu. Dashboard'da
--   "bir kursa tikla -> ogrenci listesi" gorunumu icin idealdir.
-- ---------------------------------------------------------------------
SELECT
    e.courseid,
    c.shortname                              AS kurs_kodu,   -- fullname placeholder; shortname ayirt edici
    ue.userid,
    COUNT(DISTINCT l.id)                     AS log_sayisi,
    COUNT(DISTINCT DATE(FROM_UNIXTIME(l.time))) AS aktif_gun,
    SUM(l.action LIKE 'view%')               AS goruntuleme,
    CASE WHEN MAX(l.time)>0 THEN DATE_FORMAT(FROM_UNIXTIME(MAX(l.time)),'%Y-%m-%d') END AS son_hareket,
    cg.finalgrade                            AS kurs_notu,
    cgi.grademax                             AS kurs_not_max,
    ROUND(100*cg.finalgrade/NULLIF(cgi.grademax,0),1) AS kurs_not_pct
FROM mdl_user_enrolments ue
JOIN mdl_enrol e  ON e.id = ue.enrolid
JOIN mdl_course c ON c.id = e.courseid
LEFT JOIN mdl_log l ON l.userid = ue.userid AND l.course = e.courseid
-- kurs toplam notu = grade_items.itemtype='course'
LEFT JOIN mdl_grade_items cgi ON cgi.courseid = e.courseid AND cgi.itemtype='course'
LEFT JOIN mdl_grade_grades cg ON cg.itemid = cgi.id AND cg.userid = ue.userid
GROUP BY e.courseid, c.shortname, ue.userid, cg.finalgrade, cgi.grademax
ORDER BY e.courseid, log_sayisi DESC;

-- ---------------------------------------------------------------------
-- 1.3  HAFTALIK KATILIM ZAMAN SERISI (ogrenci bazli)
--   Dashboard'da "katilim egrisi" / erken-uyari grafigi icin.
-- ---------------------------------------------------------------------
SELECT
    l.userid,
    l.course AS courseid,
    YEARWEEK(FROM_UNIXTIME(l.time), 3) AS yil_hafta,   -- ISO hafta
    COUNT(*)                            AS olay_sayisi,
    SUM(l.action LIKE 'view%')          AS goruntuleme,
    SUM(l.action IN ('submit','add','update')) AS uretim_eylemi
FROM mdl_log l
WHERE l.time > 0
GROUP BY l.userid, l.course, yil_hafta
ORDER BY l.userid, l.course, yil_hafta;

-- ---------------------------------------------------------------------
-- 1.4  RISK / TERK ADAYI OGRENCILER (completions olmadan)
--   Kayitli ama (a) hic logu yok, ya da (b) hic dolu notu yok,
--   ya da (c) son hareketi kurs ortalamasinin cok gerisinde.
-- ---------------------------------------------------------------------
SELECT
    ue.userid, e.courseid,
    COUNT(DISTINCT l.id) AS log_sayisi,
    SUM(gg.finalgrade IS NOT NULL) AS dolu_not_sayisi,
    CASE
        WHEN COUNT(DISTINCT l.id)=0                         THEN 'hic_aktivite_yok'
        WHEN SUM(gg.finalgrade IS NOT NULL)=0               THEN 'aktivite_var_not_yok'
        ELSE 'aktif'
    END AS risk_durumu
FROM mdl_user_enrolments ue
JOIN mdl_enrol e ON e.id = ue.enrolid
LEFT JOIN mdl_log l ON l.userid = ue.userid AND l.course = e.courseid
LEFT JOIN mdl_grade_items gi ON gi.courseid = e.courseid AND gi.itemtype='mod'
LEFT JOIN mdl_grade_grades gg ON gg.itemid = gi.id AND gg.userid = ue.userid
GROUP BY ue.userid, e.courseid
HAVING risk_durumu <> 'aktif'
ORDER BY e.courseid;
