import json
import os
import sys
import tempfile
from pathlib import Path
import tkinter as tk

from smoke_api import request
from smoke_login import ROOT, start_api, walk_widgets


LIVE_ENV_KEYS = ("ALP_API_URL", "DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "ALP_PHOTO_BUCKET")


def prepare_appdata(base_url, device_token, kullanici):
    tmp = tempfile.mkdtemp(prefix="alp_admin_panel_logout_")
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

        original_admin = appmod.HayvanTakipSistemi.admin_yonetim_merkezi
        admin_calls = {"count": 0}
        login_prompt = {"count": 0}

        def click_admin_logout(self):
            for widget in walk_widgets(self.root):
                if not isinstance(widget, tk.Button):
                    continue
                try:
                    text = widget.cget("text")
                except tk.TclError:
                    continue
                normalized = text.lower()
                if ("çıkış" in normalized or "cikis" in normalized) and "yap" in normalized:
                    widget.invoke()
                    return
            self._track_after(self.root, 100, lambda: click_admin_logout(self))

        def admin_with_logout_click(self):
            admin_calls["count"] += 1
            if admin_calls["count"] > 1:
                self._login_yeniden_iste = False
                return False
            self._track_after(self.root, 500, lambda: click_admin_logout(self))
            return original_admin(self)

        def manual_login_prompt(self):
            login_prompt["count"] += 1
            assert not Path(self.remembered_session_file).exists(), "remembered session was not cleared"
            assert getattr(self, "api_token", None) is None, "api token should be cleared before login prompt"
            return False

        appmod.HayvanTakipSistemi.admin_yonetim_merkezi = admin_with_logout_click
        appmod.HayvanTakipSistemi.api_giris_penceresi = manual_login_prompt

        app = appmod.HayvanTakipSistemi()
        try:
            assert admin_calls["count"] == 1, "admin panel reopened after logout"
            assert login_prompt["count"] == 1, "admin logout should force manual login"
            assert not (cfg_dir / "taninan_bilgisayar.json").exists()
            print("Admin panel logout smoke OK")
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
