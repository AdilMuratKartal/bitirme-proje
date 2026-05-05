# A-01 — 15 Kurs Grade Şema Planı

> **Kaynak:** `config.py → COURSE_GRADE_SCHEMAS`
> **Gerçek veri referansı:** `mdl_grade_items`, `mdl_grade_categories` (CC-01, Excel, AutoCAD kursları)
> **aggregation kodu:** 10=Sum | 11=WeightedMean | 13=Natural weighted mean

---

## Kurs 1 — Yazılım Geliştirme Temelleri

**Dominant:** lesson | **grademax:** 100

### Grade Kategori Hiyerarşisi
| Derinlik | Kategori | aggregation | coef | grademax |
|----------|----------|-------------|------|----------|
| 1 (kök) | ? | 13 | — | 100 |
| 2 | Vize | 10 | 0.30 | 30 |
| 2 | Final | 10 | 0.35 | 35 |
| 2 | Ödevler | 10 | 0.20 | 20 |
| 2 | Derse Katılım | 13 | 0.15 | 15 |

### Grade Item Dağılımı
| Item | itemtype | itemmodule | grademax | gradepass | aggregationcoef |
|------|----------|------------|----------|-----------|-----------------|
| Genel Not | course | — | 100 | 50 | 0.0 |
| Quiz Vize | mod | quiz | 30 | 15 | 0.30 |
| Quiz Final | mod | quiz | 35 | 17.5 | 0.35 |
| Ödev ×3 | mod | assign | 10 | 5 | 0.20 |
| Ders (lesson) | mod | lesson | 100 | 33 | 0.03846 |

### rawgrade Üretim Kuralları
| Segment | Dağılım | Min | grade_missing_prob |
|---------|---------|-----|---------------------|
| S1 | N(85, 6) | 70 | 1% |
| S2 | N(65, 8) | 50 | 4% |
| S3 | N(52, 14) | 30 | 12% |
| S4 | N(34, 10) | 0 | 30% |

---

## Kurs 2 — Veri Yapıları ve Algoritmalar

**Dominant:** quiz | **grademax:** 100

### Grade Kategori Hiyerarşisi
| Derinlik | Kategori | aggregation | coef | grademax |
|----------|----------|-------------|------|----------|
| 1 (kök) | ? | 13 | — | 100 |
| 2 | Vize | 10 | 0.30 | 30 |
| 2 | Final | 10 | 0.35 | 35 |
| 2 | Haftalık Testler | 10 | 0.20 | 20 |
| 2 | Ödevler | 10 | 0.15 | 15 |

### Grade Item Dağılımı
| Item | itemtype | itemmodule | grademax | gradepass | aggregationcoef |
|------|----------|------------|----------|-----------|-----------------|
| Genel Not | course | — | 100 | 50 | 0.0 |
| Quiz Vize | mod | quiz | 30 | 15 | 0.30 |
| Quiz Final | mod | quiz | 35 | 17.5 | 0.35 |
| Ödev ×3 | mod | assign | 10 | 5 | 0.15 |
| Ders (lesson) | mod | lesson | 100 | 33 | 0.03846 |

### rawgrade Üretim Kuralları
*(Kurs 1 ile aynı segment profilleri)*

---

## Kurs 3 — Nesne Yönelimli Programlama

**Dominant:** assign | **grademax:** 100

### Grade Kategori Hiyerarşisi
| Derinlik | Kategori | aggregation | coef | grademax |
|----------|----------|-------------|------|----------|
| 1 (kök) | ? | 13 | — | 100 |
| 2 | Projeler | 10 | 0.50 | 50 |
| 2 | Vize | 10 | 0.20 | 20 |
| 2 | Final | 10 | 0.20 | 20 |
| 2 | Ders İçeriği | 13 | 0.10 | 10 |

### Grade Item Dağılımı
| Item | itemtype | itemmodule | grademax | gradepass | aggregationcoef |
|------|----------|------------|----------|-----------|-----------------|
| Genel Not | course | — | 100 | 50 | 0.0 |
| Quiz Vize | mod | quiz | 20 | 10 | 0.20 |
| Quiz Final | mod | quiz | 20 | 10 | 0.20 |
| Ödev/Proje ×3 | mod | assign | 15 | 7.5 | 0.50 |
| Ders (lesson) | mod | lesson | 100 | 33 | 0.03846 |

---

## Kurs 4 — Veritabanı Yönetim Sistemleri

**Dominant:** scorm | **grademax:** 100
> Lesson'lar notlandırılmaz (lesson_aggregationcoef=0.0, hidden=1)

### Grade Kategori Hiyerarşisi
| Derinlik | Kategori | aggregation | coef | grademax |
|----------|----------|-------------|------|----------|
| 1 (kök) | ? | 13 | — | 100 |
| 2 | SCORM Modüller | 10 | 0.40 | 40 |
| 2 | Vize | 10 | 0.25 | 25 |
| 2 | Final | 10 | 0.25 | 25 |
| 2 | Proje | 10 | 0.10 | 10 |

### Grade Item Dağılımı
| Item | itemtype | itemmodule | grademax | gradepass | aggregationcoef |
|------|----------|------------|----------|-----------|-----------------|
| Genel Not | course | — | 100 | 50 | 0.0 |
| Quiz Vize | mod | quiz | 25 | 12.5 | 0.25 |
| Quiz Final | mod | quiz | 25 | 12.5 | 0.25 |
| Proje Ödevi | mod | assign | 100 | 50 | 0.10 |
| SCORM (notlandırılmaz) | mod | lesson | 100 | 0 | 0.0 |

---

## Kurs 5 — Web Teknolojileri

**Dominant:** h5p | **grademax:** 100
> Vize quizi yok (quiz_grademax[0]=0), sadece final sınavı

### Grade Kategori Hiyerarşisi
| Derinlik | Kategori | aggregation | coef | grademax |
|----------|----------|-------------|------|----------|
| 1 (kök) | ? | 13 | — | 100 |
| 2 | H5P Uygulamalar | 10 | 0.35 | 35 |
| 2 | Ödevler | 10 | 0.35 | 35 |
| 2 | Final Sınavı | 10 | 0.30 | 30 |

### Grade Item Dağılımı
| Item | itemtype | itemmodule | grademax | gradepass | aggregationcoef |
|------|----------|------------|----------|-----------|-----------------|
| Genel Not | course | — | 100 | 50 | 0.0 |
| Quiz Final | mod | quiz | 30 | 15 | 0.30 |
| Ödev ×3 | mod | assign | 15 | 7.5 | 0.35 |
| Ders (lesson) | mod | lesson | 100 | 33 | 0.03846 |

---

## Kurs 6 — İşletim Sistemleri

**Dominant:** quiz (lab tipi) | **grademax:** 100

### Grade Kategori Hiyerarşisi
| Derinlik | Kategori | aggregation | coef | grademax |
|----------|----------|-------------|------|----------|
| 1 (kök) | ? | 13 | — | 100 |
| 2 | Sınavlar | 10 | 0.60 | 60 |
| 2 | Lab Ödevleri | 10 | 0.30 | 30 |
| 2 | Katılım | 11 | 0.10 | 10 |

### Grade Item Dağılımı
| Item | itemtype | itemmodule | grademax | gradepass | aggregationcoef |
|------|----------|------------|----------|-----------|-----------------|
| Genel Not | course | — | 100 | 50 | 0.0 |
| Quiz Vize | mod | quiz | 20 | 10 | 0.60 (Sınavlar cat) |
| Quiz Final | mod | quiz | 40 | 20 | 0.60 (Sınavlar cat) |
| Lab Ödevi ×3 | mod | assign | 15 | 7.5 | 0.30 |
| Ders (lesson) | mod | lesson | 100 | 33 | 0.03846 |

---

## Kurs 7 — Bilgisayar Ağları

**Dominant:** quiz | **grademax:** 100

### Grade Kategori Hiyerarşisi
| Derinlik | Kategori | aggregation | coef | grademax |
|----------|----------|-------------|------|----------|
| 1 (kök) | ? | 13 | — | 100 |
| 2 | Vize | 10 | 0.25 | 25 |
| 2 | Final | 10 | 0.40 | 40 |
| 2 | Haftalık Testler | 10 | 0.25 | 25 |
| 2 | Ödev | 10 | 0.10 | 10 |

### Grade Item Dağılımı
| Item | itemtype | itemmodule | grademax | gradepass | aggregationcoef |
|------|----------|------------|----------|-----------|-----------------|
| Quiz Vize | mod | quiz | 25 | 12.5 | 0.25 |
| Quiz Final | mod | quiz | 40 | 20 | 0.40 |
| Ödev ×3 | mod | assign | 10 | 5 | 0.10 |

---

## Kurs 8 — Yazılım Mühendisliği

**Dominant:** assign (karma) | **grademax:** 100

### Grade Kategori Hiyerarşisi
| Derinlik | Kategori | aggregation | coef | grademax |
|----------|----------|-------------|------|----------|
| 1 (kök) | ? | 13 | — | 100 |
| 2 | Proje/Ödev | 10 | 0.40 | 40 |
| 2 | Vize | 10 | 0.20 | 20 |
| 2 | Final | 10 | 0.25 | 25 |
| 2 | SCORM/Ders | 13 | 0.15 | 15 |

### Grade Item Dağılımı
| Item | itemtype | itemmodule | grademax | gradepass | aggregationcoef |
|------|----------|------------|----------|-----------|-----------------|
| Quiz Vize | mod | quiz | 20 | 10 | 0.20 |
| Quiz Final | mod | quiz | 25 | 12.5 | 0.25 |
| Ödev/Proje ×3 | mod | assign | 20 | 10 | 0.40 |
| Ders (lesson) | mod | lesson | 100 | 33 | 0.03846 |

---

## Kurs 9 — Makine Öğrenmesi

**Dominant:** assign (notebook) | **grademax:** 100

### Grade Kategori Hiyerarşisi
| Derinlik | Kategori | aggregation | coef | grademax |
|----------|----------|-------------|------|----------|
| 1 (kök) | ? | 13 | — | 100 |
| 2 | Ödevler | 10 | 0.40 | 40 |
| 2 | Sınavlar | 10 | 0.40 | 40 |
| 2 | H5P/Demo | 13 | 0.20 | 20 |

### Grade Item Dağılımı
| Item | itemtype | itemmodule | grademax | gradepass | aggregationcoef |
|------|----------|------------|----------|-----------|-----------------|
| Quiz Vize | mod | quiz | 15 | 7.5 | 0.40 |
| Quiz Final | mod | quiz | 25 | 12.5 | 0.40 |
| Notebook Ödevi ×3 | mod | assign | 15 | 7.5 | 0.40 |

---

## Kurs 10 — Yapay Zeka

**Dominant:** quiz | **grademax:** 100

### Grade Kategori Hiyerarşisi
| Derinlik | Kategori | aggregation | coef | grademax |
|----------|----------|-------------|------|----------|
| 1 (kök) | ? | 13 | — | 100 |
| 2 | Sınavlar | 10 | 0.50 | 50 |
| 2 | Ödevler | 10 | 0.30 | 30 |
| 2 | Katılım | 11 | 0.20 | 20 |

---

## Kurs 11 — Siber Güvenlik

**Dominant:** quiz (CTF tipi) | **grademax:** 100

### Grade Kategori Hiyerarşisi
| Derinlik | Kategori | aggregation | coef | grademax |
|----------|----------|-------------|------|----------|
| 1 (kök) | ? | 13 | — | 100 |
| 2 | Vize | 10 | 0.30 | 30 |
| 2 | Final | 10 | 0.40 | 40 |
| 2 | Lab Sınavları | 10 | 0.20 | 20 |
| 2 | Ödev | 10 | 0.10 | 10 |

---

## Kurs 12 — Mobil Uygulama Geliştirme

**Dominant:** assign (app projects) | **grademax:** 100

### Grade Kategori Hiyerarşisi
| Derinlik | Kategori | aggregation | coef | grademax |
|----------|----------|-------------|------|----------|
| 1 (kök) | ? | 13 | — | 100 |
| 2 | Projeler | 10 | 0.55 | 55 |
| 2 | Sınavlar | 10 | 0.35 | 35 |
| 2 | Katılım | 11 | 0.10 | 10 |

---

## Kurs 13 — Bulut Bilişim

**Dominant:** scorm (sertifikasyon) | **grademax:** 100
> Lesson'lar notlandırılmaz (lesson_aggregationcoef=0.0)

### Grade Kategori Hiyerarşisi
| Derinlik | Kategori | aggregation | coef | grademax |
|----------|----------|-------------|------|----------|
| 1 (kök) | ? | 13 | — | 100 |
| 2 | SCORM Sertifikasyon | 10 | 0.45 | 45 |
| 2 | Sınavlar | 10 | 0.40 | 40 |
| 2 | Proje | 10 | 0.15 | 15 |

---

## Kurs 14 — Veri Analitiği

**Dominant:** assign (görselleştirme) | **grademax:** 100

### Grade Kategori Hiyerarşisi
| Derinlik | Kategori | aggregation | coef | grademax |
|----------|----------|-------------|------|----------|
| 1 (kök) | ? | 13 | — | 100 |
| 2 | Analizler | 10 | 0.45 | 45 |
| 2 | H5P Görsel | 13 | 0.25 | 25 |
| 2 | Sınavlar | 10 | 0.30 | 30 |

---

## Kurs 15 — İnsan-Bilgisayar Etkileşimi

**Dominant:** assign (forum + proje) | **grademax:** 100

### Grade Kategori Hiyerarşisi
| Derinlik | Kategori | aggregation | coef | grademax |
|----------|----------|-------------|------|----------|
| 1 (kök) | ? | 13 | — | 100 |
| 2 | Projeler | 10 | 0.40 | 40 |
| 2 | Sınavlar | 10 | 0.30 | 30 |
| 2 | Forum Katılımı | 11 | 0.20 | 20 |
| 2 | Derse Katılım | 13 | 0.10 | 10 |

### Grade Item Dağılımı
| Item | itemtype | itemmodule | grademax | gradepass | aggregationcoef |
|------|----------|------------|----------|-----------|-----------------|
| Genel Not | course | — | 100 | 50 | 0.0 |
| Quiz Vize | mod | quiz | 10 | 5 | 0.30 |
| Quiz Final | mod | quiz | 20 | 10 | 0.30 |
| Ödev/Proje ×3 | mod | assign | 20 | 10 | 0.40 |
| Ders (lesson) | mod | lesson | 100 | 33 | 0.03846 |

---

## Ağırlık Doğrulama

Her kurs için `Σ(coef) = 1.00`:

| Kurs | Kategori coef'leri | Toplam |
|------|--------------------|--------|
| 1 | 0.30+0.35+0.20+0.15 | **1.00** |
| 2 | 0.30+0.35+0.20+0.15 | **1.00** |
| 3 | 0.50+0.20+0.20+0.10 | **1.00** |
| 4 | 0.40+0.25+0.25+0.10 | **1.00** |
| 5 | 0.35+0.35+0.30 | **1.00** |
| 6 | 0.60+0.30+0.10 | **1.00** |
| 7 | 0.25+0.40+0.25+0.10 | **1.00** |
| 8 | 0.40+0.20+0.25+0.15 | **1.00** |
| 9 | 0.40+0.40+0.20 | **1.00** |
| 10 | 0.50+0.30+0.20 | **1.00** |
| 11 | 0.30+0.40+0.20+0.10 | **1.00** |
| 12 | 0.55+0.35+0.10 | **1.00** |
| 13 | 0.45+0.40+0.15 | **1.00** |
| 14 | 0.45+0.25+0.30 | **1.00** |
| 15 | 0.40+0.30+0.20+0.10 | **1.00** |
