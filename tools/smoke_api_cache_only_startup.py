import json
import os
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIVE_ENV_KEYS = ("ALP_API_URL", "DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "ALP_PHOTO_BUCKET")


def prepare_appdata():
    tmp = tempfile.mkdtemp(prefix="alp_api_cache_startup_")
    for key in LIVE_ENV_KEYS:
        os.environ.pop(key, None)
    os.environ["APPDATA"] = tmp
    os.environ["ALP_SKIP_UPDATE_CHECK"] = "1"
    cfg_dir = Path(tmp) / "ALP Ziraat" / "HayvanTakip"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "api_ayarlar.json").write_text(
        json.dumps({"api_url": "http://127.0.0.1:9"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (cfg_dir / "hayvan_verileri.json").write_text(
        json.dumps(
            {
                "CACHE1": {
                    "id": "CACHE1",
                    "kupe_no": "CACHE1",
                    "ciftlik_kupe_no": "CACHE1",
                    "dogum_tarihi": "01/01/2024",
                    "cins": "Düve",
                    "tohumlamalar": [],
                    "dogumlar": [],
                    "asi_prosedurler": [],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def wait_for_startup(app, timeout=8):
    start = time.time()
    while time.time() - start < timeout:
        app.root.update()
        if getattr(app, "_baslangic_hazirligi_tamam", False):
            return
        time.sleep(0.02)
    raise AssertionError("startup did not complete")


def main():
    prepare_appdata()
    sys.path.insert(0, str(ROOT))

    import alp_ziraat_hayvan_takip as appmod

    db_called = {"value": False}

    def fake_login(self):
        self.api_token = "cache-only-token"
        self.api_kullanici = {
            "id": "u1",
            "kullanici_adi": "cache-user",
            "rol": "ciftlik",
            "ciftlik_id": "farm1",
            "ciftlik_adi": "Cache Farm",
        }
        return True

    def fail_if_db_used(self):
        db_called["value"] = True
        raise AssertionError("API startup cache should not read local SQLite")

    appmod.HayvanTakipSistemi.api_giris_penceresi = fake_login
    appmod.HayvanTakipSistemi.veritabani_hazirla = fail_if_db_used
    appmod.messagebox.showwarning = lambda *args, **kwargs: None
    appmod.messagebox.showerror = lambda *args, **kwargs: None

    app = appmod.HayvanTakipSistemi()
    try:
        wait_for_startup(app)
        assert db_called["value"] is False
        assert set(app.hayvanlar.keys()) == {"CACHE1"}, app.hayvanlar.keys()
        print("API cache-only startup smoke OK")
        return 0
    finally:
        app.uygulamayi_kapat()


if __name__ == "__main__":
    raise SystemExit(main())
