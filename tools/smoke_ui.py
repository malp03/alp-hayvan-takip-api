import os
import sys
import tempfile
import time
from pathlib import Path
import tkinter as tk


ROOT = Path(__file__).resolve().parents[1]
LIVE_ENV_KEYS = ("ALP_API_URL", "DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "ALP_PHOTO_BUCKET")
SAMPLE_PHOTOS = [
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEElEQVR4nGP8zwACTGCSAQANHQEDgslx/wAAAABJRU5ErkJggg==",
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAE0lEQVR4nGNk+M/AwMDABCIYGAAMHgEDrNiLpwAAAABJRU5ErkJggg==",
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGNkYPjPwMDAxAAGAAsfAQMU4wsAAAAAAElFTkSuQmCC",
]


def prepare_local_appdata():
    tmp = tempfile.mkdtemp(prefix="alp_ui_smoke_")
    for key in LIVE_ENV_KEYS:
        os.environ.pop(key, None)
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
    filedialog.askopenfilenames = lambda *args, **kwargs: ()
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
        "irk": "Simental",
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


def widget_texts(widget):
    texts = []
    try:
        value = widget.cget("text")
        if value:
            texts.append(str(value))
    except tk.TclError:
        pass
    except Exception:
        pass
    for child in widget.winfo_children():
        texts.extend(widget_texts(child))
    return texts


def widgets_by_class(widget, cls):
    bulunan = []
    if isinstance(widget, cls):
        bulunan.append(widget)
    for child in widget.winfo_children():
        bulunan.extend(widgets_by_class(child, cls))
    return bulunan


def wait_for_startup(app, timeout=8):
    start = time.time()
    while time.time() - start < timeout:
        app.root.update()
        if getattr(app, "_baslangic_hazirligi_tamam", False):
            return
        time.sleep(0.02)
    raise AssertionError("startup did not complete")


def assert_main_layout(app):
    app.root.geometry("1280x820")
    app.root.update_idletasks()
    app.root.update()
    assert hasattr(app, "custom_tab_bar"), "custom tab bar missing"
    assert hasattr(app, "notebook"), "notebook missing"
    assert hasattr(app, "rapor_scroll_sayfa"), "report scroll page missing"
    assert hasattr(app, "asi_scroll_sayfa"), "vaccine/procedure scroll page missing"
    assert hasattr(app, "asi_tree_scroll_v") and hasattr(app, "asi_tree_scroll_h"), "vaccine/procedure table scrollbars missing"
    assert hasattr(app, "dashboard_ciftlik_label"), "dashboard farm/status label missing"
    assert hasattr(app, "dashboard_risk_label"), "dashboard risk label missing"
    assert len(getattr(app, "tab_buttons", [])) >= 7, "main tabs missing"
    dashboard_text = "\n".join(widget_texts(app.dashboard_frame))
    for expected in ("Öncelik Özeti", "Yaklaşan İşler", "Son İşlemler"):
        assert expected in dashboard_text, expected
    tab_y = app.custom_tab_bar.winfo_rooty()
    notebook_y = app.notebook.winfo_rooty()
    assert tab_y < notebook_y, f"tab bar is below content: tab_y={tab_y}, notebook_y={notebook_y}"
    bar_width = app.custom_tab_bar.winfo_width()
    for button in app.tab_buttons:
        assert button.winfo_x() + button.winfo_width() <= bar_width + 2, "tab button overflows custom tab bar"

    assert hasattr(app, "header_action_group"), "header action group missing"
    assert hasattr(app, "header_action_fallback"), "header action fallback missing"
    assert app.header_action_fallback.winfo_ismapped(), "header actions should wrap below header at 1280px"

    app.root.geometry("1540x820")
    app.root.update_idletasks()
    app.root.update()
    assert app.header_action_group.winfo_ismapped(), "header actions should stay top-right on wide screens"
    assert not app.header_action_fallback.winfo_ismapped(), "fallback action row should hide on wide screens"


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
        wait_for_startup(app)
        assert_main_layout(app)
        for entry_name in ("dogum_tarihi_entry", "tohumlama_tarih_entry"):
            entry = getattr(app, entry_name)
            entry.delete(0, tk.END)
            entry.insert(0, "01/01/2026")
            app.tarih_secici_ac(entry)
            app.root.update_idletasks()
            app.root.update()
            takvimler = [
                child for child in app.root.winfo_children()
                if isinstance(child, tk.Toplevel) and "Tarih" in child.title()
            ]
            assert takvimler, f"date picker popup not opened for {entry_name}"
            takvim_text = "\n".join(widget_texts(takvimler[-1]))
            assert "Tarih" in takvim_text and "Seçili tarih" in takvim_text and "Ocak 2026" in takvim_text, takvim_text
            day_buttons = [child for child in widgets_by_class(takvimler[-1], tk.Button) if child.cget("text") == "15"]
            assert day_buttons, f"date picker day button not found for {entry_name}"
            day_buttons[0].invoke()
            app.root.update_idletasks()
            app.root.update()
            assert entry.get() == "15/01/2026", entry.get()
            assert entry.winfo_ismapped(), f"{entry_name} selected date field is not visible"
            assert entry.master.winfo_ismapped(), f"{entry_name} date field container is not visible"
            assert entry.winfo_width() >= 80, f"{entry_name} selected date field is too narrow: {entry.winfo_width()}"

        app.root.withdraw()
        assert app.api_modu is False

        app.hayvanlar = {}
        for entry in (app.resmi_kupe_no_entry, app.ciftlik_kupe_no_entry, app.dogum_tarihi_entry, app.anne_kupe_entry):
            entry.delete(0, tk.END)
        app.resmi_kupe_no_entry.insert(0, "TR987654321")
        app.ciftlik_kupe_no_entry.insert(0, "CF99123456")
        app.dogum_tarihi_entry.insert(0, "01/01/2024")
        app.cins_combo.set("D\u00fcve")
        app.irk_combo.set("Simental")
        app.yeni_hayvan_foto_datas = list(SAMPLE_PHOTOS)
        app.yeni_hayvan_foto_data = SAMPLE_PHOTOS[0]
        app.yeni_hayvan_foto_onizleme_guncelle()
        app.root.update()
        assert all(getattr(slot, "image", None) for slot in app.yeni_hayvan_foto_previews)
        for slot in app.yeni_hayvan_foto_previews:
            img = getattr(slot, "image", None)
            assert img.width() >= slot.winfo_width() - 2, "photo preview does not fill slot width"
            assert img.height() >= slot.winfo_height() - 2, "photo preview does not fill slot height"
        app.yeni_hayvan_foto_previews[1].event_generate("<Button-1>", x=126, y=10)
        app.root.update()
        assert len(app.yeni_hayvan_foto_datas) == 2
        app.yeni_hayvan_foto_datas = list(SAMPLE_PHOTOS)
        app.yeni_hayvan_foto_data = SAMPLE_PHOTOS[0]
        app.hayvan_kaydet()

        assert len(app.hayvanlar) == 1, app.hayvanlar
        created_id = next(iter(app.hayvanlar))
        created = app.hayvanlar[created_id]
        assert created["resmi_kupe_no"] == "TR987654321"
        assert created["ciftlik_kupe_no"] == "CF99123456"
        assert created["irk"] == "Simental"
        assert len(created["foto_datas"]) == 3
        assert created["foto_data"] == SAMPLE_PHOTOS[0]
        assert getattr(app, "yeni_hayvan_foto_datas", []) == []

        for arama in ("TR987654321", "CF99123456", "123456", "TR 9876", "TR 76543"):
            app.filtre_combo.set("Aktif")
            app.arama_entry.delete(0, tk.END)
            app.arama_entry.insert(0, arama)
            app.hayvan_listesini_guncelle()
            assert len(app.hayvan_tree.get_children()) == 1, f"search failed: {arama}"
        app.arama_entry.delete(0, tk.END)
        app.arama_entry.insert(0, "ZZ 9876")
        app.hayvan_listesini_guncelle()
        assert len(app.hayvan_tree.get_children()) == 0, "wrong official tag abbreviation matched"
        app.arama_entry.delete(0, tk.END)

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
        assert app.tohumlama_hayvan_combo.get() == "CF99123456", app.tohumlama_hayvan_combo.get()
        assert app.tohumlama_tarih_entry.get()
        app.tohumlama_sekli_combo.set("Suni")
        app.suni_entry.delete(0, tk.END)
        app.suni_entry.insert(0, "Smoke")
        app.tohumlama_kaydet()
        created = app.hayvanlar[created_id]
        assert len(created.get("tohumlamalar", [])) == 1
        assert created["tohumlamalar"][0]["suni_isim"] == "Smoke"

        created.setdefault("tohumlamalar", []).append({
            "id": "smoke-toh",
            "tarih": "01/02/2026",
            "sekil": "Suni",
            "suni_isim": "Smoke",
            "gebe_mi": True,
        })
        created["gebe_mi"] = True
        created["gebelik_tarihi"] = "01/02/2026"
        created.setdefault("dogumlar", []).append({
            "tarih": "01/05/2026",
            "yavrular": [{"cins": "Di\u015fi Buza\u011f\u0131", "resmi_kupe_no": "TRY1", "ciftlik_kupe_no": "CY1"}],
        })
        created.setdefault("asi_prosedurler", []).append({
            "ad": "Smoke A\u015f\u0131",
            "tarih": "01/05/2026",
            "sonraki_tarih": "01/06/2026",
            "not": "test",
        })
        app.raporlari_guncelle()
        app.root.update()
        report_text = "\n".join(widget_texts(app.rapor_frame))
        for expected in ("Aktif hayvan", "Gebelik kontrol", "Cinsiyet Da\u011f\u0131l\u0131m\u0131", "S\u00fcr\u00fcdeki Hayvan Tipleri", "\u00d6zel Durumlar"):
            assert expected in report_text, expected
        chart_titles = [text for text in widget_texts(app.rapor_frame) if "Da\u011f\u0131l\u0131m\u0131" in text or text in ("S\u00fcr\u00fcdeki Hayvan Tipleri", "\u00d6zel Durumlar")]
        assert len(chart_titles) >= 3, chart_titles

        app.hayvan_detay_penceresi(created_id)
        app.root.update()
        profiles = [
            child for child in app.root.winfo_children()
            if isinstance(child, tk.Toplevel) and "Hayvan Profili" in child.title()
        ]
        assert profiles, "profile window not opened"
        profile_text = "\n".join(widget_texts(profiles[-1]))
        for expected in ("Foto\u011fraflar", "Kimlik ve Durum", "Irk", "Simental", "\u00d6zet", "Tohumlama Ge\u00e7mi\u015fi", "Do\u011fum ve Yavru Ge\u00e7mi\u015fi", "A\u015f\u0131 ve Prosed\u00fcrler"):
            assert expected in profile_text, expected
        popup = app.fotograf_buyut_penceresi(SAMPLE_PHOTOS[0], "Smoke Foto", profiles[-1])
        assert popup and popup.winfo_exists()
        popup.destroy()
        profiles[-1].destroy()

        male = make_animal(id="male", kupe_no="M1", resmi_kupe_no="TRM", ciftlik_kupe_no="M1", cins="Dana")
        assert not app.hayvan_tohumlanabilir_mi(male)
        assert app.foto_data_to_image(None) is None

        print(f"UI smoke OK: {tmp}")
        return 0
    finally:
        app.uygulamayi_kapat()


if __name__ == "__main__":
    raise SystemExit(main())
