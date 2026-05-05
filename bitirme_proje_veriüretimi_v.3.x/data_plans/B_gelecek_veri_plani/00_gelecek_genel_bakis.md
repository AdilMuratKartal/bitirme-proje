# B-00 — Gelecek Veri Planı: Genel Bakış

## Geçmiş / Gelecek Ayrımı

| Alan | Değer |
|------|-------|
| `FUTURE_CUTOFF_WEEK` | 10 |
| Eşik Tarihi | 2024-04-08 (Hafta 10 Pazartesi 08:00) |
| **H1–H10** | Geçmiş veri — simülasyon tam olarak üretilir |
| **H11–H14** | Gelecek / tahmin senaryosu — sadece varsayımsal çıktı |

```python
# config.py
FUTURE_CUTOFF_WEEK: int = 10   # H1-10 = gerçek simülasyon | H11-14 = tahmin
```

---

## Geçmiş Veri Özellikleri (H1–H10)

Hafta 10 sonunda aşağıdaki tablolar **tam dolu** olacak:

| Tablo | İçerik |
|-------|--------|
| `mdl_logstore_standard_log` | H1–H10 tüm oturum/aktivite logları |
| `mdl_quiz_attempts` | H4/H5, H8/H9 sınavları tamamlandı |
| `mdl_question_attempt_steps` | Tüm quiz adım kayıtları |
| `mdl_assign_submission` | H2/H3, H6/H7, H10 ödevleri (geç/erken dahil) |
| `mdl_grade_grades` | rawgrade ve finalgrade hesaplandı (completed items) |
| `mdl_course_modules_completion` | Tamamlanan modüller (timemodified ≤ H10) |

---

## Gelecek Veri Özellikleri (H11–H14)

Hafta 11–14 simülasyon verisinde **yalnızca** şunlar üretilir:

| Tablo | Durum |
|-------|-------|
| `mdl_logstore_standard_log` | Üretilir (segment'e göre seyrekleşir) |
| `mdl_quiz_attempts` (H13 final) | Üretilir — segment × senaryo kurallarına göre |
| `mdl_assign_submission` (H10 ödevi) | H11 kapanış — geç/eksik simülasyonu |
| `mdl_grade_grades` | H13 final sonrası güncellenir |
| `mdl_course_modules_completion` | S3/S4 için eksik modüller kalabilir |

---

## Özellik Seti: Hafta-10 Snapshot (X_Time, X_Static)

Tahmin modeli (MIMO) için H10 sonunda çıkarılan özellikler:

| Özellik | Kaynak Tablo | Hesap |
|---------|-------------|-------|
| `completion_rate_w10` | `mdl_course_modules_completion` | tamamlanan / toplam_modül |
| `avg_grade_w10` | `mdl_grade_grades` | AVG(finalgrade / grademax) |
| `late_submission_count` | `mdl_assign_submission` | timemodified > duedate sayısı |
| `log_activity_last2w` | `mdl_logstore_standard_log` | H9+H10 log satır sayısı |
| `quiz_fraction_avg` | `mdl_question_attempt_steps` | AVG(fraction) |
| `active_days_w10` | `mdl_logstore_standard_log` | Benzersiz aktif gün sayısı H1-H10 |
| `missing_assign_count` | `mdl_assign_submission` | Teslim edilmeyen ödev sayısı |
| `risk_label` | `student_registry.segment` | S1→low, S2→medium, S3/S4→high |

---

## Risk Label Atama Mantığı

```
risk_label:
  genel_risk ≤ 0.25  → "low"     (S1 ağırlıklı)
  genel_risk ≤ 0.55  → "medium"  (S2 ağırlıklı)
  genel_risk > 0.55  → "high"    (S3/S4 ağırlıklı)

genel_risk = Σ [ (1/15) × (1 - finalgrade/grademax) × (1 - completion_rate) ]
             kurs i=1..15
```

| Segment | Beklenen risk_label | Hafta-10 Tamamlama | Hafta-10 Ortalama Not |
|---------|--------------------|--------------------|----------------------|
| S1 | low | > %90 | > %75 |
| S2 | medium | %60–%89 | %50–%74 |
| S3 | high | %35–%59 | %30–%55 |
| S4 | high | < %35 | < %30 |

---

## Hafta-10 Sonrası Aktivite Projeksiyonu

| Hafta | Olay | Etkilenen Kurslar |
|-------|------|-------------------|
| H10 | Son ödev açılır (tüm kurslar) | C01–C15 |
| H11 | H10 ödevleri kapanır (duedate) | C01–C15 |
| H11 | Normal lesson/SCORM/H5P | C01–C15 |
| H12 | Normal lesson/SCORM/H5P | C01–C15 |
| H13 | **Final sınavı** (tüm kurslar) | C01–C15 |
| H14 | Dönem kapanışı, son aktiviteler | C01–C15 |

---

## Segment Dropout Durumu (H10 İtibariyle)

Hafta 10'da beklenen aktif öğrenci sayısı:

| Segment | Başlangıç | Dropout Oranı (H3–H10) | H10 Aktif (yaklaşık) |
|---------|-----------|------------------------|----------------------|
| S1 | 250 | %0 | ~250 |
| S2 | 350 | %2 (H10'a kadar) | ~343 |
| S3 | 250 | %20 (H7–H10) | ~200 |
| S4 | 150 | %60 (H3–H10) | ~60 |
| **Toplam** | **1000** | — | **~853** |

> S4 dropout_prob=%70, dw_range=[3,10] — büyük çoğunluğu H10'a kadar bırakmış olur.
> `is_active_in_week(userid, week)` → `week > dropout_week` ise False.
