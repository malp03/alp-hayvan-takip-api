import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def prepare_local_appdata():
    tmp = tempfile.mkdtemp(prefix="alp_ui_smoke_")
    os.environ["APPDATA"] = tmp
    cfg_dir = Path(tmp) / "ALP Ziraat" / "HayvanTakip"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "api_ayarlar.json").write_text('{"api_url":""}', encoding="utf-8")
    return tmp


def patch_dialogs():
    from tkinter import filedialog, messagebox

    messagebox.showinfo = lambda *args, **kwargs: None
    messagebox.showwarning = lambda *args, **kwargs: None
    messagebox.showerror = lambda *args, **kwargs: None
    messagebox.askyesno = lambda *args, **kwargs: True
    filedialog.askopenfilename = lambda *args, **kwargs: ""
    return messagebox


def make_animal(**overrides):
    data = {
        "id": "h1",
        "kupe_no": "C001",
        "resmi_kupe_no": "TR001",
        "ciftlik_kupe_no": "C001",
        "dogum_tarihi": "01/01/2024",
        "yas_gun": 500,
        "cins": "D\u00fcve",
        "durum": "D\u00fcve",
        "tohumlamalar": [],
        "dogumlar": [],
        "asi_prosedurler": [],
        "arsivli": False,
        "olu": False,
        "kesildi": False,
        "gebe_mi": False,
    }
    data.update(overrides)
    return data


def main():
    tmp = prepare_local_appdata()
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
        assert app.api_modu is False

        app.hayvanlar = {}
        app.resmi_kupe_no_entry.insert(0, "TR001")
        app.ciftlik_kupe_no_entry.insert(0, "C001")
        app.dogum_tarihi_entry.insert(0, "01/01/2024")
        app.cins_combo.set("D\u00fcve")
        app.hayvan_kaydet()

        assert len(app.hayvanlar) == 1, app.hayvanlar
        created_id = next(iter(app.hayvanlar))
        created = app.hayvanlar[created_id]
        assert created["resmi_kupe_no"] == "TR001"
        assert created["ciftlik_kupe_no"] == "C001"

        app.hayvanlar["arch"] = make_animal(
            id="arch",
            kupe_no="C003",
            resmi_kupe_no="TR003",
            ciftlik_kupe_no="C003",
            dogum_tarihi="01/01/2022",
            yas_gun=1200,
            cins="\u0130nek",
            durum="Ar\u015fivli",
            arsivli=True,
        )

        app.hayvan_listesini_guncelle()
        assert len(app.hayvan_tree.get_children()) == 1
        filter_values = list(app.filtre_combo["values"])
        assert "Aktif" in filter_values and "Ar\u015fivli" in filter_values
        app.filtre_combo.set("Ar\u015fivli")
        app.hayvan_listesini_guncelle()
        assert len(app.hayvan_tree.get_children()) == 1

        app.hayvan_arsivden_cikar("arch", app.root)
        assert not app.hayvanlar["arch"].get("arsivli")

        app.tohumlama_ekranina_hayvanla_git(created_id)
        assert app.tohumlama_hayvan_combo.get() == "C001", app.tohumlama_hayvan_combo.get()
        assert app.tohumlama_tarih_entry.get()

        male = make_animal(id="male", kupe_no="M1", resmi_kupe_no="TRM", ciftlik_kupe_no="M1", cins="Dana")
        assert not app.hayvan_tohumlanabilir_mi(male)
        assert app.foto_data_to_image(None) is None

        print(f"UI smoke OK: {tmp}")
        return 0
    finally:
        app.uygulamayi_kapat()


if __name__ == "__main__":
    raise SystemExit(main())
