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
