from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AlpModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        extra="allow",
    )


class KesimBilgisi(AlpModel):
    tarih: Optional[str] = None
    kilo: Optional[Any] = None
    yas_gun: Optional[int] = None


class CiftlikBase(AlpModel):
    ad: str
    aciklama: Optional[str] = None
    aktif: bool = True


class CiftlikCreate(CiftlikBase):
    id: Optional[str] = None


class CiftlikUpdate(AlpModel):
    ad: Optional[str] = None
    aciklama: Optional[str] = None
    aktif: Optional[bool] = None


class CiftlikResponse(CiftlikBase):
    id: str
    olusturma_tarihi: Optional[str] = None


class KullaniciBase(AlpModel):
    kullanici_adi: str
    rol: str = "ciftlik"
    ciftlik_id: Optional[str] = None
    aktif: bool = True


class KullaniciCreate(KullaniciBase):
    sifre: str


class KullaniciUpdate(AlpModel):
    kullanici_adi: Optional[str] = None
    sifre: Optional[str] = None
    rol: Optional[str] = None
    ciftlik_id: Optional[str] = None
    aktif: Optional[bool] = None


class KullaniciResponse(KullaniciBase):
    id: str
    olusturma_tarihi: Optional[str] = None
    son_giris: Optional[str] = None
    ciftlik: Optional[CiftlikResponse] = None


class LoginRequest(AlpModel):
    kullanici_adi: str
    sifre: str


class LoginResponse(AlpModel):
    access_token: str
    token_type: str = "bearer"
    kullanici: KullaniciResponse


class DeviceLoginRequest(AlpModel):
    device_token: str


class DeviceTokenResponse(AlpModel):
    device_token: str
    token_type: str = "device"


class SifreDegistirRequest(AlpModel):
    eski_sifre: str
    yeni_sifre: str


class SifreSifirlaRequest(AlpModel):
    yeni_sifre: str


class TohumlamaBase(AlpModel):
    tarih: str
    sekil: Optional[str] = None
    suni_isim: Optional[str] = None
    gebe_mi: Optional[bool] = None
    kontrol_tarihi: Optional[str] = None
    gebelik_suresi: int = 283


class TohumlamaCreate(TohumlamaBase):
    id: Optional[str] = None


class TohumlamaUpdate(AlpModel):
    tarih: Optional[str] = None
    sekil: Optional[str] = None
    suni_isim: Optional[str] = None
    gebe_mi: Optional[bool] = None
    kontrol_tarihi: Optional[str] = None
    gebelik_suresi: Optional[int] = None


class TohumlamaResponse(TohumlamaBase):
    id: str
    hayvan_id: Optional[str] = None


class AsiProsedurBase(AlpModel):
    ad: str
    tarih: str
    sonraki_tarih: Optional[str] = None
    not_: Optional[str] = Field(default=None, alias="not")


class AsiProsedurCreate(AsiProsedurBase):
    id: Optional[str] = None


class AsiProsedurUpdate(AlpModel):
    ad: Optional[str] = None
    tarih: Optional[str] = None
    sonraki_tarih: Optional[str] = None
    not_: Optional[str] = Field(default=None, alias="not")


class AsiProsedurResponse(AsiProsedurBase):
    id: str
    hayvan_id: Optional[str] = None


class YavruBilgi(AlpModel):
    kupe: Optional[str] = None
    resmi_kupe_no: Optional[str] = None
    ciftlik_kupe_no: Optional[str] = None
    cins: Optional[str] = None


class DogumBase(AlpModel):
    tarih: str
    yavrular: List[YavruBilgi] = Field(default_factory=list)
    laktasyon_bitis_tarihi: Optional[str] = None
    not_: Optional[str] = Field(default=None, alias="not")


class DogumCreate(DogumBase):
    id: Optional[str] = None


class DogumUpdate(AlpModel):
    tarih: Optional[str] = None
    yavrular: Optional[List[YavruBilgi]] = None
    laktasyon_bitis_tarihi: Optional[str] = None
    not_: Optional[str] = Field(default=None, alias="not")


class DogumResponse(DogumBase):
    id: Optional[str] = None


class HayvanBase(AlpModel):
    ciftlik_id: Optional[str] = None
    ciftlik_ad: Optional[str] = None
    kupe_no: Optional[str] = None
    resmi_kupe_no: Optional[str] = None
    ciftlik_kupe_no: Optional[str] = None
    ad: Optional[str] = None
    dogum_tarihi: Optional[str] = None
    cins: str = "Bilinmiyor"
    irk: Optional[str] = None
    cinsiyet: Optional[str] = None
    anne_kupe: Optional[str] = None
    kayit_tarihi: Optional[str] = None
    yas_gun: Optional[int] = None
    yas_yil: int = 0
    yas_ay: int = 0
    durum: Optional[str] = None
    durum_notu: Optional[str] = None
    ek_notlar: Optional[str] = None
    gebe_mi: bool = False
    gebelik_tarihi: Optional[str] = None
    aktif_tohumlama_id: Optional[str] = None
    olu: bool = False
    olum_tarihi: Optional[str] = None
    kesildi: bool = False
    kesim_tarihi: Optional[str] = None
    kesim_bilgisi: Optional[KesimBilgisi] = None
    satildi: bool = False
    satis_tarihi: Optional[str] = None
    satis_bilgisi: Optional[Dict[str, Any]] = None
    arsivli: bool = False
    arsiv_tarihi: Optional[str] = None
    foto_data: Optional[str] = None
    foto_datas: List[str] = Field(default_factory=list)
    foto_path: Optional[str] = None
    foto_paths: List[str] = Field(default_factory=list)
    foto_url: Optional[str] = None
    foto_urls: List[str] = Field(default_factory=list)
    son_guncelleme: Optional[str] = None
    tohumlamalar: List[TohumlamaCreate] = Field(default_factory=list)
    dogumlar: List[DogumCreate] = Field(default_factory=list)
    asi_prosedurler: List[AsiProsedurCreate] = Field(default_factory=list)


class HayvanCreate(HayvanBase):
    id: Optional[str] = None


class HayvanUpdate(AlpModel):
    ciftlik_id: Optional[str] = None
    kupe_no: Optional[str] = None
    resmi_kupe_no: Optional[str] = None
    ciftlik_kupe_no: Optional[str] = None
    ad: Optional[str] = None
    dogum_tarihi: Optional[str] = None
    cins: Optional[str] = None
    irk: Optional[str] = None
    cinsiyet: Optional[str] = None
    anne_kupe: Optional[str] = None
    kayit_tarihi: Optional[str] = None
    yas_gun: Optional[int] = None
    yas_yil: Optional[int] = None
    yas_ay: Optional[int] = None
    durum: Optional[str] = None
    durum_notu: Optional[str] = None
    ek_notlar: Optional[str] = None
    gebe_mi: Optional[bool] = None
    gebelik_tarihi: Optional[str] = None
    aktif_tohumlama_id: Optional[str] = None
    olu: Optional[bool] = None
    olum_tarihi: Optional[str] = None
    kesildi: Optional[bool] = None
    kesim_tarihi: Optional[str] = None
    kesim_bilgisi: Optional[KesimBilgisi] = None
    satildi: Optional[bool] = None
    satis_tarihi: Optional[str] = None
    satis_bilgisi: Optional[Dict[str, Any]] = None
    arsivli: Optional[bool] = None
    arsiv_tarihi: Optional[str] = None
    foto_data: Optional[str] = None
    foto_datas: Optional[List[str]] = None
    foto_path: Optional[str] = None
    foto_paths: Optional[List[str]] = None
    foto_url: Optional[str] = None
    foto_urls: Optional[List[str]] = None
    son_guncelleme: Optional[str] = None
    tohumlamalar: Optional[List[TohumlamaCreate]] = None
    dogumlar: Optional[List[DogumCreate]] = None
    asi_prosedurler: Optional[List[AsiProsedurCreate]] = None


class HayvanResponse(HayvanBase):
    id: str
    tohumlamalar: List[TohumlamaResponse] = Field(default_factory=list)
    dogumlar: List[DogumResponse] = Field(default_factory=list)
    asi_prosedurler: List[AsiProsedurResponse] = Field(default_factory=list)


class HayvanAramaResponse(AlpModel):
    ref: str
    kaynak: str = "normal"
    eslesme_sayisi: int
    tekil: bool
    hayvanlar: List[HayvanResponse] = Field(default_factory=list)


class SistemDurumuResponse(AlpModel):
    olusturma_zamani: str
    database: Dict[str, Any] = Field(default_factory=dict)
    storage: Dict[str, Any] = Field(default_factory=dict)
    kayit_sayilari: Dict[str, Any] = Field(default_factory=dict)
    fotograflar: Dict[str, Any] = Field(default_factory=dict)
    limitler: Dict[str, Any] = Field(default_factory=dict)


class UyariResponse(AlpModel):
    hayvan_id: str
    kupe_no: str
    tip: str
    mesaj: str
    kalan_gun: int
    durum: str


class RaporOzetResponse(AlpModel):
    toplam: int
    aktif: int
    gebe: int
    arsivli: int
    olu: int
    kesildi: int
    cins_dagilimi: Dict[str, int] = Field(default_factory=dict)
    acik_uyari: int = 0


class IslemSonucResponse(AlpModel):
    status: str = "ok"
    message: str
    id: Optional[str] = None


class IslemGecmisiResponse(AlpModel):
    id: str
    zaman: str
    detay: str
    islem_tipi: Optional[str] = None
    kullanici_id: Optional[str] = None
    kullanici_adi: Optional[str] = None
    rol: Optional[str] = None
    ciftlik_id: Optional[str] = None
    hedef_tipi: Optional[str] = None
    hedef_id: Optional[str] = None


class YedekResponse(AlpModel):
    olusturma_zamani: str
    ciftlikler: List[Dict[str, Any]] = Field(default_factory=list)
    kullanicilar: List[Dict[str, Any]] = Field(default_factory=list)
    hayvanlar: List[Dict[str, Any]] = Field(default_factory=list)
    islem_gecmisi: List[IslemGecmisiResponse] = Field(default_factory=list)
