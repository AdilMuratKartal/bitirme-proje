# A-00 — Program Genel Bakış: Geçmiş Veri Planı

## Program Kimliği

| Alan | Değer |
|------|-------|
| Program | Bilgisayar Mühendisliği Bölümü — 2024 Bahar Dönemi |
| Dönem Başlangıcı | 2024-02-05 08:00 (Unix: 1707116400) |
| Dönem Bitişi | 2024-05-20 23:59 (Unix: 1716249540) |
| Toplam Hafta | 14 hafta |
| Kurs Sayısı | 15 |
| Modül/Kurs | 15 |
| Öğrenci Sayısı | 1000 |
| Geçmiş/Gelecek Eşiği | Hafta 10 = 2024-04-15 (FUTURE_CUTOFF_WEEK=10) |
| Kaynak | config.py → `semester_start`, `n_weeks`, `n_students` |

---

## Segment Dağılımı

| Segment | Kod | Oran | Tanım | Dropout Olasılığı |
|---------|-----|------|-------|-------------------|
| Başarılı | S1 | %25 (250 öğrenci) | Yüksek not, erken teslim | %0 |
| Orta Başarılı | S2 | %35 (350 öğrenci) | Sınav öncesi burst | %5 (H12-14) |
| İstikrarsız | S3 | %25 (250 öğrenci) | Dalgalı, gece, geç teslim | %30 (H7-13) |
| Terke Meyilli | S4 | %15 (150 öğrenci) | Azalan aktivite, eksik | %70 (H3-10) |

---

## Genel Risk Hesaplama Formülü

```
genel_risk_skoru = Σ [ kurs_ağırlığı × (1 - normalized_grade) × (1 - completion_rate) ]

normalized_grade  = finalgrade / grademax        (mdl_grade_grades ÷ mdl_grade_items)
completion_rate   = tamamlanan_modül / toplam_modül  (mdl_course_modules_completion)
kurs_ağırlığı     = 1 / 15 ≈ 0.0667             (tüm kurslar eşit ağırlık)

risk_label:
  genel_risk ≤ 0.25 → "low"    (S1 ağırlıklı)
  genel_risk ≤ 0.55 → "medium" (S2 ağırlıklı)
  genel_risk >  0.55 → "high"  (S3/S4 ağırlıklı)
```

---

## rawgrade / finalgrade İlişki Şeması

| Alan | Tablo | Açıklama |
|------|-------|----------|
| `rawgrade` | mdl_grade_grades | Ham puan (quiz: sumgrades, assign: eğitmen girişi) |
| `rawgrademax` | mdl_grade_grades | Ham puan üst sınırı = mdl_grade_items.grademax |
| `rawgrademin` | mdl_grade_grades | Ham puan alt sınırı = 0.0 |
| `finalgrade` | mdl_grade_grades | Ağırlıklı ve ölçeklenmiş son puan |
| `aggregationstatus` | mdl_grade_grades | "used" = hesaba katıldı, "unknown" = beklemede |
| `aggregationcoef` | mdl_grade_items | Kategori içindeki ağırlık katsayısı |

**Hesap zinciri (Moodle Natural Weighted Mean, aggregation=13):**
```
category_grade = Σ(item_grade × aggregationcoef) / Σ(aggregationcoef)
course_grade   = Σ(category_grade × category_coef) / Σ(category_coef)
```

---

## Kurs Listesi ve Dominant Aktivite Tipi

| Kurs ID | Kurs Adı | Dominant | Quiz Ağırlığı | Assign Ağırlığı |
|---------|----------|----------|--------------|-----------------|
| 1 | Yazılım Geliştirme Temelleri | lesson | 65% | 20% |
| 2 | Veri Yapıları ve Algoritmalar | quiz | 85% | 15% |
| 3 | Nesne Yönelimli Programlama | assign | 40% | 50% |
| 4 | Veritabanı Yönetim Sistemleri | scorm | 50% | 10% |
| 5 | Web Teknolojileri | h5p | 30% | 35% |
| 6 | İşletim Sistemleri | quiz | 60% | 30% |
| 7 | Bilgisayar Ağları | quiz | 90% | 10% |
| 8 | Yazılım Mühendisliği | assign | 45% | 40% |
| 9 | Makine Öğrenmesi | assign | 40% | 40% |
| 10 | Yapay Zeka | quiz | 50% | 30% |
| 11 | Siber Güvenlik | quiz | 90% | 10% |
| 12 | Mobil Uygulama Geliştirme | assign | 35% | 55% |
| 13 | Bulut Bilişim | scorm | 40% | 15% |
| 14 | Veri Analitiği | assign | 30% | 45% |
| 15 | İnsan-Bilgisayar Etkileşimi | assign | 30% | 40% |

---

## Quiz / Assign Hafta Takvimi (build_semester_schedule mantığı)

`base_quiz_weeks = [4, 8, 13]`, `base_assign_weeks = [2, 6, 10]`, `stagger = (course_id-1) % 2`

| Kurs ID | Quiz Haftaları | Assign Haftaları |
|---------|----------------|------------------|
| Tek ID (1,3,5,...) | 4, 8, 13 | 2, 6, 10 |
| Çift ID (2,4,6,...) | 5, 9, 13 | 3, 7, 10 |

> **Not:** Son assign hafta 10 + 1 stagger = 10 (min(10+1, 14-2)=11 olan kurslar var, sabitlendi).

---

## Haftalık Zaman Damgaları

| Hafta | Tarih (Pazartesi 08:00) | Unix Timestamp | Durum |
|-------|------------------------|----------------|-------|
| 1 | 2024-02-05 | 1707116400 | Geçmiş |
| 2 | 2024-02-12 | 1707721200 | Geçmiş |
| 3 | 2024-02-19 | 1708326000 | Geçmiş |
| 4 | 2024-02-26 | 1708930800 | Geçmiş |
| 5 | 2024-03-04 | 1709535600 | Geçmiş |
| 6 | 2024-03-11 | 1710140400 | Geçmiş |
| 7 | 2024-03-18 | 1710745200 | Geçmiş |
| 8 | 2024-03-25 | 1711350000 | Geçmiş |
| 9 | 2024-04-01 | 1711954800 | Geçmiş |
| 10 | 2024-04-08 | 1712559600 | **Geçmiş (eşik)** |
| 11 | 2024-04-15 | 1713164400 | Gelecek (tahmin) |
| 12 | 2024-04-22 | 1713769200 | Gelecek (tahmin) |
| 13 | 2024-04-29 | 1714374000 | Gelecek (tahmin) |
| 14 | 2024-05-06 | 1714978800 | Gelecek (tahmin) |
