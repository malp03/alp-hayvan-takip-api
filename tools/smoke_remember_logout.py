import json
import os
import sys
import tempfile
from pathlib import Path

from smoke_api import request
from smoke_login import ROOT, start_api


LIVE_ENV_KEYS = ("ALP_API_URL", "DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "ALP_PHOTO_BUCKET")


def prepare_appdata(base_url, device_token, kullanici):
    tmp = tempfile.mkdtemp(prefix="alp_remember_logout_")
    for key in LIVE_ENV_KEYS:
        os.environ.pop(key, None)
    os.environ["APPDATA"] = tmp
    os.environ["ALP_SKIP_UPDATE_CHECK"] = "1"
    cfg_dir = Path(tmp) / "ALP Ziraat" / "HayvanTakip"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "api_ayarlar.json").write_text(
        json.dumps({"api_url": base_url}, ensure_ascii=False),
        encoding="utf-8",
    )
    (cfg_dir / "taninan_bilgisayar.json").write_text(
        json.dumps(
            {
                "api_url": base_url,
                "device_token": device_token,
                "kullanici": kullanici,
                "kayit_zamani": "01/01/2026 00:00:00",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return cfg_dir


def main():
    proc, base_url = start_api()
    try:
        _, login = request(
            base_url,
            "POST",
            "/api/auth/login",
            {"kullanici_adi": "admin", "sifre": "admin1234"},
            expected=200,
        )
        token = login["access_token"]
        _, device = request(base_url, "POST", "/api/auth/device-token", {}, token=token, expected=200)
        cfg_dir = prepare_appdata(base_url, device["device_token"], login["kullanici"])

        sys.path.insert(0, str(ROOT))
        import alp_ziraat_hayvan_takip as appmod

        login_prompt = {"count": 0}

        def fail_if_initial_login_prompt(self):
            login_prompt["count"] += 1
            assert not Path(self.remembered_session_file).exists(), "remembered session was not cleared on logout"
            assert getattr(self, "api_token", None) is None, "api token should be cleared before login prompt"
            return False

        appmod.HayvanTakipSistemi.admin_yonetim_merkezi = lambda self: True
        appmod.HayvanTakipSistemi.api_giris_penceresi = fail_if_initial_login_prompt

        app = appmod.HayvanTakipSistemi()
        try:
            assert app._baslatma_tamam is True
            assert login_prompt["count"] == 0, "remembered device login did not happen on startup"
            assert app.api_kullanici and app.api_kullanici.get("rol") == "admin"
            assert getattr(app, "_hatirlanan_oturum_cache_ile_acildi", False) is True
            assert getattr(app, "api_offline_oturum", False) is True
            assert app.root.winfo_width() >= 1000, "remembered startup left app at splash width"
            assert app.root.winfo_height() >= 700, "remembered startup left app at splash height"
            assert (cfg_dir / "taninan_bilgisayar.json").exists()
            app.oturumu_kapat_ve_login(onay_iste=False)
            assert login_prompt["count"] == 1, "logout should force manual login instead of remembered auto-login"
            assert not (cfg_dir / "taninan_bilgisayar.json").exists()
            print("Remembered logout smoke OK")
            return 0
        finally:
            app.uygulamayi_kapat()
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except Exception:
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
