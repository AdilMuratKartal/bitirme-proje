# Proje: Bitirme Proje Genel Moodle DB ve LMS Semantik Veri Üretici

## Mimari
- MIMO Modeli (1&2): LSTM + Dense → Risk skoru + Tahmin notu
- HKAR Modeli (3&4): LSTM + Dense → Konu başarısı + İçerik önerisi

## Dosyalar
- config.py          → Tüm parametreler ve 4 segment profili
- student_registry.py → Öğrenci-segment ataması
- faker_lite.py      → Dahili TR Faker (network gerekmez)
- raw_tables.py      → 17 MDL tablosu üreticisi
- feature_mimo.py    → X_Time (LSTM) + X_Static (Dense)
- feature_hkar.py    → X_Sequence (DKT) + X_UserHabit
- pipeline.py        → Giriş noktası: python pipeline.py

## 4 Segment
- S1 Başarılı (%25): Yüksek not, erken teslim
- S2 Orta Başarılı (%35): Orta not, sınav öncesi burst
- S3 İstikrarsız (%25): Dalgalı, gece çalışır, geç teslim
- S4 Terke Meyilli (%15): Azalan aktivite, eksik teslim

## ERD Zincirleri
### MIMO
mdl_user → mdl_grade_grades → mdl_grade_items → mdl_course
mdl_user → mdl_assign_submission → mdl_assign → mdl_course
mdl_user → mdl_quiz_attempts → mdl_quiz → mdl_course
mdl_user → mdl_logstore_standard_log → mdl_course
mdl_user → mdl_course_modules_completion → mdl_course_modules

### HKRT
mdl_quiz_attempts.uniqueid → mdl_question_attempts.questionusageid
mdl_question_attempts.questionid → mdl_question.id
mdl_question.category → mdl_question_categories.id → .name
mdl_question_attempt_steps.questionattemptid → mdl_question_attempts.id

## Kurallar
- Tablolar birbirine JOIN'lenmez, ilişkiler sadece FK ile kurulur
- mdl_question_attempts tablosunda topic sütunu YOKTUR
- Eksik veri = satır üretilmez (gerçek eksiklik simülasyonu)
- Yeni parametre → config.py SEGMENT_PROFILES
- Yeni tablo → raw_tables.py fonksiyon + load_all_tables() kaydı

## Çıktı Şekilleri
- MIMO X_Time:      (200, 3, 2)  → LSTM
- MIMO X_Static:    (200, 5)     → Dense
- HKAR X_Sequence:  (200, 10, 3) → LSTM/DKT
- HKAR X_UserHabit: (200, 5)     → Dense
```

---

## Adım 7 — Claude Code'u Başlat
```
claude
```

İlk açılışta Anthropic hesabınıza giriş isteyecek — tarayıcı açılır, onaylarsın. Sonra şu ekran gelir:
```
✓ Claude Code ready
>
```

Artık şöyle konuşabilirsin:
```
> pipeline.py'yi çalıştır, çıktıyı analiz et
> S4 segmentini daha agresif yap, missing_week_prob 0.60 olsun
> HKAR için yeni bir tablo ekle