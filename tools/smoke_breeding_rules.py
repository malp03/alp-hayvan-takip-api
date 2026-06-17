import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api import alt_kayit_tarihlerini_kontrol, tohumlama_sonucunu_isle


def test_linked_positive_does_not_reopen_pregnancy():
    veri = {
        "id": "TEST-OLD-POSITIVE",
        "durum": "Sagmal Inek",
        "dogumlar": [{"tarih": "01/06/2026"}],
        "tohumlamalar": [
            {"id": "old-positive", "tarih": "01/09/2025", "gebe_mi": True},
        ],
        "gebe_mi": False,
        "gebelik_tarihi": None,
        "aktif_tohumlama_id": None,
    }

    tohumlama_sonucunu_isle(veri)

    assert veri["gebe_mi"] is False
    assert veri["gebelik_tarihi"] is None
    assert veri["aktif_tohumlama_id"] is None


def test_open_positive_still_sets_active_pregnancy():
    veri = {
        "id": "TEST-OPEN-POSITIVE",
        "durum": "Duve",
        "dogumlar": [],
        "tohumlamalar": [
            {"id": "active-positive", "tarih": "01/06/2026", "gebe_mi": True},
        ],
        "gebe_mi": False,
        "gebelik_tarihi": None,
        "aktif_tohumlama_id": None,
    }

    tohumlama_sonucunu_isle(veri)

    assert veri["gebe_mi"] is True
    assert veri["gebelik_tarihi"] == "01/06/2026"
    assert veri["aktif_tohumlama_id"] == "active-positive"


def test_unknown_historical_births_do_not_crash_validation():
    veri = {
        "id": "TEST-UNKNOWN-BIRTHS",
        "dogum_tarihi": "15/06/2023",
        "cins": "Sagmal Inek",
        "dogumlar": [
            {
                "tarih": "Bilinmiyor",
                "laktasyon_bitis_tarihi": "Bilinmiyor",
                "yavrular": [],
            },
            {
                "tarih": "13/06/2024",
                "laktasyon_bitis_tarihi": None,
                "yavrular": [],
            },
        ],
        "tohumlamalar": [],
    }

    alt_kayit_tarihlerini_kontrol(veri)


def main():
    test_linked_positive_does_not_reopen_pregnancy()
    test_open_positive_still_sets_active_pregnancy()
    test_unknown_historical_births_do_not_crash_validation()
    print("Breeding rule smoke OK")


if __name__ == "__main__":
    main()
