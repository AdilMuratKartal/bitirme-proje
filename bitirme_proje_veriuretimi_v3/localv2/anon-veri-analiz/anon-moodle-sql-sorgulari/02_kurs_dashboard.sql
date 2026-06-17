-- =====================================================================
-- 02 — KURS TABANLI DASHBOARD SORGULARI
-- Amac: Kurs duzeyinde ozet (kayit, aktiflik, basari, modul kompozisyonu).
-- =====================================================================

-- ---------------------------------------------------------------------
-- 2.1  KURS OZET TABLOSU
-- ---------------------------------------------------------------------
SELECT
    c.id AS courseid,
    c.shortname AS kurs_kodu,
    cat.name    AS kategori,
    CASE WHEN c.startdate>0 THEN DATE_FORMAT(FROM_UNIXTIME(c.startdate),'%Y-%m-%d') END AS baslangic,
    COUNT(DISTINCT ue.userid) AS kayitli_ogrenci,
    COUNT(DISTINCT lg.userid) AS aktif_ogrenci,    -- en az 1 logu olan
    ROUND(100*COUNT(DISTINCT lg.userid)/NULLIF(COUNT(DISTINCT ue.userid),0),1) AS aktiflik_pct,
    (SELECT COUNT(*) FROM mdl_course_modules cm WHERE cm.course=c.id) AS yerlesik_modul,
    ROUND(AVG(CASE WHEN cg.finalgrade IS NOT NULL AND cgi.grademax>0
              THEN 100*cg.finalgrade/cgi.grademax END),1) AS ort_kurs_not_pct
FROM mdl_course c
LEFT JOIN mdl_course_categories cat ON cat.id = c.category
LEFT JOIN mdl_enrol e  ON e.courseid = c.id
LEFT JOIN mdl_user_enrolments ue ON ue.enrolid = e.id
LEFT JOIN (SELECT DISTINCT userid, course FROM mdl_log) lg ON lg.course = c.id AND lg.userid = ue.userid
LEFT JOIN mdl_grade_items cgi ON cgi.courseid = c.id AND cgi.itemtype='course'
LEFT JOIN mdl_grade_grades cg ON cg.itemid = cgi.id AND cg.userid = ue.userid
GROUP BY c.id, c.shortname, cat.name, c.startdate
HAVING kayitli_ogrenci > 0
ORDER BY kayitli_ogrenci DESC;

-- ---------------------------------------------------------------------
-- 2.2  KURS ICI MODUL KOMPOZISYONU (hangi tip etkinlikten kac tane)
--   Modul tipi DAIMA mdl_modules join'i ile cozulur (sabit id YOK).
-- ---------------------------------------------------------------------
SELECT
    cm.course AS courseid,
    m.name    AS modul_tipi,
    COUNT(*)  AS adet
FROM mdl_course_modules cm
JOIN mdl_modules m ON m.id = cm.module
GROUP BY cm.course, m.name
ORDER BY cm.course, adet DESC;

-- Platform geneli modul dagilimi (tek bakista hangi araclar kullanilmis):
SELECT m.name AS modul_tipi, COUNT(*) AS yerlesim_sayisi
FROM mdl_course_modules cm JOIN mdl_modules m ON m.id = cm.module
GROUP BY m.name ORDER BY yerlesim_sayisi DESC;

-- ---------------------------------------------------------------------
-- 2.3  KURS NOT DAGILIMI (histogram kovalari) — dashboard grafigi icin
-- ---------------------------------------------------------------------
SELECT
    e.courseid,
    CASE
        WHEN 100*cg.finalgrade/NULLIF(cgi.grademax,0) < 20 THEN '00-20'
        WHEN 100*cg.finalgrade/NULLIF(cgi.grademax,0) < 40 THEN '20-40'
        WHEN 100*cg.finalgrade/NULLIF(cgi.grademax,0) < 60 THEN '40-60'
        WHEN 100*cg.finalgrade/NULLIF(cgi.grademax,0) < 80 THEN '60-80'
        ELSE '80-100'
    END AS not_araligi,
    COUNT(*) AS ogrenci
FROM mdl_enrol e
JOIN mdl_grade_items cgi ON cgi.courseid = e.courseid AND cgi.itemtype='course'
JOIN mdl_grade_grades cg ON cg.itemid = cgi.id
WHERE cg.finalgrade IS NOT NULL AND cgi.grademax>0
GROUP BY e.courseid, not_araligi
ORDER BY e.courseid, not_araligi;
