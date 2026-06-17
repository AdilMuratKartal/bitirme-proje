SELECT *, AVG(mgg.aggregationweight) ortalama_ağırlık,mgg.itemid as item_id,mgi.courseid as kurs_id FROM mdl_grade_grades mgg 
INNER JOIN mdl_grade_items mgi ON mgg.itemid = mgi.id 
Group BY mgi.courseid,mgg.itemid  ;

SELECT mgg.userid,mgg.id,mgg.itemid,mgg.aggregationweight   FROM mdl_grade_grades mgg 
WHERE mgg.itemid = 391;

SELECT mgg.id as gradeid,mgi.id as itemid, mgc.id as kategoriid, mgi.itemname as itemismi, 
mgi.itemtype as itemtipi, mgi.itemmodule as itemmodul_tipi,mgc.fullname as kategori_ismi
FROM mdl_grade_grades mgg 
INNER JOIN mdl_grade_items mgi ON mgg.itemid  = mgi.id 
INNER JOIN mdl_grade_categories mgc ON mgi.categoryid = mgc.id 
WHERE kategori_ismi NOT LIKE "%?%"

SELECT id, itemid, mgg.finalgrade, mgg.aggregationweight, mgg.aggregationstatus, mgg.rawgrade as hamnot 
FROM mdl_grade_grades mgg 
WHERE mgg.aggregationweight = 0.00000 
  AND mgg.finalgrade IS NOT NULL
  AND mgg.overridden = 0
  -- Replaced finalgrade::numeric with standard CAST()
  AND ROUND(CAST(mgg.finalgrade AS NUMERIC), 2) != 0.00;


SELECT id, itemid, mgg.finalgrade, mgg.aggregationweight, mgg.aggregationstatus, mgg.rawgrade as hamnot,
(SELECT mgi.itemmodule FROM mdl_grade_items mgi WHERE mgi.id = mgg.itemid  ) AS itemmodule
FROM mdl_grade_grades mgg 
WHERE mgg.aggregationweight != 0.00000 
  AND mgg.finalgrade IS NOT NULL
  AND mgg.overridden = 0
  -- Replaced finalgrade::numeric with standard CAST()
  AND ROUND(CAST(mgg.finalgrade AS NUMERIC), 2) != 0.00;

--agregation hesaplama basitçe bu grade den yukarı grade_item'a gi onun kategoriid sini al sonra sonra kategoriid=iteminstance olucakşekilde eşlersen 
---grade_items içerisinde o gradenin kategorisinin grade_item'ını bulursun. sonra onun grade_items.idsini al ve git grade_grade'ye yordan aggreagationweight al
---ilk grade ile kategorinin grade aggreagationweightalt / aggregationweightüst yapınca kurs içindeki ağırlığı bulursun

---bulemoodledenemeleri--