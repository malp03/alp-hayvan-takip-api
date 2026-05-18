from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base
import uuid

def generate_uuid():
    return uuid.uuid4().hex

class Hayvan(Base):
    __tablename__ = "hayvanlar"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    ciftlik_id = Column(String, ForeignKey("ciftlikler.id"), index=True, nullable=True)
    resmi_kupe_no = Column(String, index=True, nullable=True)
    ciftlik_kupe_no = Column(String, index=True, nullable=True)
    ad = Column(String, nullable=True)
    
    yas_yil = Column(Integer, default=0)
    yas_ay = Column(Integer, default=0)
    cins = Column(String, default="Bilinmiyor")
    cinsiyet = Column(String, default="Dişi")
    durum_notu = Column(String, nullable=True)
    dogum_tarihi = Column(String, nullable=True) 
    ek_notlar = Column(Text, nullable=True)
    veri_json = Column(Text, nullable=True)
    
    # Durumlar
    olu = Column(Boolean, default=False)
    kesildi = Column(Boolean, default=False)
    arsivli = Column(Boolean, default=False)
    
    olum_tarihi = Column(String, nullable=True)
    kesim_tarihi = Column(String, nullable=True)
    arsiv_tarihi = Column(String, nullable=True)
    
    son_guncelleme = Column(String, nullable=True)

    # İlişkiler
    ciftlik = relationship("Ciftlik", back_populates="hayvanlar")
    tohumlamalar = relationship("Tohumlama", back_populates="hayvan", cascade="all, delete-orphan")
    asi_prosedurler = relationship("AsiProsedur", back_populates="hayvan", cascade="all, delete-orphan")
    uyarilar = relationship("Uyari", back_populates="hayvan", cascade="all, delete-orphan")


class Ciftlik(Base):
    __tablename__ = "ciftlikler"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    ad = Column(String, nullable=False)
    aciklama = Column(Text, nullable=True)
    aktif = Column(Boolean, default=True)
    olusturma_tarihi = Column(String, nullable=True)

    hayvanlar = relationship("Hayvan", back_populates="ciftlik")
    kullanicilar = relationship("Kullanici", back_populates="ciftlik")


class Kullanici(Base):
    __tablename__ = "kullanicilar"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    kullanici_adi = Column(String, unique=True, index=True, nullable=False)
    sifre_hash = Column(Text, nullable=False)
    rol = Column(String, default="ciftlik", nullable=False)  # admin / ciftlik
    ciftlik_id = Column(String, ForeignKey("ciftlikler.id"), nullable=True)
    aktif = Column(Boolean, default=True)
    olusturma_tarihi = Column(String, nullable=True)
    son_giris = Column(String, nullable=True)

    ciftlik = relationship("Ciftlik", back_populates="kullanicilar")

class Tohumlama(Base):
    __tablename__ = "tohumlamalar"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    hayvan_id = Column(String, ForeignKey("hayvanlar.id"))
    
    tarih = Column(String, nullable=False)
    sekil = Column(String, nullable=True) # Suni / Boğa
    suni_isim = Column(String, nullable=True)
    gebe_mi = Column(Boolean, nullable=True) # True: Pozitif, False: Negatif, None: Beklemede
    kontrol_tarihi = Column(String, nullable=True)
    
    hayvan = relationship("Hayvan", back_populates="tohumlamalar")

class AsiProsedur(Base):
    __tablename__ = "asi_prosedurler"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    hayvan_id = Column(String, ForeignKey("hayvanlar.id"))
    
    ad = Column(String, nullable=False)
    tarih = Column(String, nullable=False)
    sonraki_tarih = Column(String, nullable=True)
    not_ = Column("not", Text, nullable=True) 
    
    hayvan = relationship("Hayvan", back_populates="asi_prosedurler")

class Uyari(Base):
    __tablename__ = "uyarilar"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    hayvan_id = Column(String, ForeignKey("hayvanlar.id"), nullable=True) # None ise sistem uyarısı
    
    tip = Column(String, nullable=False)
    mesaj = Column(Text, nullable=False)
    tarih = Column(String, nullable=True)
    onem_derecesi = Column(Integer, default=1)
    okundu = Column(Boolean, default=False)
    
    hayvan = relationship("Hayvan", back_populates="uyarilar")

class IslemGecmisi(Base):
    __tablename__ = "islem_gecmisi"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    zaman = Column(String, nullable=False)
    detay = Column(Text, nullable=False)
