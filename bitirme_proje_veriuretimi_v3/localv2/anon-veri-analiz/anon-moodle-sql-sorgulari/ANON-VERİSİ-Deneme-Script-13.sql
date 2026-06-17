
---STUDENT OLAN KURSA KAYDOLAN VE NORMAL KURSA KAYITLI OLANLAR SAYILARI---
SELECT 
    -- 1. Hem rolü 5 olan hem de kurs kaydı olan benzersiz kullanıcılar
    (SELECT COUNT(DISTINCT amu.id) 
     FROM anon_mdl_user amu 
     INNER JOIN anon_mdl_role_assignments amra ON amu.id = amra.userid 
     INNER JOIN anon_mdl_user_enrolments amue ON amu.id = amue.userid 
     WHERE amra.roleid = 5 AND amu.deleted = 0 AND amu.confirmed = 1
    ) AS kursa_kayitli_ogrenci_sayisi,

    -- 2. Kurs kaydına bakılmaksızın sistemdeki toplam aktif öğrenci sayısı (Roleid = 5)
    (SELECT COUNT(DISTINCT amu.id) 
     FROM anon_mdl_user amu 
     INNER JOIN anon_mdl_role_assignments amra ON amra.userid = amu.id
     WHERE amra.roleid = 5 AND amu.deleted = 0 AND amu.confirmed = 1
    ) AS ogrenci_sayisi,

    -- 3. Rolüne bakılmaksızın kursa kayıtlı toplam benzersiz kullanıcı sayısı
    (SELECT COUNT(DISTINCT amue.userid) 
     FROM anon_mdl_user_enrolments amue
    ) AS kursa_kayitli_user_sayisi;
    
    

---BİRLEŞMİŞ VERİ AMA SAÇMA AYRI TABLO OLARAK KALSIN--
SELECT 
    gg.id AS gg_id,
    gg.userid AS gg_ogrenci_id,
    gg.finalgrade AS gg_final_notu,
    gi.id AS etkinlik_id,
    gi.itemmodule AS etkinlik_turu, 
    gi.courseid AS kurs_id,
    gi.gradepass AS gecme_notu,
    ml.action AS log_aksiyonu,
    ml.time AS log_zamani
FROM (
    anon_mdl_grade_grades AS gg
    LEFT JOIN anon_mdl_grade_items AS gi ON gg.itemid = gi.id
)
LEFT JOIN anon_mdl_log AS ml ON gg.userid = ml.userid;


---Bazı Grade'lerin grademax, finalgrade değerleri yüksek onun sorgusu, veride mantıklı olarak sadece shift etmiş gözüküyor normalize şart---
SELECT 
    gi.id AS grade_item_id,
    gi.itemtype AS item_tipi,
    gi.itemmodule AS module_tipi,
    gi.grademin AS sistem_min,
    gi.grademax AS sistem_max,
    gi.gradepass AS gecme_notu,
    -- Gerçekten girilen en yüksek not
    MAX(gg.finalgrade) AS alinan_en_yuksek_not, 
    -- Bu aktivitede kaç adet not kaydı olduğunu görmek için (güvenilirlik testi)
    COUNT(gg.finalgrade) AS toplam_not_adedi 
FROM anon_mdl_grade_items gi
LEFT JOIN anon_mdl_grade_grades gg ON gi.id = gg.itemid
-- Sadece notlandırılan modülleri veya kategorileri görmek için grupluyoruz
WHERE gi.grademax >= 101
GROUP BY gi.id, gi.itemtype, gi.itemmodule, gi.grademin, gi.grademax
ORDER BY gi.id,toplam_not_adedi  ASC;

--HANGİ GRADEİTEMLAR HESAPLANMIYOR--
select amgi.id, amgi.itemtype , amgi.itemmodule , amgi.gradetype from anon_mdl_grade_items amgi 
WHERE amgi.gradetype = 0


