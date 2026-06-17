-- =====================================================================
-- 04 — VERI KALITESI / SAHTELIK (SYNTHETIC) KONTROL SORGULARI
-- Esik yorumu (sizin kriteriniz): tutarsizlik <%1 temiz, %15-20+ ciddi sorun.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 4.1  HAYALET NOT — finalgrade>0 ama ne teslim, ne bitmis quiz, ne log var
-- ---------------------------------------------------------------------
SELECT gg.id AS grade_id, gg.userid, gi.itemmodule, gi.iteminstance, gg.finalgrade
FROM mdl_grade_grades gg
JOIN mdl_grade_items gi ON gi.id = gg.itemid AND gi.itemmodule IN ('assign','quiz')
JOIN mdl_modules m      ON m.name = gi.itemmodule
JOIN mdl_course_modules cm ON cm.module = m.id AND cm.instance = gi.iteminstance
WHERE gg.finalgrade IS NOT NULL AND gg.finalgrade > 0
  AND NOT EXISTS (SELECT 1 FROM mdl_log l WHERE l.cmid=cm.id AND l.userid=gg.userid)
  AND NOT EXISTS (SELECT 1 FROM mdl_assign_submission s
                  WHERE gi.itemmodule='assign' AND s.assignment=gi.iteminstance AND s.userid=gg.userid)
  AND NOT EXISTS (SELECT 1 FROM mdl_quiz_attempts qa
                  WHERE gi.itemmodule='quiz' AND qa.quiz=gi.iteminstance
                        AND qa.userid=gg.userid AND qa.timefinish>0);

-- 4.1b  Hayalet not ORANI (assign icin ozet)
SELECT
  ROUND(100*AVG(hayalet),2) AS hayalet_pct, COUNT(*) AS pozitif_not
FROM (
  SELECT gg.id,
    (NOT EXISTS (SELECT 1 FROM mdl_assign_submission s
                 WHERE s.assignment=gi.iteminstance AND s.userid=gg.userid)) AS hayalet
  FROM mdl_grade_grades gg
  JOIN mdl_grade_items gi ON gi.id=gg.itemid AND gi.itemmodule='assign'
  WHERE gg.finalgrade>0
) t;

-- ---------------------------------------------------------------------
-- 4.2  KAYIP NOT — teslim VAR ama not satiri yok / finalgrade NULL
-- ---------------------------------------------------------------------
SELECT
  ROUND(100*AVG(CASE WHEN gg.id IS NULL OR gg.finalgrade IS NULL THEN 1 ELSE 0 END),2) AS kayip_pct,
  SUM(gg.id IS NULL) AS satir_yok,
  SUM(gg.id IS NOT NULL AND gg.finalgrade IS NULL) AS finalgrade_null
FROM mdl_assign_submission s
JOIN mdl_grade_items gi ON gi.itemmodule='assign' AND gi.iteminstance = s.assignment
LEFT JOIN mdl_grade_grades gg ON gg.itemid = gi.id AND gg.userid = s.userid;

-- ---------------------------------------------------------------------
-- 4.3  NOT DOGALLIGI — yuvarlaklik + en sik degerler (sentetiklik isareti)
-- ---------------------------------------------------------------------
SELECT
  COUNT(*) AS n_pozitif_not,
  ROUND(100*AVG(finalgrade = FLOOR(finalgrade)),1) AS tam_sayi_pct,
  ROUND(100*AVG(MOD(finalgrade,5)=0),1)            AS bes_kati_pct,
  ROUND(100*AVG(MOD(finalgrade,10)=0),1)           AS on_kati_pct
FROM mdl_grade_grades WHERE finalgrade IS NOT NULL AND finalgrade>0;

SELECT finalgrade, COUNT(*) AS adet
FROM mdl_grade_grades WHERE finalgrade>0
GROUP BY finalgrade ORDER BY adet DESC LIMIT 15;
-- YORUM: quiz otomatik -> ondalik dogal; assign elle -> 5/10 kati dogal.
-- Tek bir degerin payi cok yuksekse ve tum modullerde %95+ tam sayi varsa sentetik suphesi.

-- ---------------------------------------------------------------------
-- 4.4  TOPLU GIRIS TUZAGI — notlar ayni dakikada mi girilmis?
-- ---------------------------------------------------------------------
SELECT FLOOR(timemodified/60) AS epoch_dakika,
       DATE_FORMAT(FROM_UNIXTIME(FLOOR(timemodified/60)*60),'%Y-%m-%d %H:%i') AS zaman,
       COUNT(*) AS ayni_dakika_not
FROM mdl_grade_grades WHERE timemodified>0
GROUP BY 1,2 ORDER BY ayni_dakika_not DESC LIMIT 20;
-- YORUM: Buyuk yigilma = hoca toplu Excel yuklemesi (gercek ama zamansal feature zayif)
-- ya da uretici scriptin topluca basmasi. Tek basina sentetiklik KANITLAMAZ; 4.1/4.3/4.5 ile birlikte yorumlayin.

-- ---------------------------------------------------------------------
-- 4.5  NOT, TESLIMDEN ONCE mi girilmis? (>1 gun once = guclu sentetiklik isareti)
-- ---------------------------------------------------------------------
SELECT COUNT(*) AS not_teslimden_once_1gun
FROM mdl_grade_grades gg
JOIN mdl_grade_items gi ON gi.id=gg.itemid AND gi.itemmodule='assign'
JOIN (SELECT assignment, userid, MIN(timecreated) tc
      FROM mdl_assign_submission GROUP BY assignment, userid) s
  ON s.assignment=gi.iteminstance AND s.userid=gg.userid
WHERE gg.finalgrade>0 AND gg.timemodified < s.tc - 86400;

-- ---------------------------------------------------------------------
-- 4.6  KURS PENCERESI - LOG UYUMU (enddate YOK -> 'baslangictan once' en guvenilir sinyal)
-- ---------------------------------------------------------------------
SELECT
  ROUND(100*AVG(l.time < c.startdate),2)                  AS kurs_oncesi_log_pct,
  ROUND(100*AVG(l.time > c.startdate + 6*30*86400),2)     AS varsayilan_pencere_sonrasi_pct
FROM mdl_log l JOIN mdl_course c ON c.id = l.course
WHERE c.startdate>0;

-- ---------------------------------------------------------------------
-- 4.7  REFERANS BUTUNLUGU (FK yetim oranlari) — JOIN'ler veri kaybettiriyor mu?
-- ---------------------------------------------------------------------
SELECT 'grade_grades.itemid->grade_items' AS kontrol,
       ROUND(100*AVG(gi.id IS NULL),3) AS yetim_pct
FROM mdl_grade_grades gg LEFT JOIN mdl_grade_items gi ON gi.id=gg.itemid
UNION ALL SELECT 'grade_grades.userid->user',
       ROUND(100*AVG(u.id IS NULL),3)
FROM mdl_grade_grades gg LEFT JOIN mdl_user u ON u.id=gg.userid
UNION ALL SELECT 'log.userid->user',
       ROUND(100*AVG(u.id IS NULL),3)
FROM mdl_log l LEFT JOIN mdl_user u ON u.id=l.userid
UNION ALL SELECT 'log.course->course',
       ROUND(100*AVG(c.id IS NULL),3)
FROM mdl_log l LEFT JOIN mdl_course c ON c.id=l.course
UNION ALL SELECT 'course_modules.module->modules',
       ROUND(100*AVG(m.id IS NULL),3)
FROM mdl_course_modules cm LEFT JOIN mdl_modules m ON m.id=cm.module
UNION ALL SELECT 'user_enrolments.enrolid->enrol',
       ROUND(100*AVG(e.id IS NULL),3)
FROM mdl_user_enrolments ue LEFT JOIN mdl_enrol e ON e.id=ue.enrolid;

-- ---------------------------------------------------------------------
-- 4.8  ALTIN OGRENCI KUMESI (eksiksiz profil; completions yok -> kanit tabanli)
-- ---------------------------------------------------------------------
SELECT COUNT(*) AS altin_ogrenci,
       ROUND(100*COUNT(*)/(SELECT COUNT(DISTINCT userid) FROM mdl_user_enrolments),1) AS kayitliya_oran_pct
FROM (
  SELECT DISTINCT ue.userid
  FROM mdl_user_enrolments ue
  WHERE EXISTS (SELECT 1 FROM mdl_log l WHERE l.userid=ue.userid)
    AND EXISTS (SELECT 1 FROM mdl_grade_grades g WHERE g.userid=ue.userid AND g.finalgrade IS NOT NULL)
    AND ( EXISTS (SELECT 1 FROM mdl_assign_submission s WHERE s.userid=ue.userid)
       OR EXISTS (SELECT 1 FROM mdl_quiz_attempts qa WHERE qa.userid=ue.userid AND qa.timefinish>0) )
) t;
