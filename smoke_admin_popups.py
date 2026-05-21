import os
import sys
import tempfile
from pathlib import Path
import tkinter as tk


ROOT = Path(__file__).resolve().parents[1]


def prepare_appdata():
    tmp = tempfile.mkdtemp(prefix="alp_admin_popup_smoke_")
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
        app.online_islem_gerekli = lambda *args, **kwargs: True
        app.api_ciftlikleri_yukle = lambda: [
            {"id": "c1", "ad": "Sametin Çiftliği", "aktif": True, "aciklama": "Ana deneme çiftliği"},
            {"id": "c2", "ad": "Varsayılan Çiftlik", "aktif": True, "aciklama": ""},
        ]
        app.api_kullanicilari_yukle = lambda: [
            {"id": "u1", "kullanici_adi": "admin", "rol": "admin", "aktif": True, "ciftlik": None, "ciftlik_id": None},
            {"id": "u2", "kullanici_adi": "samet", "rol": "ciftlik", "aktif": True, "ciftlik": {"ad": "Sametin Çiftliği"}, "ciftlik_id": "c1"},
        ]
        app.api_istek = lambda *args, **kwargs: []

        def closer():
            close_toplevels(app.root)
            app.root.after(200, closer)

        app.root.after(400, closer)
        app.admin_ciftlik_yonetim_penceresi()
        app.admin_kullanici_yonetim_penceresi()
        print(f"Admin popup smoke OK: {tmp}")
        return 0
    finally:
        app.uygulamayi_kapat()


if __name__ == "__main__":
    raise SystemExit(main())
