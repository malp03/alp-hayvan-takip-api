import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def prepare_appdata():
    tmp = tempfile.mkdtemp(prefix="alp_update_smoke_")
    os.environ["APPDATA"] = tmp
    os.environ["ALP_SKIP_UPDATE_CHECK"] = "1"
    cfg_dir = Path(tmp) / "ALP Ziraat" / "HayvanTakip"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "api_ayarlar.json").write_text('{"api_url":""}', encoding="utf-8")
    return tmp


def main():
    prepare_appdata()
    sys.path.insert(0, str(ROOT))

    import alp_ziraat_hayvan_takip as appmod

    assert appmod.surum_daha_yeni_mi("v1.10.0", "1.9.0")
    assert not appmod.surum_daha_yeni_mi("v1.9.0", "1.9.0")
    assert not appmod.surum_daha_yeni_mi("v1.8.9", "1.9.0")

    app = appmod.HayvanTakipSistemi()
    try:
        release = {
            "tag_name": f"v{appmod.APP_VERSION}",
            "name": "Smoke Release",
            "body": "- Smoke değişiklik notu",
            "html_url": "https://example.invalid/release",
            "assets": [
                {"name": "source.zip", "browser_download_url": "https://example.invalid/source.zip"},
                {"name": appmod.UPDATE_SETUP_ASSET, "browser_download_url": "https://example.invalid/setup.exe"},
            ],
        }
        assert app.guncelleme_asset_bul(release)["name"] == appmod.UPDATE_SETUP_ASSET
        assert not app.guncelleme_var_mi(release)
        newer = dict(release, tag_name="v9.9.9")
        assert app.guncelleme_var_mi(newer)

        app.guncelleme_notu_kaydet(release)
        note = app.guncelleme_notu_yukle()
        assert note and note["title"] == "Smoke Release"
        app.guncelleme_notu_temizle()
        assert app.guncelleme_notu_yukle() is None
        print("Update smoke OK")
        return 0
    finally:
        app.uygulamayi_kapat()


if __name__ == "__main__":
    raise SystemExit(main())
