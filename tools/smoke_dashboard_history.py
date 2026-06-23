import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "alp_ziraat_hayvan_takip.py"
sys.path.insert(0, str(ROOT))


def load_app_class():
    spec = importlib.util.spec_from_file_location("alp_ziraat_hayvan_takip", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.HayvanTakipSistemi


def main():
    App = load_app_class()
    app = object.__new__(App)

    app.api_modu = True
    app.api_son_islemler = []
    app.api_son_islemler_yuklendi = False
    app.islem_gecmisi = [
        {"zaman": "24/06/2026 01:00:00", "aciklama": "Eski lokal kayit"},
    ]
    kayitlar, bos_mesaj = app.dashboard_son_islem_kayitlari()
    assert kayitlar == []
    assert "API" in bos_mesaj

    api_kayitlari = app.api_islem_gecmisi_dashboarda_cevir(
        [
            {
                "zaman": "24/06/2026 01:55:43",
                "detay": "Hayvan guncellendi",
                "islem_tipi": "hayvan_guncelle",
            }
        ]
    )
    assert api_kayitlari == [{"zaman": "24/06/2026 01:55:43", "aciklama": "Hayvan guncellendi"}]

    app.api_son_islemler = api_kayitlari
    app.api_son_islemler_yuklendi = True
    kayitlar, _ = app.dashboard_son_islem_kayitlari()
    assert kayitlar[0]["aciklama"] == "Hayvan guncellendi"

    app.api_modu = False
    app.islem_gecmisi = [
        {"zaman": "03/06/2026 01:55:43", "aciklama": "Eski"},
        {"zaman": "24/06/2026 01:55:43", "aciklama": "Yeni"},
    ]
    kayitlar, _ = app.dashboard_son_islem_kayitlari()
    assert kayitlar[0]["aciklama"] == "Yeni"

    print("Dashboard history smoke passed.")


if __name__ == "__main__":
    raise SystemExit(main())
