from datetime import datetime, timedelta
import json
import os
from typing import Any, Dict, Iterable, List, Optional
import uuid

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import or_
from sqlalchemy.orm import Session
import uvicorn

from database import Base, engine, ensure_postgres_security, ensure_sqlite_schema, get_db
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
ensure_postgres_security()

TARIH_FORMATI = "%d/%m/%Y"
ZAMAN_FORMATI = "%d/%m/%Y %H:%M:%S"
ERKEK_CINSLER = {"Erkek Buzağı", "Dana"}
DISI_CINSLER = {"Dişi Buzağı", "Düve", "Sağmal İnek", "Kuru İnek"}


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
    parse_tarih(sonuc.get("tarih"), "Tohumlama tarihi", zorunlu=True)
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
    if sonuc.get("laktasyon_bitis_tarihi"):
        parse_tarih(sonuc.get("laktasyon_bitis_tarihi"), "Laktasyon bitiş tarihi")
    yavrular = []
    for yavru in sonuc.get("yavrular") or []:
        yavrular.append(
            {
                **dict(yavru),
                "kupe": metin(yavru.get("kupe"), upper=True),
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


def hayvan_bul(db: Session, ref: str) -> models.Hayvan:
    ref_metin = metin(ref)
    hayvan = db.query(models.Hayvan).filter(models.Hayvan.id == ref_metin).first()
    if hayvan:
        return hayvan
    ref_kupe = ref_metin.upper()
    hayvan = (
        db.query(models.Hayvan)
        .filter(
            or_(
                models.Hayvan.resmi_kupe_no == ref_kupe,
                models.Hayvan.ciftlik_kupe_no == ref_kupe,
            )
        )
        .first()
    )
    if not hayvan:
        raise HTTPException(status_code=404, detail="Hayvan bulunamadı.")
    return hayvan


def kupe_cakismasi_kontrol(db: Session, veri: Dict[str, Any], *, haric_id: Optional[str] = None) -> None:
    kupeler = [k for k in {veri.get("resmi_kupe_no"), veri.get("ciftlik_kupe_no")} if k]
    if not kupeler:
        raise HTTPException(status_code=400, detail="En az bir küpe numarası girilmelidir.")
    for kupe in kupeler:
        mevcut = (
            db.query(models.Hayvan)
            .filter(
                or_(
                    models.Hayvan.resmi_kupe_no == kupe,
                    models.Hayvan.ciftlik_kupe_no == kupe,
                )
            )
            .first()
        )
        if mevcut and mevcut.id != haric_id:
            raise HTTPException(status_code=400, detail=f"{kupe} küpe numarası zaten kayıtlı.")


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


def response_kaydet(db: Session, db_hayvan: models.Hayvan, veri: Dict[str, Any]) -> Dict[str, Any]:
    veri["son_guncelleme"] = simdi()
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


@app.get("/")
def read_root():
    return {"status": "ok", "message": "ALP Ziraat Hayvan Takip API çalışıyor."}


@app.get("/api/health")
def health():
    return {"status": "ok", "database": "connected"}


@app.get("/api/hayvanlar", response_model=List[schemas.HayvanResponse])
def get_hayvanlar(
    skip: int = 0,
    limit: int = Query(default=100, le=1000),
    q: Optional[str] = None,
    arsiv_dahil: bool = True,
    db: Session = Depends(get_db),
):
    sorgu = db.query(models.Hayvan)
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
def get_hayvan(hayvan_ref: str, db: Session = Depends(get_db)):
    return db_hayvandan_payload(hayvan_bul(db, hayvan_ref))


@app.post("/api/hayvanlar", response_model=schemas.HayvanResponse, status_code=status.HTTP_201_CREATED)
def create_hayvan(hayvan: schemas.HayvanCreate, db: Session = Depends(get_db)):
    veri = normalize_hayvan(model_verisi(hayvan))
    if db.query(models.Hayvan).filter(models.Hayvan.id == veri["id"]).first():
        raise HTTPException(status_code=400, detail="Bu id ile kayıt zaten var.")
    kupe_cakismasi_kontrol(db, veri)
    db_hayvan = models.Hayvan(id=veri["id"])
    db.add(db_hayvan)
    db_hayvana_yaz(db, db_hayvan, veri)
    db.commit()
    db.refresh(db_hayvan)
    return db_hayvandan_payload(db_hayvan)


@app.put("/api/hayvanlar/{hayvan_ref}", response_model=schemas.HayvanResponse)
@app.patch("/api/hayvanlar/{hayvan_ref}", response_model=schemas.HayvanResponse)
def update_hayvan(hayvan_ref: str, hayvan: schemas.HayvanUpdate, db: Session = Depends(get_db)):
    db_hayvan = hayvan_bul(db, hayvan_ref)
    mevcut = db_hayvandan_payload(db_hayvan)
    guncelleme = model_verisi(hayvan, exclude_unset=True)
    guncelleme.pop("id", None)
    mevcut.update(guncelleme)
    mevcut["id"] = db_hayvan.id
    veri = normalize_hayvan(mevcut, hayvan_id=db_hayvan.id)
    kupe_cakismasi_kontrol(db, veri, haric_id=db_hayvan.id)
    return response_kaydet(db, db_hayvan, veri)


@app.delete("/api/hayvanlar/{hayvan_ref}", response_model=schemas.IslemSonucResponse)
def delete_hayvan(
    hayvan_ref: str,
    kalici: bool = False,
    db: Session = Depends(get_db),
):
    db_hayvan = hayvan_bul(db, hayvan_ref)
    if kalici:
        silinen_id = db_hayvan.id
        db.delete(db_hayvan)
        db.commit()
        return {"status": "ok", "message": "Hayvan kalıcı olarak silindi.", "id": silinen_id}

    veri = db_hayvandan_payload(db_hayvan)
    veri["arsivli"] = True
    veri["arsiv_tarihi"] = bugun()
    response_kaydet(db, db_hayvan, veri)
    return {"status": "ok", "message": "Hayvan arşive alındı.", "id": db_hayvan.id}


@app.post(
    "/api/hayvanlar/{hayvan_ref}/tohumlamalar",
    response_model=schemas.TohumlamaResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_tohumlama(hayvan_ref: str, tohumlama: schemas.TohumlamaCreate, db: Session = Depends(get_db)):
    db_hayvan = hayvan_bul(db, hayvan_ref)
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
):
    db_hayvan = hayvan_bul(db, hayvan_ref)
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
def delete_tohumlama(hayvan_ref: str, tohumlama_ref: str, db: Session = Depends(get_db)):
    db_hayvan = hayvan_bul(db, hayvan_ref)
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
def create_asi(hayvan_ref: str, asi: schemas.AsiProsedurCreate, db: Session = Depends(get_db)):
    db_hayvan = hayvan_bul(db, hayvan_ref)
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
):
    db_hayvan = hayvan_bul(db, hayvan_ref)
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
def delete_asi(hayvan_ref: str, asi_ref: str, db: Session = Depends(get_db)):
    db_hayvan = hayvan_bul(db, hayvan_ref)
    veri = db_hayvandan_payload(db_hayvan)
    silinen = nested_kayit_sil(veri.setdefault("asi_prosedurler", []), asi_ref, "Aşı/prosedür")
    response_kaydet(db, db_hayvan, veri)
    return {"status": "ok", "message": "Aşı/prosedür kaydı silindi.", "id": silinen.get("id")}


@app.post(
    "/api/hayvanlar/{hayvan_ref}/dogumlar",
    response_model=schemas.DogumResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_dogum(hayvan_ref: str, dogum: schemas.DogumCreate, db: Session = Depends(get_db)):
    db_hayvan = hayvan_bul(db, hayvan_ref)
    anne = db_hayvandan_payload(db_hayvan)
    yeni = normalize_dogum(model_verisi(dogum), yeni=True)
    dogum_tarihi = parse_tarih(yeni.get("tarih"), "Doğum tarihi", zorunlu=True)
    anne_dogum_tarihi = parse_tarih(anne.get("dogum_tarihi"), "Anne doğum tarihi")
    if anne_dogum_tarihi and dogum_tarihi < anne_dogum_tarihi:
        raise HTTPException(status_code=400, detail="Doğum tarihi annenin doğum tarihinden önce olamaz.")
    gebelik_tarihi = parse_tarih(anne.get("gebelik_tarihi"), "Gebelik tarihi")
    if gebelik_tarihi and dogum_tarihi < gebelik_tarihi:
        raise HTTPException(status_code=400, detail="Doğum tarihi gebelik başlangıcından önce olamaz.")

    yavru_kupeleri = [y["kupe"] for y in yeni.get("yavrular") or [] if y.get("kupe")]
    if len(yavru_kupeleri) != len(set(yavru_kupeleri)):
        raise HTTPException(status_code=400, detail="Yavru küpe numaraları kendi içinde tekrar edemez.")
    for kupe in yavru_kupeleri:
        try:
            hayvan_bul(db, kupe)
        except HTTPException as hata:
            if hata.status_code == 404:
                continue
            raise
        raise HTTPException(status_code=400, detail=f"{kupe} yavru küpe numarası zaten kayıtlı.")

    kaydedilen_yavrular = []
    for yavru in yeni.get("yavrular") or []:
        yavru_id = yeni_id()
        yavru_kupe = yavru.get("kupe") or yavru_id
        yavru_veri = normalize_hayvan(
            {
                "id": yavru_id,
                "kupe_no": yavru_kupe,
                "resmi_kupe_no": yavru_kupe if yavru.get("kupe") else "",
                "ciftlik_kupe_no": "",
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
        kaydedilen_yavrular.append({"kupe": yavru_kupe, "cins": yavru_veri["cins"]})

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
def update_dogum(hayvan_ref: str, dogum_ref: str, dogum: schemas.DogumUpdate, db: Session = Depends(get_db)):
    db_hayvan = hayvan_bul(db, hayvan_ref)
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
def delete_dogum(hayvan_ref: str, dogum_ref: str, db: Session = Depends(get_db)):
    db_hayvan = hayvan_bul(db, hayvan_ref)
    veri = db_hayvandan_payload(db_hayvan)
    silinen = nested_kayit_sil(veri.setdefault("dogumlar", []), dogum_ref, "Doğum")
    response_kaydet(db, db_hayvan, veri)
    return {"status": "ok", "message": "Doğum/laktasyon kaydı silindi.", "id": silinen.get("id")}


@app.get("/api/uyarilar", response_model=List[schemas.UyariResponse])
def get_uyarilar(db: Session = Depends(get_db)):
    hayvanlar = [db_hayvandan_payload(h) for h in db.query(models.Hayvan).all()]
    return uyarilari_hesapla(hayvanlar)


@app.get("/api/raporlar/ozet", response_model=schemas.RaporOzetResponse)
def get_rapor_ozet(db: Session = Depends(get_db)):
    hayvanlar = [db_hayvandan_payload(h) for h in db.query(models.Hayvan).all()]
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


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
