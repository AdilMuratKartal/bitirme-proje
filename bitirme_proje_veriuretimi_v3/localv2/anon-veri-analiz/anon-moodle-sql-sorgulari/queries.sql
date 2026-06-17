-- ============================================================================
-- MOODLE VERI KALITESI SORGULARI (PostgreSQL + MySQL)
-- Bu setin gercekleri:
--   * Tablolar "anon_" on ekli CSV; DB'ye yuklerseniz ister anon_ ister mdl_ kullanin
--   * mdl_logstore_standard_log YOK -> ESKI mdl_log kullanilir
--     (kolonlar: id, time, userid, ip, course, module, cmid, action, url, info)
--   * mdl_course_completions YOK
--   * mdl_course.enddate buyuk olasilikla YOK (Moodle <3.2)
-- Zaman: Unix epoch saniye.
--   MySQL    : FROM_UNIXTIME(x)
--   PostgreSQL: TO_TIMESTAMP(x)
-- CSV'leri DB kurmadan test icin DuckDB:
--   SELECT * FROM read_csv_auto('anon_log.csv') LIMIT 5;
-- ============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- 1) HAYALET NOT: finalgrade>0 ama ne teslim, ne bitmis deneme, ne log var
-- ─────────────────────────────────────────────────────────────────────────────
SELECT gg.id      AS grade_id,
       gg.userid,
       gi.itemmodule,
       gi.iteminstance,
       gg.finalgrade
FROM   mdl_grade_grades     gg
JOIN   mdl_grade_items      gi ON gi.id = gg.itemid
                              AND gi.itemmodule IN ('assign','quiz')
JOIN   mdl_modules          m  ON m.name = gi.itemmodule
JOIN   mdl_course_modules   cm ON cm.module = m.id
                              AND cm.instance = gi.iteminstance
WHERE  gg.finalgrade IS NOT NULL
  AND  gg.finalgrade > 0
  AND  NOT EXISTS (
        SELECT 1 FROM mdl_log l
        WHERE  l.cmid = cm.id AND l.userid = gg.userid)
  AND  NOT EXISTS (
        SELECT 1 FROM mdl_assign_submission s
        WHERE  gi.itemmodule = 'assign'
          AND  s.assignment  = gi.iteminstance
          AND  s.userid      = gg.userid)
  AND  NOT EXISTS (
        SELECT 1 FROM mdl_quiz_attempts qa
        WHERE  gi.itemmodule = 'quiz'
          AND  qa.quiz       = gi.iteminstance
          AND  qa.userid     = gg.userid
          AND  qa.timefinish > 0);

-- ─────────────────────────────────────────────────────────────────────────────
-- 2) KAYIP NOT (assign): teslim var, not satiri yok VEYA finalgrade NULL
-- ─────────────────────────────────────────────────────────────────────────────
SELECT s.assignment,
       s.userid,
       CASE WHEN gg.id IS NULL THEN 'satir_yok' ELSE 'finalgrade_null' END AS durum
FROM   mdl_assign_submission s
JOIN   mdl_grade_items       gi ON gi.itemmodule = 'assign'
                               AND gi.iteminstance = s.assignment
LEFT JOIN mdl_grade_grades   gg ON gg.itemid = gi.id
                               AND gg.userid  = s.userid
WHERE  gg.id IS NULL OR gg.finalgrade IS NULL;

-- Oran (MySQL — %XX.XX):
SELECT ROUND(100 * AVG(
         CASE WHEN gg.id IS NULL OR gg.finalgrade IS NULL THEN 1 ELSE 0 END
       ), 2) AS kayip_not_pct
FROM   mdl_assign_submission s
JOIN   mdl_grade_items       gi ON gi.itemmodule = 'assign'
                               AND gi.iteminstance = s.assignment
LEFT JOIN mdl_grade_grades   gg ON gg.itemid = gi.id
                               AND gg.userid  = s.userid;
-- PostgreSQL: AVG((gg.id IS NULL OR gg.finalgrade IS NULL)::int) * 100

-- ─────────────────────────────────────────────────────────────────────────────
-- 3) NOT DAGILIMI: tam-sayi / 5-kati oranlari + en sik degerler
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
  ROUND(100 * AVG(CASE WHEN finalgrade = FLOOR(finalgrade) THEN 1 ELSE 0 END), 1) AS tam_sayi_pct,
  ROUND(100 * AVG(CASE WHEN MOD(finalgrade, 5) = 0         THEN 1 ELSE 0 END), 1) AS bes_kati_pct,
  ROUND(100 * AVG(CASE WHEN MOD(finalgrade, 10) = 0        THEN 1 ELSE 0 END), 1) AS on_kati_pct
FROM mdl_grade_grades
WHERE finalgrade IS NOT NULL AND finalgrade > 0;

-- En sik 15 not degeri:
SELECT finalgrade,
       COUNT(*) AS adet,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS yuzde
FROM   mdl_grade_grades
WHERE  finalgrade IS NOT NULL AND finalgrade > 0
GROUP  BY finalgrade
ORDER  BY adet DESC
LIMIT  15;

-- ─────────────────────────────────────────────────────────────────────────────
-- 4) TOPLU GIRIS: ayni dakikada en fazla not girilen 20 dakika
-- ─────────────────────────────────────────────────────────────────────────────
-- MySQL:
SELECT FLOOR(timemodified / 60)                          AS epoch_dakika,
       FROM_UNIXTIME(FLOOR(timemodified / 60) * 60)      AS zaman,
       COUNT(*)                                          AS adet
FROM   mdl_grade_grades
WHERE  timemodified > 0
GROUP  BY 1, 2
ORDER  BY adet DESC
LIMIT  20;
-- PostgreSQL: TO_TIMESTAMP(FLOOR(timemodified/60)*60) AS zaman

-- Kalem bazinda: notlarinin >= %80'i tek dakikada girilen kalemler (PostgreSQL):
WITH dakika_grp AS (
  SELECT itemid,
         FLOOR(timemodified / 60) AS dk,
         COUNT(*) AS c
  FROM   mdl_grade_grades
  WHERE  timemodified > 0
  GROUP  BY itemid, FLOOR(timemodified / 60)
),
kalem_toplam AS (
  SELECT itemid, SUM(c) AS n, MAX(c) AS maxc
  FROM   dakika_grp
  GROUP  BY itemid
)
SELECT itemid,
       n,
       ROUND(100.0 * maxc / n, 1) AS modal_dakika_pct
FROM   kalem_toplam
WHERE  n >= 20
  AND  maxc >= 0.8 * n
ORDER  BY n DESC;

-- ─────────────────────────────────────────────────────────────────────────────
-- 5) KURS PENCERESI - LOG UYUMU (enddate yoksa start + 6 ay varsayimi)
-- ─────────────────────────────────────────────────────────────────────────────
-- MySQL:
SELECT ROUND(100 * AVG(l.time < c.startdate),                     2) AS once_pct,
       ROUND(100 * AVG(l.time > c.startdate + 6 * 30 * 86400),    2) AS sonra_pct,
       ROUND(100 * AVG(l.time BETWEEN c.startdate
                            AND c.startdate + 6*30*86400),         2) AS icinde_pct
FROM   mdl_log l
JOIN   mdl_course c ON c.id = l.course
WHERE  c.startdate > 0;
-- PostgreSQL: AVG((l.time < c.startdate)::int) * 100

-- Kurs bazinda once-pct (en sorunlu 20 kurs):
SELECT l.course                                               AS courseid,
       COUNT(*)                                               AS n_log,
       ROUND(100 * AVG(l.time < c.startdate), 2)             AS once_pct
FROM   mdl_log l
JOIN   mdl_course c ON c.id = l.course
WHERE  c.startdate > 0
GROUP  BY l.course
HAVING n_log >= 50
ORDER  BY once_pct DESC
LIMIT  20;

-- ─────────────────────────────────────────────────────────────────────────────
-- 6) ALTIN OGRENCI KUMESI (completions yok -> teslim/deneme kaniti kullanilir)
-- ─────────────────────────────────────────────────────────────────────────────
SELECT COUNT(*) AS altin_ogrenci_sayisi
FROM (
  SELECT DISTINCT ue.userid
  FROM   mdl_user_enrolments ue
  WHERE  EXISTS (SELECT 1 FROM mdl_log l
                 WHERE  l.userid = ue.userid)
    AND  EXISTS (SELECT 1 FROM mdl_grade_grades g
                 WHERE  g.userid = ue.userid
                   AND  g.finalgrade IS NOT NULL)
    AND  (
           EXISTS (SELECT 1 FROM mdl_assign_submission s
                   WHERE  s.userid = ue.userid)
        OR EXISTS (SELECT 1 FROM mdl_quiz_attempts qa
                   WHERE  qa.userid = ue.userid
                     AND  qa.timefinish > 0)
         )
) t;

-- Oran (kayitli ogrenci bazinda):
SELECT altin_sayisi,
       kayitli_sayisi,
       ROUND(100.0 * altin_sayisi / kayitli_sayisi, 1) AS altin_oran_pct
FROM (
  SELECT COUNT(DISTINCT ue.userid) AS kayitli_sayisi,
         COUNT(DISTINCT CASE
               WHEN EXISTS (SELECT 1 FROM mdl_log l WHERE l.userid = ue.userid)
                AND EXISTS (SELECT 1 FROM mdl_grade_grades g
                            WHERE g.userid = ue.userid AND g.finalgrade IS NOT NULL)
                AND (EXISTS (SELECT 1 FROM mdl_assign_submission s WHERE s.userid = ue.userid)
                  OR EXISTS (SELECT 1 FROM mdl_quiz_attempts qa
                             WHERE qa.userid = ue.userid AND qa.timefinish > 0))
               THEN ue.userid END) AS altin_sayisi
  FROM mdl_user_enrolments ue
) x;

-- ─────────────────────────────────────────────────────────────────────────────
-- 7) FK YETIM ORANLARI (MySQL; PostgreSQL icin ::int cast kullanin)
-- ─────────────────────────────────────────────────────────────────────────────
SELECT 'grade_grades.itemid'      AS kontrol,
       ROUND(100 * AVG(gi.id IS NULL), 3) AS yetim_pct
FROM   mdl_grade_grades gg
LEFT JOIN mdl_grade_items gi ON gi.id = gg.itemid
UNION ALL
SELECT 'grade_grades.userid',
       ROUND(100 * AVG(u.id IS NULL), 3)
FROM   mdl_grade_grades gg
LEFT JOIN mdl_user u ON u.id = gg.userid
UNION ALL
SELECT 'log.userid',
       ROUND(100 * AVG(u.id IS NULL), 3)
FROM   mdl_log l
LEFT JOIN mdl_user u ON u.id = l.userid
UNION ALL
SELECT 'log.course',
       ROUND(100 * AVG(c.id IS NULL), 3)
FROM   mdl_log l
LEFT JOIN mdl_course c ON c.id = l.course
UNION ALL
SELECT 'assign_submission.userid',
       ROUND(100 * AVG(u.id IS NULL), 3)
FROM   mdl_assign_submission s
LEFT JOIN mdl_user u ON u.id = s.userid;

-- ─────────────────────────────────────────────────────────────────────────────
-- 8) NOT TESLIMDEN ONCE MI GIRILMIS? (guclu sentetiklik isareti)
-- ─────────────────────────────────────────────────────────────────────────────
SELECT COUNT(*) AS not_teslimden_once_girilen
FROM   mdl_grade_grades gg
JOIN   mdl_grade_items gi ON gi.id = gg.itemid
                         AND gi.itemmodule = 'assign'
JOIN (
  SELECT assignment, userid, MIN(timecreated) AS ilk_teslim
  FROM   mdl_assign_submission
  GROUP  BY assignment, userid
) s ON s.assignment = gi.iteminstance
   AND s.userid     = gg.userid
WHERE  gg.finalgrade  > 0
  AND  gg.timemodified < s.ilk_teslim - 86400;   -- 1 gunluk tolerans

-- ─────────────────────────────────────────────────────────────────────────────
-- 9) KRONOLOJI: user.lastaccess < firstaccess (imkansiz durum)
-- ─────────────────────────────────────────────────────────────────────────────
SELECT COUNT(*) AS tutarsiz_erisim
FROM   mdl_user
WHERE  firstaccess > 0
  AND  lastaccess  > 0
  AND  lastaccess  < firstaccess;

-- ─────────────────────────────────────────────────────────────────────────────
-- 10) QUIZ: timefinish < timestart (imkansiz durum)
-- ─────────────────────────────────────────────────────────────────────────────
SELECT COUNT(*) AS imkansiz_quiz_suresi
FROM   mdl_quiz_attempts
WHERE  timefinish > 0
  AND  timefinish < timestart;
