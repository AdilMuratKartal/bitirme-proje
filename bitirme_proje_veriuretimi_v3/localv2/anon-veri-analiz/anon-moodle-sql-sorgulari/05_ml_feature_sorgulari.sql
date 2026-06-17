-- =====================================================================
-- 05 — ML FEATURE URETIM SORGULARI  (grain: ogrenci x kurs)
-- Hedef adaylari: kurs notu yuzdesi (regresyon) veya gecti/kaldi (siniflandirma).
-- Uyari: 04.6'da kurs-oncesi log orani yuksek cikan kurslarda ZAMANSAL feature'lari
--        ve 04.4'te toplu girilen kalemlerin timemodified'ini KULLANMAYIN.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 5.1  LOG TABANLI KATILIM FEATURE'LARI (ogrenci x kurs)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_feat_log AS
SELECT
    l.userid, l.course AS courseid,
    COUNT(*)                                   AS n_log,
    SUM(l.action LIKE 'view%')                 AS n_view,
    SUM(l.module='course')                     AS n_course_view,
    SUM(l.module IN ('resource','url','folder','page')) AS n_kaynak_eylem,
    SUM(l.module='forum')                      AS n_forum_eylem,
    COUNT(DISTINCT DATE(FROM_UNIXTIME(l.time))) AS n_aktif_gun,
    MIN(NULLIF(l.time,0))                       AS ilk_log,
    MAX(l.time)                                 AS son_log,
    ROUND((MAX(l.time)-MIN(NULLIF(l.time,0)))/86400,1) AS aktif_sure_gun
FROM mdl_log l
WHERE l.time>0 AND l.userid>0 AND l.course>1   -- course=1 site baglami, haric
GROUP BY l.userid, l.course;

-- ---------------------------------------------------------------------
-- 5.2  TESLIM / QUIZ FEATURE'LARI (ogrenci x kurs)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_feat_aktivite AS
SELECT u_c.userid, u_c.courseid,
       COALESCE(sub.n_teslim,0)      AS n_teslim,
       COALESCE(qz.n_quiz_deneme,0)  AS n_quiz_deneme,
       qz.ort_quiz_sure_dk
FROM (SELECT DISTINCT userid, course AS courseid FROM mdl_log WHERE course>1) u_c
LEFT JOIN (
    SELECT a.course AS courseid, s.userid, COUNT(*) AS n_teslim
    FROM mdl_assign_submission s JOIN mdl_assign a ON a.id=s.assignment
    GROUP BY a.course, s.userid
) sub ON sub.courseid=u_c.courseid AND sub.userid=u_c.userid
LEFT JOIN (
    SELECT q.course AS courseid, qa.userid,
           COUNT(*) AS n_quiz_deneme,
           ROUND(AVG(CASE WHEN qa.timefinish>0 AND qa.timestart>0
                     THEN (qa.timefinish-qa.timestart)/60 END),1) AS ort_quiz_sure_dk
    FROM mdl_quiz_attempts qa JOIN mdl_quiz q ON q.id=qa.quiz
    WHERE qa.timefinish>0
    GROUP BY q.course, qa.userid
) qz ON qz.courseid=u_c.courseid AND qz.userid=u_c.userid;

-- ---------------------------------------------------------------------
-- 5.3  NOT FEATURE'LARI + HEDEF (ogrenci x kurs)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_feat_not AS
SELECT m.courseid, m.userid,
       ROUND(AVG(m.pct),1) AS modul_not_ort,
       ROUND(STDDEV_SAMP(m.pct),1) AS modul_not_std,
       COUNT(*) AS n_dolu_not,
       MAX(crs.kurs_not_pct) AS hedef_kurs_not_pct
FROM (
    SELECT gi.courseid, gg.userid, 100*gg.finalgrade/NULLIF(gi.grademax,0) AS pct
    FROM mdl_grade_grades gg JOIN mdl_grade_items gi ON gi.id=gg.itemid
    WHERE gi.itemtype='mod' AND gg.finalgrade IS NOT NULL AND gi.grademax>0
) m
LEFT JOIN (
    SELECT gi.courseid, gg.userid, 100*gg.finalgrade/NULLIF(gi.grademax,0) AS kurs_not_pct
    FROM mdl_grade_grades gg JOIN mdl_grade_items gi ON gi.id=gg.itemid
    WHERE gi.itemtype='course' AND gg.finalgrade IS NOT NULL AND gi.grademax>0
) crs ON crs.courseid=m.courseid AND crs.userid=m.userid
GROUP BY m.courseid, m.userid;

-- ---------------------------------------------------------------------
-- 5.4  NIHAI FEATURE TABLOSU (tek satir = ogrenci x kurs)  -> ML'e bu beslenir
-- ---------------------------------------------------------------------
SELECT
    fl.userid, fl.courseid,
    fl.n_log, fl.n_view, fl.n_course_view, fl.n_kaynak_eylem, fl.n_forum_eylem,
    fl.n_aktif_gun, fl.aktif_sure_gun,
    ROUND(fl.n_log/GREATEST(fl.n_aktif_gun,1),2) AS log_per_gun,
    fa.n_teslim, fa.n_quiz_deneme, fa.ort_quiz_sure_dk,
    fn.modul_not_ort, fn.modul_not_std, fn.n_dolu_not,
    fn.hedef_kurs_not_pct,
    CASE WHEN fn.hedef_kurs_not_pct >= 50 THEN 1 ELSE 0 END AS hedef_gecti  -- esigi kendinize gore degistirin
FROM v_feat_log fl
LEFT JOIN v_feat_aktivite fa ON fa.userid=fl.userid AND fa.courseid=fl.courseid
LEFT JOIN v_feat_not fn      ON fn.userid=fl.userid AND fn.courseid=fl.courseid
ORDER BY fl.courseid, fl.userid;

-- HIZLI TUTARLILIK TESTI: katilim ile basari pozitif iliskili mi olmali (gercek veride 0.1-0.4)?
SELECT
  (COUNT(*)*SUM(n_log*hedef_kurs_not_pct) - SUM(n_log)*SUM(hedef_kurs_not_pct)) /
  SQRT( (COUNT(*)*SUM(n_log*n_log)-SUM(n_log)*SUM(n_log)) *
        (COUNT(*)*SUM(hedef_kurs_not_pct*hedef_kurs_not_pct)-SUM(hedef_kurs_not_pct)*SUM(hedef_kurs_not_pct)) )
  AS pearson_log_vs_not
FROM v_feat_log fl
JOIN v_feat_not fn ON fn.userid=fl.userid AND fn.courseid=fl.courseid
WHERE fn.hedef_kurs_not_pct IS NOT NULL;
-- ~0 veya negatifse loglar ile notlar BIRBIRINDEN BAGIMSIZ uretilmis olabilir (sentetiklik kaniti).
