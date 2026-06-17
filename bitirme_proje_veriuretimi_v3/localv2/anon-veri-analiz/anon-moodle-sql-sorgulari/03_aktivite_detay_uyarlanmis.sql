-- =====================================================================
-- 03 — AKTIVITE DETAY SORGULARI  (yukledginiz scriptlerden UYARLANMIS)
-- Olmayan tablolar/kolonlar cikarildi; modul-tipi mdl_modules ile cozuldu;
-- isim alanlari placeholder olabilir (ID ile gruplayin).
-- =====================================================================

-- ---------------------------------------------------------------------
-- 3.1  ODEV TESLIMLERI + NOT + GEC/ZAMANINDA  (Script.sql #1'in temizlenmis hali)
--   Cikarildi: assignsubmission_onlinetext, assignsubmission_file (sette YOK),
--              assign.timelimit, submission.latest (bu surumde YOK).
-- ---------------------------------------------------------------------
SELECT
    sub.id            AS submission_id,
    sub.userid,
    a.course          AS courseid,
    a.id              AS assignment_id,
    sub.status        AS teslim_durumu,
    sub.attemptnumber AS deneme_no,
    g.grade           AS final_grade,
    a.grade           AS max_grade,
    CASE WHEN sub.timecreated!=0 THEN DATE_FORMAT(FROM_UNIXTIME(sub.timecreated),'%Y-%m-%d %H:%i') END AS teslim_zamani,
    CASE WHEN a.duedate!=0       THEN DATE_FORMAT(FROM_UNIXTIME(a.duedate),'%Y-%m-%d %H:%i')       END AS son_teslim,
    CASE WHEN g.timemodified!=0  THEN DATE_FORMAT(FROM_UNIXTIME(g.timemodified),'%Y-%m-%d %H:%i')  END AS not_giris_zamani,
    CASE
        WHEN a.duedate=0                  THEN 'son_tarih_yok'
        WHEN sub.timecreated > a.duedate  THEN 'gec'
        ELSE 'zamaninda'
    END AS gec_mi
FROM mdl_assign_submission sub
JOIN mdl_assign a  ON a.id = sub.assignment
LEFT JOIN mdl_assign_grades g
       ON g.assignment = a.id AND g.userid = sub.userid AND g.attemptnumber = sub.attemptnumber;

-- ---------------------------------------------------------------------
-- 3.2  TUM MODULLERDE OGRENCI NOTLARI  (Script.sql "users activity all moduls" uyarlamasi)
--   Orijinal h5pactivity/hvp/game/lti iceriyordu -> sette OLMAYANLAR cikarildi.
--   Modul adi placeholder olabilir; iteminstance + courseid gercek baglanti noktasidir.
-- ---------------------------------------------------------------------
SELECT
    gi.courseid,
    c.shortname AS kurs_kodu,
    gi.itemmodule AS modul_tipi,
    gi.iteminstance,
    CASE gi.itemmodule
        WHEN 'quiz'     THEN mq.name
        WHEN 'assign'   THEN ma.name
        WHEN 'forum'    THEN mf.name
        WHEN 'data'     THEN md.name
        WHEN 'glossary' THEN mg.name
        WHEN 'lesson'   THEN ml.name
        WHEN 'scorm'    THEN ms.name
        WHEN 'workshop' THEN mw.name
        ELSE gi.itemmodule
    END AS aktivite_adi,
    gg.userid,
    gg.finalgrade, gg.rawgrade,
    gi.gradetype, gi.grademax, gi.grademin, gi.gradepass
FROM mdl_grade_grades gg
JOIN mdl_grade_items gi ON gi.id = gg.itemid
JOIN mdl_course c       ON c.id = gi.courseid
LEFT JOIN mdl_quiz     mq ON gi.itemmodule='quiz'     AND gi.iteminstance = mq.id
LEFT JOIN mdl_assign   ma ON gi.itemmodule='assign'   AND gi.iteminstance = ma.id
LEFT JOIN mdl_forum    mf ON gi.itemmodule='forum'    AND gi.iteminstance = mf.id
LEFT JOIN mdl_data     md ON gi.itemmodule='data'     AND gi.iteminstance = md.id
LEFT JOIN mdl_glossary mg ON gi.itemmodule='glossary' AND gi.iteminstance = mg.id
LEFT JOIN mdl_lesson   ml ON gi.itemmodule='lesson'   AND gi.iteminstance = ml.id
LEFT JOIN mdl_scorm    ms ON gi.itemmodule='scorm'    AND gi.iteminstance = ms.id
LEFT JOIN mdl_workshop mw ON gi.itemmodule='workshop' AND gi.iteminstance = mw.id
WHERE gi.itemmodule IS NOT NULL AND gg.finalgrade IS NOT NULL
ORDER BY gi.courseid, gi.itemmodule, gg.userid;

-- ---------------------------------------------------------------------
-- 3.3  DERS (LESSON) SORU BAZINDA DOGRU/YANLIS ORANI  (Script-2.sql #3 uyarlamasi)
--   lesson, lesson_attempts, lesson_pages, lesson_answers sette MEVCUT (lesson kucuk hacimli).
-- ---------------------------------------------------------------------
SELECT
    ml.course AS courseid,
    mla.lessonid,
    mlp.id AS page_id,
    mlp.title,
    SUM(1)                                  AS toplam_deneme,
    SUM(CASE WHEN mla.correct=1 THEN 1 ELSE 0 END) AS dogru,
    ROUND(100*SUM(CASE WHEN mla.correct=1 THEN 1 ELSE 0 END)/COUNT(*),1) AS dogru_pct
FROM mdl_lesson_attempts mla
JOIN mdl_lesson ml      ON ml.id  = mla.lessonid
JOIN mdl_lesson_pages mlp ON mlp.id = mla.pageid
GROUP BY ml.course, mla.lessonid, mlp.id, mlp.title
ORDER BY ml.course, mla.lessonid, mlp.id;

-- ---------------------------------------------------------------------
-- 3.4  QUIZ DENEME OZETI (Script'lerde dolayli vardi; sette quiz_attempts MEVCUT)
-- ---------------------------------------------------------------------
SELECT
    q.course AS courseid,
    qa.quiz  AS quiz_id,
    qa.userid,
    COUNT(*) AS deneme_sayisi,
    SUM(qa.timefinish>0) AS bitmis_deneme,
    MIN(CASE WHEN qa.timestart>0 THEN qa.timestart END) AS ilk_baslama_epoch,
    MAX(qa.timefinish) AS son_bitis_epoch,
    ROUND(AVG(CASE WHEN qa.timefinish>0 AND qa.timestart>0
              THEN (qa.timefinish-qa.timestart)/60 END),1) AS ort_sure_dk
FROM mdl_quiz_attempts qa
JOIN mdl_quiz q ON q.id = qa.quiz
GROUP BY q.course, qa.quiz, qa.userid
ORDER BY q.course, qa.quiz, qa.userid;
