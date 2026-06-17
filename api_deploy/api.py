from datetime import datetime, timedelta
import base64
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import time
from typing import Any, Dict, Iterable, List, Optional
import urllib.error
import urllib.parse
import urllib.request
import uuid
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageOps
from sqlalchemy import or_, text as sql_text
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


app = FastAPI(title="ALP Ziraat Sürü Takip API", version="1.0.0")

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
LEGACY_DEFAULT_CIFTLIK_ID = "varsayilan-ciftlik"
LEGACY_DEFAULT_CIFTLIK_ADI = "Varsayılan Çiftlik"
DEFAULT_AUTH_SECRET = "alp-ziraat-dev-secret-change-me"
AUTH_SECRET = os.getenv("ALP_AUTH_SECRET", DEFAULT_AUTH_SECRET)
TOKEN_TTL_SECONDS = int(os.getenv("ALP_TOKEN_TTL_SECONDS", str(12 * 60 * 60)))
DEVICE_TOKEN_TTL_SECONDS = int(os.getenv("ALP_DEVICE_TOKEN_TTL_SECONDS", str(90 * 24 * 60 * 60)))
APP_TIMEZONE_NAME = os.getenv("ALP_TIMEZONE", "Europe/Istanbul")
try:
    APP_TIMEZONE = ZoneInfo(APP_TIMEZONE_NAME)
except Exception:
    APP_TIMEZONE = None


def simdi_dt() -> datetime:
    if APP_TIMEZONE is None:
        return datetime.now()
    return datetime.now(APP_TIMEZONE).replace(tzinfo=None)


def bugun_tarih():
    return simdi_dt().date()


def supabase_base_url(url: str) -> str:
    url = str(url or "").strip().rstrip("/")
    if not url:
        return ""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme and parsed.netloc:
        path = parsed.path.rstrip("/")
        if "supabase.co" in parsed.netloc or path in {"/rest/v1", "/storage/v1", "/auth/v1", "/functions/v1"}:
            return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    for suffix in ("/rest/v1", "/storage/v1", "/auth/v1", "/functions/v1"):
        if url.endswith(suffix):
            return url[: -len(suffix)].rstrip("/")
    return url


SUPABASE_URL = supabase_base_url(os.getenv("SUPABASE_URL", ""))
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or ""
ALP_PHOTO_BUCKET = os.getenv("ALP_PHOTO_BUCKET", "animal-photos").strip() or "animal-photos"
ALP_DB_QUOTA_MB = float(os.getenv("ALP_DB_QUOTA_MB", "500"))
ALP_STORAGE_QUOTA_MB = float(os.getenv("ALP_STORAGE_QUOTA_MB", "1024"))
ALP_MAX_PHOTOS_PER_ANIMAL = 3
ALP_PHOTO_MAX_SOURCE_MB = float(os.getenv("ALP_PHOTO_MAX_SOURCE_MB", "12"))
ALP_PHOTO_MAX_SOURCE_BYTES = int(ALP_PHOTO_MAX_SOURCE_MB * 1024 * 1024)
ALP_PHOTO_MAX_OUTPUT_BYTES = int(float(os.getenv("ALP_PHOTO_MAX_OUTPUT_MB", "3")) * 1024 * 1024)
ALP_PHOTO_COMPRESS_MAX_EDGE = int(os.getenv("ALP_PHOTO_COMPRESS_MAX_EDGE", "900"))
ALP_PHOTO_COMPRESS_QUALITY = int(os.getenv("ALP_PHOTO_COMPRESS_QUALITY", "82"))
ALP_PHOTO_BUCKET_PUBLIC = os.getenv("ALP_PHOTO_BUCKET_PUBLIC", "false").strip().lower() in {
    "1",
    "true",
    "evet",
    "public",
    "on",
}
ALP_PHOTO_SIGNED_URL_TTL_SECONDS = int(os.getenv("ALP_PHOTO_SIGNED_URL_TTL_SECONDS", str(7 * 24 * 60 * 60)))
ALP_PHOTO_SIGNED_URL_TIMEOUT_SECONDS = float(os.getenv("ALP_PHOTO_SIGNED_URL_TIMEOUT_SECONDS", "5"))
STORAGE_SIGNED_URL_CACHE: Dict[str, tuple[str, float]] = {}


def simdi() -> str:
    return simdi_dt().strftime(ZAMAN_FORMATI)


def bugun() -> str:
    return simdi_dt().strftime(TARIH_FORMATI)


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


TURKCE_METIN_ONARIMLARI = {
    "Sa?mal ?nek": "Sa\u011fmal \u0130nek",
    "Sagmal Inek": "Sa\u011fmal \u0130nek",
    "sagmal": "Sa\u011fmal \u0130nek",
    "D?ve": "D\u00fcve",
    "Duve": "D\u00fcve",
    "duve": "D\u00fcve",
    "Kuru ?nek": "Kuru \u0130nek",
    "Kuru Inek": "Kuru \u0130nek",
    "Di?i Buza??": "Di\u015fi Buza\u011f\u0131",
    "Disi Buzagi": "Di\u015fi Buza\u011f\u0131",
    "Erkek Buza??": "Erkek Buza\u011f\u0131",
    "Erkek Buzagi": "Erkek Buza\u011f\u0131",
    "Sat?ld?": "Sat\u0131ld\u0131",
    "Ar?ivli": "Ar\u015fivli",
}


def turkce_metin_onar(deger: Any) -> str:
    sonuc = metin(deger)
    return TURKCE_METIN_ONARIMLARI.get(sonuc, sonuc)


def kupe_arama_temizle(deger: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", metin(deger, upper=True))


def kupe_arama_rakamlar(deger: Any) -> str:
    return re.sub(r"\D", "", metin(deger))


def resmi_kupe_kisaltma_eslesir(arama: Any, resmi_kupe: Any) -> bool:
    eslesme = re.fullmatch(r"\s*([A-Z]{2})\s+(\d{4,5})\s*", metin(arama, upper=True))
    if not eslesme:
        return False
    resmi_temiz = kupe_arama_temizle(resmi_kupe)
    if not resmi_temiz.startswith(eslesme.group(1)):
        return False
    return eslesme.group(2) in kupe_arama_rakamlar(resmi_temiz)


def hayvan_arama_eslesir(hayvan: models.Hayvan, arama: Any, *, kaynak: str = "normal") -> bool:
    arama_metin = metin(arama, upper=True)
    arama_temiz = kupe_arama_temizle(arama_metin)
    arama_rakam = kupe_arama_rakamlar(arama_metin)
    if not arama_metin:
        return True

    resmi = metin(hayvan.resmi_kupe_no, upper=True)
    ciftlik = metin(hayvan.ciftlik_kupe_no, upper=True)
    ad = metin(hayvan.ad, upper=True)
    kimlikler = [metin(hayvan.id, upper=True), resmi, ciftlik, ad]
    kimlikler = [k for k in kimlikler if k]
    temiz_kimlikler = [kupe_arama_temizle(k) for k in kimlikler]
    ciftlik_rakam = kupe_arama_rakamlar(ciftlik)

    if metin(kaynak, upper=True) == "KAMERA":
        if arama_temiz and kupe_arama_temizle(resmi) and arama_temiz == kupe_arama_temizle(resmi):
            return True
        if len(arama_rakam) >= 6 and ciftlik_rakam and ciftlik_rakam.endswith(arama_rakam[-6:]):
            return True
        return False

    if arama_metin in " ".join(kimlikler):
        return True
    if arama_temiz and any(arama_temiz in temiz for temiz in temiz_kimlikler):
        return True
    if len(arama_rakam) == 6 and ciftlik_rakam.endswith(arama_rakam):
        return True
    if resmi_kupe_kisaltma_eslesir(arama_metin, resmi):
        return True
    return False


def foto_url_mu(deger: Any) -> bool:
    metin_deger = metin(deger)
    return metin_deger.startswith("http://") or metin_deger.startswith("https://")


def storage_aktif_mi() -> bool:
    ayar = os.getenv("ALP_PHOTO_STORAGE_ENABLED", "auto").strip().lower()
    if ayar in {"0", "false", "hayir", "hayır", "kapali", "kapalı", "off"}:
        return False
    aktif = bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and ALP_PHOTO_BUCKET)
    if ayar in {"1", "true", "evet", "aktif", "on"} and not aktif:
        raise HTTPException(
            status_code=500,
            detail="Foto storage aktif istendi ama SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY veya ALP_PHOTO_BUCKET eksik.",
        )
    return aktif


def foto_data_ayristir(foto: str) -> tuple[str, bytes]:
    raw = metin(foto)
    mime = "image/jpeg"
    if raw.startswith("data:") and "," in raw:
        header, raw = raw.split(",", 1)
        if ";" in header:
            mime = header[5:].split(";", 1)[0] or mime
    try:
        return mime, base64.b64decode(raw, validate=False)
    except Exception as hata:
        raise HTTPException(status_code=400, detail="Fotoğraf verisi okunamadı.") from hata


def fotograf_sikistir(mime: str, data: bytes) -> tuple[str, bytes]:
    if not data:
        raise HTTPException(status_code=400, detail="Boş fotoğraf yüklenemez.")
    if len(data) > ALP_PHOTO_MAX_SOURCE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Fotoğraf çok büyük. Lütfen {ALP_PHOTO_MAX_SOURCE_MB:g} MB altında fotoğraf seçin.",
        )
    try:
        with Image.open(io.BytesIO(data)) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode in {"RGBA", "LA"} or (img.mode == "P" and "transparency" in img.info):
                rgba = img.convert("RGBA")
                arka_plan = Image.new("RGB", rgba.size, (255, 255, 255))
                arka_plan.paste(rgba, mask=rgba.split()[-1])
                img = arka_plan
            else:
                img = img.convert("RGB")
            max_edge = max(320, ALP_PHOTO_COMPRESS_MAX_EDGE)
            img.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
            kalite = max(45, min(95, ALP_PHOTO_COMPRESS_QUALITY))
            son_data = b""
            for deneme_kalite in (kalite, 76, 68, 60):
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=deneme_kalite, optimize=True, progressive=True)
                son_data = buffer.getvalue()
                if len(son_data) <= ALP_PHOTO_MAX_OUTPUT_BYTES:
                    break
            if len(son_data) > ALP_PHOTO_MAX_OUTPUT_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail="Fotoğraf sıkıştırıldıktan sonra da çok büyük kaldı.",
                )
            return "image/jpeg", son_data
    except HTTPException:
        raise
    except Exception as hata:
        raise HTTPException(status_code=400, detail="Fotoğraf işlenemedi. Lütfen JPEG/PNG/WebP bir görsel seçin.") from hata


def storage_public_url(path: str, version_hash: str = "") -> str:
    bucket = urllib.parse.quote(ALP_PHOTO_BUCKET, safe="")
    quoted_path = urllib.parse.quote(path, safe="/")
    version = f"?v={version_hash[:12]}" if version_hash else ""
    return f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{quoted_path}{version}"


def storage_signed_url(path: str) -> Optional[str]:
    if not storage_aktif_mi():
        return None
    simdi_ts = time.time()
    cached = STORAGE_SIGNED_URL_CACHE.get(path)
    if cached and cached[1] > simdi_ts + 30:
        return cached[0]
    bucket = urllib.parse.quote(ALP_PHOTO_BUCKET, safe="")
    quoted_path = urllib.parse.quote(path, safe="/")
    sign_url = f"{SUPABASE_URL}/storage/v1/object/sign/{bucket}/{quoted_path}"
    request = urllib.request.Request(
        sign_url,
        data=json.dumps({"expiresIn": ALP_PHOTO_SIGNED_URL_TTL_SECONDS}).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=ALP_PHOTO_SIGNED_URL_TIMEOUT_SECONDS) as response:
        payload = json.loads(response.read().decode("utf-8") or "{}")
    signed = payload.get("signedURL") or payload.get("signedUrl") or payload.get("signed_url")
    if not signed:
        return None
    signed = str(signed)
    if signed.startswith("http://") or signed.startswith("https://"):
        return signed
    if signed.startswith("/storage/v1"):
        signed = f"{SUPABASE_URL}{signed}"
    elif not (signed.startswith("http://") or signed.startswith("https://")):
        signed = f"{SUPABASE_URL}/storage/v1/{signed.lstrip('/')}"
    STORAGE_SIGNED_URL_CACHE[path] = (
        signed,
        simdi_ts + max(60, ALP_PHOTO_SIGNED_URL_TTL_SECONDS - 60),
    )
    return signed


def storage_goruntuleme_url(path: str) -> Optional[str]:
    if not path:
        return None
    if ALP_PHOTO_BUCKET_PUBLIC:
        return storage_public_url(path)
    try:
        return storage_signed_url(path)
    except Exception as hata:
        print(f"Storage signed URL olusturma hatasi: {hata}")
        return None


def storage_path_from_url(url: str) -> Optional[str]:
    if not foto_url_mu(url):
        return None
    parsed = urllib.parse.urlparse(str(url))
    path = parsed.path or ""
    markers = (
        f"/storage/v1/object/public/{ALP_PHOTO_BUCKET}/",
        f"/storage/v1/object/sign/{ALP_PHOTO_BUCKET}/",
        f"/storage/v1/object/authenticated/{ALP_PHOTO_BUCKET}/",
        f"/storage/v1/object/{ALP_PHOTO_BUCKET}/",
    )
    for marker in markers:
        if marker in path:
            return urllib.parse.unquote(path.split(marker, 1)[1]).strip("/")
    return None


def storage_path_from_ref(ref: Any) -> Optional[str]:
    raw = metin(ref)
    if not raw:
        return None
    if foto_url_mu(raw):
        return storage_path_from_url(raw)
    if raw.startswith("storage://"):
        parca = raw[len("storage://") :]
        if "/" in parca:
            bucket, path = parca.split("/", 1)
            if bucket == ALP_PHOTO_BUCKET:
                return path.strip("/")
        return parca.strip("/")
    if raw.startswith("data:"):
        return None
    if "/" in raw and len(raw) < 260:
        return raw.strip("/")
    return None


def foto_base64_boyutu(foto: Any) -> int:
    if not foto or foto_url_mu(foto) or storage_path_from_ref(foto):
        return 0
    try:
        _, data = foto_data_ayristir(str(foto))
        return len(data)
    except HTTPException:
        return 0


def foto_referanslarini_topla(veri: Dict[str, Any]) -> tuple[List[str], List[str], List[str]]:
    paths: List[str] = []
    urls: List[str] = []
    datas: List[str] = []

    def ekle(foto: Any) -> None:
        deger = metin(foto)
        if not deger:
            return
        path = storage_path_from_ref(deger)
        if path:
            if path not in paths:
                paths.append(path)
            return
        if foto_url_mu(deger):
            if deger not in urls:
                urls.append(deger)
            return
        if deger not in datas:
            datas.append(deger)

    for alan in ("foto_paths", "foto_path", "foto_urls", "foto_url", "foto_datas", "foto_data"):
        deger = veri.get(alan)
        if isinstance(deger, list):
            for foto in deger:
                ekle(foto)
        else:
            ekle(deger)

    kalan = ALP_MAX_PHOTOS_PER_ANIMAL
    paths = paths[:kalan]
    kalan -= len(paths)
    urls = urls[:kalan]
    kalan -= len(urls)
    datas = datas[:kalan]
    return paths, urls, datas


def foto_alanlarini_normalize_et(veri: Dict[str, Any]) -> Dict[str, Any]:
    paths, urls, datas = foto_referanslarini_topla(veri)
    veri["foto_paths"] = paths
    veri["foto_path"] = paths[0] if paths else None
    veri["foto_urls"] = urls
    veri["foto_url"] = veri["foto_urls"][0] if veri["foto_urls"] else None
    veri["foto_datas"] = datas
    veri["foto_data"] = veri["foto_datas"][0] if veri["foto_datas"] else None
    return veri


def foto_goruntuleme_url_ekle(veri: Dict[str, Any], *, include_photo_urls: bool = True) -> Dict[str, Any]:
    sonuc = dict(veri or {})
    paths, urls, datas = foto_referanslarini_topla(sonuc)
    goruntuleme_urls: List[str] = []
    if include_photo_urls:
        for path in paths:
            url = storage_goruntuleme_url(path)
            if url and url not in goruntuleme_urls:
                goruntuleme_urls.append(url)
    sonuc["foto_paths"] = paths
    sonuc["foto_path"] = paths[0] if paths else None
    sonuc["foto_urls"] = (goruntuleme_urls + urls)[:ALP_MAX_PHOTOS_PER_ANIMAL]
    sonuc["foto_url"] = sonuc["foto_urls"][0] if sonuc["foto_urls"] else None
    sonuc["foto_datas"] = datas
    sonuc["foto_data"] = datas[0] if datas else None
    return sonuc


def storage_pathlari(refs: Iterable[str]) -> List[str]:
    paths: List[str] = []
    for ref in refs or []:
        path = storage_path_from_ref(ref)
        if path and path not in paths:
            paths.append(path)
    return paths


def storage_fotograflari_sil(refs: Iterable[str]) -> int:
    if not storage_aktif_mi():
        return 0
    paths = storage_pathlari(refs)
    if not paths:
        return 0
    bucket = urllib.parse.quote(ALP_PHOTO_BUCKET, safe="")
    delete_url = f"{SUPABASE_URL}/storage/v1/object/{bucket}"
    silinen = 0
    for start in range(0, len(paths), 1000):
        grup = paths[start:start + 1000]
        request = urllib.request.Request(
            delete_url,
            data=json.dumps({"prefixes": grup}, ensure_ascii=False).encode("utf-8"),
            method="DELETE",
            headers={
                "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                "apikey": SUPABASE_SERVICE_ROLE_KEY,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30):
                silinen += len(grup)
        except Exception as hata:
            print(f"Storage fotograf temizleme hatasi: {hata}")
    return silinen


def storage_dosyalari_listele(prefix: str = "", max_derinlik: int = 8) -> List[str]:
    if not storage_aktif_mi():
        return []
    bucket = urllib.parse.quote(ALP_PHOTO_BUCKET, safe="")
    list_url = f"{SUPABASE_URL}/storage/v1/object/list/{bucket}"
    bulunan: List[str] = []
    gorulen_prefixler: set[str] = set()

    def gez(aktif_prefix: str, derinlik: int) -> None:
        if derinlik > max_derinlik or aktif_prefix in gorulen_prefixler:
            return
        gorulen_prefixler.add(aktif_prefix)
        limit = 1000
        offset = 0
        while True:
            body = {
                "prefix": aktif_prefix,
                "limit": limit,
                "offset": offset,
                "sortBy": {"column": "name", "order": "asc"},
            }
            request = urllib.request.Request(
                list_url,
                data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                method="POST",
                headers={
                    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                    "apikey": SUPABASE_SERVICE_ROLE_KEY,
                    "Content-Type": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    kayitlar = json.loads(response.read().decode("utf-8") or "[]")
            except Exception as hata:
                print(f"Storage listeleme hatasi: {hata}")
                return
            if not isinstance(kayitlar, list) or not kayitlar:
                return
            for kayit in kayitlar:
                if not isinstance(kayit, dict):
                    continue
                ad = metin(kayit.get("name"))
                if not ad:
                    continue
                yol = f"{aktif_prefix.rstrip('/')}/{ad}" if aktif_prefix else ad
                if kayit.get("id") or kayit.get("metadata") or kayit.get("updated_at"):
                    if yol not in bulunan:
                        bulunan.append(yol)
                else:
                    gez(yol, derinlik + 1)
            if len(kayitlar) < limit:
                return
            offset += limit

    gez(prefix.strip("/"), 0)
    return bulunan


def storage_foto_yukle(veri: Dict[str, Any], foto: str, index: int) -> str:
    mime, data = foto_data_ayristir(foto)
    if not data:
        raise HTTPException(status_code=400, detail="Boş fotoğraf yüklenemez.")
    if len(data) > 3 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Fotoğraf çok büyük. Lütfen daha küçük bir fotoğraf seçin.")

    mime, data = fotograf_sikistir(mime, data)

    uzanti = "jpg"
    if "png" in mime:
        uzanti = "png"
    elif "webp" in mime:
        uzanti = "webp"
    version_hash = hashlib.sha256(data).hexdigest()
    ciftlik_id = kupe_arama_temizle(veri.get("ciftlik_id")) or "genel"
    hayvan_id = kupe_arama_temizle(veri.get("id")) or yeni_id(12)
    path = f"{ciftlik_id}/{hayvan_id}/foto-{index}-{version_hash[:12]}.{uzanti}"
    bucket = urllib.parse.quote(ALP_PHOTO_BUCKET, safe="")
    quoted_path = urllib.parse.quote(path, safe="/")
    upload_url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{quoted_path}"
    request = urllib.request.Request(
        upload_url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Content-Type": mime,
            "Cache-Control": "3600",
            "x-upsert": "true",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status >= 400:
                raise HTTPException(status_code=502, detail="Fotoğraf storage yüklemesi başarısız oldu.")
    except urllib.error.HTTPError as hata:
        detay = hata.read().decode("utf-8", errors="ignore")[:300]
        raise HTTPException(status_code=502, detail=f"Fotoğraf storage yüklemesi başarısız oldu: {detay}") from hata
    except urllib.error.URLError as hata:
        raise HTTPException(status_code=502, detail=f"Storage bağlantısı kurulamadı: {hata.reason}") from hata
    return path


def fotograflari_storagea_tasi(veri: Dict[str, Any]) -> Dict[str, Any]:
    veri = dict(veri)
    paths, urls, datas = foto_referanslarini_topla(veri)
    if storage_aktif_mi() and datas:
        kalan_slot = ALP_MAX_PHOTOS_PER_ANIMAL - len(paths) - len(urls)
        for index, foto in enumerate(datas[:kalan_slot], start=len(paths) + len(urls) + 1):
            yuklenen_path = storage_foto_yukle(veri, foto, index)
            if yuklenen_path not in paths:
                paths.append(yuklenen_path)
        datas = []
    veri["foto_paths"] = paths[:ALP_MAX_PHOTOS_PER_ANIMAL]
    veri["foto_path"] = veri["foto_paths"][0] if veri["foto_paths"] else None
    veri["foto_urls"] = urls[: max(0, ALP_MAX_PHOTOS_PER_ANIMAL - len(veri["foto_paths"]))]
    veri["foto_url"] = veri["foto_urls"][0] if veri["foto_urls"] else None
    veri["foto_datas"] = datas[: max(0, ALP_MAX_PHOTOS_PER_ANIMAL - len(veri["foto_paths"]) - len(veri["foto_urls"]))]
    veri["foto_data"] = veri["foto_datas"][0] if veri["foto_datas"] else None
    return veri


def veri_json_fotograf_istatistikleri(db: Session) -> Dict[str, Any]:
    database_base64_adet = 0
    storage_url_adet = 0
    tahmini_base64_bytes = 0
    foto_hayvan_adet = 0
    for satir in db.query(models.Hayvan.veri_json).all():
        try:
            veri = json.loads(satir[0] or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        paths, urls, datas = foto_referanslarini_topla(veri if isinstance(veri, dict) else {})
        if paths or urls or datas:
            foto_hayvan_adet += 1
        storage_url_adet += len(paths)
        database_base64_adet += len(datas)
        tahmini_base64_bytes += sum(foto_base64_boyutu(foto) for foto in datas)
    return {
        "fotografli_hayvan": foto_hayvan_adet,
        "storage_url_adet": storage_url_adet,
        "storage_path_adet": storage_url_adet,
        "database_base64_adet": database_base64_adet,
        "database_base64_mb": round(tahmini_base64_bytes / (1024 * 1024), 2),
    }


def database_boyutu_bytes(db: Session) -> Optional[int]:
    try:
        backend = engine.url.get_backend_name()
        if backend.startswith("sqlite"):
            path = engine.url.database
            if path and os.path.exists(path):
                return os.path.getsize(path)
            return None
        return int(db.execute(sql_text("select pg_database_size(current_database())")).scalar() or 0)
    except Exception:
        return None


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
    if tarih and tarih.date() > bugun_tarih():
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


def sonraki_surum_zamani(
    mevcut_zaman: Optional[str],
    onerilen_zaman: Optional[str] = None,
) -> str:
    """Kayit surumunu, ayni saniyedeki islemlerde bile monoton ilerletir."""
    mevcut = parse_zaman_sessiz(mevcut_zaman)
    onerilen = parse_zaman_sessiz(onerilen_zaman)
    aday = (onerilen or simdi_dt()).replace(microsecond=0)
    if mevcut and aday <= mevcut:
        aday = max(simdi_dt(), mevcut + timedelta(seconds=1))
    return aday.strftime(ZAMAN_FORMATI)


def eski_degisim_cakismasi(mevcut_zaman: Optional[str]) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "stale_update",
            "message": "Merkezdeki kayit daha yeni. Cevrimdisi degisiklik otomatik uygulanmadi.",
            "server_updated_at": mevcut_zaman,
        },
    )


def alt_kayit_cakisma_kontrol(
    db_hayvan: models.Hayvan,
    beklenen_son_guncelleme: Optional[str],
) -> None:
    if not beklenen_son_guncelleme:
        return
    beklenen = parse_zaman_sessiz(beklenen_son_guncelleme)
    mevcut = parse_zaman_sessiz(db_hayvan.son_guncelleme)
    if beklenen and mevcut and beklenen != mevcut:
        raise eski_degisim_cakismasi(db_hayvan.son_guncelleme)


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
        return max((simdi_dt() - dogum_tarihi).days, 0)
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
    if tohumlama_tarihi and tohumlama_tarihi.date() > bugun_tarih():
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
    if asi_tarihi and asi_tarihi.date() > bugun_tarih():
        raise HTTPException(status_code=400, detail="Aşı/prosedür uygulama tarihi gelecekte olamaz.")
    if sonuc.get("sonraki_tarih"):
        sonraki_tarih = parse_tarih(sonuc.get("sonraki_tarih"), "Sonraki tarih")
        if asi_tarihi and sonraki_tarih and sonraki_tarih < asi_tarihi:
            raise HTTPException(
                status_code=400,
                detail="Sonraki tarih uygulama tarihinden önce olamaz.",
            )
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
    if dogum_tarihi and dogum_tarihi.date() > bugun_tarih():
        raise HTTPException(status_code=400, detail="Doğum tarihi gelecekte olamaz.")
    if sonuc.get("laktasyon_bitis_tarihi"):
        parse_tarih(sonuc.get("laktasyon_bitis_tarihi"), "Laktasyon bitiş tarihi")
        if dogum_tarihi:
            bitis_tarihi = parse_tarih_sessiz(sonuc.get("laktasyon_bitis_tarihi"))
            if bitis_tarihi and bitis_tarihi < dogum_tarihi:
                raise HTTPException(
                    status_code=400,
                    detail="Laktasyon bitiş tarihi doğum tarihinden önce olamaz.",
                )
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

    sonuc["cins"] = turkce_metin_onar(sonuc.get("cins")) or "Bilinmiyor"
    sonuc["irk"] = turkce_metin_onar(sonuc.get("irk"))
    sonuc["ad"] = bos_yoksa_none(sonuc.get("ad"))
    sonuc["anne_kupe"] = metin(sonuc.get("anne_kupe"), upper=True)
    sonuc["kayit_tarihi"] = metin(sonuc.get("kayit_tarihi")) or simdi()
    sonuc["yas_gun"] = yas_gun_hesapla(sonuc)
    sonuc["yas_yil"] = sonuc["yas_gun"] // 365
    sonuc["yas_ay"] = (sonuc["yas_gun"] % 365) // 30
    sonuc["durum"] = turkce_metin_onar(sonuc.get("durum") or sonuc.get("durum_notu")) or "Bilinmiyor"
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
    sonuc["satildi"] = bool(sonuc.get("satildi", False))
    sonuc["satis_tarihi"] = bos_yoksa_none(sonuc.get("satis_tarihi"))
    satis_bilgisi = sonuc.get("satis_bilgisi") or {}
    if not satis_bilgisi and sonuc["satis_tarihi"]:
        satis_bilgisi = {"tarih": sonuc["satis_tarihi"]}
    if satis_bilgisi.get("tarih"):
        parse_tarih(satis_bilgisi.get("tarih"), "Satış tarihi")
    sonuc["satis_bilgisi"] = satis_bilgisi or None
    if sonuc["satildi"]:
        sonuc["durum"] = "Satıldı"
        sonuc["durum_notu"] = "Satıldı"
    sonuc["arsivli"] = bool(sonuc.get("arsivli", False))
    sonuc["arsiv_tarihi"] = bos_yoksa_none(sonuc.get("arsiv_tarihi"))
    if sonuc["arsiv_tarihi"]:
        parse_tarih(sonuc["arsiv_tarihi"], "Arşiv tarihi")
    if sonuc["satildi"] or sonuc["arsivli"] or sonuc["olu"] or sonuc["kesildi"]:
        sonuc["gebe_mi"] = False
        sonuc["gebelik_tarihi"] = None
        sonuc["aktif_tohumlama_id"] = None
    foto_alanlarini_normalize_et(sonuc)
    for alan, etiket in [
        ("dogum_tarihi", "Doğum tarihi"),
        ("gebelik_tarihi", "Gebelik tarihi"),
        ("olum_tarihi", "Ölüm tarihi"),
        ("satis_tarihi", "Satış tarihi"),
        ("arsiv_tarihi", "Arşiv tarihi"),
    ]:
        tarih = parse_tarih_sessiz(sonuc.get(alan))
        if tarih and tarih.date() > bugun_tarih():
            raise HTTPException(status_code=400, detail=f"{etiket} gelecekte olamaz.")
    kesim_tarihi = parse_tarih_sessiz((sonuc.get("kesim_bilgisi") or {}).get("tarih"))
    if kesim_tarihi and kesim_tarihi.date() > bugun_tarih():
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


def db_hayvandan_payload(h: models.Hayvan, *, include_photo_urls: bool = True) -> Dict[str, Any]:
    if h.veri_json:
        try:
            veri = json.loads(h.veri_json)
            if isinstance(veri, dict):
                veri["ciftlik_id"] = h.ciftlik_id or veri.get("ciftlik_id")
                if h.ciftlik:
                    veri["ciftlik_ad"] = h.ciftlik.ad
                return foto_goruntuleme_url_ekle(
                    normalize_hayvan(veri, hayvan_id=h.id),
                    include_photo_urls=include_photo_urls,
                )
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
    son_tohumlama = max(
        enumerate(tohumlamalar),
        key=lambda item: _tohumlama_sira_anahtari(item[1], item[0]),
    )[1] if tohumlamalar else None
    aktif_tohumlama = son_tohumlama if son_tohumlama and son_tohumlama.get("gebe_mi") is True else None
    yas_gun = (h.yas_yil or 0) * 365 + (h.yas_ay or 0) * 30
    return foto_goruntuleme_url_ekle(normalize_hayvan(
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
            "satildi": h.durum_notu == "Satıldı",
            "satis_tarihi": None,
            "satis_bilgisi": None,
            "arsivli": bool(h.arsivli),
            "arsiv_tarihi": h.arsiv_tarihi,
            "son_guncelleme": h.son_guncelleme or "",
            "tohumlamalar": tohumlamalar,
            "dogumlar": [],
            "asi_prosedurler": asi_prosedurler,
        },
        hayvan_id=h.id,
    ), include_photo_urls=include_photo_urls)


def db_hayvana_yaz(db: Session, db_hayvan: models.Hayvan, veri: Dict[str, Any]) -> models.Hayvan:
    veri = normalize_hayvan(veri, hayvan_id=db_hayvan.id)
    veri = normalize_hayvan(fotograflari_storagea_tasi(veri), hayvan_id=db_hayvan.id)
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


def kupe_eslesme_anahtari(deger: Any) -> str:
    return re.sub(r"\s+", "", metin(deger, upper=True))


def hayvan_kupe_anahtarlari(veri: Dict[str, Any]) -> set[str]:
    return {
        anahtar
        for anahtar in (
            kupe_eslesme_anahtari(veri.get("resmi_kupe_no")),
            kupe_eslesme_anahtari(veri.get("ciftlik_kupe_no")),
            kupe_eslesme_anahtari(veri.get("kupe_no")),
        )
        if anahtar
    }


def yavru_kupe_anahtarlari(yavru: Dict[str, Any]) -> set[str]:
    return {
        anahtar
        for anahtar in (
            kupe_eslesme_anahtari(yavru.get("hayvan_id")),
            kupe_eslesme_anahtari(yavru.get("id")),
            kupe_eslesme_anahtari(yavru.get("kupe")),
            kupe_eslesme_anahtari(yavru.get("resmi_kupe_no")),
            kupe_eslesme_anahtari(yavru.get("ciftlik_kupe_no")),
        )
        if anahtar
    }


def dogum_kaydi_otomatik_yavru_baglantisi_mi(dogum: Dict[str, Any]) -> bool:
    not_metni = metin(dogum.get("not")).lower()
    return "anne" in not_metni and "otomatik" in not_metni


def silinen_hayvan_dogum_referanslarini_temizle(
    db: Session,
    silinen_id: str,
    silinen_veri: Dict[str, Any],
    ciftlik_id: Optional[str],
) -> int:
    if not ciftlik_id:
        return 0
    silinen_anahtarlar = hayvan_kupe_anahtarlari(silinen_veri) | {kupe_eslesme_anahtari(silinen_id)}
    silinen_anahtarlar = {anahtar for anahtar in silinen_anahtarlar if anahtar}
    if not silinen_anahtarlar:
        return 0

    temizlenen_yavru = 0
    adaylar = db.query(models.Hayvan).filter(
        models.Hayvan.ciftlik_id == ciftlik_id,
        models.Hayvan.id != silinen_id,
    ).all()
    for anne_db in adaylar:
        anne_veri = db_hayvandan_payload(anne_db, include_photo_urls=False)
        dogumlar = anne_veri.get("dogumlar") or []
        if not dogumlar:
            continue

        degisti = False
        yeni_dogumlar = []
        for dogum in dogumlar:
            dogum_kopya = dict(dogum or {})
            yavrular = dogum_kopya.get("yavrular") or []
            if not yavrular:
                yeni_dogumlar.append(dogum_kopya)
                continue

            kalan_yavrular = []
            for yavru in yavrular:
                if silinen_anahtarlar.intersection(yavru_kupe_anahtarlari(yavru)):
                    temizlenen_yavru += 1
                    degisti = True
                    continue
                kalan_yavrular.append(yavru)

            dogum_kopya["yavrular"] = kalan_yavrular
            if not kalan_yavrular and dogum_kaydi_otomatik_yavru_baglantisi_mi(dogum_kopya):
                continue
            yeni_dogumlar.append(dogum_kopya)

        if degisti:
            anne_veri["dogumlar"] = yeni_dogumlar
            anne_veri["son_guncelleme"] = simdi()
            db_hayvana_yaz(db, anne_db, anne_veri)

    return temizlenen_yavru


def annenin_dogum_kaydina_yavru_ekle(
    db: Session,
    cocuk_db: models.Hayvan,
    cocuk_veri: Dict[str, Any],
) -> bool:
    anne_kupe = kupe_eslesme_anahtari(cocuk_veri.get("anne_kupe"))
    ciftlik_id = cocuk_veri.get("ciftlik_id")
    if not anne_kupe or not ciftlik_id:
        return False

    olasi_anneler = db.query(models.Hayvan).filter(models.Hayvan.ciftlik_id == ciftlik_id).all()
    anne_db = None
    for aday in olasi_anneler:
        if aday.id == cocuk_db.id:
            continue
        aday_veri = db_hayvandan_payload(aday, include_photo_urls=False)
        if anne_kupe in hayvan_kupe_anahtarlari(aday_veri):
            anne_db = aday
            break
    if not anne_db:
        return False

    anne_veri = db_hayvandan_payload(anne_db, include_photo_urls=False)
    cocuk_anahtarlari = hayvan_kupe_anahtarlari(cocuk_veri) | {kupe_eslesme_anahtari(cocuk_db.id)}
    for dogum in anne_veri.get("dogumlar") or []:
        for yavru in dogum.get("yavrular") or []:
            yavru_anahtarlari = {
                kupe_eslesme_anahtari(yavru.get("kupe")),
                kupe_eslesme_anahtari(yavru.get("resmi_kupe_no")),
                kupe_eslesme_anahtari(yavru.get("ciftlik_kupe_no")),
            }
            if cocuk_anahtarlari.intersection({anahtar for anahtar in yavru_anahtarlari if anahtar}):
                return False

    dogum_tarihi = cocuk_veri.get("dogum_tarihi") or ""
    if not parse_tarih_sessiz(dogum_tarihi):
        dogum_tarihi = simdi_dt().strftime(TARIH_FORMATI)
    dogum_kaydi = normalize_dogum(
        {
            "tarih": dogum_tarihi,
            "yavrular": [
                {
                    "kupe": cocuk_veri.get("kupe_no") or cocuk_db.id,
                    "resmi_kupe_no": cocuk_veri.get("resmi_kupe_no") or "",
                    "ciftlik_kupe_no": cocuk_veri.get("ciftlik_kupe_no") or "",
                    "cins": cocuk_veri.get("cins") or "Bilinmiyor",
                }
            ],
            "not": "Yeni hayvan kaydindaki anne kupesi eslesmesiyle otomatik olusturuldu.",
        },
        yeni=True,
    )
    anne_veri.setdefault("dogumlar", []).append(dogum_kaydi)
    db_hayvana_yaz(db, anne_db, anne_veri)
    return True


def auth_baslangic_verisini_hazirla():
    db = next(get_db())
    try:
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
    return not (veri.get("arsivli") or veri.get("olu") or veri.get("kesildi") or veri.get("satildi"))


def tohumlama_tarih_kurallarini_kontrol(veri: Dict[str, Any], tohumlama: Dict[str, Any]) -> None:
    cins = veri.get("cins") or ""
    if cins in ERKEK_CINSLER or veri.get("cinsiyet") == "Erkek":
        raise HTTPException(status_code=400, detail="Erkek hayvana tohumlama eklenemez.")
    dogum_tarihi = parse_tarih(veri.get("dogum_tarihi"), "Hayvan doğum tarihi")
    tohumlama_tarihi = parse_tarih(tohumlama.get("tarih"), "Tohumlama tarihi", zorunlu=True)
    if dogum_tarihi and tohumlama_tarihi < dogum_tarihi:
        raise HTTPException(status_code=400, detail="Tohumlama tarihi doğum tarihinden önce olamaz.")
    if cins in DISI_CINSLER and dogum_tarihi and (tohumlama_tarihi - dogum_tarihi).days < 365:
        raise HTTPException(status_code=400, detail="12 aylıktan küçük dişi hayvana tohumlama eklenemez.")


def tohumlama_kurallarini_kontrol(veri: Dict[str, Any], tohumlama: Dict[str, Any]) -> None:
    if not hayvan_aktif_mi(veri):
        raise HTTPException(status_code=400, detail="Aktif olmayan hayvana tohumlama eklenemez.")
    tohumlama_tarih_kurallarini_kontrol(veri, tohumlama)
    if veri.get("gebe_mi"):
        raise HTTPException(status_code=400, detail="Gebe hayvana yeni tohumlama eklenemez.")
    son_tohumlama = en_son_tohumlama(veri)
    if son_tohumlama and son_tohumlama.get("gebe_mi") is None:
        raise HTTPException(status_code=400, detail="Önce bekleyen tohumlama sonucunu girin.")


def _tohumlama_sira_anahtari(tohumlama: Dict[str, Any], index: int) -> tuple:
    tarih = parse_tarih_sessiz(tohumlama.get("tarih")) or datetime.min
    return tarih, index


def en_son_tohumlama(veri: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    kayitlar = veri.get("tohumlamalar") or []
    if not kayitlar:
        return None
    return max(
        enumerate(kayitlar),
        key=lambda item: _tohumlama_sira_anahtari(item[1], item[0]),
    )[1]


def aktif_gebelik_tohumlamasi(veri: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    tohumlama = en_son_tohumlama(veri)
    if (
        tohumlama
        and tohumlama.get("gebe_mi") is True
        and not tohumlama_doguma_bagli_mi(veri, tohumlama)
    ):
        return tohumlama
    return None


def tohumlama_sonucunu_isle(veri: Dict[str, Any]) -> None:
    tohumlama = aktif_gebelik_tohumlamasi(veri)
    if tohumlama:
        veri["gebe_mi"] = True
        veri["gebelik_tarihi"] = tohumlama.get("tarih")
        veri["aktif_tohumlama_id"] = tohumlama.get("id")
        if veri.get("durum") not in {"Sağmal İnek", "Kuru İnek"}:
            veri["durum"] = "Gebe"
            veri["durum_notu"] = "Gebe"
    else:
        veri["gebe_mi"] = False
        veri["gebelik_tarihi"] = None
        veri["aktif_tohumlama_id"] = None


def tohumlama_doguma_bagli_mi(veri: Dict[str, Any], kayit: Dict[str, Any]) -> bool:
    if kayit.get("gebe_mi") is not True:
        return False
    tohumlama_tarihi = parse_tarih_sessiz(kayit.get("tarih"))
    if not tohumlama_tarihi:
        return False
    for dogum in veri.get("dogumlar") or []:
        dogum_tarihi = parse_tarih_sessiz(dogum.get("tarih"))
        if dogum_tarihi and dogum_tarihi.date() >= tohumlama_tarihi.date():
            return True
    return False


def doguma_bagli_tohumlama_silme_hatasi() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Bu pozitif tohumlama doğum/laktasyon geçmişine bağlı olduğu için silinemez.",
    )


def doguma_bagli_tohumlama_duzenleme_kontrolu(
    veri: Dict[str, Any],
    eski_kayit: Dict[str, Any],
    yeni_kayit: Dict[str, Any],
) -> None:
    if not tohumlama_doguma_bagli_mi(veri, eski_kayit):
        return
    tarih_degisti = metin(eski_kayit.get("tarih")) != metin(yeni_kayit.get("tarih"))
    sonuc_degisti = yeni_kayit.get("gebe_mi") is not True
    if tarih_degisti or sonuc_degisti:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu pozitif tohumlama doğum/laktasyon geçmişine bağlı olduğu için sonucu veya tarihi değiştirilemez.",
        )


def eski_tohumlama_pozitif_olamaz(veri: Dict[str, Any], kayit: Dict[str, Any]) -> None:
    if kayit.get("gebe_mi") is not True:
        return
    son = en_son_tohumlama(veri)
    if son and metin(son.get("id")) != metin(kayit.get("id")):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Daha yeni bir tohumlama kaydı varken eski kayıt pozitif yapılamaz.",
        )


def alt_kayit_tarihlerini_kontrol(veri: Dict[str, Any]) -> None:
    hayvan_dogum = parse_tarih(veri.get("dogum_tarihi"), "Hayvan doğum tarihi")
    for tohumlama in veri.get("tohumlamalar") or []:
        tohumlama_tarih_kurallarini_kontrol(veri, tohumlama)
    erkek_hayvan = veri.get("cins") in ERKEK_CINSLER or veri.get("cinsiyet") == "Erkek"
    if erkek_hayvan and (veri.get("dogumlar") or []):
        raise HTTPException(status_code=400, detail="Erkek hayvana doğum kaydı eklenemez.")
    for dogum in veri.get("dogumlar") or []:
        tarih = parse_tarih(dogum.get("tarih"), "Doğum tarihi", zorunlu=True)
        if tarih and hayvan_dogum and tarih < hayvan_dogum:
            raise HTTPException(status_code=400, detail="Doğum tarihi annenin doğum tarihinden önce olamaz.")
        bitis = parse_tarih(dogum.get("laktasyon_bitis_tarihi"), "Laktasyon bitiş tarihi")
        if tarih and bitis and bitis < tarih:
            raise HTTPException(status_code=400, detail="Laktasyon bitiş tarihi doğum tarihinden önce olamaz.")


def dogum_tarihi_degisimlerini_yavrulara_yansit(
    db: Session,
    db_hayvan: models.Hayvan,
    onceki_dogumlar: List[Dict[str, Any]],
    yeni_dogumlar: List[Dict[str, Any]],
) -> None:
    onceki_idler = {
        metin(kayit.get("id")): kayit
        for kayit in onceki_dogumlar
        if metin(kayit.get("id"))
    }
    for index, yeni_dogum in enumerate(yeni_dogumlar):
        onceki = onceki_idler.get(metin(yeni_dogum.get("id")))
        if onceki is None and index < len(onceki_dogumlar):
            onceki = onceki_dogumlar[index]
        if not onceki or onceki.get("tarih") == yeni_dogum.get("tarih"):
            continue

        yeni_tarih = metin(yeni_dogum.get("tarih"))
        if not yeni_tarih:
            continue
        for yavru in yeni_dogum.get("yavrular") or []:
            refs = {
                metin(yavru.get("id")),
                metin(yavru.get("hayvan_id")),
                metin(yavru.get("ciftlik_kupe_no")),
                metin(yavru.get("resmi_kupe_no")),
                metin(yavru.get("kupe")),
            }
            refs.discard("")
            if not refs:
                continue
            yavru_db = (
                db.query(models.Hayvan)
                .filter(
                    models.Hayvan.ciftlik_id == db_hayvan.ciftlik_id,
                    models.Hayvan.id != db_hayvan.id,
                    or_(
                        models.Hayvan.id.in_(refs),
                        models.Hayvan.ciftlik_kupe_no.in_(refs),
                        models.Hayvan.resmi_kupe_no.in_(refs),
                    ),
                )
                .first()
            )
            if not yavru_db:
                continue
            yavru_veri = db_hayvandan_payload(yavru_db, include_photo_urls=False)
            yavru_veri["dogum_tarihi"] = yeni_tarih
            yavru_veri["son_guncelleme"] = sonraki_surum_zamani(
                yavru_db.son_guncelleme,
            )
            db_hayvana_yaz(db, yavru_db, yavru_veri)


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
    include_photo_urls: bool = True,
) -> Dict[str, Any]:
    veri["son_guncelleme"] = sonraki_surum_zamani(
        db_hayvan.son_guncelleme,
        son_guncelleme,
    )
    db_hayvana_yaz(db, db_hayvan, veri)
    db.commit()
    db.refresh(db_hayvan)
    return db_hayvandan_payload(db_hayvan, include_photo_urls=include_photo_urls)


def dogum_uyarilari(veri: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    aktif_tohumlama_id = veri.get("aktif_tohumlama_id")
    if not aktif_tohumlama_id or not veri.get("gebe_mi"):
        return []
    gebelik_tarihi = parse_tarih_sessiz(veri.get("gebelik_tarihi"))
    if not gebelik_tarihi:
        return []
    kalan = (gebelik_tarihi + timedelta(days=283) - simdi_dt()).days
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
        son = en_son_tohumlama(veri)
        if son and son.get("gebe_mi") is None:
                t_tarihi = parse_tarih_sessiz(son.get("tarih"))
                if t_tarihi:
                    kontrol = t_tarihi + timedelta(days=21)
                    kalan = (kontrol - simdi_dt()).days
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
            kalan = (sonraki - simdi_dt()).days
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
    return {"status": "ok", "message": "ALP Ziraat Sürü Takip API çalışıyor."}


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(sql_text("SELECT 1")).scalar_one()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "error",
                "database": "disconnected",
                "message": "Veritabanı bağlantısı doğrulanamadı.",
            },
        ) from exc

    auth_secret_configured = bool(
        AUTH_SECRET
        and AUTH_SECRET != DEFAULT_AUTH_SECRET
        and len(AUTH_SECRET) >= 32
    )
    backend = engine.url.get_backend_name()
    if backend != "sqlite" and not auth_secret_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "error",
                "database": "connected",
                "auth_secret_configured": False,
                "message": "ALP_AUTH_SECRET üretim ortamında tanımlı değil veya çok kısa.",
            },
        )
    return {
        "status": "ok",
        "database": "connected",
        "database_backend": backend,
        "auth_secret_configured": auth_secret_configured,
    }


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
    silinecek_fotograflar: List[str] = []
    for hayvan in db.query(models.Hayvan).filter(models.Hayvan.ciftlik_id == ciftlik_id).all():
        paths, _, _ = foto_referanslarini_topla(db_hayvandan_payload(hayvan, include_photo_urls=False))
        silinecek_fotograflar.extend(paths)
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
    storage_fotograflari_sil(silinecek_fotograflar)
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
    yeni_kullanici_adi = str(
        veri.get("kullanici_adi", db_kullanici.kullanici_adi) or ""
    ).strip().lower()
    if not yeni_kullanici_adi:
        raise HTTPException(status_code=400, detail="Kullanici adi bos olamaz.")
    ayni_ad = (
        db.query(models.Kullanici)
        .filter(
            models.Kullanici.kullanici_adi == yeni_kullanici_adi,
            models.Kullanici.id != db_kullanici.id,
        )
        .first()
    )
    if ayni_ad:
        raise HTTPException(status_code=400, detail="Bu kullanici adi zaten kayitli.")

    yeni_rol = str(veri.get("rol", db_kullanici.rol) or "ciftlik").strip().lower()
    if yeni_rol not in {"admin", "ciftlik"}:
        raise HTTPException(status_code=400, detail="Gecersiz kullanici rolu.")
    yeni_aktif = bool(veri.get("aktif", db_kullanici.aktif))
    yeni_ciftlik_id = veri.get("ciftlik_id", db_kullanici.ciftlik_id)
    if yeni_rol == "admin":
        yeni_ciftlik_id = None
    else:
        if not yeni_ciftlik_id:
            raise HTTPException(status_code=400, detail="Ciftlik kullanicisi icin ciftlik secilmelidir.")
        ciftlik_bul(db, yeni_ciftlik_id)

    adminlik_sona_eriyor = (
        db_kullanici.rol == "admin"
        and db_kullanici.aktif
        and (yeni_rol != "admin" or not yeni_aktif)
    )
    if adminlik_sona_eriyor:
        kalan_admin = (
            db.query(models.Kullanici)
            .filter(
                models.Kullanici.rol == "admin",
                models.Kullanici.aktif.is_(True),
                models.Kullanici.id != db_kullanici.id,
            )
            .count()
        )
        if kalan_admin == 0:
            raise HTTPException(
                status_code=400,
                detail="Son aktif admin pasiflestirilemez veya ciftlik kullanicisina cevrilemez.",
            )

    db_kullanici.kullanici_adi = yeni_kullanici_adi
    if "sifre" in veri and veri["sifre"]:
        sifre_gucu_kontrol(veri["sifre"])
        db_kullanici.sifre_hash = sifre_hashle(veri["sifre"])
    db_kullanici.rol = yeni_rol
    db_kullanici.ciftlik_id = yeni_ciftlik_id
    db_kullanici.aktif = yeni_aktif
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
            or_(models.Hayvan.durum_notu.is_(None), models.Hayvan.durum_notu != "Satıldı"),
        )
    if q:
        eslesenler = [h for h in sorgu.all() if hayvan_arama_eslesir(h, q, kaynak="normal")]
        hayvanlar = eslesenler[skip: skip + limit]
    else:
        hayvanlar = sorgu.offset(skip).limit(limit).all()
    return [db_hayvandan_payload(h, include_photo_urls=False) for h in hayvanlar]


@app.get("/api/hayvanlar/bul", response_model=schemas.HayvanAramaResponse)
def hayvan_ref_ara(
    ref: str = Query(..., min_length=1),
    kaynak: str = Query(default="normal", pattern="^(normal|kamera)$"),
    ciftlik_id: Optional[str] = None,
    arsiv_dahil: bool = True,
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    sorgu = hayvan_sorgusu_scope(db, kullanici, ciftlik_id)
    if not arsiv_dahil:
        sorgu = sorgu.filter(
            models.Hayvan.arsivli.is_(False),
            models.Hayvan.olu.is_(False),
            models.Hayvan.kesildi.is_(False),
            or_(models.Hayvan.durum_notu.is_(None), models.Hayvan.durum_notu != "Satıldı"),
        )
    eslesenler = [h for h in sorgu.all() if hayvan_arama_eslesir(h, ref, kaynak=kaynak)]
    return {
        "ref": ref,
        "kaynak": kaynak,
        "eslesme_sayisi": len(eslesenler),
        "tekil": len(eslesenler) == 1,
        "hayvanlar": [db_hayvandan_payload(h, include_photo_urls=False) for h in eslesenler[:limit]],
    }


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
    if not hedef_ciftlik_id:
        raise HTTPException(status_code=400, detail="Hayvan kaydı için çiftlik seçilmelidir.")
    veri["ciftlik_id"] = hedef_ciftlik_id
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
    alt_kayit_tarihlerini_kontrol(veri)
    kupe_cakismasi_kontrol(db, veri, ciftlik_id=veri["ciftlik_id"])
    db_hayvan = models.Hayvan(id=veri["id"])
    db.add(db_hayvan)
    db_hayvana_yaz(db, db_hayvan, veri)
    anne_baglanti_eklendi = annenin_dogum_kaydina_yavru_ekle(db, db_hayvan, veri)
    audit_kaydi(
        db,
        kullanici,
        "hayvan_olustur",
        f"Hayvan olusturuldu: {veri.get('kupe_no') or db_hayvan.id}",
        ciftlik_id=db_hayvan.ciftlik_id,
        hedef_tipi="hayvan",
        hedef_id=db_hayvan.id,
    )
    if anne_baglanti_eklendi:
        audit_kaydi(
            db,
            kullanici,
            "dogum_otomatik_yavru",
            f"Anne kupesi eslesmesiyle yavru dogum gecmisine baglandi: {veri.get('kupe_no') or db_hayvan.id}",
            ciftlik_id=db_hayvan.ciftlik_id,
            hedef_tipi="hayvan",
            hedef_id=db_hayvan.id,
        )
    db.commit()
    db.refresh(db_hayvan)
    return db_hayvandan_payload(db_hayvan, include_photo_urls=False)


@app.put("/api/hayvanlar/{hayvan_ref}", response_model=schemas.HayvanResponse)
@app.patch("/api/hayvanlar/{hayvan_ref}", response_model=schemas.HayvanResponse)
def update_hayvan(
    hayvan_ref: str,
    hayvan: schemas.HayvanUpdate,
    beklenen_son_guncelleme: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    db_hayvan = hayvan_bul(db, hayvan_ref, kullanici)
    alt_kayit_cakisma_kontrol(db_hayvan, beklenen_son_guncelleme)
    mevcut = db_hayvandan_payload(db_hayvan, include_photo_urls=False)
    onceki_dogumlar = json.loads(
        json.dumps(mevcut.get("dogumlar") or [], ensure_ascii=False)
    )
    onceki_foto_paths, _, _ = foto_referanslarini_topla(mevcut)
    guncelleme = model_verisi(hayvan, exclude_unset=True)
    guncelleme.pop("id", None)
    gelen_son_guncelleme = guncelleme.get("son_guncelleme")
    if gelen_zaman_daha_eski_mi(gelen_son_guncelleme, db_hayvan.son_guncelleme):
        raise eski_degisim_cakismasi(db_hayvan.son_guncelleme)
    if "ciftlik_id" in guncelleme and kullanici.rol != "admin":
        guncelleme.pop("ciftlik_id", None)
    mevcut.update(guncelleme)
    mevcut["id"] = db_hayvan.id
    if kullanici.rol != "admin":
        mevcut["ciftlik_id"] = kullanici.ciftlik_id
    if mevcut.get("ciftlik_id"):
        ciftlik_bul(db, mevcut["ciftlik_id"])
    veri = normalize_hayvan(mevcut, hayvan_id=db_hayvan.id)
    alt_kayit_tarihlerini_kontrol(veri)
    dogum_tarihi_degisimlerini_yavrulara_yansit(
        db,
        db_hayvan,
        onceki_dogumlar,
        veri.get("dogumlar") or [],
    )
    kupe_cakismasi_kontrol(db, veri, haric_id=db_hayvan.id, ciftlik_id=veri.get("ciftlik_id"))
    annenin_dogum_kaydina_yavru_ekle(db, db_hayvan, veri)
    audit_kaydi(
        db,
        kullanici,
        "hayvan_guncelle",
        f"Hayvan guncellendi: {veri.get('kupe_no') or db_hayvan.id}",
        ciftlik_id=veri.get("ciftlik_id"),
        hedef_tipi="hayvan",
        hedef_id=db_hayvan.id,
    )
    sonuc = response_kaydet(db, db_hayvan, veri, son_guncelleme=gelen_son_guncelleme or simdi(), include_photo_urls=False)
    yeni_foto_paths, _, _ = foto_referanslarini_topla(sonuc)
    yeni_paths = set(yeni_foto_paths)
    silinecek_paths = [path for path in onceki_foto_paths if path not in yeni_paths]
    storage_fotograflari_sil(silinecek_paths)
    return sonuc


@app.delete("/api/hayvanlar/{hayvan_ref}", response_model=schemas.IslemSonucResponse)
def delete_hayvan(
    hayvan_ref: str,
    kalici: bool = False,
    degisiklik_zamani: Optional[str] = None,
    beklenen_son_guncelleme: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    db_hayvan = hayvan_bul(db, hayvan_ref, kullanici)
    alt_kayit_cakisma_kontrol(db_hayvan, beklenen_son_guncelleme)
    if kalici:
        if gelen_zaman_daha_eski_mi(degisiklik_zamani, db_hayvan.son_guncelleme):
            raise eski_degisim_cakismasi(db_hayvan.son_guncelleme)
        silinen_id = db_hayvan.id
        silinen_kupe = db_hayvan.ciftlik_kupe_no or db_hayvan.resmi_kupe_no or db_hayvan.id
        silinen_ciftlik_id = db_hayvan.ciftlik_id
        silinecek_refs: List[str] = []
        silinen_payload = db_hayvandan_payload(db_hayvan, include_photo_urls=False)
        for kaynak in (silinen_payload,):
            paths, urls, _ = foto_referanslarini_topla(kaynak)
            silinecek_refs.extend(paths)
            silinecek_refs.extend(urls)
        try:
            ham_veri = json.loads(db_hayvan.veri_json or "{}")
            if isinstance(ham_veri, dict):
                paths, urls, _ = foto_referanslarini_topla(ham_veri)
                silinecek_refs.extend(paths)
                silinecek_refs.extend(urls)
        except (TypeError, json.JSONDecodeError):
            pass
        silinecek_foto_paths = storage_pathlari(silinecek_refs)
        temizlenen_yavru_sayisi = silinen_hayvan_dogum_referanslarini_temizle(
            db,
            silinen_id,
            silinen_payload,
            silinen_ciftlik_id,
        )
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
        storage_fotograflari_sil(silinecek_foto_paths)
        mesaj = "Hayvan kalıcı olarak silindi."
        if temizlenen_yavru_sayisi:
            mesaj += f" Anne doğum geçmişinden {temizlenen_yavru_sayisi} yavru bağlantısı temizlendi."
        return {
            "status": "ok",
            "message": mesaj,
            "id": silinen_id,
            "detay": {"temizlenen_yavru_baglantisi": temizlenen_yavru_sayisi},
        }

    veri = db_hayvandan_payload(db_hayvan, include_photo_urls=False)
    veri["arsivli"] = True
    veri["arsiv_tarihi"] = bugun()
    veri["gebe_mi"] = False
    veri["gebelik_tarihi"] = None
    veri["aktif_tohumlama_id"] = None
    audit_kaydi(
        db,
        kullanici,
        "hayvan_arsivle",
        f"Hayvan arsive alindi: {veri.get('kupe_no') or db_hayvan.id}",
        ciftlik_id=veri.get("ciftlik_id"),
        hedef_tipi="hayvan",
        hedef_id=db_hayvan.id,
    )
    response_kaydet(db, db_hayvan, veri, include_photo_urls=False)
    return {"status": "ok", "message": "Hayvan arşive alındı.", "id": db_hayvan.id}


@app.post("/api/hayvanlar/{hayvan_ref}/fotograflar", response_model=schemas.HayvanResponse)
async def upload_hayvan_fotograflari(
    hayvan_ref: str,
    fotograflar: List[UploadFile] = File(...),
    replace: bool = Form(False),
    beklenen_son_guncelleme: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    db_hayvan = hayvan_bul(db, hayvan_ref, kullanici)
    alt_kayit_cakisma_kontrol(db_hayvan, beklenen_son_guncelleme)
    veri = db_hayvandan_payload(db_hayvan, include_photo_urls=False)
    onceki_paths, _, _ = foto_referanslarini_topla(veri)
    mevcut_paths, mevcut_urls, mevcut_datas = foto_referanslarini_topla(veri)
    mevcut_fotograflar = [] if replace else mevcut_paths + mevcut_urls + mevcut_datas
    kalan_slot = ALP_MAX_PHOTOS_PER_ANIMAL - len(mevcut_fotograflar)
    if kalan_slot <= 0:
        raise HTTPException(status_code=400, detail="Bu hayvan için en fazla 3 fotoğraf eklenebilir.")
    if not fotograflar:
        raise HTTPException(status_code=400, detail="Yüklenecek fotoğraf seçilmedi.")
    yeni_fotograflar: List[str] = []
    for dosya in fotograflar[:kalan_slot]:
        mime = dosya.content_type or "image/jpeg"
        if not mime.startswith("image/"):
            raise HTTPException(status_code=400, detail="Sadece görsel dosyası yüklenebilir.")
        data = await dosya.read()
        if not data:
            continue
        if len(data) > ALP_PHOTO_MAX_SOURCE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Fotoğraf çok büyük. Lütfen {ALP_PHOTO_MAX_SOURCE_MB:g} MB altında fotoğraf seçin.",
            )
        mime, data = fotograf_sikistir(mime, data)
        encoded = base64.b64encode(data).decode("ascii")
        yeni_fotograflar.append(f"data:{mime};base64,{encoded}")
    if not yeni_fotograflar:
        raise HTTPException(status_code=400, detail="Yüklenecek geçerli fotoğraf bulunamadı.")
    tum_fotograflar = (mevcut_fotograflar + yeni_fotograflar)[:ALP_MAX_PHOTOS_PER_ANIMAL]
    paths = [foto for foto in tum_fotograflar if storage_path_from_ref(foto)]
    urls = [foto for foto in tum_fotograflar if foto_url_mu(foto) and not storage_path_from_ref(foto)]
    datas = [foto for foto in tum_fotograflar if not foto_url_mu(foto) and not storage_path_from_ref(foto)]
    veri["foto_paths"] = paths
    veri["foto_path"] = paths[0] if paths else None
    veri["foto_urls"] = urls
    veri["foto_url"] = urls[0] if urls else None
    veri["foto_datas"] = datas
    veri["foto_data"] = datas[0] if datas else None
    audit_kaydi(
        db,
        kullanici,
        "hayvan_fotograf_yukle",
        f"Hayvan fotoğrafı yüklendi: {veri.get('kupe_no') or db_hayvan.id} ({len(yeni_fotograflar)} adet)",
        ciftlik_id=veri.get("ciftlik_id"),
        hedef_tipi="hayvan",
        hedef_id=db_hayvan.id,
    )
    sonuc = response_kaydet(db, db_hayvan, veri, include_photo_urls=False)
    if replace:
        yeni_paths, _, _ = foto_referanslarini_topla(sonuc)
        yeni_path_set = set(yeni_paths)
        silinecek_paths = [path for path in onceki_paths if path not in yeni_path_set]
        storage_fotograflari_sil(silinecek_paths)
    return sonuc


def hayvan_fotografi_sil_ve_kaydet(
    db: Session,
    kullanici: models.Kullanici,
    db_hayvan: models.Hayvan,
    veri: Dict[str, Any],
    silinecek_index: int,
):
    paths, urls, datas = foto_referanslarini_topla(veri)
    fotograflar = paths + urls + datas
    if silinecek_index < 0 or silinecek_index >= len(fotograflar):
        raise HTTPException(status_code=404, detail="Fotoğraf bulunamadı.")
    silinen = fotograflar.pop(silinecek_index)
    paths = [foto for foto in fotograflar if storage_path_from_ref(foto)]
    urls = [foto for foto in fotograflar if foto_url_mu(foto) and not storage_path_from_ref(foto)]
    datas = [foto for foto in fotograflar if not foto_url_mu(foto) and not storage_path_from_ref(foto)]
    veri["foto_paths"] = paths
    veri["foto_path"] = paths[0] if paths else None
    veri["foto_urls"] = urls
    veri["foto_url"] = urls[0] if urls else None
    veri["foto_datas"] = datas
    veri["foto_data"] = datas[0] if datas else None
    audit_kaydi(
        db,
        kullanici,
        "hayvan_fotograf_sil",
        f"Hayvan fotoğrafı silindi: {veri.get('kupe_no') or db_hayvan.id}",
        ciftlik_id=veri.get("ciftlik_id"),
        hedef_tipi="hayvan",
        hedef_id=db_hayvan.id,
    )
    sonuc = response_kaydet(db, db_hayvan, veri, include_photo_urls=False)
    storage_fotograflari_sil([silinen])
    return sonuc


@app.delete("/api/hayvanlar/{hayvan_ref}/fotograflar", response_model=schemas.HayvanResponse)
def delete_hayvan_fotografi_by_path(
    hayvan_ref: str,
    foto_path: str = Query(..., min_length=1),
    beklenen_son_guncelleme: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    db_hayvan = hayvan_bul(db, hayvan_ref, kullanici)
    alt_kayit_cakisma_kontrol(db_hayvan, beklenen_son_guncelleme)
    veri = db_hayvandan_payload(db_hayvan, include_photo_urls=False)
    paths, urls, datas = foto_referanslarini_topla(veri)
    fotograflar = paths + urls + datas
    try:
        silinecek_index = fotograflar.index(foto_path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Fotoğraf bulunamadı.") from exc
    return hayvan_fotografi_sil_ve_kaydet(
        db,
        kullanici,
        db_hayvan,
        veri,
        silinecek_index,
    )


@app.delete("/api/hayvanlar/{hayvan_ref}/fotograflar/{foto_index}", response_model=schemas.HayvanResponse)
def delete_hayvan_fotografi(
    hayvan_ref: str,
    foto_index: int,
    beklenen_son_guncelleme: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    db_hayvan = hayvan_bul(db, hayvan_ref, kullanici)
    alt_kayit_cakisma_kontrol(db_hayvan, beklenen_son_guncelleme)
    veri = db_hayvandan_payload(db_hayvan, include_photo_urls=False)
    return hayvan_fotografi_sil_ve_kaydet(
        db,
        kullanici,
        db_hayvan,
        veri,
        foto_index - 1,
    )


@app.post(
    "/api/hayvanlar/{hayvan_ref}/tohumlamalar",
    response_model=schemas.TohumlamaResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_tohumlama(
    hayvan_ref: str,
    tohumlama: schemas.TohumlamaCreate,
    beklenen_son_guncelleme: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    db_hayvan = hayvan_bul(db, hayvan_ref, kullanici)
    alt_kayit_cakisma_kontrol(db_hayvan, beklenen_son_guncelleme)
    veri = db_hayvandan_payload(db_hayvan, include_photo_urls=False)
    yeni = normalize_tohumlama(model_verisi(tohumlama), yeni=True)
    tohumlama_kurallarini_kontrol(veri, yeni)
    veri.setdefault("tohumlamalar", []).append(yeni)
    eski_tohumlama_pozitif_olamaz(veri, yeni)
    tohumlama_sonucunu_isle(veri)
    audit_kaydi(
        db, kullanici, "tohumlama_olustur", "Tohumlama kaydı oluşturuldu.",
        ciftlik_id=veri.get("ciftlik_id"), hedef_tipi="hayvan", hedef_id=db_hayvan.id,
    )
    hayvan_sonuc = response_kaydet(db, db_hayvan, veri, include_photo_urls=False)
    return {**yeni, "hayvan_id": db_hayvan.id, "hayvan_son_guncelleme": hayvan_sonuc.get("son_guncelleme")}


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
    beklenen_son_guncelleme: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    db_hayvan = hayvan_bul(db, hayvan_ref, kullanici)
    alt_kayit_cakisma_kontrol(db_hayvan, beklenen_son_guncelleme)
    veri = db_hayvandan_payload(db_hayvan, include_photo_urls=False)
    mevcut_kayit = nested_kayit_bul(veri.setdefault("tohumlamalar", []), tohumlama_ref, "Tohumlama")
    kayit = dict(mevcut_kayit)
    kayit.update(model_verisi(tohumlama, exclude_unset=True))
    kayit = normalize_tohumlama(kayit)
    doguma_bagli_tohumlama_duzenleme_kontrolu(veri, mevcut_kayit, kayit)
    tohumlama_tarih_kurallarini_kontrol(veri, kayit)
    for index, mevcut in enumerate(veri["tohumlamalar"]):
        if mevcut.get("id") == kayit.get("id"):
            veri["tohumlamalar"][index] = kayit
            break
    eski_tohumlama_pozitif_olamaz(veri, kayit)
    tohumlama_sonucunu_isle(veri)
    audit_kaydi(
        db, kullanici, "tohumlama_guncelle", "Tohumlama kaydı güncellendi.",
        ciftlik_id=veri.get("ciftlik_id"), hedef_tipi="hayvan", hedef_id=db_hayvan.id,
    )
    hayvan_sonuc = response_kaydet(db, db_hayvan, veri, include_photo_urls=False)
    return {**kayit, "hayvan_id": db_hayvan.id, "hayvan_son_guncelleme": hayvan_sonuc.get("son_guncelleme")}


@app.delete("/api/hayvanlar/{hayvan_ref}/tohumlamalar/{tohumlama_ref}", response_model=schemas.IslemSonucResponse)
def delete_tohumlama(
    hayvan_ref: str,
    tohumlama_ref: str,
    beklenen_son_guncelleme: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    db_hayvan = hayvan_bul(db, hayvan_ref, kullanici)
    alt_kayit_cakisma_kontrol(db_hayvan, beklenen_son_guncelleme)
    veri = db_hayvandan_payload(db_hayvan, include_photo_urls=False)
    kayit = nested_kayit_bul(veri.setdefault("tohumlamalar", []), tohumlama_ref, "Tohumlama")
    if tohumlama_doguma_bagli_mi(veri, kayit):
        raise doguma_bagli_tohumlama_silme_hatasi()
    silinen = nested_kayit_sil(veri.setdefault("tohumlamalar", []), tohumlama_ref, "Tohumlama")
    tohumlama_sonucunu_isle(veri)
    audit_kaydi(
        db, kullanici, "tohumlama_sil", "Tohumlama kaydı silindi.",
        ciftlik_id=veri.get("ciftlik_id"), hedef_tipi="hayvan", hedef_id=db_hayvan.id,
    )
    hayvan_sonuc = response_kaydet(db, db_hayvan, veri, include_photo_urls=False)
    return {"status": "ok", "message": "Tohumlama kaydı silindi.", "id": silinen.get("id"), "son_guncelleme": hayvan_sonuc.get("son_guncelleme")}


@app.post(
    "/api/hayvanlar/{hayvan_ref}/asi-prosedurler",
    response_model=schemas.AsiProsedurResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_asi(
    hayvan_ref: str,
    asi: schemas.AsiProsedurCreate,
    beklenen_son_guncelleme: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    db_hayvan = hayvan_bul(db, hayvan_ref, kullanici)
    alt_kayit_cakisma_kontrol(db_hayvan, beklenen_son_guncelleme)
    veri = db_hayvandan_payload(db_hayvan, include_photo_urls=False)
    yeni = normalize_asi(model_verisi(asi), yeni=True)
    veri.setdefault("asi_prosedurler", []).append(yeni)
    audit_kaydi(
        db, kullanici, "asi_prosedur_olustur", "Aşı/prosedür kaydı oluşturuldu.",
        ciftlik_id=veri.get("ciftlik_id"), hedef_tipi="hayvan", hedef_id=db_hayvan.id,
    )
    hayvan_sonuc = response_kaydet(db, db_hayvan, veri, include_photo_urls=False)
    return {**yeni, "hayvan_id": db_hayvan.id, "hayvan_son_guncelleme": hayvan_sonuc.get("son_guncelleme")}


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
    beklenen_son_guncelleme: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    db_hayvan = hayvan_bul(db, hayvan_ref, kullanici)
    alt_kayit_cakisma_kontrol(db_hayvan, beklenen_son_guncelleme)
    veri = db_hayvandan_payload(db_hayvan, include_photo_urls=False)
    kayit = nested_kayit_bul(veri.setdefault("asi_prosedurler", []), asi_ref, "Aşı/prosedür")
    kayit.update(model_verisi(asi, exclude_unset=True))
    kayit = normalize_asi(kayit)
    for index, mevcut in enumerate(veri["asi_prosedurler"]):
        if mevcut.get("id") == kayit.get("id"):
            veri["asi_prosedurler"][index] = kayit
            break
    audit_kaydi(
        db, kullanici, "asi_prosedur_guncelle", "Aşı/prosedür kaydı güncellendi.",
        ciftlik_id=veri.get("ciftlik_id"), hedef_tipi="hayvan", hedef_id=db_hayvan.id,
    )
    hayvan_sonuc = response_kaydet(db, db_hayvan, veri, include_photo_urls=False)
    return {**kayit, "hayvan_id": db_hayvan.id, "hayvan_son_guncelleme": hayvan_sonuc.get("son_guncelleme")}


@app.delete("/api/hayvanlar/{hayvan_ref}/asi-prosedurler/{asi_ref}", response_model=schemas.IslemSonucResponse)
def delete_asi(
    hayvan_ref: str,
    asi_ref: str,
    beklenen_son_guncelleme: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    db_hayvan = hayvan_bul(db, hayvan_ref, kullanici)
    alt_kayit_cakisma_kontrol(db_hayvan, beklenen_son_guncelleme)
    veri = db_hayvandan_payload(db_hayvan, include_photo_urls=False)
    silinen = nested_kayit_sil(veri.setdefault("asi_prosedurler", []), asi_ref, "Aşı/prosedür")
    audit_kaydi(
        db, kullanici, "asi_prosedur_sil", "Aşı/prosedür kaydı silindi.",
        ciftlik_id=veri.get("ciftlik_id"), hedef_tipi="hayvan", hedef_id=db_hayvan.id,
    )
    hayvan_sonuc = response_kaydet(db, db_hayvan, veri, include_photo_urls=False)
    return {"status": "ok", "message": "Aşı/prosedür kaydı silindi.", "id": silinen.get("id"), "son_guncelleme": hayvan_sonuc.get("son_guncelleme")}


@app.post(
    "/api/hayvanlar/{hayvan_ref}/dogumlar",
    response_model=schemas.DogumResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_dogum(
    hayvan_ref: str,
    dogum: schemas.DogumCreate,
    beklenen_son_guncelleme: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    db_hayvan = hayvan_bul(db, hayvan_ref, kullanici)
    alt_kayit_cakisma_kontrol(db_hayvan, beklenen_son_guncelleme)
    anne = db_hayvandan_payload(db_hayvan, include_photo_urls=False)
    if anne.get("cins") in ERKEK_CINSLER or anne.get("cinsiyet") == "Erkek":
        raise HTTPException(status_code=400, detail="Erkek hayvana doğum kaydı eklenemez.")
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
        yavru_id = metin(yavru.get("hayvan_id") or yavru.get("id")) or yeni_id()
        if db.query(models.Hayvan).filter(models.Hayvan.id == yavru_id).first():
            raise HTTPException(status_code=400, detail="Yavru kimligi zaten kayitli.")
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
            "id": yavru_id,
            "hayvan_id": yavru_id,
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
    audit_kaydi(
        db, kullanici, "dogum_olustur", "Doğum/laktasyon kaydı oluşturuldu.",
        ciftlik_id=anne.get("ciftlik_id"), hedef_tipi="hayvan", hedef_id=db_hayvan.id,
    )
    hayvan_sonuc = response_kaydet(db, db_hayvan, anne, include_photo_urls=False)
    return {**yeni, "hayvan_son_guncelleme": hayvan_sonuc.get("son_guncelleme")}


@app.put("/api/hayvanlar/{hayvan_ref}/dogumlar/{dogum_ref}", response_model=schemas.DogumResponse)
@app.patch("/api/hayvanlar/{hayvan_ref}/dogumlar/{dogum_ref}", response_model=schemas.DogumResponse)
def update_dogum(
    hayvan_ref: str,
    dogum_ref: str,
    dogum: schemas.DogumUpdate,
    beklenen_son_guncelleme: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    db_hayvan = hayvan_bul(db, hayvan_ref, kullanici)
    alt_kayit_cakisma_kontrol(db_hayvan, beklenen_son_guncelleme)
    veri = db_hayvandan_payload(db_hayvan, include_photo_urls=False)
    if veri.get("cins") in ERKEK_CINSLER or veri.get("cinsiyet") == "Erkek":
        raise HTTPException(status_code=400, detail="Erkek hayvanın doğum kaydı düzenlenemez.")
    mevcut_kayit = nested_kayit_bul(veri.setdefault("dogumlar", []), dogum_ref, "Doğum")
    eski_tarih = mevcut_kayit.get("tarih")
    kayit = dict(mevcut_kayit)
    kayit.update(model_verisi(dogum, exclude_unset=True))
    kayit = normalize_dogum(kayit)
    anne_dogum = parse_tarih(veri.get("dogum_tarihi"), "Anne doğum tarihi")
    dogum_tarihi = parse_tarih(kayit.get("tarih"), "Doğum tarihi", zorunlu=True)
    if anne_dogum and dogum_tarihi < anne_dogum:
        raise HTTPException(status_code=400, detail="Doğum tarihi annenin doğum tarihinden önce olamaz.")
    for index, mevcut in enumerate(veri["dogumlar"]):
        if mevcut is kayit or mevcut.get("id") == kayit.get("id"):
            veri["dogumlar"][index] = kayit
            break
    dogum_tarihi_degisimlerini_yavrulara_yansit(
        db,
        db_hayvan,
        [{**mevcut_kayit, "tarih": eski_tarih}],
        [kayit],
    )
    audit_kaydi(
        db, kullanici, "dogum_guncelle", "Doğum/laktasyon kaydı güncellendi.",
        ciftlik_id=veri.get("ciftlik_id"), hedef_tipi="hayvan", hedef_id=db_hayvan.id,
    )
    hayvan_sonuc = response_kaydet(db, db_hayvan, veri, include_photo_urls=False)
    return {**kayit, "hayvan_son_guncelleme": hayvan_sonuc.get("son_guncelleme")}


@app.delete("/api/hayvanlar/{hayvan_ref}/dogumlar/{dogum_ref}", response_model=schemas.IslemSonucResponse)
def delete_dogum(
    hayvan_ref: str,
    dogum_ref: str,
    beklenen_son_guncelleme: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    db_hayvan = hayvan_bul(db, hayvan_ref, kullanici)
    alt_kayit_cakisma_kontrol(db_hayvan, beklenen_son_guncelleme)
    veri = db_hayvandan_payload(db_hayvan, include_photo_urls=False)
    silinen = nested_kayit_sil(veri.setdefault("dogumlar", []), dogum_ref, "Doğum")
    audit_kaydi(
        db, kullanici, "dogum_sil", "Doğum/laktasyon kaydı silindi.",
        ciftlik_id=veri.get("ciftlik_id"), hedef_tipi="hayvan", hedef_id=db_hayvan.id,
    )
    hayvan_sonuc = response_kaydet(db, db_hayvan, veri, include_photo_urls=False)
    return {"status": "ok", "message": "Doğum/laktasyon kaydı silindi.", "id": silinen.get("id"), "son_guncelleme": hayvan_sonuc.get("son_guncelleme")}


@app.get("/api/uyarilar", response_model=List[schemas.UyariResponse])
def get_uyarilar(
    ciftlik_id: Optional[str] = None,
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    hayvanlar = [db_hayvandan_payload(h, include_photo_urls=False) for h in hayvan_sorgusu_scope(db, kullanici, ciftlik_id).all()]
    return uyarilari_hesapla(hayvanlar)


@app.get("/api/raporlar/ozet", response_model=schemas.RaporOzetResponse)
def get_rapor_ozet(
    ciftlik_id: Optional[str] = None,
    db: Session = Depends(get_db),
    kullanici: models.Kullanici = Depends(get_current_user),
):
    hayvanlar = [db_hayvandan_payload(h, include_photo_urls=False) for h in hayvan_sorgusu_scope(db, kullanici, ciftlik_id).all()]
    aktif_hayvanlar = [h for h in hayvanlar if hayvan_aktif_mi(h)]
    cinsiyet_dagilimi: Dict[str, int] = {}
    hayvan_tipi_dagilimi: Dict[str, int] = {}
    for h in aktif_hayvanlar:
        tip = h.get("cins") or "Bilinmiyor"
        cinsiyet = h.get("cinsiyet") or ("Erkek" if tip in ERKEK_CINSLER else "Dişi")
        cinsiyet_dagilimi[cinsiyet] = cinsiyet_dagilimi.get(cinsiyet, 0) + 1
        hayvan_tipi_dagilimi[tip] = hayvan_tipi_dagilimi.get(tip, 0) + 1
    uyarilar = uyarilari_hesapla(hayvanlar)
    return {
        "toplam": len(hayvanlar),
        "aktif": sum(1 for h in hayvanlar if hayvan_aktif_mi(h)),
        "gebe": sum(1 for h in hayvanlar if hayvan_aktif_mi(h) and h.get("gebe_mi")),
        "arsivli": sum(1 for h in hayvanlar if h.get("arsivli")),
        "olu": sum(1 for h in hayvanlar if h.get("olu")),
        "kesildi": sum(1 for h in hayvanlar if h.get("kesildi")),
        "cins_dagilimi": cinsiyet_dagilimi,
        "hayvan_tipi_dagilimi": hayvan_tipi_dagilimi,
        "acik_uyari": len(uyarilar),
    }


@app.get("/api/sistem-durumu", response_model=schemas.SistemDurumuResponse)
def get_sistem_durumu(
    db: Session = Depends(get_db),
    _: models.Kullanici = Depends(require_admin),
):
    db_bytes = database_boyutu_bytes(db)
    db_mb = round((db_bytes or 0) / (1024 * 1024), 2) if db_bytes is not None else None
    db_yuzde = round((db_mb / ALP_DB_QUOTA_MB) * 100, 1) if db_mb is not None and ALP_DB_QUOTA_MB else None
    toplam_hayvan = db.query(models.Hayvan).count()
    aktif_hayvan = (
        db.query(models.Hayvan)
        .filter(
            models.Hayvan.arsivli.is_(False),
            models.Hayvan.olu.is_(False),
            models.Hayvan.kesildi.is_(False),
            or_(models.Hayvan.durum_notu.is_(None), models.Hayvan.durum_notu != "Satıldı"),
        )
        .count()
    )
    foto_istatistik = veri_json_fotograf_istatistikleri(db)
    storage_aktif = bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and ALP_PHOTO_BUCKET)
    tahmini_foto_adet = 0
    ortalama_mb = 0.18
    if ALP_STORAGE_QUOTA_MB:
        tahmini_foto_adet = int(ALP_STORAGE_QUOTA_MB / ortalama_mb)
    return {
        "olusturma_zamani": simdi(),
        "database": {
            "backend": engine.url.get_backend_name(),
            "boyut_bytes": db_bytes,
            "boyut_mb": db_mb,
            "limit_mb": ALP_DB_QUOTA_MB,
            "kullanim_yuzde": db_yuzde,
        },
        "storage": {
            "aktif": storage_aktif,
            "bucket": ALP_PHOTO_BUCKET,
            "public_url": ALP_PHOTO_BUCKET_PUBLIC,
            "signed_url_ttl_seconds": ALP_PHOTO_SIGNED_URL_TTL_SECONDS,
            "limit_mb": ALP_STORAGE_QUOTA_MB,
            "tahmini_foto_kapasitesi": tahmini_foto_adet,
            "not": "Kapasite tahmini 180 KB ortalama sıkıştırılmış fotoğrafa göre hesaplanır.",
        },
        "kayit_sayilari": {
            "ciftlik": db.query(models.Ciftlik).count(),
            "kullanici": db.query(models.Kullanici).count(),
            "hayvan": toplam_hayvan,
            "aktif_hayvan": aktif_hayvan,
            "arsivli_hayvan": db.query(models.Hayvan).filter(models.Hayvan.arsivli.is_(True)).count(),
            "tohumlama": db.query(models.Tohumlama).count(),
            "asi_prosedur": db.query(models.AsiProsedur).count(),
            "islem_gecmisi": db.query(models.IslemGecmisi).count(),
        },
        "fotograflar": foto_istatistik,
        "limitler": {
            "hayvan_basi_maks_fotograf": ALP_MAX_PHOTOS_PER_ANIMAL,
            "storage_env": "SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY + ALP_PHOTO_BUCKET",
        },
    }


def veri_sagligi_raporu(db: Session) -> Dict[str, Any]:
    ciftlikler = db.query(models.Ciftlik).all()
    kullanicilar = db.query(models.Kullanici).all()
    hayvanlar = db.query(models.Hayvan).all()
    ciftlik_adlari = {c.id: c.ad for c in ciftlikler}
    hayvan_idleri = {h.id for h in hayvanlar}
    kontroller: List[Dict[str, Any]] = []

    def ekle(seviye: str, baslik: str, mesaj: str, adet: int, ornekler: Iterable[Any] = (), onerilen_islem: Optional[str] = None) -> None:
        if adet <= 0 and seviye != "bilgi":
            return
        kontroller.append(
            {
                "seviye": seviye,
                "baslik": baslik,
                "mesaj": mesaj,
                "adet": int(adet),
                "ornekler": [metin(ornek) for ornek in list(ornekler)[:12]],
                "onerilen_islem": onerilen_islem,
            }
        )

    def hayvan_etiketi(h: models.Hayvan) -> str:
        kupe = h.ciftlik_kupe_no or h.resmi_kupe_no or h.id
        ciftlik = ciftlik_adlari.get(h.ciftlik_id or "", h.ciftlik_id or "ciftlik yok")
        return f"{kupe} / {ciftlik}"

    def veri_json_oku(h: models.Hayvan) -> Dict[str, Any]:
        if not h.veri_json:
            return {}
        try:
            veri = json.loads(h.veri_json)
            return veri if isinstance(veri, dict) else {}
        except Exception:
            return {}

    legacy_ciftlikler = [
        c for c in ciftlikler if c.id == LEGACY_DEFAULT_CIFTLIK_ID or c.ad == LEGACY_DEFAULT_CIFTLIK_ADI
    ]
    ekle(
        "uyari",
        "Varsayilan ciftlik kalintisi",
        "Eski/test doneminden kalan Varsayilan Ciftlik kaydi bulundu.",
        len(legacy_ciftlikler),
        [f"{c.ad} ({c.id})" for c in legacy_ciftlikler],
        "Canli veri degilse admin temizlik islemiyle kaldirilabilir.",
    )

    sahipsiz_hayvanlar = [h for h in hayvanlar if not h.ciftlik_id or h.ciftlik_id not in ciftlik_adlari]
    ekle(
        "kritik",
        "Ciftliksiz hayvan",
        "Bir hayvan kaydinin hangi ciftlige ait oldugu net degil.",
        len(sahipsiz_hayvanlar),
        [hayvan_etiketi(h) for h in sahipsiz_hayvanlar],
        "Hayvan kaydina dogru ciftlik atanmalidir.",
    )

    sorunlu_kullanicilar = [
        k
        for k in kullanicilar
        if k.rol != "admin" and (not k.ciftlik_id or k.ciftlik_id not in ciftlik_adlari)
    ]
    ekle(
        "kritik",
        "Ciftliksiz kullanici",
        "Normal kullanici hesabi bir ciftlige bagli degil veya bagli oldugu ciftlik yok.",
        len(sorunlu_kullanicilar),
        [f"{k.kullanici_adi} ({k.ciftlik_id or 'ciftlik yok'})" for k in sorunlu_kullanicilar],
        "Kullanici yonetiminden dogru ciftlik atanmalidir.",
    )

    def tekrarli_kupe_kontrol(alan: str, baslik: str) -> None:
        gruplar: Dict[tuple, List[str]] = {}
        for h in hayvanlar:
            deger = metin(getattr(h, alan, None), upper=True)
            if not deger:
                continue
            key = (h.ciftlik_id or "-", deger)
            gruplar.setdefault(key, []).append(hayvan_etiketi(h))
        tekrarlar = [f"{deger}: {len(ornekler)} kayit" for (_, deger), ornekler in gruplar.items() if len(ornekler) > 1]
        ekle(
            "kritik",
            baslik,
            "Ayni ciftlikte ayni kupe numarasi birden fazla hayvanda gorunuyor.",
            len(tekrarlar),
            tekrarlar,
            "Cakisan kupe numaralari hayvan listesinden duzeltilmelidir.",
        )

    tekrarli_kupe_kontrol("resmi_kupe_no", "Tekrarli resmi kupe")
    tekrarli_kupe_kontrol("ciftlik_kupe_no", "Tekrarli ciftlik kupesi")

    bozuk_markerlar = tuple(TURKCE_METIN_ONARIMLARI.keys()) + ("Ä", "Å", "Ã")
    bozuk_turkce_ornekleri = []
    bozuk_turkce_adet = 0
    for h in hayvanlar:
        raw = " ".join(
            metin(parca)
            for parca in (h.cins, h.cinsiyet, h.durum_notu, h.dogum_tarihi, h.ek_notlar, h.veri_json)
            if parca is not None
        )
        if any(marker in raw for marker in bozuk_markerlar):
            bozuk_turkce_adet += 1
            bozuk_turkce_ornekleri.append(hayvan_etiketi(h))
    ekle(
        "uyari",
        "Bozuk Turkce metin",
        "Kayitlarda karakter bozulmasi olabilecek metinler bulundu.",
        bozuk_turkce_adet,
        bozuk_turkce_ornekleri,
        "Gerekirse bu kayitlar yeniden kaydedilerek normalize edilebilir.",
    )

    gecersiz_tarih_ornekleri = []
    gelecek_tarih_ornekleri = []
    tarih_alanlari = ("dogum_tarihi", "gebelik_tarihi", "olum_tarihi", "satis_tarihi", "arsiv_tarihi")
    for h in hayvanlar:
        veri = veri_json_oku(h)
        if h.dogum_tarihi and not veri.get("dogum_tarihi"):
            veri["dogum_tarihi"] = h.dogum_tarihi
        for alan in tarih_alanlari:
            deger = metin(veri.get(alan))
            if not deger or deger == "Bilinmiyor":
                continue
            tarih = parse_tarih_sessiz(deger)
            if not tarih:
                gecersiz_tarih_ornekleri.append(f"{hayvan_etiketi(h)} - {alan}: {deger}")
            elif tarih.date() > bugun_tarih():
                gelecek_tarih_ornekleri.append(f"{hayvan_etiketi(h)} - {alan}: {deger}")
        for liste_adi, tarih_anahtarlari in (
            ("tohumlamalar", ("tarih", "kontrol_tarihi")),
            ("dogumlar", ("tarih", "laktasyon_bitis_tarihi")),
            ("asi_prosedurler", ("tarih", "sonraki_tarih")),
        ):
            for kayit in veri.get(liste_adi) or []:
                if not isinstance(kayit, dict):
                    continue
                for alan in tarih_anahtarlari:
                    deger = metin(kayit.get(alan))
                    if deger and deger != "Bilinmiyor" and not parse_tarih_sessiz(deger):
                        gecersiz_tarih_ornekleri.append(f"{hayvan_etiketi(h)} - {liste_adi}.{alan}: {deger}")
    ekle(
        "uyari",
        "Gecersiz tarih",
        "GG/AA/YYYY formatina uymayan tarih degerleri bulundu.",
        len(gecersiz_tarih_ornekleri),
        gecersiz_tarih_ornekleri,
        "Ilgili hayvan profilinden tarih degerleri duzeltilmelidir.",
    )
    ekle(
        "uyari",
        "Gelecek tarih",
        "Gecmiste olmasi beklenen bazi tarih alanlari gelecekte gorunuyor.",
        len(gelecek_tarih_ornekleri),
        gelecek_tarih_ornekleri,
        "Tarihlerin bilerek girildigi kontrol edilmelidir.",
    )

    yetim_tohumlama = [t.hayvan_id for t in db.query(models.Tohumlama).all() if t.hayvan_id not in hayvan_idleri]
    yetim_asi = [a.hayvan_id for a in db.query(models.AsiProsedur).all() if a.hayvan_id not in hayvan_idleri]
    yetim_uyari = [u.hayvan_id for u in db.query(models.Uyari).all() if u.hayvan_id and u.hayvan_id not in hayvan_idleri]
    ekle(
        "uyari",
        "Sahipsiz alt kayit",
        "Hayvani bulunmayan tohumlama, asi/prosedur veya uyari kayitlari var.",
        len(yetim_tohumlama) + len(yetim_asi) + len(yetim_uyari),
        [f"tohumlama:{x}" for x in yetim_tohumlama] + [f"asi:{x}" for x in yetim_asi] + [f"uyari:{x}" for x in yetim_uyari],
        "Bu durum genellikle eski test silmelerinden kalir; temizlik araci ile kaldirilabilir.",
    )

    durum_celiski_ornekleri = []
    kullanilan_foto_pathleri: set[str] = set()
    for h in hayvanlar:
        veri = veri_json_oku(h)
        paths, _, _ = foto_referanslarini_topla(veri)
        kullanilan_foto_pathleri.update(paths)
        pasif = bool(veri.get("arsivli") or veri.get("olu") or veri.get("kesildi") or veri.get("satildi"))
        if pasif and bool(veri.get("gebe_mi")):
            durum_celiski_ornekleri.append(f"{hayvan_etiketi(h)} - pasif ama gebe isaretli")
        if veri.get("satildi") and metin(veri.get("durum")) != "Satıldı":
            durum_celiski_ornekleri.append(f"{hayvan_etiketi(h)} - satildi/durum uyumsuz")
    ekle(
        "uyari",
        "Durum celiskisi",
        "Hayvan durum bayraklari ile profil bilgileri uyusmuyor.",
        len(durum_celiski_ornekleri),
        durum_celiski_ornekleri,
        "Hayvan profilinde durum bilgisi yeniden kaydedilmelidir.",
    )

    foto_istatistik = veri_json_fotograf_istatistikleri(db)
    ekle(
        "uyari",
        "Veritabaninda gomulu fotograf",
        "Bazi fotograflar storage yerine veritabaninda base64 olarak duruyor.",
        int(foto_istatistik.get("database_base64_adet") or 0),
        [],
        "Fotograflar tekrar kaydedildikce storage'a tasinir; buyuk veriler icin temizlik planlanabilir.",
    )

    storage_durumu = "pasif"
    eksik_storage_ornekleri: List[str] = []
    sahipsiz_storage_ornekleri: List[str] = []
    if kullanilan_foto_pathleri and not storage_aktif_mi():
        ekle(
            "kritik",
            "Storage pasif",
            "Hayvan kayitlarinda storage referansi var ama storage ayarlari aktif degil.",
            len(kullanilan_foto_pathleri),
            list(kullanilan_foto_pathleri),
            "Render environment variables icindeki Supabase storage ayarlari kontrol edilmelidir.",
        )
    elif storage_aktif_mi():
        try:
            storage_dosyalari = set(storage_dosyalari_listele())
            storage_durumu = "aktif"
            eksik_storage_ornekleri = sorted(kullanilan_foto_pathleri - storage_dosyalari)[:12]
            sahipsiz_storage_ornekleri = sorted(storage_dosyalari - kullanilan_foto_pathleri)[:12]
        except Exception as hata:
            storage_durumu = "listeleme hatasi"
            ekle(
                "uyari",
                "Storage listelenemedi",
                f"Storage dosyalari kontrol edilirken hata alindi: {hata}",
                1,
                [],
                "Supabase service role key ve bucket yetkileri kontrol edilmeli.",
            )
    ekle(
        "kritik",
        "Eksik fotograf dosyasi",
        "Hayvan kaydinda fotograf yolu var ama storage dosyasi bulunamadi.",
        len(eksik_storage_ornekleri),
        eksik_storage_ornekleri,
        "Ilgili hayvana fotograf yeniden yuklenmelidir.",
    )
    ekle(
        "uyari",
        "Sahipsiz storage dosyasi",
        "Storage'da hicbir hayvan kaydinin kullanmadigi fotograf dosyalari var.",
        len(sahipsiz_storage_ornekleri),
        sahipsiz_storage_ornekleri,
        "Canli kayitla iliskisi yoksa storage temizligi yapilabilir.",
    )

    if not kontroller:
        ekle("bilgi", "Sorun bulunmadi", "Temel veri sagligi kontrollerinde sorun gorunmuyor.", 0)

    ozet = {
        "kritik": sum(1 for k in kontroller if k["seviye"] == "kritik"),
        "uyari": sum(1 for k in kontroller if k["seviye"] == "uyari"),
        "bilgi": sum(1 for k in kontroller if k["seviye"] == "bilgi"),
        "kontrol": len(kontroller),
    }
    genel_durum = "kritik" if ozet["kritik"] else ("uyari" if ozet["uyari"] else "saglikli")
    return {
        "olusturma_zamani": simdi(),
        "genel_durum": genel_durum,
        "ozet": ozet,
        "sayilar": {
            "ciftlik": len(ciftlikler),
            "kullanici": len(kullanicilar),
            "hayvan": len(hayvanlar),
            "storage_durumu": storage_durumu,
            "kullanilan_foto_path": len(kullanilan_foto_pathleri),
        },
        "kontroller": kontroller,
    }


@app.get("/api/admin/veri-sagligi", response_model=schemas.VeriSagligiResponse)
def get_veri_sagligi(
    db: Session = Depends(get_db),
    _: models.Kullanici = Depends(require_admin),
):
    return veri_sagligi_raporu(db)


@app.post("/api/admin/test-verilerini-sifirla", response_model=schemas.IslemSonucResponse)
def test_verilerini_sifirla(
    db: Session = Depends(get_db),
    admin: models.Kullanici = Depends(require_admin),
):
    silinecek_fotograflar: List[str] = []
    for hayvan in db.query(models.Hayvan).all():
        paths, _, _ = foto_referanslarini_topla(db_hayvandan_payload(hayvan, include_photo_urls=False))
        silinecek_fotograflar.extend(paths)

    sayilar = {
        "hayvan": db.query(models.Hayvan).count(),
        "ciftlik": db.query(models.Ciftlik).count(),
        "kullanici": db.query(models.Kullanici).filter(models.Kullanici.rol != "admin").count(),
        "tohumlama": db.query(models.Tohumlama).count(),
        "asi_prosedur": db.query(models.AsiProsedur).count(),
        "uyari": db.query(models.Uyari).count(),
        "islem_gecmisi": db.query(models.IslemGecmisi).count(),
    }

    db.query(models.Tohumlama).delete(synchronize_session=False)
    db.query(models.AsiProsedur).delete(synchronize_session=False)
    db.query(models.Uyari).delete(synchronize_session=False)
    db.query(models.Hayvan).delete(synchronize_session=False)
    db.query(models.Kullanici).filter(models.Kullanici.rol != "admin").delete(synchronize_session=False)
    db.query(models.Ciftlik).delete(synchronize_session=False)
    db.query(models.IslemGecmisi).delete(synchronize_session=False)
    audit_kaydi(
        db,
        admin,
        "test_verilerini_sifirla",
        (
            "Test verileri sifirlandi. "
            f"{sayilar['hayvan']} hayvan, {sayilar['ciftlik']} ciftlik, "
            f"{sayilar['kullanici']} kullanici temizlendi."
        ),
        hedef_tipi="sistem",
        hedef_id="test-verileri",
    )
    db.commit()
    storage_fotograflari_sil(silinecek_fotograflar)
    return {
        "status": "ok",
        "message": (
            "Test verileri sifirlandi; admin hesaplari korundu. "
            f"Silinen: {sayilar}"
        ),
        "id": "test-verileri",
    }


@app.post("/api/admin/canli-temizlik", response_model=schemas.IslemSonucResponse)
def canli_temizlik(
    varsayilan_ciftlik: bool = Query(default=True),
    islem_gecmisi: bool = Query(default=True),
    storage: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: models.Kullanici = Depends(require_admin),
):
    silinecek_fotograflar: List[str] = []
    sonuc = {
        "varsayilan_ciftlik": 0,
        "varsayilan_hayvan": 0,
        "varsayilan_kullanici": 0,
        "islem_gecmisi": 0,
        "storage": 0,
    }

    if varsayilan_ciftlik:
        legacy_ciftlikler = db.query(models.Ciftlik).filter(
            or_(
                models.Ciftlik.id == LEGACY_DEFAULT_CIFTLIK_ID,
                models.Ciftlik.ad == LEGACY_DEFAULT_CIFTLIK_ADI,
            )
        ).all()
        for ciftlik in legacy_ciftlikler:
            ciftlik_id = ciftlik.id
            for hayvan in db.query(models.Hayvan).filter(models.Hayvan.ciftlik_id == ciftlik_id).all():
                paths, _, _ = foto_referanslarini_topla(db_hayvandan_payload(hayvan, include_photo_urls=False))
                silinecek_fotograflar.extend(paths)
            hayvan_idleri = [
                satir[0]
                for satir in db.query(models.Hayvan.id).filter(models.Hayvan.ciftlik_id == ciftlik_id).all()
            ]
            if hayvan_idleri:
                db.query(models.Tohumlama).filter(models.Tohumlama.hayvan_id.in_(hayvan_idleri)).delete(synchronize_session=False)
                db.query(models.AsiProsedur).filter(models.AsiProsedur.hayvan_id.in_(hayvan_idleri)).delete(synchronize_session=False)
                db.query(models.Uyari).filter(models.Uyari.hayvan_id.in_(hayvan_idleri)).delete(synchronize_session=False)
            sonuc["varsayilan_hayvan"] += db.query(models.Hayvan).filter(
                models.Hayvan.ciftlik_id == ciftlik_id
            ).delete(synchronize_session=False)
            sonuc["varsayilan_kullanici"] += db.query(models.Kullanici).filter(
                models.Kullanici.ciftlik_id == ciftlik_id
            ).delete(synchronize_session=False)
            db.query(models.IslemGecmisi).filter(models.IslemGecmisi.ciftlik_id == ciftlik_id).delete(synchronize_session=False)
            db.delete(ciftlik)
            sonuc["varsayilan_ciftlik"] += 1

    if islem_gecmisi:
        sonuc["islem_gecmisi"] = db.query(models.IslemGecmisi).delete(synchronize_session=False)

    db.commit()

    if storage:
        silinecek_fotograflar.extend(storage_dosyalari_listele())
    sonuc["storage"] = storage_fotograflari_sil(silinecek_fotograflar)

    return {
        "status": "ok",
        "message": f"Canli temizlik tamamlandi: {sonuc}",
        "id": "canli-temizlik",
        "detay": sonuc,
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
    kayitlar = sorgu.all()
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
    kayitlar.sort(
        key=lambda kayit: parse_zaman_sessiz(kayit.zaman) or datetime.min,
        reverse=True,
    )
    kayitlar = kayitlar[:limit]
    return [islem_payload(kayit) for kayit in kayitlar]


@app.delete("/api/islem-gecmisi", response_model=schemas.IslemSonucResponse)
def clear_islem_gecmisi(
    ciftlik_id: Optional[str] = None,
    db: Session = Depends(get_db),
    _: models.Kullanici = Depends(require_admin),
):
    sorgu = db.query(models.IslemGecmisi)
    if ciftlik_id:
        sorgu = sorgu.filter(models.IslemGecmisi.ciftlik_id == ciftlik_id)
    silinen = sorgu.delete(synchronize_session=False)
    db.commit()
    return {
        "status": "ok",
        "message": f"Islem gecmisi temizlendi. Silinen kayit: {silinen}",
        "id": "islem-gecmisi-temizle",
        "detay": {"silinen": silinen, "ciftlik_id": ciftlik_id},
    }


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
    hayvanlar = [db_hayvandan_payload(h, include_photo_urls=False) for h in db.query(models.Hayvan).order_by(models.Hayvan.id).all()]
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
