import os
import sys
import tempfile
from pathlib import Path
import tkinter as tk


ROOT = Path(__file__).resolve().parents[1]
LIVE_ENV_KEYS = ("ALP_API_URL", "DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "ALP_PHOTO_BUCKET")


def prepare_appdata():
    tmp = tempfile.mkdtemp(prefix="alp_admin_popup_smoke_")
    for key in LIVE_ENV_KEYS:
        os.environ.pop(key, None)
    os.environ["APPDATA"] = tmp
    cfg_dir = Path(tmp) / "ALP Ziraat" / "HayvanTakip"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "api_ayarlar.json").write_text('{"api_url":""}', encoding="utf-8")
    return tmp


def patch_dialogs():
    from tkinter import messagebox

    messagebox.showinfo = lambda *args, **kwargs: None
    messagebox.showwarning = lambda *args, **kwargs: None
    messagebox.showerror = lambda *args, **kwargs: None
    messagebox.askyesno = lambda *args, **kwargs: False
    return messagebox


def close_toplevels(root):
    names = root.tk.call("winfo", "children", ".")
    for name in names:
        try:
            widget = root.nametowidget(str(name))
        except Exception:
            continue
        if isinstance(widget, tk.Toplevel):
            widget.destroy()


def main():
    tmp = prepare_appdata()
    messagebox = patch_dialogs()
    sys.path.insert(0, str(ROOT))

    import alp_ziraat_hayvan_takip as appmod

    appmod.messagebox.showinfo = messagebox.showinfo
    appmod.messagebox.showwarning = messagebox.showwarning
    appmod.messagebox.showerror = messagebox.showerror
    appmod.messagebox.askyesno = messagebox.askyesno

    app = appmod.HayvanTakipSistemi()
    try:
        app.root.withdraw()
        app.api_kullanici = {"rol": "admin", "kullanici_adi": "admin"}
        app.online_islem_gerekli = lambda *args, **kwargs: True
        app.api_ciftlikleri_yukle = lambda: [
            {"id": "c1", "ad": "Sametin Çiftliği", "aktif": True, "aciklama": "Ana deneme çiftliği"},
            {"id": "c2", "ad": "Varsayılan Çiftlik", "aktif": True, "aciklama": ""},
        ]
        app.api_kullanicilari_yukle = lambda: [
            {"id": "u1", "kullanici_adi": "admin", "rol": "admin", "aktif": True, "ciftlik": None, "ciftlik_id": None},
            {"id": "u2", "kullanici_adi": "samet", "rol": "ciftlik", "aktif": True, "ciftlik": {"ad": "Sametin Çiftliği"}, "ciftlik_id": "c1"},
        ]
        def fake_api_istek(method, path, *args, **kwargs):
            if path == "/api/sistem-durumu":
                return {
                    "database": {"backend": "sqlite", "boyut_mb": 0.2, "limit_mb": 500, "kullanim_yuzde": 0.1},
                    "storage": {"aktif": False, "bucket": "animal-photos", "limit_mb": 1024, "tahmini_foto_kapasitesi": 5000},
                    "kayit_sayilari": {"ciftlik": 2, "kullanici": 2, "hayvan": 3, "aktif_hayvan": 2, "arsivli_hayvan": 1},
                    "fotograflar": {"fotografli_hayvan": 1, "storage_url_adet": 0, "database_base64_adet": 1, "database_base64_mb": 0.1},
                }
            return []

        app.api_istek = fake_api_istek

        def closer():
            close_toplevels(app.root)
            app.root.after(200, closer)

        app.root.after(400, closer)
        app.admin_ciftlik_yonetim_penceresi()
        app.admin_kullanici_yonetim_penceresi()
        app.admin_sistem_durumu_penceresi()
        print(f"Admin popup smoke OK: {tmp}")
        return 0
    finally:
        app.uygulamayi_kapat()


if __name__ == "__main__":
    raise SystemExit(main())
