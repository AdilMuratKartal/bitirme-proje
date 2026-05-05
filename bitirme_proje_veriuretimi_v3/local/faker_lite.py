"""
faker_lite.py — Hafif Türkçe Faker (network gerektirmez)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Gerçek Faker kütüphanesi bulunamadığında bu modül devreye girer.
API yüzeyi: FakerLite(seed).first_name() / last_name() / email() / sentence()
"""

import random
import string
from typing import Optional

TR_FIRST_NAMES = [
    "Ahmet","Mehmet","Mustafa","Ali","Hüseyin","Hasan","İbrahim","İsmail","Halil","Yusuf",
    "Ayşe","Fatma","Emine","Hatice","Zeynep","Elif","Meryem","Esra","Derya","Selin",
    "Emre","Burak","Onur","Cem","Mert","Kerem","Berk","Oğuz","Taner","Serkan",
    "Gamze","Pınar","Burcu","Deniz","Nilüfer","Ceren","Tuğçe","Büşra","Merve","Kübra",
    "Ömer","Kaan","Adem","Tarık","Volkan","Selim","Erdal","Orhan","Coşkun","Gökhan",
    "Sibel","Gülşen","Arzu","Neslihan","Filiz","Özlem","Leyla","Güneş","Aslı","Yıldız",
]

TR_LAST_NAMES = [
    "Yılmaz","Kaya","Demir","Şahin","Çelik","Yıldız","Yıldırım","Öztürk","Aydın","Özdemir",
    "Arslan","Doğan","Kılıç","Aslan","Çetin","Erdoğan","Koç","Kurt","Özkan","Şimşek",
    "Aktaş","Güneş","Korkmaz","Polat","Karahan","Bulut","Aksoy","Tekin","Acar","Güler",
    "Bozkurt","Demirkaya","Kaplan","Keskin","Uçar","Kara","Aşık","Tunç","Eroğlu","Saraç",
]

TR_DOMAINS = [
    "gmail.com","hotmail.com","yahoo.com","outlook.com",
    "icloud.com","yandex.com","mynet.com","turk.net",
]

TR_WORDS = [
    "veri","analiz","sistem","model","konu","öğrenci","başarı","proje",
    "fonksiyon","döngü","sınav","ödev","not","kayıt","işlem","sonuç",
    "değerlendirme","strateji","geliştirme","çözüm","uygulama","yöntem",
    "algoritma","yapı","liste","sözlük","sınıf","nesne","modül","dosya",
]


class FakerLite:
    """Gerçek Faker API'sine benzer arayüz."""

    def __init__(self, seed: Optional[int] = None):
        self._rnd = random.Random(seed)

    def first_name(self) -> str:
        return self._rnd.choice(TR_FIRST_NAMES)

    def last_name(self) -> str:
        return self._rnd.choice(TR_LAST_NAMES)

    def email(self) -> str:
        local = (
            self._rnd.choice(TR_FIRST_NAMES).lower()
            + "."
            + self._rnd.choice(TR_LAST_NAMES).lower()
            + str(self._rnd.randint(10, 999))
        )
        local = local.replace("İ", "i").replace("Ş", "s").replace("Ğ", "g") \
                     .replace("Ü", "u").replace("Ö", "o").replace("Ç", "c") \
                     .replace("ı", "i").replace("ş", "s").replace("ğ", "g") \
                     .replace("ü", "u").replace("ö", "o").replace("ç", "c")
        return f"{local}@{self._rnd.choice(TR_DOMAINS)}"

    def sentence(self, nb_words: int = 6) -> str:
        words = self._rnd.choices(TR_WORDS, k=nb_words)
        s = " ".join(words).capitalize()
        return s + "?"

    def seed_instance(self, seed: int) -> None:
        self._rnd.seed(seed)
