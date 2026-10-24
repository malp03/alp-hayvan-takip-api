import copy
from datetime import datetime


def otomatik_cins_guncelle(mevcut_cins, yas_gun):
    if mevcut_cins == "Dişi Buzağı" and yas_gun >= 180:
        return "Düve"
    if mevcut_cins == "Erkek Buzağı" and yas_gun >= 180:
        return "Dana"
    return mevcut_cins


def durum_hesapla(cins, yas_gun):
    if "Buzağı" in (cins or ""):
        return "Buzağı"
    if cins == "Dana":
        return "Dana"
    if cins == "Düve":
        return "Düve"
    if cins == "Sağmal İnek":
        return "Sağmal İnek"
    if cins == "Kuru İnek":
        return "Kuru İnek"
    return "Bilinmiyor"


def uyari_esigi(kalan_gun):
    if kalan_gun <= 0:
        return "gecikti"
    if kalan_gun <= 7:
        return "7gun"
    if kalan_gun <= 30:
        return "30gun"
    if kalan_gun <= 60:
        return "60gun"
    return None


def tarih_oku(deger):
    try:
        return datetime.strptime(str(deger or ""), "%d/%m/%Y").date()
    except (ValueError, TypeError):
        return None


def son_dogum_kaydi(veri, sadece_acik=False):
    kayitlar = [(tarih_oku(d.get("tarih")), index, d)
                for index, d in enumerate(veri.get("dogumlar") or [])
                if isinstance(d, dict) and tarih_oku(d.get("tarih"))
                and (not sadece_acik or not str(d.get("laktasyon_bitis_tarihi") or "").strip())]
    return max(kayitlar, key=lambda item: item[:2])[2] if kayitlar else None


def normalize_yasam_dongusu(veri, bugun=None):
    bugun = bugun or datetime.now().date()
    sonuc = dict(veri)
    aktif = not any(sonuc.get(k) for k in ("satildi", "olu", "kesildi", "arsivli"))
    if not aktif:
        sonuc.update(gebe_mi=False, gebelik_tarihi=None, aktif_tohumlama_id=None)
    dogum = tarih_oku(sonuc.get("dogum_tarihi"))
    if dogum:
        yas = max((bugun - dogum).days, 0)
        sonuc.update(yas_gun=yas, yas_yil=yas // 365, yas_ay=(yas % 365) // 30)
        if aktif and not sonuc.get("gebe_mi"):
            eski = sonuc.get("cins")
            yeni = otomatik_cins_guncelle(eski, yas)
            sonuc["cins"] = yeni
            if yeni != eski and sonuc.get("durum") in (None, "", "Buzağı", eski):
                sonuc["durum"] = yeni
                sonuc["durum_notu"] = yeni
    cikislar = [tarih_oku(sonuc.get(k)) for k in
                ("satis_tarihi", "olum_tarihi", "kesim_tarihi", "arsiv_tarihi")]
    for k in ("satis_bilgisi", "kesim_bilgisi"):
        cikislar.append(tarih_oku((sonuc.get(k) or {}).get("tarih")))
    cikislar = [t for t in cikislar if t and t <= bugun]
    if not aktif and cikislar:
        bitis = min(cikislar)
        dogumlar = []
        for dogum in sonuc.get("dogumlar") or []:
            kayit = dict(dogum)
            baslangic = tarih_oku(kayit.get("tarih"))
            if baslangic and baslangic <= bitis and not str(kayit.get("laktasyon_bitis_tarihi") or "").strip():
                kayit["laktasyon_bitis_tarihi"] = bitis.strftime("%d/%m/%Y")
            dogumlar.append(kayit)
        sonuc["dogumlar"] = dogumlar
    return sonuc


def laktasyon_ozeti(veri, bugun=None):
    bugun = bugun or datetime.now().date()
    veri = normalize_yasam_dongusu(veri, bugun)
    son = son_dogum_kaydi(veri)
    aktif = not any(veri.get(k) for k in ("satildi", "olu", "kesildi", "arsivli"))
    sagmal = veri.get("cins") == "Sağmal İnek" or veri.get("durum") == "Sağmal İnek"
    toplam, aktif_sagim, son_sagim = 0, "-", "-"
    for kayit in veri.get("dogumlar") or []:
        baslangic = tarih_oku(kayit.get("tarih"))
        if not baslangic:
            continue
        bitis_metni = str(kayit.get("laktasyon_bitis_tarihi") or "").strip()
        bitis = tarih_oku(bitis_metni)
        if not bitis_metni and kayit is son and aktif and sagmal:
            bitis = bugun
            aktif_sagim = f"{max((bitis - baslangic).days, 0)} gün"
        if bitis:
            gun = max((min(bitis, bugun) - baslangic).days, 0)
            toplam += gun
            if kayit is son:
                son_sagim = f"{gun} gün"
    return {"laktasyon_sayisi": len(veri.get("dogumlar") or []),
            "toplam_sagim": toplam, "aktif_sagim": aktif_sagim,
            "aktif_sagim_gun": int(aktif_sagim.split()[0]) if aktif_sagim != "-" else None,
            "son_dogum": son.get("tarih") if son else "-", "son_sagim": son_sagim}


def laktasyon_kayitlarini_birlestir(mevcut, istenen):
    if not mevcut:
        return copy.deepcopy(istenen)
    if len(istenen) < len(mevcut):
        raise ValueError("Laktasyon sayisi mevcut dogum kayitlarindan az olamaz. Gecmisi ilgili kayittan duzenleyin.")
    kayitlar = copy.deepcopy(mevcut)
    son = son_dogum_kaydi({"dogumlar": kayitlar}) or kayitlar[-1]
    son["tarih"] = istenen[-1]["tarih"]
    for _ in range(len(istenen) - len(mevcut)):
        kayitlar.insert(0, {"tarih": "Bilinmiyor", "yavrular": [],
                           "laktasyon_bitis_tarihi": "Bilinmiyor",
                           "not": "Gecmis kayit, sure bilinmiyor"})
    return kayitlar
