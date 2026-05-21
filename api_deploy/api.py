from datetime import datetime, timedelta
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any, Dict, Iterable, List, Optional
import uuid

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import or_
from sqlalchemy.orm import Session
import uvicorn

from database import (
    Base,
    engine,
    ensure_postgres_schema_updates,
    ensure_postgres_security,
    ensure_sqlite_schema,
    get_db,
)
import models
import schemas


app = FastAPI(title="ALP Ziraat Hayvan Takip API", version="1.0.0")

cors_origins = [
    origin.strip()
    for origin in os.getenv("ALP_API_CORS_ORIGINS", "*").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)
ensure_sqlite_schema()
ensure_postgres_schema_updates()
ensure_postgres_security()

TARIH_FORMATI = "%d/%m/%Y"
ZAMAN_FORMATI = "%d/%m/%Y %H:%M:%S"
ERKEK_CINSLER = {"Erkek Buzağı", "Dana"}
DISI_CINSLER = {"Dişi Buzağı", "Düve", "Sağmal İnek", "Kuru İnek"}
DEFAULT_CIFTLIK_ID = os.getenv("ALP_DEFAULT_CIFTLIK_ID", "varsayilan-ciftlik")
DEFAULT_CIFTLIK_ADI = os.getenv("ALP_DEFAULT_CIFTLIK_ADI", "Varsayılan Çiftlik")
AUTH_SECRET = os.getenv("ALP_AUTH_SECRET", "alp-ziraat-dev-secret-change-me")
TOKEN_TTL_SECONDS = int(os.getenv("ALP_TOKEN_TTL_SECONDS", str(12 * 60 * 60)))
DEVICE_TOKEN_TTL_SECONDS = int(os.getenv("ALP_DEVICE_TOKEN_TTL_SECONDS", str(90 * 24 * 60 * 60)))


def simdi() -> str:
    return datetime.now().strftime(ZAMAN_FORMATI)


def bugun() -> str:
    return datetime.now().strftime(TARIH_FORMATI)


def yeni_id(uzunluk: Optional[int] = None) -> str:
    deger = uuid.uuid4().hex
    return deger[:uzunluk] if uzunluk else deger


def stabil_alt_kayit_id(hayvan_id: str, tip: str, index: int, veri: Dict[str, Any]) -> str:
    parca = "|".join(
        [
            hayvan_id,
            tip,
            str(index),
            metin(veri.get("tarih")),
            metin(veri.get("ad")),
            metin(veri.get("sekil")),
        ]
    )
    return uuid.uuid5(uuid.NAMESPACE_URL, parca).hex[:12]


def model_verisi(model: Any, *, exclude_unset: bool = False) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(
            exclude_unset=exclude_unset,
            by_alias=True,
        )
    return model.dict(exclude_unset=exclude_unset, by_alias=True)


def b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def b64_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def sifre_hashle(sifre: str) -> str:
    salt = secrets.token_bytes(16)
    iterations = 210_000
    digest = hashlib.pbkdf2_hmac("sha256", sifre.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def sifre_dogrula(sifre: str, sifre_hash: str) -> bool:
    try:
        algoritma, iterations, salt_hex, digest_hex = sifre_hash.split("$", 3)
        if algoritma != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            sifre.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def token_uret(kullanici: models.Kullanici) -> str:
    payload = {
        "sub": kullanici.id,
        "rol": kullanici.rol,
        "ciftlik_id": kullanici.ciftlik_id,
        "typ": "access",
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    payload_b64 = b64_encode(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    imza = hmac.new(AUTH_SECRET.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    return f"{payload_b64}.{b64_encode(imza)}"


def device_token_uret(kullanici: models.Kullanici) -> str:
    payload = {
        "sub": kullanici.id,
        "rol": kullanici.rol,
        "ciftlik_id": kullanici.ciftlik_id,
        "typ": "device",
        "exp": int(time.time()) + DEVICE_TOKEN_TTL_SECONDS,
    }
    payload_b64 = b64_encode(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    imza = hmac.new(AUTH_SECRET.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    return f"{payload_b64}.{b64_encode(imza)}"


def token_coz(token: str) -> Dict[str, Any]:
    try:
        payload_b64, imza_b64 = token.split(".", 1)
        beklenen = hmac.new(AUTH_SECRET.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(b64_decode(imza_b64), beklenen):
            raise ValueError("geçersiz imza")
        payload = json.loads(b64_decode(payload_b64).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("token süresi doldu")
        return payload
    except Exception as hata:
        raise HTTPException(status_code=401, detail="Oturum geçersiz veya süresi dolmuş.") from hata


def kullanici_payload(kullanici: models.Kullanici) -> Dict[str, Any]:
    ciftlik = None
    if kullanici.ciftlik:
        ciftlik = {
            "id": kullanici.ciftlik.id,
            "ad": kullanici.ciftlik.ad,
            "aciklama": kullanici.ciftlik.aciklama,
            "aktif": bool(kullanici.ciftlik.aktif),
            "olusturma_tarihi": kullanici.ciftlik.olusturma_tarihi,
        }
    return {
        "id": kullanici.id,
        "kullanici_adi": kullanici.kullanici_adi,
        "rol": kullanici.rol,
        "ciftlik_id": kullanici.ciftlik_id,
        "aktif": bool(kullanici.aktif),
        "olusturma_tarihi": kullanici.olusturma_tarihi,
        "son_giris": kullanici.son_giris,
        "ciftlik": ciftlik,
    }


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> models.Kullanici:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Giriş yapılmalıdır.")
    payload = token_coz(authorization.split(" ", 1)[1].strip())
    if payload.get("typ") == "device":
        raise HTTPException(status_code=401, detail="Cihaz tokeniyle işlem yapılamaz; önce oturum yenileyin.")
    kullanici = db.query(models.Kullanici).filter(models.Kullanici.id == payload.get("sub")).first()
    if not kullanici or not kullanici.aktif:
        raise HTTPException(status_code=401, detail="Kullanıcı aktif değil veya bulunamadı.")
    return kullanici


def require_admin(kullanici: models.Kullanici = Depends(get_current_user)) -> models.Kullanici:
    if kullanici.rol != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için admin yetkisi gerekir.")
    return kullanici


def sifre_gucu_kontrol(sifre: str) -> None:
    if not sifre or len(sifre) < 8:
        raise HTTPException(status_code=400, detail="Sifre en az 8 karakter olmalidir.")


def islem_payload(kayit: models.IslemGecmisi) -> Dict[str, Any]:
    return {
        "id": kayit.id,
        "zaman": kayit.zaman,
        "detay": kayit.detay,
        "islem_tipi": kayit.islem_tipi,
        "kullanici_id": kayit.kullanici_id,
        "kullanici_adi": kayit.kullanici_adi,
        "rol": kayit.rol,
        "ciftlik_id": kayit.ciftlik_id,
        "hedef_tipi": kayit.hedef_tipi,
        "hedef_id": kayit.hedef_id,
    }


def audit_kaydi(
    db: Session,
    kullanici: Optional[models.Kullanici],
    islem_tipi: str,
    detay: str,
    *,
    ciftlik_id: Optional[str] = None,
    hedef_tipi: Optional[str] = None,
    hedef_id: Optional[str] = None,
) -> None:
    if kullanici and kullanici.rol != "admin" and not ciftlik_id:
        ciftlik_id = kullanici.ciftlik_id
    db.add(
        models.IslemGecmisi(
            id=yeni_id(),
            zaman=simdi(),
            detay=detay,
            islem_tipi=islem_tipi,
            kullanici_id=kullanici.id if kullanici else None,
            kullanici_adi=kullanici.kullanici_adi if kullanici else None,
            rol=kullanici.rol if kullanici else None,
            ciftlik_id=ciftlik_id,
            hedef_tipi=hedef_tipi,
            hedef_id=hedef_id,
        )
    )


def kullanici_ciftlik_id(kullanici: models.Kullanici, requested_ciftlik_id: Optional[str] = None) -> Optional[str]:
    if kullanici.rol == "admin":
        return requested_ciftlik_id
    if not kullanici.ciftlik_id:
        raise HTTPException(status_code=403, detail="Kullanıcı bir çiftliğe bağlı değil.")
    return kullanici.ciftlik_id


def ciftlik_erisim_kontrol(kullanici: models.Kullanici, ciftlik_id: Optional[str]) -> None:
    if kullanici.rol == "admin":
        return
    if not ciftlik_id or ciftlik_id != kullanici.ciftlik_id:
        raise HTTPException(status_code=403, detail="Bu çiftlik verisine erişim yok.")


def bos_yoksa_none(deger: Any) -> Optional[str]:
    if deger is None:
        return None
    deger = str(deger).strip()
    return deger or None


def metin(deger: Any, *, upper: bool = False) -> str:
    if deger is None:
        return ""
    sonuc = str(deger).strip()
    return sonuc.upper() if upper else sonuc


def parse_tarih(deger: Optional[str], alan: str, *, zorunlu: bool = False) -> Optional[datetime]:
    deger = metin(deger)
    if not deger:
        if zorunlu:
            raise HTTPException(status_code=400, detail=f"{alan} zorunludur.")
        return None
    if deger == "Bilinmiyor":
        return None
    try:
        return datetime.strptime(deger, TARIH_FORMATI)
    except ValueError as hata:
        raise HTTPException(
            status_code=400,
            detail=f"{alan} GG/AA/YYYY formatında olmalıdır.",
        ) from hata


def parse_tarih_sessiz(deger: Optional[str]) -> Optional[datetime]:
    try:
        return parse_tarih(deger, "Tarih")
    except HTTPException:
        return None


def tarih_gelecekte_olamaz(deger: Optional[str], alan: str) -> Optional[datetime]:
    tarih = parse_tarih(deger, alan)
    if tarih and tarih.date() > datetime.now().date():
        raise HTTPException(status_code=400, detail=f"{alan} gelecekte olamaz.")
    return tarih


def parse_zaman_sessiz(deger: Optional[str]) -> Optional[datetime]:
    deger = metin(deger)
    if not deger:
        return None
    for fmt in (ZAMAN_FORMATI, TARIH_FORMATI):
        try:
            return datetime.strptime(deger, fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(deger.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def gelen_zaman_daha_eski_mi(gelen_zaman: Optional[str], mevcut_zaman: Optional[str]) -> bool:
    gelen = parse_zaman_sessiz(gelen_zaman)
    mevcut = parse_zaman_sessiz(mevcut_zaman)
    return bool(gelen and mevcut and gelen < mevcut)


def son_silme_zamani(db: Session, hayvan_id: str) -> Optional[datetime]:
    kayitlar = (
        db.query(models.IslemGecmisi)
        .filter(
            models.IslemGecmisi.islem_tipi == "hayvan_sil",
            models.IslemGecmisi.hedef_tipi == "hayvan",
            models.IslemGecmisi.hedef_id == hayvan_id,
        )
        .all()
    )
    zamanlar = [parse_zaman_sessiz(k.zaman) for k in kayitlar]
    zamanlar = [z for z in zamanlar if z is not None]
    return max(zamanlar) if zamanlar else None


def yas_gun_hesapla(veri: Dict[str, Any]) -> int:
    dogum_tarihi = parse_tarih(veri.get("dogum_tarihi"), "Doğum tarihi")
    if dogum_tarihi:
        return max((datetime.now() - dogum_tarihi).days, 0)
    if veri.get("yas_gun") is not None:
        try:
            return max(int(veri.get("yas_gun") or 0), 0)
        except (TypeError, ValueError):
            return 0
    yil = int(veri.get("yas_yil") or 0)
    ay = int(veri.get("yas_ay") or 0)
    return max((yil * 365) + (ay * 30), 0)


def normalize_tohumlama(veri: Dict[str, Any], *, yeni: bool = False) -> Dict[str, Any]:
    sonuc = dict(veri or {})
    if yeni:
        sonuc["id"] = sonuc.get("id") or yeni_id(12)
    sonuc["tarih"] = metin(sonuc.get("tarih"))
    tohumlama_tarihi = parse_tarih(sonuc.get("tarih"), "Tohumlama tarihi", zorunlu=True)
    if tohumlama_tarihi and tohumlama_tarihi.date() > datetime.now().date():
        raise HTTPException(status_code=400, detail="Tohumlama tarihi gelecekte olamaz.")
    sonuc["sekil"] = metin(sonuc.get("sekil")) or None
    sonuc["suni_isim"] = metin(sonuc.get("suni_isim")) or ""
    if sonuc.get("kontrol_tarihi"):
        parse_tarih(sonuc.get("kontrol_tarihi"), "Kontrol tarihi")
    sonuc["kontrol_tarihi"] = bos_yoksa_none(sonuc.get("kontrol_tarihi"))
    sonuc["gebelik_suresi"] = int(sonuc.get("gebelik_suresi") or 283)
    return sonuc


def normalize_asi(veri: Dict[str, Any], *, yeni: bool = False) -> Dict[str, Any]:
    sonuc = dict(veri or {})
    if yeni:
        sonuc["id"] = sonuc.get("id") or yeni_id(12)
    sonuc["ad"] = metin(sonuc.get("ad"))
    if not sonuc["ad"]:
        raise HTTPException(status_code=400, detail="Aşı/prosedür adı zorunludur.")
    sonuc["tarih"] = metin(sonuc.get("tarih"))
    parse_tarih(sonuc.get("tarih"), "Aşı/prosedür tarihi", zorunlu=True)
    asi_tarihi = parse_tarih_sessiz(sonuc.get("tarih"))
    if asi_tarihi and asi_tarihi.date() > datetime.now().date():
        raise HTTPException(status_code=400, detail="Aşı/prosedür uygulama tarihi gelecekte olamaz.")
    if sonuc.get("sonraki_tarih"):
        parse_tarih(sonuc.get("sonraki_tarih"), "Sonraki tarih")
    sonuc["sonraki_tarih"] = bos_yoksa_none(sonuc.get("sonraki_tarih"))
    sonuc["not"] = sonuc.pop("not_", sonuc.get("not", "")) or ""
    return sonuc


def normalize_dogum(veri: Dict[str, Any], *, yeni: bool = False) -> Dict[str, Any]:
    sonuc = dict(veri or {})
    if yeni:
        sonuc["id"] = sonuc.get("id") or yeni_id(12)
    sonuc["tarih"] = metin(sonuc.get("tarih"))
    parse_tarih(sonuc.get("tarih"), "Doğum tarihi", zorunlu=True)
    dogum_tarihi = parse_tarih_sessiz(sonuc.get("tarih"))
    if dogum_tarihi and dogum_tarihi.date() > datetime.now().date():
        raise HTTPException(status_code=400, detail="Doğum tarihi gelecekte olamaz.")
    if sonuc.get("laktasyon_bitis_tarihi"):
        parse_tarih(sonuc.get("laktasyon_bitis_tarihi"), "Laktasyon bitiş tarihi")
    yavrular = []
    for yavru in sonuc.get("yavrular") or []:
        resmi = metin(yavru.get("resmi_kupe_no"), upper=True)
        ciftlik = metin(yavru.get("ciftlik_kupe_no"), upper=True)
        eski_kupe = metin(yavru.get("kupe"), upper=True)
        if not resmi and not ciftlik and eski_kupe:
            resmi = eski_kupe
        yavrular.append(
            {
                **dict(yavru),
                "kupe": ciftlik or resmi or eski_kupe,
                "resmi_kupe_no": resmi,
                "ciftlik_kupe_no": ciftlik,
                "cins": metin(yavru.get("cins")) or "Bilinmiyor",
            }
        )
    sonuc["yavrular"] = yavrular
    sonuc["laktasyon_bitis_tarihi"] = bos_yoksa_none(sonuc.get("laktasyon_bitis_tarihi"))
    sonuc["not"] = sonuc.pop("not_", sonuc.get("not", "")) or ""
    return sonuc


def normalize_hayvan(veri: Dict[str, Any], *, hayvan_id: Optional[str] = None) -> Dict[str, Any]:
    sonuc = dict(veri or {})
    sonuc["id"] = metin(sonuc.get("id") or hayvan_id) or yeni_id()
    sonuc["ciftlik_id"] = bos_yoksa_none(sonuc.get("ciftlik_id"))
    sonuc["ciftlik_ad"] = bos_yoksa_none(sonuc.get("ciftlik_ad"))

    eski_kupe = metin(sonuc.get("kupe_no"), upper=True)
    resmi = metin(sonuc.get("resmi_kupe_no"), upper=True)
    ciftlik = metin(sonuc.get("ciftlik_kupe_no"), upper=True)
    if not resmi and not ciftlik and eski_kupe and eski_kupe not in {"BILINMIYOR", "BİLİNMİYOR"}:
        ciftlik = eski_kupe

    sonuc["resmi_kupe_no"] = resmi
    sonuc["ciftlik_kupe_no"] = ciftlik
    sonuc["kupe_no"] = ciftlik or resmi or eski_kupe or sonuc["id"]
    sonuc["dogum_tarihi"] = metin(sonuc.get("dogum_tarihi"))
    if sonuc["dogum_tarihi"]:
        parse_tarih(sonuc["dogum_tarihi"], "Doğum tarihi")

    sonuc["cins"] = metin(sonuc.get("cins")) or "Bilinmiyor"
    sonuc["ad"] = bos_yoksa_none(sonuc.get("ad"))
    sonuc["anne_kupe"] = metin(sonuc.get("anne_kupe"), upper=True)
    sonuc["kayit_tarihi"] = metin(sonuc.get("kayit_tarihi")) or simdi()
    sonuc["yas_gun"] = yas_gun_hesapla(sonuc)
    sonuc["yas_yil"] = sonuc["yas_gun"] // 365
    sonuc["yas_ay"] = (sonuc["yas_gun"] % 365) // 30
    sonuc["durum"] = metin(sonuc.get("durum") or sonuc.get("durum_notu")) or "Bilinmiyor"
    sonuc["durum_notu"] = sonuc["durum"]
    sonuc["ek_notlar"] = bos_yoksa_none(sonuc.get("ek_notlar"))
    sonuc["gebe_mi"] = bool(sonuc.get("gebe_mi", False))
    sonuc["gebelik_tarihi"] = bos_yoksa_none(sonuc.get("gebelik_tarihi"))
    if sonuc["gebelik_tarihi"]:
        parse_tarih(sonuc["gebelik_tarihi"], "Gebelik tarihi")
    sonuc["aktif_tohumlama_id"] = bos_yoksa_none(sonuc.get("aktif_tohumlama_id"))
    sonuc["olu"] = bool(sonuc.get("olu", False))
    sonuc["olum_tarihi"] = bos_yoksa_none(sonuc.get("olum_tarihi"))
    if sonuc["olum_tarihi"]:
        parse_tarih(sonuc["olum_tarihi"], "Ölüm tarihi")
    sonuc["kesildi"] = bool(sonuc.get("kesildi", False))
    sonuc["kesim_tarihi"] = bos_yoksa_none(sonuc.get("kesim_tarihi"))
    kesim_bilgisi = sonuc.get("kesim_bilgisi") or {}
    if not kesim_bilgisi and sonuc["kesim_tarihi"]:
        kesim_bilgisi = {"tarih": sonuc["kesim_tarihi"]}
    if kesim_bilgisi.get("tarih"):
        parse_tarih(kesim_bilgisi.get("tarih"), "Kesim tarihi")
    sonuc["kesim_bilgisi"] = kesim_bilgisi or None
    sonuc["arsivli"] = bool(sonuc.get("arsivli", False))
    sonuc["arsiv_tarihi"] = bos_yoksa_none(sonuc.get("arsiv_tarihi"))
    if sonuc["arsiv_tarihi"]:
        parse_tarih(sonuc["arsiv_tarihi"], "Arşiv tarihi")
    sonuc["foto_data"] = bos_yoksa_none(sonuc.get("foto_data"))
    foto_datas = sonuc.get("foto_datas") or []
    if not isinstance(foto_datas, list):
        foto_datas = []
    foto_datas = [foto for foto in foto_datas if foto]
    if sonuc["foto_data"] and sonuc["foto_data"] not in foto_datas:
        foto_datas.insert(0, sonuc["foto_data"])
    sonuc["foto_datas"] = foto_datas[:3]
    sonuc["foto_data"] = sonuc["foto_datas"][0] if sonuc["foto_datas"] else None
    sonuc["foto_url"] = bos_yoksa_none(sonuc.get("foto_url"))
    for alan, etiket in [
        ("dogum_tarihi", "Doğum tarihi"),
        ("gebelik_tarihi", "Gebelik tarihi"),
        ("olum_tarihi", "Ölüm tarihi"),
        ("arsiv_tarihi", "Arşiv tarihi"),
    ]:
        tarih = parse_tarih_sessiz(sonuc.get(alan))
        if tarih and tarih.date() > datetime.now().date():
            raise HTTPException(status_code=400, detail=f"{etiket} gelecekte olamaz.")
    kesim_tarihi = parse_tarih_sessiz((sonuc.get("kesim_bilgisi") or {}).get("tarih"))
    if kesim_tarihi and kesim_tarihi.date() > datetime.now().date():
        raise HTTPException(status_code=400, detail="Kesim tarihi gelecekte olamaz.")
    sonuc["son_guncelleme"] = metin(sonuc.get("son_guncelleme")) or simdi()
    tohumlamalar = []
    for index, tohumlama in enumerate(sonuc.get("tohumlamalar") or []):
        kayit = normalize_tohumlama(tohumlama)
        kayit["id"] = kayit.get("id") or stabil_alt_kayit_id(sonuc["id"], "tohumlama", index, kayit)
        tohumlamalar.append(kayit)
    sonuc["tohumlamalar"] = tohumlamalar

    dogumlar = []
    for index, dogum in enumerate(sonuc.get("dogumlar") or []):
        kayit = normalize_dogum(dogum)
        kayit["id"] = kayit.get("id") or stabil_alt_kayit_id(sonuc["id"], "dogum", index, kayit)
        dogumlar.append(kayit)
    sonuc["dogumlar"] = dogumlar

    asi_prosedurler = []
    for index, asi in enumerate(sonuc.get("asi_prosedurler") or []):
        kayit = normalize_asi(asi)
        kayit["id"] = kayit.get("id") or stabil_alt_kayit_id(sonuc["id"], "asi", index, kayit)
        asi_prosedurler.append(kayit)
    sonuc["asi_prosedurler"] = asi_prosedurler
    return sonuc


def db_hayvandan_payload(h: models.Hayvan) -> Dict[str, Any]:
    if h.veri_json:
        try:
            veri = json.loads(h.veri_json)
            if isinstance(veri, dict):
                veri["ciftlik_id"] = h.ciftlik_id or veri.get("ciftlik_id")
                if h.ciftlik:
                    veri["ciftlik_ad"] = h.ciftlik.ad
                return normalize_hayvan(veri, hayvan_id=h.id)
        except json.JSONDecodeError:
            pass

    tohumlamalar = [
        {
            "id": t.id,
            "hayvan_id": h.id,
            "tarih": t.tarih,
            "sekil": t.sekil,
            "suni_isim": t.suni_isim,
            "gebe_mi": t.gebe_mi,
            "kontrol_tarihi": t.kontrol_tarihi,
            "gebelik_suresi": 283,
        }
        for t in h.tohumlamalar
    ]
    asi_prosedurler = [
        {
            "id": a.id,
            "hayvan_id": h.id,
            "ad": a.ad,
            "tarih": a.tarih,
            "sonraki_tarih": a.sonraki_tarih,
            "not": a.not_,
        }
        for a in h.asi_prosedurler
    ]
    aktif_tohumlama = next((t for t in reversed(tohumlamalar) if t.get("gebe_mi") is True), None)
    yas_gun = (h.yas_yil or 0) * 365 + (h.yas_ay or 0) * 30
    return normalize_hayvan(
        {
            "id": h.id,
            "ciftlik_id": h.ciftlik_id,
            "ciftlik_ad": h.ciftlik.ad if h.ciftlik else None,
            "kupe_no": h.ciftlik_kupe_no or h.resmi_kupe_no or h.id,
            "resmi_kupe_no": h.resmi_kupe_no or "",
            "ciftlik_kupe_no": h.ciftlik_kupe_no or "",
            "ad": h.ad,
            "dogum_tarihi": h.dogum_tarihi or "",
            "cins": h.cins or "Bilinmiyor",
            "cinsiyet": h.cinsiyet,
            "yas_gun": yas_gun,
            "durum": h.durum_notu or "",
            "durum_notu": h.durum_notu or "",
            "ek_notlar": h.ek_notlar,
            "gebe_mi": aktif_tohumlama is not None,
            "gebelik_tarihi": aktif_tohumlama.get("tarih") if aktif_tohumlama else None,
            "aktif_tohumlama_id": aktif_tohumlama.get("id") if aktif_tohumlama else None,
            "olu": bool(h.olu),
            "olum_tarihi": h.olum_tarihi,
            "kesildi": bool(h.kesildi),
            "kesim_tarihi": h.kesim_tarihi,
            "kesim_bilgisi": {"tarih": h.kesim_tarihi} if h.kesim_tarihi else None,
            "arsivli": bool(h.arsivli),
            "arsiv_tarihi": h.arsiv_tarihi,
            "son_guncelleme": h.son_guncelleme or "",
            "tohumlamalar": tohumlamalar,
            "dogumlar": [],
            "asi_prosedurler": asi_prosedurler,
        },
        hayvan_id=h.id,
    )


def db_hayvana_yaz(db: Session, db_hayvan: models.Hayvan, veri: Dict[str, Any]) -> models.Hayvan:
    veri = normalize_hayvan(veri, hayvan_id=db_hayvan.id)
    yas_gun = int(veri.get("yas_gun") or 0)
    kesim_bilgisi = veri.get("kesim_bilgisi") or {}

    db_hayvan.id = veri["id"]
    db_hayvan.ciftlik_id = veri.get("ciftlik_id")
    db_hayvan.resmi_kupe_no = bos_yoksa_none(veri.get("resmi_kupe_no"))
    db_hayvan.ciftlik_kupe_no = bos_yoksa_none(veri.get("ciftlik_kupe_no"))
    db_hayvan.ad = bos_yoksa_none(veri.get("ad"))
    db_hayvan.yas_yil = yas_gun // 365
    db_hayvan.yas_ay = (yas_gun % 365) // 30
    db_hayvan.cins = veri.get("cins") or "Bilinmiyor"
    db_hayvan.cinsiyet = veri.get("cinsiyet") or ("Erkek" if db_hayvan.cins in ERKEK_CINSLER else "Dişi")
    db_hayvan.durum_notu = veri.get("durum") or ""
    db_hayvan.dogum_tarihi = bos_yoksa_none(veri.get("dogum_tarihi"))
    db_hayvan.ek_notlar = bos_yoksa_none(veri.get("ek_notlar"))
    db_hayvan.olu = bool(veri.get("olu", False))
    db_hayvan.kesildi = bool(veri.get("kesildi", False))
    db_hayvan.arsivli = bool(veri.get("arsivli", False))
    db_hayvan.olum_tarihi = bos_yoksa_none(veri.get("olum_tarihi"))
    db_hayvan.kesim_tarihi = bos_yoksa_none(kesim_bilgisi.get("tarih") or veri.get("kesim_tarihi"))
    db_hayvan.arsiv_tarihi = bos_yoksa_none(veri.get("arsiv_tarihi"))
    db_hayvan.son_guncelleme = bos_yoksa_none(veri.get("son_guncelleme"))
    db_hayvan.veri_json = json.dumps(veri, ensure_ascii=False)

    db.query(models.Tohumlama).filter(models.Tohumlama.hayvan_id == db_hayvan.id).delete()
    for t in veri.get("tohumlamalar") or []:
        db.add(
            models.Tohumlama(
                id=t.get("id") or yeni_id(12),
                hayvan_id=db_hayvan.id,
                tarih=t.get("tarih") or "",
                sekil=t.get("sekil") or "",
                suni_isim=t.get("suni_isim") or "",
                gebe_mi=t.get("gebe_mi"),
                kontrol_tarihi=t.get("kontrol_tarihi"),
            )
        )

    db.query(models.AsiProsedur).filter(models.AsiProsedur.hayvan_id == db_hayvan.id).delete()
    for a in veri.get("asi_prosedurler") or []:
        db.add(
            models.AsiProsedur(
                id=a.get("id") or yeni_id(12),
                hayvan_id=db_hayvan.id,
                ad=a.get("ad") or "",
                tarih=a.get("tarih") or "",
                sonraki_tarih=a.get("sonraki_tarih"),
                not_=a.get("not") or "",
            )
        )
    return db_hayvan


def hayvan_bul(db: Session, ref: str, kullanici: Optional[models.Kullanici] = None) -> models.Hayvan:
    ref_metin = metin(ref)
    sorgu = db.query(models.Hayvan)
    if kullanici and kullanici.rol != "admin":
        sorgu = sorgu.filter(models.Hayvan.ciftlik_id == kullanici.ciftlik_id)
    hayvan = sorgu.filter(models.Hayvan.id == ref_metin).first()
    if hayvan:
        return hayvan
    ref_kupe = ref_metin.upper()
    hayvan = sorgu.filter(
        or_(
            models.Hayvan.resmi_kupe_no == ref_kupe,
            models.Hayvan.ciftlik_kupe_no == ref_kupe,
        )
    ).first()
    if hayvan and kullanici:
        ciftlik_erisim_kontrol(kullanici, hayvan.ciftlik_id)
    if not hayvan:
        raise HTTPException(status_code=404, detail="Hayvan bulunamadı.")
    return hayvan


def ciftlik_bul(db: Session, ciftlik_id: str) -> models.Ciftlik:
    ciftlik = db.query(models.Ciftlik).filter(models.Ciftlik.id == ciftlik_id).first()
    if not ciftlik:
        raise HTTPException(status_code=404, detail="Çiftlik bulunamadı.")
    return ciftlik


def hayvan_sorgusu_scope(db: Session, kullanici: models.Kullanici, ciftlik_id: Optional[str] = None):
    sorgu = db.query(models.Hayvan)
    hedef_ciftlik_id = kullanici_ciftlik_id(kullanici, ciftlik_id)
    if hedef_ciftlik_id:
        sorgu = sorgu.filter(models.Hayvan.ciftlik_id == hedef_ciftlik_id)
    return sorgu


def kupe_cakismasi_kontrol(
    db: Session,
    veri: Dict[str, Any],
    *,
    haric_id: Optional[str] = None,
    ciftlik_id: Optional[str] = None,
) -> None:
    kupeler = [k for k in {veri.get("resmi_kupe_no"), veri.get("ciftlik_kupe_no")} if k]
    if not kupeler:
        raise HTTPException(status_code=400, detail="En az bir küpe numarası girilmelidir.")
    sorgu = db.query(models.Hayvan)
    if ciftlik_id:
        sorgu = sorgu.filter(models.Hayvan.ciftlik_id == ciftlik_id)
    for kupe in kupeler:
        mevcut = sorgu.filter(
            or_(
                models.Hayvan.resmi_kupe_no == kupe,
                models.Hayvan.ciftlik_kupe_no == kupe,
            )
        ).first()
        if mevcut and mevcut.id != haric_id:
            raise HTTPException(status_code=400, detail=f"{kupe} küpe numarası bu çiftlikte zaten kayıtlı.")


def varsayilan_ciftlik_ve_kayitlari_hazirla(db: Session) -> Optional[models.Ciftlik]:
    ciftlik = db.query(models.Ciftlik).filter(models.Ciftlik.id == DEFAULT_CIFTLIK_ID).first()
    ciftliksiz_hayvan_sayisi = db.query(models.Hayvan).filter(models.Hayvan.ciftlik_id.is_(None)).count()
    if ciftliksiz_hayvan_sayisi == 0:
        return ciftlik
    if not ciftlik:
        ciftlik = models.Ciftlik(
            id=DEFAULT_CIFTLIK_ID,
            ad=DEFAULT_CIFTLIK_ADI,
            aciklama="Mevcut kayıtların taşındığı varsayılan çiftlik",
            aktif=True,
            olusturma_tarihi=simdi(),
        )
        db.add(ciftlik)
        db.flush()
    db.query(models.Hayvan).filter(models.Hayvan.ciftlik_id.is_(None)).update(
        {models.Hayvan.ciftlik_id: ciftlik.id},
        synchronize_session=False,
    )
    return ciftlik


def auth_baslangic_verisini_hazirla():
    db = next(get_db())
    try:
        varsayilan_ciftlik_ve_kayitlari_hazirla(db)
        if db.query(models.Kullanici).count() == 0:
            admin_sifre = os.getenv("ALP_BOOTSTRAP_ADMIN_PASSWORD")
            if admin_sifre:
                db.add(
                    models.Kullanici(
                        id=yeni_id(),
                        kullanici_adi=os.getenv("ALP_BOOTSTRAP_ADMIN_USERNAME", "admin").strip().lower(),
                        sifre_hash=sifre_hashle(admin_sifre),
                        rol="admin",
                        ciftlik_id=None,
                        aktif=True,
                        olusturma_tarihi=simdi(),
                    )
                )
        db.commit()
    finally:
        db.close()


def hayvan_aktif_mi(veri: Dict[str, Any]) -> bool:
    return not (veri.get("arsivli") or veri.get("olu") or veri.get("kesildi"))


def tohumlama_kurallarini_kontrol(veri: Dict[str, Any], tohumlama: Dict[str, Any]) -> None:
    if not hayvan_aktif_mi(veri):
        raise HTTPException(status_code=400, detail="Aktif olmayan hayvana tohumlama eklenemez.")
    cins = veri.get("cins") or ""
    if cins in ERKEK_CINSLER:
        raise HTTPException(status_code=400, detail="Erkek hayvana tohumlama eklenemez.")
    dogum_tarihi = parse_tarih(veri.get("dogum_tarihi"), "Hayvan doğum tarihi")
    tohumlama_tarihi = parse_tarih(tohumlama.get("tarih"), "Tohumlama tarihi", zorunlu=True)
    if dogum_tarihi and tohumlama_tarihi < dogum_tarihi:
        raise HTTPException(status_code=400, detail="Tohumlama tarihi doğum tarihinden önce olamaz.")
    if cins in DISI_CINSLER and dogum_tarihi and (tohumlama_tarihi - dogum_tarihi).days < 365:
        raise HTTPException(status_code=400, detail="12 aylıktan küçük dişi hayvana tohumlama eklenemez.")
    if veri.get("gebe_mi"):
        raise HTTPException(status_code=400, detail="Gebe hayvana yeni tohumlama eklenemez.")
    son_tohumlama = (veri.get("tohumlamalar") or [None])[-1]
    if son_tohumlama and son_tohumlama.get("gebe_mi") is None:
        raise HTTPException(status_code=400, detail="Önce bekleyen tohumlama sonucunu girin.")


def tohumlama_sonucunu_isle(veri: Dict[str, Any], tohumlama: Dict[str, Any]) -> None:
    if tohumlama.get("gebe_mi") is True:
        veri["gebe_mi"] = True
        veri["gebelik_tarihi"] = tohumlama.get("tarih")
        veri["aktif_tohumlama_id"] = tohumlama.get("id")
        if veri.get("durum") not in {"Sağmal İnek", "Kuru İnek"}:
            veri["durum"] = "Gebe"
            veri["durum_notu"] = "Gebe"
    elif veri.get("aktif_tohumlama_id") == tohumlama.get("id"):
        veri["gebe_mi"] = False
        veri["gebelik_tarihi"] = None
        veri["aktif_tohumlama_id"] = None


def nested_kayit_bul(liste: List[Dict[str, Any]], ref: str, etiket: str) -> Dict[str, Any]:
    ref_metin = metin(ref)
    for kayit in liste:
        if metin(kayit.get("id")) == ref_metin:
            return kayit
    if ref_metin.isdigit():
        index = int(ref_metin) - 1
        if 0 <= index < len(liste):
            return liste[index]
    raise HTTPException(status_code=404, detail=f"{etiket} kaydı bulunamadı.")


def nested_kayit_sil(liste: List[Dict[str, Any]], ref: str, etiket: str) -> Dict[str, Any]:
    kayit = nested_kayit_bul(liste, ref, etiket)
    liste.remove(kayit)
    return kayit


def response_kaydet(
    db: Session,
    db_hayvan: models.Hayvan,
    veri: Dict[str, Any],
    *,
    son_guncelleme: Optional[str] = None,
) -> Dict[str, Any]:
    veri["son_guncelleme"] = son_guncelleme or simdi()
    db_hayvana_yaz(db, db_hayvan, veri)
    db.commit()
    db.refresh(db_hayvan)
    return db_hayvandan_payload(db_hayvan)


def dogum_uyarilari(veri: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    aktif_tohumlama_id = veri.get("aktif_tohumlama_id")
    if not aktif_tohumlama_id or not veri.get("gebe_mi"):
        return []
    gebelik_tarihi = parse_tarih_sessiz(veri.get("gebelik_tarihi"))
    if not gebelik_tarihi:
        return []
    kalan = (gebelik_tarihi + timedelta(days=283) - datetime.now()).days
    if kalan > 60:
        return []
    kupe = veri.get("ciftlik_kupe_no") or veri.get("resmi_kupe_no") or veri.get("id")
    durum = "kritik" if kalan <= 7 else "uyarı"
    tip = "Doğum vakti" if kalan <= 0 else "Doğum yaklaşıyor"
    if veri.get("durum") == "Sağmal İnek" and kalan <= 60:
        yield {
            "hayvan_id": veri["id"],
            "kupe_no": kupe,
            "tip": "Kuruya alınmalı",
            "mesaj": f"Doğuma {kalan} gün kaldı. Kuruya ayrılmalı.",
            "kalan_gun": kalan,
            "durum": "kritik",
        }
    yield {
        "hayvan_id": veri["id"],
        "kupe_no": kupe,
        "tip": tip,
        "mesaj": "Doğum vakti." if kalan <= 0 else f"Doğuma {kalan} gün kaldı.",
        "kalan_gun": kalan,
        "durum": durum,
    }


def uyarilari_hesapla(hayvanlar: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    uyarilar: List[Dict[str, Any]] = []
    for veri in hayvanlar:
        if not hayvan_aktif_mi(veri):
            continue
        kupe = veri.get("ciftlik_kupe_no") or veri.get("resmi_kupe_no") or veri.get("id")
        tohumlamalar = veri.get("tohumlamalar") or []
        if tohumlamalar:
            son = tohumlamalar[-1]
            if son.get("gebe_mi") is None:
                t_tarihi = parse_tarih_sessiz(son.get("tarih"))
                if t_tarihi:
                    kontrol = t_tarihi + timedelta(days=21)
                    kalan = (kontrol - datetime.now()).days
                    if kalan <= 7:
                        uyarilar.append(
                            {
                                "hayvan_id": veri["id"],
                                "kupe_no": kupe,
                                "tip": "Gebelik kontrolü",
                                "mesaj": f"Kontrol tarihi: {kontrol.strftime(TARIH_FORMATI)}",
                                "kalan_gun": kalan,
                                "durum": "kritik" if kalan <= 0 else "önemli",
                            }
                        )
        uyarilar.extend(dogum_uyarilari(veri))
        for prosedur in veri.get("asi_prosedurler") or []:
            sonraki = parse_tarih_sessiz(prosedur.get("sonraki_tarih"))
            if not sonraki:
                continue
            kalan = (sonraki - datetime.now()).days
            if kalan <= 7:
                uyarilar.append(
                    {
                        "hayvan_id": veri["id"],
                        "kupe_no": kupe,
                        "tip": "Aşı/prosedür gecikti" if kalan <= 0 else "Aşı/prosedür yaklaşıyor",
                        "mesaj": f"{prosedur.get('ad', 'Prosedür')} - tarih: {sonraki.strftime(TARIH_FORMATI)}",
                        "kalan_gun": kalan,
                        "durum": "kritik" if kalan <= 0 else "uyarı",
                    }
                )
    return sorted(uyarilar, key=lambda u: u["kalan_gun"])


auth_baslangic_verisini_hazirla()


@app.get("/")
def read_root():
    return {"status": "ok", "message": "ALP Ziraat Hayvan Takip API çalışıyor."}


@app.get("/api/health")
def health():
    return {"status": "ok", "database": "connected"}


@app.post("/api/auth/login", response_model=schemas.LoginResponse)
def login(giris: schemas.LoginRequest, db: Session = Depends(get_db)):
    kullanici_adi = giris.kullanici_adi.strip().lower()
    kullanici = db.query(models.Kullanici).filter(models.Kullanici.kullanici_adi == kullanici_adi).first()
    if not kullanici or not kullanici.aktif or not sifre_dogrula(giris.sifre, kullanici.sifre_hash):
        raise HTTPException(status_code=401, detail="Kullanıcı adı veya şifre hatalı.")
    kullanici.son_giris = simdi()
    audit_kaydi(
        db,
        kullanici,
        "giris",
        f"Kullanici giris yapti: {kullanici.kullanici_adi}",
        ciftlik_id=kullanici.ciftlik_id,
        hedef_tipi="kullanici",
        hedef_id=kullanici.id,
    )
    db.commit()
    db.refresh(kullanici)
    return {"access_token": token_uret(kullanici), "kullanici": kullanici_payload(kullanici)}


@app.get("/api/auth/me", response_model=schemas.KullaniciResponse)
def me(kullanici: models.Kullanici = Depends(get_current_user)):
    return kullanici_payload(kullanici)


@app.post("/api/auth/device-token", response_model=schemas.DeviceTokenResponse)
def create_device_token(kullanici: models.Kullanici = Depends(get_current_user)):
    return {"device_token": device_token_uret(kullanici)}


@app.post("/api/auth/device-login", response_model=schemas.LoginResponse)
def device_login(istek: schemas.DeviceLoginRequest, db: Session = Depends(get_db)):
    payload = token_coz(istek.device_token)
    if payload.get("typ") != "device":
        raise HTTPException(status_code=401, detail="Cihaz oturumu geçersiz.")
    kullanici = db.query(models.Kullanici).filter(models.Kullanici.id == payload.get("sub")).first()
    if not kullanici or not kullanici.aktif:
        raise HTTPException(status_code=401, detail="Kullanıcı aktif değil veya bulunamadı.")
    kullanici.son_giris = simdi()
    db.commit()
    db.refresh(kullanici)
    return {"access_token": token_uret(kullanici), "kullanici": kullanici_payload(kullanici)}


@app.post("/api/auth/change-password", response_model=schemas.IslemSonucResponse)
def change_password(
    istek: schemas.SifreDegistirRequest,
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    if not sifre_dogrula(istek.eski_sifre, kullanici.sifre_hash):
        raise HTTPException(status_code=400, detail="Eski sifre hatali.")
    sifre_gucu_kontrol(istek.yeni_sifre)
    kullanici.sifre_hash = sifre_hashle(istek.yeni_sifre)
    audit_kaydi(
        db,
        kullanici,
        "sifre_degistir",
        f"Kullanici sifresini degistirdi: {kullanici.kullanici_adi}",
        ciftlik_id=kullanici.ciftlik_id,
        hedef_tipi="kullanici",
        hedef_id=kullanici.id,
    )
    db.commit()
    return {"status": "ok", "message": "Sifre degistirildi.", "id": kullanici.id}


@app.get("/api/ciftlikler", response_model=List[schemas.CiftlikResponse])
def get_ciftlikler(
    aktif_dahil: bool = True,
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    if kullanici.rol != "admin":
        return [ciftlik_bul(db, kullanici.ciftlik_id)] if kullanici.ciftlik_id else []
    sorgu = db.query(models.Ciftlik)
    if not aktif_dahil:
        sorgu = sorgu.filter(models.Ciftlik.aktif.is_(True))
    return sorgu.order_by(models.Ciftlik.ad).all()


@app.post("/api/ciftlikler", response_model=schemas.CiftlikResponse, status_code=status.HTTP_201_CREATED)
def create_ciftlik(
    ciftlik: schemas.CiftlikCreate,
    db: Session = Depends(get_db),
    admin: models.Kullanici = Depends(require_admin),
):
    veri = model_verisi(ciftlik)
    ciftlik_id = metin(veri.get("id")) or yeni_id()
    if db.query(models.Ciftlik).filter(models.Ciftlik.id == ciftlik_id).first():
        raise HTTPException(status_code=400, detail="Bu çiftlik id zaten kullanılıyor.")
    db_ciftlik = models.Ciftlik(
        id=ciftlik_id,
        ad=veri.get("ad"),
        aciklama=veri.get("aciklama"),
        aktif=bool(veri.get("aktif", True)),
        olusturma_tarihi=simdi(),
    )
    db.add(db_ciftlik)
    audit_kaydi(
        db,
        admin,
        "ciftlik_olustur",
        f"Ciftlik olusturuldu: {db_ciftlik.ad}",
        ciftlik_id=db_ciftlik.id,
        hedef_tipi="ciftlik",
        hedef_id=db_ciftlik.id,
    )
    db.commit()
    db.refresh(db_ciftlik)
    return db_ciftlik


@app.patch("/api/ciftlikler/{ciftlik_id}", response_model=schemas.CiftlikResponse)
def update_ciftlik(
    ciftlik_id: str,
    ciftlik: schemas.CiftlikUpdate,
    db: Session = Depends(get_db),
    admin: models.Kullanici = Depends(require_admin),
):
    db_ciftlik = ciftlik_bul(db, ciftlik_id)
    veri = model_verisi(ciftlik, exclude_unset=True)
    for alan in ("ad", "aciklama", "aktif"):
        if alan in veri:
            setattr(db_ciftlik, alan, veri[alan])
    audit_kaydi(
        db,
        admin,
        "ciftlik_guncelle",
        f"Ciftlik guncellendi: {db_ciftlik.ad}",
        ciftlik_id=db_ciftlik.id,
        hedef_tipi="ciftlik",
        hedef_id=db_ciftlik.id,
    )
    db.commit()
    db.refresh(db_ciftlik)
    return db_ciftlik


@app.delete("/api/ciftlikler/{ciftlik_id}", response_model=schemas.IslemSonucResponse)
def delete_ciftlik(
    ciftlik_id: str,
    db: Session = Depends(get_db),
    admin: models.Kullanici = Depends(require_admin),
):
    db_ciftlik = ciftlik_bul(db, ciftlik_id)
    silinen_ad = db_ciftlik.ad
    hayvan_idleri = [
        satir[0]
        for satir in db.query(models.Hayvan.id).filter(models.Hayvan.ciftlik_id == ciftlik_id).all()
    ]
    silinen_tohumlama = 0
    silinen_asi = 0
    silinen_uyari = 0
    if hayvan_idleri:
        silinen_tohumlama = db.query(models.Tohumlama).filter(
            models.Tohumlama.hayvan_id.in_(hayvan_idleri)
        ).delete(synchronize_session=False)
        silinen_asi = db.query(models.AsiProsedur).filter(
            models.AsiProsedur.hayvan_id.in_(hayvan_idleri)
        ).delete(synchronize_session=False)
        silinen_uyari = db.query(models.Uyari).filter(
            models.Uyari.hayvan_id.in_(hayvan_idleri)
        ).delete(synchronize_session=False)
    silinen_hayvan = db.query(models.Hayvan).filter(
        models.Hayvan.ciftlik_id == ciftlik_id
    ).delete(synchronize_session=False)
    silinen_kullanici = db.query(models.Kullanici).filter(
        models.Kullanici.ciftlik_id == ciftlik_id
    ).delete(synchronize_session=False)
    db.delete(db_ciftlik)
    audit_kaydi(
        db,
        admin,
        "ciftlik_sil",
        (
            f"Ciftlik silindi: {silinen_ad}. {silinen_hayvan} hayvan, "
            f"{silinen_kullanici} kullanici kaldirildi."
        ),
        ciftlik_id=ciftlik_id,
        hedef_tipi="ciftlik",
        hedef_id=ciftlik_id,
    )
    db.commit()
    return {
        "status": "ok",
        "message": (
            f"Ciftlik silindi. {silinen_hayvan} hayvan, {silinen_kullanici} kullanici, "
            f"{silinen_tohumlama} tohumlama, {silinen_asi} asi/prosedur ve "
            f"{silinen_uyari} uyari kaydi kaldirildi."
        ),
        "id": ciftlik_id,
    }


@app.get("/api/kullanicilar", response_model=List[schemas.KullaniciResponse])
def get_kullanicilar(
    db: Session = Depends(get_db),
    _: models.Kullanici = Depends(require_admin),
):
    return [kullanici_payload(k) for k in db.query(models.Kullanici).order_by(models.Kullanici.kullanici_adi).all()]


@app.post("/api/kullanicilar", response_model=schemas.KullaniciResponse, status_code=status.HTTP_201_CREATED)
def create_kullanici(
    kullanici: schemas.KullaniciCreate,
    db: Session = Depends(get_db),
    admin: models.Kullanici = Depends(require_admin),
):
    veri = model_verisi(kullanici)
    kullanici_adi = veri["kullanici_adi"].strip().lower()
    sifre_gucu_kontrol(veri["sifre"])
    if db.query(models.Kullanici).filter(models.Kullanici.kullanici_adi == kullanici_adi).first():
        raise HTTPException(status_code=400, detail="Bu kullanıcı adı zaten kayıtlı.")
    rol = veri.get("rol") or "ciftlik"
    ciftlik_id = veri.get("ciftlik_id")
    if rol != "admin":
        if not ciftlik_id:
            raise HTTPException(status_code=400, detail="Çiftlik kullanıcısı için çiftlik seçilmelidir.")
        ciftlik_bul(db, ciftlik_id)
    db_kullanici = models.Kullanici(
        id=yeni_id(),
        kullanici_adi=kullanici_adi,
        sifre_hash=sifre_hashle(veri["sifre"]),
        rol=rol,
        ciftlik_id=ciftlik_id if rol != "admin" else None,
        aktif=bool(veri.get("aktif", True)),
        olusturma_tarihi=simdi(),
    )
    db.add(db_kullanici)
    audit_kaydi(
        db,
        admin,
        "kullanici_olustur",
        f"Kullanici olusturuldu: {db_kullanici.kullanici_adi}",
        ciftlik_id=db_kullanici.ciftlik_id,
        hedef_tipi="kullanici",
        hedef_id=db_kullanici.id,
    )
    db.commit()
    db.refresh(db_kullanici)
    return kullanici_payload(db_kullanici)


@app.patch("/api/kullanicilar/{kullanici_id}", response_model=schemas.KullaniciResponse)
def update_kullanici(
    kullanici_id: str,
    kullanici: schemas.KullaniciUpdate,
    db: Session = Depends(get_db),
    admin: models.Kullanici = Depends(require_admin),
):
    db_kullanici = db.query(models.Kullanici).filter(models.Kullanici.id == kullanici_id).first()
    if not db_kullanici:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")
    veri = model_verisi(kullanici, exclude_unset=True)
    if "kullanici_adi" in veri:
        db_kullanici.kullanici_adi = veri["kullanici_adi"].strip().lower()
    if "sifre" in veri and veri["sifre"]:
        sifre_gucu_kontrol(veri["sifre"])
        db_kullanici.sifre_hash = sifre_hashle(veri["sifre"])
    if "rol" in veri:
        db_kullanici.rol = veri["rol"]
    if "ciftlik_id" in veri:
        db_kullanici.ciftlik_id = veri["ciftlik_id"] if db_kullanici.rol != "admin" else None
    if "aktif" in veri:
        db_kullanici.aktif = bool(veri["aktif"])
    audit_kaydi(
        db,
        admin,
        "kullanici_guncelle",
        f"Kullanici guncellendi: {db_kullanici.kullanici_adi}",
        ciftlik_id=db_kullanici.ciftlik_id,
        hedef_tipi="kullanici",
        hedef_id=db_kullanici.id,
    )
    db.commit()
    db.refresh(db_kullanici)
    return kullanici_payload(db_kullanici)


@app.post("/api/kullanicilar/{kullanici_id}/sifre-sifirla", response_model=schemas.IslemSonucResponse)
def reset_kullanici_sifresi(
    kullanici_id: str,
    istek: schemas.SifreSifirlaRequest,
    db: Session = Depends(get_db),
    admin: models.Kullanici = Depends(require_admin),
):
    db_kullanici = db.query(models.Kullanici).filter(models.Kullanici.id == kullanici_id).first()
    if not db_kullanici:
        raise HTTPException(status_code=404, detail="Kullanici bulunamadi.")
    sifre_gucu_kontrol(istek.yeni_sifre)
    db_kullanici.sifre_hash = sifre_hashle(istek.yeni_sifre)
    audit_kaydi(
        db,
        admin,
        "sifre_sifirla",
        f"Kullanici sifresi sifirlandi: {db_kullanici.kullanici_adi}",
        ciftlik_id=db_kullanici.ciftlik_id,
        hedef_tipi="kullanici",
        hedef_id=db_kullanici.id,
    )
    db.commit()
    return {"status": "ok", "message": "Kullanici sifresi sifirlandi.", "id": kullanici_id}


@app.delete("/api/kullanicilar/{kullanici_id}", response_model=schemas.IslemSonucResponse)
def delete_kullanici(
    kullanici_id: str,
    db: Session = Depends(get_db),
    admin: models.Kullanici = Depends(require_admin),
):
    db_kullanici = db.query(models.Kullanici).filter(models.Kullanici.id == kullanici_id).first()
    if not db_kullanici:
        raise HTTPException(status_code=404, detail="Kullanici bulunamadi.")
    if db_kullanici.id == admin.id:
        raise HTTPException(status_code=400, detail="Kendi admin kullanicinizi silemezsiniz.")
    if db_kullanici.rol == "admin":
        kalan_admin = db.query(models.Kullanici).filter(
            models.Kullanici.rol == "admin",
            models.Kullanici.aktif.is_(True),
            models.Kullanici.id != kullanici_id,
        ).count()
        if kalan_admin == 0:
            raise HTTPException(status_code=400, detail="Son aktif admin kullanicisi silinemez.")
    silinen_ad = db_kullanici.kullanici_adi
    silinen_ciftlik_id = db_kullanici.ciftlik_id
    db.delete(db_kullanici)
    audit_kaydi(
        db,
        admin,
        "kullanici_sil",
        f"Kullanici silindi: {silinen_ad}",
        ciftlik_id=silinen_ciftlik_id,
        hedef_tipi="kullanici",
        hedef_id=kullanici_id,
    )
    db.commit()
    return {"status": "ok", "message": f"Kullanici silindi: {silinen_ad}", "id": kullanici_id}


@app.get("/api/hayvanlar", response_model=List[schemas.HayvanResponse])
def get_hayvanlar(
    skip: int = 0,
    limit: int = Query(default=100, le=1000),
    q: Optional[str] = None,
    ciftlik_id: Optional[str] = None,
    arsiv_dahil: bool = True,
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    sorgu = hayvan_sorgusu_scope(db, kullanici, ciftlik_id)
    if not arsiv_dahil:
        sorgu = sorgu.filter(
            models.Hayvan.arsivli.is_(False),
            models.Hayvan.olu.is_(False),
            models.Hayvan.kesildi.is_(False),
        )
    if q:
        arama = f"%{q.strip().upper()}%"
        sorgu = sorgu.filter(
            or_(
                models.Hayvan.resmi_kupe_no.ilike(arama),
                models.Hayvan.ciftlik_kupe_no.ilike(arama),
                models.Hayvan.ad.ilike(f"%{q.strip()}%"),
            )
        )
    hayvanlar = sorgu.offset(skip).limit(limit).all()
    return [db_hayvandan_payload(h) for h in hayvanlar]


@app.get("/api/hayvanlar/{hayvan_ref}", response_model=schemas.HayvanResponse)
def get_hayvan(
    hayvan_ref: str,
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    return db_hayvandan_payload(hayvan_bul(db, hayvan_ref, kullanici))


@app.post("/api/hayvanlar", response_model=schemas.HayvanResponse, status_code=status.HTTP_201_CREATED)
def create_hayvan(
    hayvan: schemas.HayvanCreate,
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    veri = normalize_hayvan(model_verisi(hayvan))
    hedef_ciftlik_id = kullanici_ciftlik_id(kullanici, veri.get("ciftlik_id"))
    veri["ciftlik_id"] = hedef_ciftlik_id or DEFAULT_CIFTLIK_ID
    ciftlik_bul(db, veri["ciftlik_id"])
    if db.query(models.Hayvan).filter(models.Hayvan.id == veri["id"]).first():
        raise HTTPException(status_code=400, detail="Bu id ile kayıt zaten var.")
    silme_zamani = son_silme_zamani(db, veri["id"])
    gelen_zaman = parse_zaman_sessiz(veri.get("son_guncelleme"))
    if gelen_zaman and silme_zamani and gelen_zaman < silme_zamani:
        raise HTTPException(
            status_code=409,
            detail="Bu hayvan merkezde daha yeni silinmis; eski offline kayit geri yuklenmedi.",
        )
    kupe_cakismasi_kontrol(db, veri, ciftlik_id=veri["ciftlik_id"])
    db_hayvan = models.Hayvan(id=veri["id"])
    db.add(db_hayvan)
    db_hayvana_yaz(db, db_hayvan, veri)
    audit_kaydi(
        db,
        kullanici,
        "hayvan_olustur",
        f"Hayvan olusturuldu: {veri.get('kupe_no') or db_hayvan.id}",
        ciftlik_id=db_hayvan.ciftlik_id,
        hedef_tipi="hayvan",
        hedef_id=db_hayvan.id,
    )
    db.commit()
    db.refresh(db_hayvan)
    return db_hayvandan_payload(db_hayvan)


@app.put("/api/hayvanlar/{hayvan_ref}", response_model=schemas.HayvanResponse)
@app.patch("/api/hayvanlar/{hayvan_ref}", response_model=schemas.HayvanResponse)
def update_hayvan(
    hayvan_ref: str,
    hayvan: schemas.HayvanUpdate,
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    db_hayvan = hayvan_bul(db, hayvan_ref, kullanici)
    mevcut = db_hayvandan_payload(db_hayvan)
    guncelleme = model_verisi(hayvan, exclude_unset=True)
    guncelleme.pop("id", None)
    gelen_son_guncelleme = guncelleme.get("son_guncelleme")
    if gelen_zaman_daha_eski_mi(gelen_son_guncelleme, db_hayvan.son_guncelleme):
        return mevcut
    if "ciftlik_id" in guncelleme and kullanici.rol != "admin":
        guncelleme.pop("ciftlik_id", None)
    mevcut.update(guncelleme)
    mevcut["id"] = db_hayvan.id
    if kullanici.rol != "admin":
        mevcut["ciftlik_id"] = kullanici.ciftlik_id
    if mevcut.get("ciftlik_id"):
        ciftlik_bul(db, mevcut["ciftlik_id"])
    veri = normalize_hayvan(mevcut, hayvan_id=db_hayvan.id)
    kupe_cakismasi_kontrol(db, veri, haric_id=db_hayvan.id, ciftlik_id=veri.get("ciftlik_id"))
    audit_kaydi(
        db,
        kullanici,
        "hayvan_guncelle",
        f"Hayvan guncellendi: {veri.get('kupe_no') or db_hayvan.id}",
        ciftlik_id=veri.get("ciftlik_id"),
        hedef_tipi="hayvan",
        hedef_id=db_hayvan.id,
    )
    return response_kaydet(db, db_hayvan, veri, son_guncelleme=gelen_son_guncelleme or simdi())


@app.delete("/api/hayvanlar/{hayvan_ref}", response_model=schemas.IslemSonucResponse)
def delete_hayvan(
    hayvan_ref: str,
    kalici: bool = False,
    degisiklik_zamani: Optional[str] = None,
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    db_hayvan = hayvan_bul(db, hayvan_ref, kullanici)
    if kalici:
        if gelen_zaman_daha_eski_mi(degisiklik_zamani, db_hayvan.son_guncelleme):
            return {
                "status": "skipped",
                "message": "Merkezdeki hayvan kaydi daha yeni; eski offline silme uygulanmadi.",
                "id": db_hayvan.id,
            }
        silinen_id = db_hayvan.id
        silinen_kupe = db_hayvan.ciftlik_kupe_no or db_hayvan.resmi_kupe_no or db_hayvan.id
        silinen_ciftlik_id = db_hayvan.ciftlik_id
        db.delete(db_hayvan)
        audit_kaydi(
            db,
            kullanici,
            "hayvan_sil",
            f"Hayvan kalici silindi: {silinen_kupe}",
            ciftlik_id=silinen_ciftlik_id,
            hedef_tipi="hayvan",
            hedef_id=silinen_id,
        )
        db.commit()
        return {"status": "ok", "message": "Hayvan kalıcı olarak silindi.", "id": silinen_id}

    veri = db_hayvandan_payload(db_hayvan)
    veri["arsivli"] = True
    veri["arsiv_tarihi"] = bugun()
    audit_kaydi(
        db,
        kullanici,
        "hayvan_arsivle",
        f"Hayvan arsive alindi: {veri.get('kupe_no') or db_hayvan.id}",
        ciftlik_id=veri.get("ciftlik_id"),
        hedef_tipi="hayvan",
        hedef_id=db_hayvan.id,
    )
    response_kaydet(db, db_hayvan, veri)
    return {"status": "ok", "message": "Hayvan arşive alındı.", "id": db_hayvan.id}


@app.post(
    "/api/hayvanlar/{hayvan_ref}/tohumlamalar",
    response_model=schemas.TohumlamaResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_tohumlama(
    hayvan_ref: str,
    tohumlama: schemas.TohumlamaCreate,
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    db_hayvan = hayvan_bul(db, hayvan_ref, kullanici)
    veri = db_hayvandan_payload(db_hayvan)
    yeni = normalize_tohumlama(model_verisi(tohumlama), yeni=True)
    tohumlama_kurallarini_kontrol(veri, yeni)
    tohumlama_sonucunu_isle(veri, yeni)
    veri.setdefault("tohumlamalar", []).append(yeni)
    response_kaydet(db, db_hayvan, veri)
    return {**yeni, "hayvan_id": db_hayvan.id}


@app.put(
    "/api/hayvanlar/{hayvan_ref}/tohumlamalar/{tohumlama_ref}",
    response_model=schemas.TohumlamaResponse,
)
@app.patch(
    "/api/hayvanlar/{hayvan_ref}/tohumlamalar/{tohumlama_ref}",
    response_model=schemas.TohumlamaResponse,
)
def update_tohumlama(
    hayvan_ref: str,
    tohumlama_ref: str,
    tohumlama: schemas.TohumlamaUpdate,
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    db_hayvan = hayvan_bul(db, hayvan_ref, kullanici)
    veri = db_hayvandan_payload(db_hayvan)
    kayit = nested_kayit_bul(veri.setdefault("tohumlamalar", []), tohumlama_ref, "Tohumlama")
    kayit.update(model_verisi(tohumlama, exclude_unset=True))
    kayit = normalize_tohumlama(kayit)
    for index, mevcut in enumerate(veri["tohumlamalar"]):
        if mevcut.get("id") == kayit.get("id"):
            veri["tohumlamalar"][index] = kayit
            break
    tohumlama_sonucunu_isle(veri, kayit)
    response_kaydet(db, db_hayvan, veri)
    return {**kayit, "hayvan_id": db_hayvan.id}


@app.delete("/api/hayvanlar/{hayvan_ref}/tohumlamalar/{tohumlama_ref}", response_model=schemas.IslemSonucResponse)
def delete_tohumlama(
    hayvan_ref: str,
    tohumlama_ref: str,
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    db_hayvan = hayvan_bul(db, hayvan_ref, kullanici)
    veri = db_hayvandan_payload(db_hayvan)
    silinen = nested_kayit_sil(veri.setdefault("tohumlamalar", []), tohumlama_ref, "Tohumlama")
    if veri.get("aktif_tohumlama_id") == silinen.get("id"):
        veri["gebe_mi"] = False
        veri["gebelik_tarihi"] = None
        veri["aktif_tohumlama_id"] = None
    response_kaydet(db, db_hayvan, veri)
    return {"status": "ok", "message": "Tohumlama kaydı silindi.", "id": silinen.get("id")}


@app.post(
    "/api/hayvanlar/{hayvan_ref}/asi-prosedurler",
    response_model=schemas.AsiProsedurResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_asi(
    hayvan_ref: str,
    asi: schemas.AsiProsedurCreate,
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    db_hayvan = hayvan_bul(db, hayvan_ref, kullanici)
    veri = db_hayvandan_payload(db_hayvan)
    yeni = normalize_asi(model_verisi(asi), yeni=True)
    veri.setdefault("asi_prosedurler", []).append(yeni)
    response_kaydet(db, db_hayvan, veri)
    return {**yeni, "hayvan_id": db_hayvan.id}


@app.put(
    "/api/hayvanlar/{hayvan_ref}/asi-prosedurler/{asi_ref}",
    response_model=schemas.AsiProsedurResponse,
)
@app.patch(
    "/api/hayvanlar/{hayvan_ref}/asi-prosedurler/{asi_ref}",
    response_model=schemas.AsiProsedurResponse,
)
def update_asi(
    hayvan_ref: str,
    asi_ref: str,
    asi: schemas.AsiProsedurUpdate,
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    db_hayvan = hayvan_bul(db, hayvan_ref, kullanici)
    veri = db_hayvandan_payload(db_hayvan)
    kayit = nested_kayit_bul(veri.setdefault("asi_prosedurler", []), asi_ref, "Aşı/prosedür")
    kayit.update(model_verisi(asi, exclude_unset=True))
    kayit = normalize_asi(kayit)
    for index, mevcut in enumerate(veri["asi_prosedurler"]):
        if mevcut.get("id") == kayit.get("id"):
            veri["asi_prosedurler"][index] = kayit
            break
    response_kaydet(db, db_hayvan, veri)
    return {**kayit, "hayvan_id": db_hayvan.id}


@app.delete("/api/hayvanlar/{hayvan_ref}/asi-prosedurler/{asi_ref}", response_model=schemas.IslemSonucResponse)
def delete_asi(
    hayvan_ref: str,
    asi_ref: str,
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    db_hayvan = hayvan_bul(db, hayvan_ref, kullanici)
    veri = db_hayvandan_payload(db_hayvan)
    silinen = nested_kayit_sil(veri.setdefault("asi_prosedurler", []), asi_ref, "Aşı/prosedür")
    response_kaydet(db, db_hayvan, veri)
    return {"status": "ok", "message": "Aşı/prosedür kaydı silindi.", "id": silinen.get("id")}


@app.post(
    "/api/hayvanlar/{hayvan_ref}/dogumlar",
    response_model=schemas.DogumResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_dogum(
    hayvan_ref: str,
    dogum: schemas.DogumCreate,
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    db_hayvan = hayvan_bul(db, hayvan_ref, kullanici)
    anne = db_hayvandan_payload(db_hayvan)
    yeni = normalize_dogum(model_verisi(dogum), yeni=True)
    dogum_tarihi = parse_tarih(yeni.get("tarih"), "Doğum tarihi", zorunlu=True)
    anne_dogum_tarihi = parse_tarih(anne.get("dogum_tarihi"), "Anne doğum tarihi")
    if anne_dogum_tarihi and dogum_tarihi < anne_dogum_tarihi:
        raise HTTPException(status_code=400, detail="Doğum tarihi annenin doğum tarihinden önce olamaz.")
    gebelik_tarihi = parse_tarih(anne.get("gebelik_tarihi"), "Gebelik tarihi")
    if gebelik_tarihi and dogum_tarihi < gebelik_tarihi:
        raise HTTPException(status_code=400, detail="Doğum tarihi gebelik başlangıcından önce olamaz.")

    yavru_kupeleri = []
    for yavru in yeni.get("yavrular") or []:
        alanlar = ["resmi_kupe_no", "ciftlik_kupe_no"]
        if not any(yavru.get(alan) for alan in alanlar):
            alanlar = ["kupe"]
        for alan in alanlar:
            kupe = yavru.get(alan)
            if kupe:
                yavru_kupeleri.append(kupe)
    if len(yavru_kupeleri) != len(set(yavru_kupeleri)):
        raise HTTPException(status_code=400, detail="Yavru küpe numaraları kendi içinde tekrar edemez.")
    for kupe in yavru_kupeleri:
        mevcut_yavru = (
            db.query(models.Hayvan)
            .filter(
                models.Hayvan.ciftlik_id == anne.get("ciftlik_id"),
                or_(
                    models.Hayvan.resmi_kupe_no == kupe,
                    models.Hayvan.ciftlik_kupe_no == kupe,
                ),
            )
            .first()
        )
        if mevcut_yavru:
            raise HTTPException(status_code=400, detail=f"{kupe} yavru küpe numarası bu çiftlikte zaten kayıtlı.")

    kaydedilen_yavrular = []
    for yavru in yeni.get("yavrular") or []:
        yavru_id = yeni_id()
        yavru_resmi = yavru.get("resmi_kupe_no") or ""
        yavru_ciftlik = yavru.get("ciftlik_kupe_no") or ""
        yavru_kupe = yavru_ciftlik or yavru_resmi or yavru.get("kupe") or yavru_id
        yavru_veri = normalize_hayvan(
            {
                "id": yavru_id,
                "ciftlik_id": anne.get("ciftlik_id"),
                "kupe_no": yavru_kupe,
                "resmi_kupe_no": yavru_resmi,
                "ciftlik_kupe_no": yavru_ciftlik,
                "dogum_tarihi": yeni["tarih"],
                "cins": yavru.get("cins") or "Bilinmiyor",
                "anne_kupe": anne.get("kupe_no") or anne.get("id"),
                "kayit_tarihi": simdi(),
                "durum": "Buzağı",
                "gebe_mi": False,
                "olu": False,
                "kesildi": False,
                "arsivli": False,
                "tohumlamalar": [],
                "dogumlar": [],
                "asi_prosedurler": [],
            }
        )
        yavru_db = models.Hayvan(id=yavru_id)
        db.add(yavru_db)
        db_hayvana_yaz(db, yavru_db, yavru_veri)
        kaydedilen_yavrular.append({
            "kupe": yavru_kupe,
            "resmi_kupe_no": yavru_resmi,
            "ciftlik_kupe_no": yavru_ciftlik,
            "cins": yavru_veri["cins"],
        })

    yeni["yavrular"] = kaydedilen_yavrular
    anne.setdefault("dogumlar", []).append(yeni)
    if not anne.get("olu"):
        anne["gebe_mi"] = False
        anne["gebelik_tarihi"] = None
        anne["aktif_tohumlama_id"] = None
        anne["cins"] = "Sağmal İnek"
        anne["durum"] = "Sağmal İnek"
        anne["durum_notu"] = "Sağmal İnek"
    response_kaydet(db, db_hayvan, anne)
    return yeni


@app.put("/api/hayvanlar/{hayvan_ref}/dogumlar/{dogum_ref}", response_model=schemas.DogumResponse)
@app.patch("/api/hayvanlar/{hayvan_ref}/dogumlar/{dogum_ref}", response_model=schemas.DogumResponse)
def update_dogum(
    hayvan_ref: str,
    dogum_ref: str,
    dogum: schemas.DogumUpdate,
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    db_hayvan = hayvan_bul(db, hayvan_ref, kullanici)
    veri = db_hayvandan_payload(db_hayvan)
    kayit = nested_kayit_bul(veri.setdefault("dogumlar", []), dogum_ref, "Doğum")
    kayit.update(model_verisi(dogum, exclude_unset=True))
    kayit = normalize_dogum(kayit)
    for index, mevcut in enumerate(veri["dogumlar"]):
        if mevcut is kayit or mevcut.get("id") == kayit.get("id"):
            veri["dogumlar"][index] = kayit
            break
    response_kaydet(db, db_hayvan, veri)
    return kayit


@app.delete("/api/hayvanlar/{hayvan_ref}/dogumlar/{dogum_ref}", response_model=schemas.IslemSonucResponse)
def delete_dogum(
    hayvan_ref: str,
    dogum_ref: str,
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    db_hayvan = hayvan_bul(db, hayvan_ref, kullanici)
    veri = db_hayvandan_payload(db_hayvan)
    silinen = nested_kayit_sil(veri.setdefault("dogumlar", []), dogum_ref, "Doğum")
    response_kaydet(db, db_hayvan, veri)
    return {"status": "ok", "message": "Doğum/laktasyon kaydı silindi.", "id": silinen.get("id")}


@app.get("/api/uyarilar", response_model=List[schemas.UyariResponse])
def get_uyarilar(
    ciftlik_id: Optional[str] = None,
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    hayvanlar = [db_hayvandan_payload(h) for h in hayvan_sorgusu_scope(db, kullanici, ciftlik_id).all()]
    return uyarilari_hesapla(hayvanlar)


@app.get("/api/raporlar/ozet", response_model=schemas.RaporOzetResponse)
def get_rapor_ozet(
    ciftlik_id: Optional[str] = None,
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    hayvanlar = [db_hayvandan_payload(h) for h in hayvan_sorgusu_scope(db, kullanici, ciftlik_id).all()]
    cins_dagilimi: Dict[str, int] = {}
    for h in hayvanlar:
        cins = h.get("cins") or "Bilinmiyor"
        cins_dagilimi[cins] = cins_dagilimi.get(cins, 0) + 1
    uyarilar = uyarilari_hesapla(hayvanlar)
    return {
        "toplam": len(hayvanlar),
        "aktif": sum(1 for h in hayvanlar if hayvan_aktif_mi(h)),
        "gebe": sum(1 for h in hayvanlar if h.get("gebe_mi")),
        "arsivli": sum(1 for h in hayvanlar if h.get("arsivli")),
        "olu": sum(1 for h in hayvanlar if h.get("olu")),
        "kesildi": sum(1 for h in hayvanlar if h.get("kesildi")),
        "cins_dagilimi": cins_dagilimi,
        "acik_uyari": len(uyarilar),
    }


@app.get("/api/islem-gecmisi", response_model=List[schemas.IslemGecmisiResponse])
def get_islem_gecmisi(
    limit: int = Query(default=100, ge=1, le=500),
    ciftlik_id: Optional[str] = None,
    kullanici_adi: Optional[str] = None,
    islem_tipi: Optional[str] = None,
    hedef_tipi: Optional[str] = None,
    hedef_id: Optional[str] = None,
    q: Optional[str] = None,
    tarih_baslangic: Optional[str] = None,
    tarih_bitis: Optional[str] = None,
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    sorgu = db.query(models.IslemGecmisi)
    if kullanici.rol == "admin":
        if ciftlik_id:
            sorgu = sorgu.filter(models.IslemGecmisi.ciftlik_id == ciftlik_id)
    else:
        sorgu = sorgu.filter(models.IslemGecmisi.ciftlik_id == kullanici.ciftlik_id)
    if kullanici_adi:
        sorgu = sorgu.filter(models.IslemGecmisi.kullanici_adi.ilike(f"%{kullanici_adi.strip()}%"))
    if islem_tipi:
        sorgu = sorgu.filter(models.IslemGecmisi.islem_tipi == islem_tipi.strip())
    if hedef_tipi:
        sorgu = sorgu.filter(models.IslemGecmisi.hedef_tipi == hedef_tipi.strip())
    if hedef_id:
        sorgu = sorgu.filter(models.IslemGecmisi.hedef_id == hedef_id.strip())
    if q:
        arama = f"%{q.strip()}%"
        sorgu = sorgu.filter(
            or_(
                models.IslemGecmisi.detay.ilike(arama),
                models.IslemGecmisi.kullanici_adi.ilike(arama),
                models.IslemGecmisi.islem_tipi.ilike(arama),
                models.IslemGecmisi.hedef_id.ilike(arama),
            )
        )
    baslangic = parse_zaman_sessiz(tarih_baslangic)
    bitis = parse_zaman_sessiz(tarih_bitis)
    if bitis and tarih_bitis and len(tarih_bitis.strip()) <= 10:
        bitis = bitis.replace(hour=23, minute=59, second=59)
    kayitlar = sorgu.order_by(models.IslemGecmisi.zaman.desc()).limit(max(limit * 3, limit)).all()
    if baslangic or bitis:
        filtreli = []
        for kayit in kayitlar:
            zaman = parse_zaman_sessiz(kayit.zaman)
            if baslangic and (not zaman or zaman < baslangic):
                continue
            if bitis and (not zaman or zaman > bitis):
                continue
            filtreli.append(kayit)
        kayitlar = filtreli
    kayitlar = kayitlar[:limit]
    return [islem_payload(kayit) for kayit in kayitlar]


@app.get("/api/yedek", response_model=schemas.YedekResponse)
def get_yedek(
    db: Session = Depends(get_db),
    admin: models.Kullanici = Depends(require_admin),
):
    ciftlikler = [
        {
            "id": c.id,
            "ad": c.ad,
            "aciklama": c.aciklama,
            "aktif": bool(c.aktif),
            "olusturma_tarihi": c.olusturma_tarihi,
        }
        for c in db.query(models.Ciftlik).order_by(models.Ciftlik.ad).all()
    ]
    kullanicilar = [kullanici_payload(k) for k in db.query(models.Kullanici).order_by(models.Kullanici.kullanici_adi).all()]
    hayvanlar = [db_hayvandan_payload(h) for h in db.query(models.Hayvan).order_by(models.Hayvan.id).all()]
    gecmis = db.query(models.IslemGecmisi).order_by(models.IslemGecmisi.zaman.desc()).limit(500).all()
    audit_kaydi(
        db,
        admin,
        "yedek_al",
        "Online yedek indirildi.",
        hedef_tipi="yedek",
    )
    db.commit()
    return {
        "olusturma_zamani": simdi(),
        "ciftlikler": ciftlikler,
        "kullanicilar": kullanicilar,
        "hayvanlar": hayvanlar,
        "islem_gecmisi": [islem_payload(kayit) for kayit in gecmis],
    }


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
