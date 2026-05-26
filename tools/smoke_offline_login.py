import os
import sys
import tempfile
from pathlib import Path

from smoke_login import ROOT, start_api


LIVE_ENV_KEYS = ("ALP_API_URL", "DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "ALP_PHOTO_BUCKET")


def prepare_appdata(base_url):
    tmp = tempfile.mkdtemp(prefix="alp_offline_login_")
    for key in LIVE_ENV_KEYS:
        os.environ.pop(key, None)
    os.environ["APPDATA"] = tmp
    os.environ["ALP_SKIP_UPDATE_CHECK"] = "1"
    cfg_dir = Path(tmp) / "ALP Ziraat" / "HayvanTakip"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "api_ayarlar.json").write_text(
        f'{{"api_url":"{base_url}"}}',
        encoding="utf-8",
    )
    return cfg_dir


def main():
    proc, base_url = start_api()
    cfg_dir = prepare_appdata(base_url)

    sys.path.insert(0, str(ROOT))
    import alp_ziraat_hayvan_takip as appmod

    def online_login(self):
        self.api_giris_yap("admin", "admin1234", bu_bilgisayari_tani=False)
        return True

    appmod.HayvanTakipSistemi.api_giris_penceresi = online_login
    appmod.HayvanTakipSistemi.admin_yonetim_merkezi = lambda self: True

    app = appmod.HayvanTakipSistemi()
    try:
        assert app._baslatma_tamam is True
        assert app.api_kullanici and app.api_kullanici.get("kullanici_adi") == "admin"
        assert (cfg_dir / "offline_oturum.json").exists(), "online login did not cache offline credentials"
        assert not (cfg_dir / "taninan_bilgisayar.json").exists(), "test should not rely on remembered device login"
    finally:
        app.uygulamayi_kapat()

    if proc.poll() is None:
        proc.terminate()
        proc.wait(timeout=10)

    def offline_login(self):
        self.api_giris_yap("admin", "admin1234", bu_bilgisayari_tani=False)
        assert self.api_offline_oturum is True
        assert self.api_cevrimdisi is True
        assert self.api_kullanici and self.api_kullanici.get("kullanici_adi") == "admin"
        return True

    appmod.HayvanTakipSistemi.api_giris_penceresi = offline_login
    appmod.HayvanTakipSistemi.admin_yonetim_merkezi = lambda self: True

    app2 = appmod.HayvanTakipSistemi()
    try:
        assert app2._baslatma_tamam is True
        assert app2.api_offline_oturum is True
        assert app2.api_cevrimdisi is True
        print("Offline login smoke OK")
        return 0
    finally:
        app2.uygulamayi_kapat()


if __name__ == "__main__":
    raise SystemExit(main())
