import os
import sys
import tempfile
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk


ROOT = Path(__file__).resolve().parents[1]


def walk_widgets(widget):
    widgets = [widget]
    try:
        children = widget.winfo_children()
    except tk.TclError:
        children = []
    for child in children:
        widgets.extend(walk_widgets(child))
    return widgets


def prepare_appdata():
    tmp = tempfile.mkdtemp(prefix="alp_login_responsive_")
    os.environ["APPDATA"] = tmp
    cfg_dir = Path(tmp) / "ALP Ziraat" / "HayvanTakip"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "api_ayarlar.json").write_text(
        '{"api_url":"http://127.0.0.1:9"}',
        encoding="utf-8",
    )
    return tmp


def main():
    prepare_appdata()
    sys.path.insert(0, str(ROOT))

    import alp_ziraat_hayvan_takip as appmod

    original_login = appmod.HayvanTakipSistemi.api_giris_penceresi
    probes = {"count": 0}

    def fake_api_login(self, kullanici_adi, sifre, bu_bilgisayari_tani=False):
        time.sleep(1.4)
        self.api_token = "responsive-smoke-token"
        self.api_kullanici = {
            "id": "u1",
            "kullanici_adi": kullanici_adi,
            "rol": "ciftlik",
            "ciftlik_id": "farm1",
            "ciftlik_adi": "Smoke Ciftlik",
        }
        self.api_cevrimdisi = False
        self.api_offline_oturum = False
        return True

    def auto_login(self):
        attempts = {"count": 0}

        def probe():
            probes["count"] += 1
            if not getattr(self, "api_token", None):
                self._track_after(self.root, 100, probe)

        def fill_and_submit():
            attempts["count"] += 1
            entries = [w for w in walk_widgets(self.root) if isinstance(w, ttk.Entry)]
            if len(entries) < 2:
                if attempts["count"] < 20:
                    self._track_after(self.root, 100, fill_and_submit)
                return
            entries[0].insert(0, "admin")
            entries[1].insert(0, "admin1234")
            for widget in walk_widgets(self.root):
                if isinstance(widget, tk.Canvas) and hasattr(widget, "text_item"):
                    try:
                        text = widget.itemcget(widget.text_item, "text")
                    except tk.TclError:
                        continue
                    if text == "Giriş":
                        getattr(widget, "command", lambda: widget.event_generate("<Button-1>", x=8, y=8))()
                        self._track_after(self.root, 250, probe)
                        return

        self._track_after(self.root, 250, fill_and_submit)
        return original_login(self)

    appmod.HayvanTakipSistemi.taninan_bilgisayar_giris_dene = lambda self: False
    appmod.HayvanTakipSistemi.api_giris_yap = fake_api_login
    appmod.HayvanTakipSistemi.api_giris_penceresi = auto_login
    appmod.HayvanTakipSistemi.veri_yukle = lambda self: {}

    app = appmod.HayvanTakipSistemi()
    try:
        assert app._baslatma_tamam is True
        assert probes["count"] >= 5, f"login window did not stay responsive: probes={probes['count']}"
        print(f"Login responsiveness smoke OK: probes={probes['count']}")
        return 0
    finally:
        app.uygulamayi_kapat()


if __name__ == "__main__":
    raise SystemExit(main())
