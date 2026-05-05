# C-00 — Aktivite Matrisi Özeti

## Tablo 1: Kurs × Aktivite Tipi Dağılımı

Her kursun dominant ve yardımcı aktivite tipleri:

| Kurs | Ad | Dominant | lesson | quiz | assign | scorm | h5p | forum |
|------|----|----------|--------|------|--------|-------|-----|-------|
| C01 | Yazılım Geliştirme Temelleri | lesson | ✓✓✓ | ✓✓ | ✓✓ | — | — | — |
| C02 | Veri Yapıları ve Algoritmalar | quiz | ✓✓ | ✓✓✓ | ✓ | — | — | — |
| C03 | Nesne Yönelimli Programlama | assign | ✓✓ | ✓✓ | ✓✓✓ | — | — | — |
| C04 | Veritabanı Yönetim Sistemleri | scorm | — | ✓✓ | ✓ | ✓✓✓ | — | — |
| C05 | Web Teknolojileri | h5p | ✓ | ✓ | ✓✓ | — | ✓✓✓ | — |
| C06 | İşletim Sistemleri | quiz | ✓✓ | ✓✓✓ | ✓✓ | — | — | — |
| C07 | Bilgisayar Ağları | quiz | ✓ | ✓✓✓ | ✓ | — | — | — |
| C08 | Yazılım Mühendisliği | assign | ✓✓ | ✓✓ | ✓✓✓ | ✓ | — | — |
| C09 | Makine Öğrenmesi | assign | ✓ | ✓✓ | ✓✓✓ | — | ✓ | — |
| C10 | Yapay Zeka | quiz | ✓✓ | ✓✓✓ | ✓✓ | — | — | — |
| C11 | Siber Güvenlik | quiz | ✓ | ✓✓✓ | ✓ | — | — | — |
| C12 | Mobil Uygulama Geliştirme | assign | ✓ | ✓✓ | ✓✓✓ | — | — | — |
| C13 | Bulut Bilişim | scorm | — | ✓✓ | ✓ | ✓✓✓ | — | — |
| C14 | Veri Analitiği | assign | ✓ | ✓✓ | ✓✓✓ | — | ✓✓ | — |
| C15 | İnsan-Bilgisayar Etkileşimi | assign | ✓ | ✓✓ | ✓✓✓ | — | — | ✓✓ |

> ✓✓✓ = dominant (yüksek ağırlık), ✓✓ = yardımcı, ✓ = minimal, — = yok

---

## Tablo 2: Kurs × Grade Ağırlık Dağılımı (%)

`COURSE_GRADE_SCHEMAS` içindeki `coef` değerlerine dayalı gerçek ağırlıklar:

| Kurs | Dominant | Vize/Ara | Final | Ödev/Proje | SCORM/H5P/Katılım | Diğer |
|------|----------|----------|-------|------------|-------------------|-------|
| C01 | lesson | 30% (Vize) | 35% (Final) | 20% (Ödevler) | 15% (Derse Katılım) | — |
| C02 | quiz | 30% (Vize) | 35% (Final) | 15% (Ödevler) | 20% (Haftalık Testler) | — |
| C03 | assign | 20% (Vize) | 20% (Final) | 50% (Projeler) | 10% (Ders İçeriği) | — |
| C04 | scorm | 25% (Vize) | 25% (Final) | 10% (Proje) | 40% (SCORM Modüller) | — |
| C05 | h5p | — | 30% (Final Sınavı) | 35% (Ödevler) | 35% (H5P Uygulamalar) | — |
| C06 | quiz | 60% (Sınavlar) | — | 30% (Lab Ödevleri) | 10% (Katılım) | — |
| C07 | quiz | 25% (Vize) | 40% (Final) | 10% (Ödev) | 25% (Haftalık Testler) | — |
| C08 | assign | 20% (Vize) | 25% (Final) | 40% (Proje/Ödev) | 15% (SCORM/Ders) | — |
| C09 | assign | 40% (Sınavlar) | — | 40% (Ödevler) | 20% (H5P/Demo) | — |
| C10 | quiz | 50% (Sınavlar) | — | 30% (Ödevler) | 20% (Katılım) | — |
| C11 | quiz | 30% (Vize) | 40% (Final) | 10% (Ödev) | 20% (Lab Sınavları) | — |
| C12 | assign | 35% (Sınavlar) | — | 55% (Projeler) | 10% (Katılım) | — |
| C13 | scorm | 40% (Sınavlar) | — | 15% (Proje) | 45% (SCORM Sertifikasyon) | — |
| C14 | assign | 30% (Sınavlar) | — | 45% (Analizler) | 25% (H5P Görsel) | — |
| C15 | assign | 30% (Sınavlar) | — | 40% (Projeler) | 30% (Forum+Katılım) | — |

---

## Tablo 3: Risk Ağırlık Tablosu (Kurs Bazlı)

Genel risk formülü: `risk = Σ(kurs_ağırlığı × (1 - finalgrade/grademax) × (1 - completion_rate))`

| Kurs | Ağırlık | Dominant Aktivite | Quiz Grademax (vize/final) | Assign Grademax |
|------|---------|-------------------|--------------------------|-----------------|
| C01 | 1/15 ≈ 0.0667 | lesson | 30 / 35 | 10 |
| C02 | 1/15 ≈ 0.0667 | quiz | 30 / 35 | 10 |
| C03 | 1/15 ≈ 0.0667 | assign | 20 / 20 | 15 |
| C04 | 1/15 ≈ 0.0667 | scorm | 25 / 25 | 100 |
| C05 | 1/15 ≈ 0.0667 | h5p | 0 / 30 | 15 |
| C06 | 1/15 ≈ 0.0667 | quiz | 20 / 40 | 15 |
| C07 | 1/15 ≈ 0.0667 | quiz | 25 / 40 | 10 |
| C08 | 1/15 ≈ 0.0667 | assign | 20 / 25 | 20 |
| C09 | 1/15 ≈ 0.0667 | assign | 15 / 25 | 15 |
| C10 | 1/15 ≈ 0.0667 | quiz | 20 / 30 | 15 |
| C11 | 1/15 ≈ 0.0667 | quiz | 30 / 40 | 10 |
| C12 | 1/15 ≈ 0.0667 | assign | 15 / 20 | 20 |
| C13 | 1/15 ≈ 0.0667 | scorm | 15 / 25 | 15 |
| C14 | 1/15 ≈ 0.0667 | assign | 10 / 20 | 15 |
| C15 | 1/15 ≈ 0.0667 | assign | 10 / 20 | 20 |

> Tüm kurslar **eşit ağırlık** taşır (1/15). Hibrit ağırlık sistemi kullanılmamıştır.

---

## Tablo 4: Grade Kategori Aggregation Özeti

| aggregation Kodu | Adı | Kullanan Kurslar |
|-----------------|-----|-----------------|
| 10 — Sum | Ham toplam | Tüm alt kategoriler (vize, final, ödev, proje) |
| 11 — Weighted Mean | Ağırlıklı ortalama | Katılım kategorileri (C06, C10, C12) |
| 13 — Natural WM | Doğal ağırlıklı ortalama | Root kategoriler (tüm kurslar), Ders içeriği (C03, C08) |

---

## Tablo 5: Dominant Tip × Kurs Sayısı

| Dominant Tip | Kurs Sayısı | Kurslar |
|-------------|-------------|---------|
| assign | 6 | C03, C08, C09, C12, C14, C15 |
| quiz | 5 | C02, C06, C07, C10, C11 |
| scorm | 2 | C04, C13 |
| lesson | 1 | C01 |
| h5p | 1 | C05 |
| **Toplam** | **15** | — |

---

## Tablo 6: SCORM-Dominant Kurslar — Özel Kurallar

C04 (Veritabanı) ve C13 (Bulut Bilişim) için özel davranış:

| Alan | C04 | C13 | Açıklama |
|------|-----|-----|----------|
| `lesson_aggregationcoef` | 0.0 | 0.0 | Lesson aktivitesi notlandırılmaz |
| Lesson `hidden` | 1 | 1 | Grade hesabında görünmez |
| SCORM kayıt | `mdl_scorm_scoes_track` | `mdl_scorm_scoes_track` | Tamamlama: `cmi.core.lesson_status = passed` |
| Grade kaynağı | SCORM + Quiz + Proje | SCORM + Quiz + Proje | Lesson dışı tüm aktiviteler |

---

## Tablo 7: Haftalık Quiz Grademax Özeti (Kurs Bazlı)

| Kurs | H4/H5 Quiz (Vize) | H8/H9 Quiz (Ara) | H13 Quiz (Final) |
|------|-------------------|------------------|------------------|
| C01 | 30 | 30 | 35 |
| C02 | 30 | 30 | 35 |
| C03 | 20 | 20 | 20 |
| C04 | 25 | 25 | 25 |
| C05 | — (vize yok) | — | 30 |
| C06 | 20 | 20 | 40 |
| C07 | 25 | 25 | 40 |
| C08 | 20 | 20 | 25 |
| C09 | 15 | 15 | 25 |
| C10 | 20 | 20 | 30 |
| C11 | 30 | 30 | 40 |
| C12 | 15 | 15 | 20 |
| C13 | 15 | 15 | 25 |
| C14 | 10 | 10 | 20 |
| C15 | 10 | 10 | 20 |

> C05'te `quiz_grademax=[0,30]` — H4 quiz ateşlenmez (grademax=0 → atlanır).
> `_quiz_index[course_id]` sayacı: H4/H5→index 0, H8/H9→index 1, H13→index 2 (capped at len-1).
