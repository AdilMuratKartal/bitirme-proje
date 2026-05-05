# A-02 — 14 Haftalık Aktivite Takvimi

## Hafta–Tarih Eşleştirmesi

| Hafta | Tarih (Pzt 08:00) | Durum |
|-------|-------------------|-------|
| H1  | 2024-02-05 | Geçmiş |
| H2  | 2024-02-12 | Geçmiş |
| H3  | 2024-02-19 | Geçmiş |
| H4  | 2024-02-26 | Geçmiş |
| H5  | 2024-03-04 | Geçmiş |
| H6  | 2024-03-11 | Geçmiş |
| H7  | 2024-03-18 | Geçmiş |
| H8  | 2024-03-25 | Geçmiş |
| H9  | 2024-04-01 | Geçmiş |
| H10 | 2024-04-08 | **Geçmiş (eşik)** |
| H11 | 2024-04-15 | Gelecek (tahmin) |
| H12 | 2024-04-22 | Gelecek (tahmin) |
| H13 | 2024-04-29 | Gelecek (tahmin) |
| H14 | 2024-05-06 | Gelecek (tahmin) |

---

## Quiz / Ödev Hafta Kuralları

```
base_quiz_weeks   = [4, 8, 13]
base_assign_weeks = [2, 6, 10]
stagger = (course_id - 1) % 2   # tek_kurs → 0, çift_kurs → 1
```

| Kurs Tipi | Quiz Haftaları | Ödev Haftaları |
|-----------|----------------|----------------|
| Tek ID (1,3,5,7,9,11,13,15) | 4, 8, 13 | 2, 6, 10 |
| Çift ID (2,4,6,8,10,12,14)  | 5, 9, 13 | 3, 7, 10 |

---

## Hücre Kısaltmaları

| Simge | Anlam |
|-------|-------|
| `L`   | lesson — normal ders içeriği |
| `Q`   | QUIZ — vize veya ara sınav |
| `QF`  | QUIZ-FINAL — dönem sonu sınavı (H13) |
| `A`   | ÖDEV — assignment açılır (duedate +1 hafta) |
| `S`   | SCORM — e-öğrenim modülü |
| `H`   | H5P — interaktif içerik |
| `—`   | Aktivite yok (dropout / planlanmamış) |

> **Not:** Bir hücrede iki simge varsa (örn. `Q+L`) o hafta hem quiz hem de lesson aktivitesi ateşlenir.
> H13 tüm kurslar için `QF` (final sınavı) haftasıdır.

---

## 14 Hafta × 15 Kurs Aktivite Matrisi

| H  | Tarih | C01-VGT | C02-VYA | C03-NYP | C04-VTS | C05-Web | C06-İOS | C07-BAG | C08-YMH | C09-MÖ | C10-YZ | C11-SG | C12-MAG | C13-BB | C14-VA | C15-İBE |
|----|-------|---------|---------|---------|---------|---------|---------|---------|---------|--------|--------|--------|---------|--------|--------|---------|
| 1  | 02/05 | L       | L       | L       | S       | H       | L       | L       | L       | L      | L      | L      | L       | S      | L      | L       |
| 2  | 02/12 | A+L     | L       | A+L     | S       | H       | L       | A+L     | A+L     | A+L    | L      | A+L    | A+L     | S      | A+L    | A+L     |
| 3  | 02/19 | L       | A+L     | L       | A+S     | H       | A+L     | L       | L       | L      | A+L    | L      | L       | A+S    | A+L    | L       |
| 4  | 02/26 | Q+L     | L       | Q+L     | S       | H       | L       | Q+L     | Q+L     | Q+L    | L      | Q+L    | Q+L     | S      | L      | Q+L     |
| 5  | 03/04 | L       | Q+L     | L       | Q+S     | Q+H     | Q+L     | L       | L       | L      | Q+L    | L      | L       | Q+S    | Q+L    | L       |
| 6  | 03/11 | A+L     | L       | A+L     | S       | H       | L       | A+L     | A+L     | A+L    | L      | A+L    | A+L     | S      | L      | A+L     |
| 7  | 03/18 | L       | A+L     | L       | A+S     | H       | A+L     | L       | L       | L      | A+L    | L      | L       | A+S    | A+L    | L       |
| 8  | 03/25 | Q+L     | L       | Q+L     | S       | H       | L       | Q+L     | Q+L     | Q+L    | L      | Q+L    | Q+L     | S      | L      | Q+L     |
| 9  | 04/01 | L       | Q+L     | L       | Q+S     | Q+H     | Q+L     | L       | L       | L      | Q+L    | L      | L       | Q+S    | Q+L    | L       |
| 10 | 04/08 | A+L     | A+L     | A+L     | A+S     | H       | A+L     | A+L     | A+L     | A+L    | A+L    | A+L    | A+L     | A+S    | A+L    | A+L     |
| 11 | 04/15 | L       | L       | L       | S       | H       | L       | L       | L       | L      | L      | L      | L       | S      | L      | L       |
| 12 | 04/22 | L       | L       | L       | S       | H       | L       | L       | L       | L      | L      | L      | L       | S      | L      | L       |
| 13 | 04/29 | QF+L    | QF+L    | QF+L    | QF+S    | QF+H    | QF+L    | QF+L    | QF+L    | QF+L   | QF+L   | QF+L   | QF+L    | QF+S   | QF+L   | QF+L    |
| 14 | 05/06 | L       | L       | L       | S       | H       | L       | L       | L       | L      | L      | L      | L       | S      | L      | L       |

---

## Kurs Kısa Adları

| Kurs | Kısa | Tam Ad | Dominant |
|------|------|--------|----------|
| C01 | VGT | Yazılım Geliştirme Temelleri | lesson |
| C02 | VYA | Veri Yapıları ve Algoritmalar | quiz |
| C03 | NYP | Nesne Yönelimli Programlama | assign |
| C04 | VTS | Veritabanı Yönetim Sistemleri | scorm |
| C05 | Web | Web Teknolojileri | h5p |
| C06 | İOS | İşletim Sistemleri | quiz |
| C07 | BAG | Bilgisayar Ağları | quiz |
| C08 | YMH | Yazılım Mühendisliği | assign |
| C09 | MÖ  | Makine Öğrenmesi | assign |
| C10 | YZ  | Yapay Zeka | quiz |
| C11 | SG  | Siber Güvenlik | quiz |
| C12 | MAG | Mobil Uygulama Geliştirme | assign |
| C13 | BB  | Bulut Bilişim | scorm |
| C14 | VA  | Veri Analitiği | assign |
| C15 | İBE | İnsan-Bilgisayar Etkileşimi | assign |

---

## Quiz Programı (Vize / Final Eşleştirmesi)

| Kurs (Tek ID) | H4 → | H8 → | H13 → |
|---------------|------|------|-------|
| C01, C03, C07, C09, C11, C15 | Vize (quiz_grademax[0]) | Ara Sınav (quiz_grademax[0]) | Final (quiz_grademax[1]) |
| **Kurs (Çift ID)** | H5 → | H9 → | H13 → |
| C02, C04, C06, C08, C10, C12, C14 | Vize (quiz_grademax[0]) | Ara Sınav (quiz_grademax[0]) | Final (quiz_grademax[1]) |

> **_quiz_index takibi:** Her kurs için `_quiz_index[course_id]` sayacı H4/H5'te 0→1, H8/H9'da 1→2, H13'de 2→3 olarak artar. `quiz_grademax = [vize, final]`; index ≥ 1 olduğunda `quiz_grademax[1]` (final) kullanılır.

---

## Ödev Programı (Açılış / Kapanış)

| Hafta | Kurslar (Tek) | Kurslar (Çift) | Açılış | Kapanış |
|-------|---------------|----------------|--------|---------|
| H2    | C01,C03,C07,C09,C11,C15 | — | H2 Pzt 08:00 | H3 Cum 23:59 |
| H3    | — | C02,C04,C06,C08,C10,C12,C14 | H3 Pzt 08:00 | H4 Cum 23:59 |
| H6    | C01,C03,C07,C09,C11,C15 | — | H6 Pzt 08:00 | H7 Cum 23:59 |
| H7    | — | C02,C04,C06,C08,C10,C12,C14 | H7 Pzt 08:00 | H8 Cum 23:59 |
| H10   | Tüm Kurslar (1-15) | Tüm Kurslar (1-15) | H10 Pzt 08:00 | H11 Cum 23:59 |

> H10'da tüm kursların son ödevi açılır (geçmiş/gelecek eşiği haftası).

---

## Segment × Hafta Aktivite Özeti

| Segment | H1-4 | H5-8 | H9-10 (eşik öncesi) | H11-14 |
|---------|------|------|---------------------|--------|
| S1 | lesson/quiz/assign düzenli | Yüksek tamamlama | Tüm ödevler erken teslim | Devam eder, final quiz |
| S2 | Düzenli, hafif gecikme | Hafta 7-8 burst | Sınav öncesi yoğunluk | H12-13 panic submit |
| S3 | Gece oturumları, dalgalı | Bazı haftalarda kayıp | Gecikmiş ödevler var | H13 quiz riski |
| S4 | H3-5 itibaren seyrelme | Dropout başlar (H7-10) | Eksik modüller artar | Büyük ihtimalle inaktif |
