# B-01 — Risk Tahmin Senaryoları (H11–H14)

## Senaryo Çerçevesi

Hafta 11–14 veri üretimi üç senaryo altında modellenir.
Her senaryo, öğrencinin H10 snapshot özelliklerine göre hangi aktiviteyi yapacağını tanımlar.

---

## SENARYO A — İyimser (risk_label = "low")

**Hedef Segment:** S1  
**H10 Koşulları:**
- `completion_rate_w10` > 0.90
- `avg_grade_w10 / grademax` > 0.75
- Gecikmiş ödev yok (`late_submission_count` = 0)

**H11–H14 Davranış Kuralları:**

| Hafta | Aktivite | Detay |
|-------|----------|-------|
| H11 | H10 ödevi teslim | Erken teslim — `timemodified < duedate` |
| H11 | lesson/SCORM/H5P | Düzenli devam, yüksek tamamlama |
| H12 | lesson/SCORM/H5P | Düzenli devam |
| H13 | Final quiz | Yüksek puan → `fraction ≥ 0.80` |
| H14 | Son aktiviteler | Log yoğunluğu sabit veya hafif düşüş |

**Beklenen Çıktı:**
```
finalgrade / grademax > 0.80
completion_rate = 1.00 (tüm modüller tamamlandı)
quiz_fraction_avg (H13) ≥ 0.80
risk_label = "low"
```

---

## SENARYO B — Orta Risk (risk_label = "medium")

**Hedef Segment:** S2  
**H10 Koşulları:**
- `completion_rate_w10` 0.60 – 0.89
- `avg_grade_w10 / grademax` 0.50 – 0.74
- Hafif gecikme (`late_submission_count` ≥ 1, ≤ 3)

**H11–H14 Davranış Kuralları:**

| Hafta | Aktivite | Detay |
|-------|----------|-------|
| H11 | H10 ödevi teslim | Geç teslim mümkün — `timemodified ≤ duedate + 3gün` |
| H11–H12 | lesson/SCORM/H5P | Ara ara boşluk, bazı modüller eksik |
| H12–H13 | **Sınav öncesi burst** | Log yoğunluğu artar (S2 "panic" davranışı) |
| H13 | Final quiz | Orta puan → `fraction 0.50–0.75` |
| H14 | Düşen aktivite | Sınav sonrası düşüş |

**Beklenen Çıktı:**
```
finalgrade / grademax 0.55 – 0.75
completion_rate 0.65 – 0.90
quiz_fraction_avg (H13) 0.50 – 0.75
risk_label = "medium"
```

---

## SENARYO C — Yüksek Risk (risk_label = "high")

**Hedef Segment:** S3 / S4  
**H10 Koşulları:**
- `completion_rate_w10` < 0.60
- `avg_grade_w10 / grademax` < 0.50
- Çok sayıda eksik teslim (`missing_assign_count` ≥ 2)

**H11–H14 Davranış Kuralları:**

| Hafta | Aktivite | Detay |
|-------|----------|-------|
| H11 | H10 ödevi | S3: geç teslim olasılığı %50 / S4: büyük ihtimalle eksik |
| H11–H12 | Seyrek log | S4 büyük çoğunluğu bu haftalarda artık inaktif |
| H13 | Final quiz | S3: düşük puan `fraction < 0.50` / S4: katılım belirsiz |
| H14 | Minimal | S4 için neredeyse hiç aktivite yok |

**S4 Özel Kuralı:**
- `dropout_week ∈ [3, 10]` → H11+ için `is_active_in_week = False`
- Log üretilmez, quiz attempt üretilmez, ödev teslimi yoktur

**Beklenen Çıktı:**
```
finalgrade / grademax < 0.50 (S3) / < 0.30 (S4 aktif kalanlar)
completion_rate < 0.60
quiz_fraction_avg (H13): S3 → 0.30–0.50, S4 → 0.00–0.30
risk_label = "high"
```

---

## Tahmin Özellik Tablosu (MIMO Modeli için)

### X_Static — Dense Katmanı Girdisi (n=5)

| # | Özellik | Kaynak Tablo | Hesap Formülü |
|---|---------|-------------|---------------|
| 1 | `completion_rate_w10` | `mdl_course_modules_completion` | `COUNT(completed=1) / total_modules` |
| 2 | `avg_grade_w10` | `mdl_grade_grades` | `AVG(finalgrade / grademax)` where `timemodified ≤ H10` |
| 3 | `late_submission_count` | `mdl_assign_submission` | `COUNT(timemodified > duedate)` |
| 4 | `log_activity_last2w` | `mdl_logstore_standard_log` | `COUNT(*)` where `timecreated ∈ [H9, H10]` |
| 5 | `quiz_fraction_avg` | `mdl_question_attempt_steps` | `AVG(fraction)` where state='gradedright'/'gradedwrong' |

### X_Time — LSTM Katmanı Girdisi (hafta × özellik)

| Hafta | `log_count` | `grade_delta` |
|-------|------------|--------------|
| H1 | mdl_logstore H1 COUNT | 0.0 (ilk hafta referans) |
| H2 | mdl_logstore H2 COUNT | grade_w2 - grade_w1 |
| ... | ... | ... |
| H10 | mdl_logstore H10 COUNT | grade_w10 - grade_w9 |

> MIMO X_Time şekli: `(n_students, 10, 2)` — 10 hafta × 2 özellik

---

## Senaryo × Segment × risk_label Eşleştirmesi

| Senaryo | Segment | risk_label | Öğrenci Sayısı (yaklaşık) |
|---------|---------|-----------|--------------------------|
| A — İyimser | S1 | low | ~250 |
| B — Orta Risk | S2 | medium | ~343 |
| C — Yüksek Risk | S3 | high | ~200 |
| C — Yüksek Risk | S4 (aktif) | high | ~60 |
| **Toplam** | | | **~853** |

> S4'ün ~90'ı H10 öncesinde dropout_week ile çıkmış olur.
> Bu öğrenciler için H11–H14 tablosunda kayıt üretilmez (is_active = False).

---

## Özellik Bazlı Senaryo Karar Ağacı

```
completion_rate_w10 > 0.90
  AND avg_grade_w10 > 0.75
  AND late_submission_count == 0
  → risk_label = "low"   (Senaryo A)

ELSE completion_rate_w10 > 0.60
  AND avg_grade_w10 > 0.50
  → risk_label = "medium"  (Senaryo B)

ELSE
  → risk_label = "high"    (Senaryo C)
```

---

## H13 Final Quiz Katılım Tahminleri

| Segment | Katılım Oranı | Beklenen fraction Aralığı |
|---------|--------------|--------------------------|
| S1 | %99 | 0.75 – 1.00 |
| S2 | %90 | 0.50 – 0.80 |
| S3 | %70 | 0.25 – 0.60 |
| S4 (aktif) | %40 | 0.10 – 0.45 |
