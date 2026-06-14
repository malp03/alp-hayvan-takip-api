import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime, timedelta
import base64
import calendar
import json
import copy
import hashlib
import hmac
import io
import os
import queue
import re
import shutil
import secrets
import socket
import subprocess
import tempfile
import threading
import uuid
import urllib.error
import urllib.parse
import urllib.request
try:
    from PIL import Image, ImageTk, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    Image = None
    ImageTk = None
    PIL_AVAILABLE = False
import sys

from alp_ziraat_export import export_rows_to_excel, export_rows_to_pdf
from alp_ziraat_is_kurallari import (
    durum_hesapla as is_durum_hesapla,
    otomatik_cins_guncelle as is_otomatik_cins_guncelle,
    uyari_esigi as is_uyari_esigi,
)

class ApiHatasi(Exception):
    def __init__(self, mesaj, status=None):
        super().__init__(mesaj)
        self.status = status


VARSAYILAN_API_URL = "https://alp-hayvan-takip-api.onrender.com"
APP_VERSION = "1.9.35"
GITHUB_REPO = "malp03/alp-hayvan-takip-api"
GITHUB_LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
UPDATE_SETUP_ASSET = "ALP_Ziraat_Suru_Takip_Setup.exe"
LEGACY_UPDATE_SETUP_ASSETS = ("ALP_Ziraat_Hayvan_Takip_Setup.exe",)
# --------------------------------------------------------------------


def surum_parcalari(surum):
    parcalar = re.findall(r"\d+", str(surum or ""))
    sayilar = [int(p) for p in parcalar[:3]]
    while len(sayilar) < 3:
        sayilar.append(0)
    return tuple(sayilar)


def surum_daha_yeni_mi(yeni_surum, mevcut_surum):
    return surum_parcalari(yeni_surum) > surum_parcalari(mevcut_surum)

# --- Exe'de dosya yolunu doğru bulmak için fonksiyon ---
def resource_path(relative_path):
    """Hem script hem de donmuş exe için varlıklara mutlak yol oluşturur. """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)
# -------------------------------------------------------------------------


# --- Sınıf Tanımlaması ---
class HayvanTakipSistemi:
    def __init__(self):
        self._baslatma_tamam = False
        try:
            self.root = tk.Tk()

            # --- TEMA RENK PALETLERİ ---
            self.dark_theme = {
                "ana_kirmizi": "#2F81F7", "koyu_kirmizi": "#1D4ED8",
                "siyah": "#0B1220",
                "arkaplan": "#070D16",
                "kart_arkaplan": "#0F1826",
                "kart_ikincil": "#142238",
                "gri": "#1B2A3D",
                "kenarlik": "#243855",
                "input_bg": "#050B14",
                "muted": "#7EA0C4",
                "yazi_rengi": "#EAF2FF",
                "beyaz": "#FFFFFF",
                "yesil": "#22C55E", "koyu_yesil": "#16A34A",
                "uyari": "#F59E0B", "uyari_yazi": "#111827",
                "kesildi_bg": "#334155", "kesildi_fg": "#EAF2FF",
                "button_default_bg": "#132238", "button_default_fg": "#D9E8FF",
                "button_success_bg": "#10B981", "button_success_fg": "#FFFFFF",
                "button_danger_bg": "#EF4444", "button_danger_fg": "#FFFFFF",
                "button_warning_bg": "#F59E0B", "button_warning_fg": "#111827",
                "button_theme_bg": "#101B2C", "button_theme_fg": "#D9E8FF",
                "button_primary_bg": "#3B82F6", "button_primary_fg": "#FFFFFF",
                "table_heading_bg": "#101B2C",
                "band_normal_bg": "#062D22", "band_normal_fg": "#A7F3D0",
                "band_warning_bg": "#3A2A09", "band_warning_fg": "#FDE68A",
                "band_critical_bg": "#40181A", "band_critical_fg": "#FECACA",
            }

            self.light_theme = {
                "ana_kirmizi": "#DC2626", "koyu_kirmizi": "#B91C1C",
                "siyah": "#111816",
                "arkaplan": "#F5F7F4",
                "kart_arkaplan": "#FFFFFF",
                "kart_ikincil": "#F1F5EF",
                "gri": "#E5EBE3",
                "kenarlik": "#D5DDD2",
                "input_bg": "#FFFFFF",
                "muted": "#637064",
                "yazi_rengi": "#18211A",
                "beyaz": "#FFFFFF",
                "yesil": "#15803D", "koyu_yesil": "#166534",
                "uyari": "#C27A0A", "uyari_yazi": "#1F2A1D",
                "kesildi_bg": "#A3ADA0", "kesildi_fg": "#FFFFFF",
                "button_default_bg": "#E9EFE6", "button_default_fg": "#18211A",
                "button_success_bg": "#15803D", "button_success_fg": "#FFFFFF",
                "button_danger_bg": "#DC2626", "button_danger_fg": "#FFFFFF",
                "button_warning_bg": "#D99A12", "button_warning_fg": "#1F2A1D",
                "button_theme_bg": "#FFFFFF", "button_theme_fg": "#18211A",
                "button_primary_bg": "#2563EB", "button_primary_fg": "#FFFFFF",
                "table_heading_bg": "#EDF3EA",
                "band_normal_bg": "#DDF7E8", "band_normal_fg": "#14532D",
                "band_warning_bg": "#FEF3C7", "band_warning_fg": "#78350F",
                "band_critical_bg": "#FEE2E2", "band_critical_fg": "#991B1B",
            }
            
            self.theme_mode = "dark"
            self.renkler = self.dark_theme
            self.themed_widgets = []
            self.themed_buttons = []

            self.logo_path = resource_path("alp_ziraat_logo_led.png")
            if not os.path.exists(self.logo_path):
                self.logo_path = resource_path("alp_ziraat_logo.png")
            self.icon_path = resource_path("alp_ziraat_icon_led.png")
            if not os.path.exists(self.icon_path):
                self.icon_path = resource_path("alp_ziraat_icon.png")
            self.icon_ico_path = resource_path("alp_ziraat_pdf_dark.ico")
            if not os.path.exists(self.icon_ico_path):
                self.icon_ico_path = resource_path("alp_ziraat_shortcut_led.ico")
            
            self.root.title("ALP ZİRAAT - Sürü Takip Sistemi")
            self.root.geometry("1500x900")
            self.root.configure(bg=self.renkler["arkaplan"])

            try:
                self.logo_ikon = ImageTk.PhotoImage(file=self.icon_path)
            except Exception as e:
                self.logo_ikon = None
                print(f"Logo ikonu yüklenemedi: {e}")
            self.uygula_pencere_ikonu(self.root)

            self.stil_ayarla()
            self.veri_klasoru_hazirla()
            self.api_token = None
            self.api_kullanici = None
            self._pending_update_notes = None
            self._guncelleme_kontrol_edildi = False
            self.yeni_hayvan_foto_data = None
            self.yeni_hayvan_foto_datas = []
            self._foto_referanslari = []
            self._foto_url_cache = {}
            self._foto_loading_urls = set()
            self._foto_loading_callbacks = {}
            self._foto_cache_lock = threading.Lock()
            self._hayvan_kayit_devam_ediyor = False
            self.hayvan_secimleri = set()
            self.admin_aktif_ciftlik_id = None
            self.admin_aktif_ciftlik_ad = None
            self._login_yeniden_iste = False
            self._otomatik_baglanti_after_id = None
            self._tracked_after_ids = []
            self._otomatik_baglanti_kontrol_ediliyor = False
            self.otomatik_baglanti_araligi_ms = 60 * 1000
            self.otomatik_baglanti_ilk_gecikme_ms = 30 * 1000
            if self.api_modu and not self.login_akisini_baslat():
                self.root.destroy()
                return
            self.hayvanlar = self.veri_yukle()
            self.geri_al_yigini = []
            if getattr(self, "_veri_migrasyonu_gerekli", False):
                self.veri_kaydet()
            self.okunan_uyarilar = self.okunan_uyarilar_yukle()
            self.islem_gecmisi = self.islem_gecmisi_yukle()
            self.uyari_thread_running = True
            self._uyari_after_id = None
            self._saat_after_id = None
            self._baslangic_after_id = None
            self._puls_after_id = None
            self._otomatik_baglanti_after_id = None
            self._kapanis_istegi = False
            self.ana_interface_olustur()
            self.uyari_sistemi_baslat()
            self._pending_update_notes = self.guncelleme_notu_yukle()
            self._track_after(self.root, 900, self.guncelleme_baslangic_akisi)
            self._baslatma_tamam = True

        except Exception as e:
            messagebox.showerror("Başlatma Hatası", f"Uygulama başlatılamadı: {e}")

    def stil_ayarla(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background=self.renkler["arkaplan"])
        style.configure('TLabel', background=self.renkler["arkaplan"], foreground=self.renkler["yazi_rengi"], font=('Segoe UI', 11))
        style.configure('TNotebook', background=self.renkler["arkaplan"], borderwidth=0, tabmargins=[0, 0, 0, 0])
        style.configure(
            'Modern.TNotebook',
            background=self.renkler["arkaplan"],
            borderwidth=0,
            relief='flat',
            bordercolor=self.renkler["arkaplan"],
            lightcolor=self.renkler["arkaplan"],
            darkcolor=self.renkler["arkaplan"],
        )
        style.configure('Modern.TNotebook.Tab',
            padding=[28, 16],
            font=('Segoe UI', 12, 'bold'),
            background=self.renkler["gri"],
            foreground=self.renkler["yazi_rengi"],
            borderwidth=0, focuscolor='')
        style.map('Modern.TNotebook.Tab',
            background=[('selected', self.renkler["koyu_kirmizi"]), ('active', self.renkler["ana_kirmizi"])],
            foreground=[('selected', '#FFFFFF'), ('active', '#FFFFFF')])
        style.configure('Modern.Treeview',
            font=('Segoe UI', 10), rowheight=38,
            background=self.renkler["kart_arkaplan"],
            foreground=self.renkler["yazi_rengi"],
            fieldbackground=self.renkler["kart_arkaplan"],
            borderwidth=0,
            relief='flat')
        style.configure('Modern.Treeview.Heading',
            font=('Segoe UI', 10, 'bold'),
            background=self.renkler.get("table_heading_bg", self.renkler["siyah"]),
            foreground=self.renkler["yazi_rengi"],
            padding=[10, 12],
            relief='flat')
        
        selection_bg = self.renkler.get("button_primary_bg", "#3B82F6")
        style.map('Modern.Treeview',
            background=[('selected', selection_bg)],
            foreground=[('selected', '#FFFFFF')])
        style.map('Modern.Treeview.Heading',
            background=[('active', self.renkler["gri"])])
        style.configure('TCombobox',
            fieldbackground=self.renkler["input_bg"],
            background=self.renkler["input_bg"],
            foreground=self.renkler["yazi_rengi"],
            arrowcolor=self.renkler["yazi_rengi"],
            selectbackground=self.renkler["input_bg"],
            selectforeground=self.renkler["yazi_rengi"],
            padding=[12, 9],
            borderwidth=1,
            relief='flat',
            bordercolor=self.renkler["kenarlik"],
            lightcolor=self.renkler["kenarlik"],
            darkcolor=self.renkler["kenarlik"])
        style.map('TCombobox',
            fieldbackground=[('readonly', self.renkler["input_bg"]), ('focus', self.renkler["input_bg"])],
            selectbackground=[('readonly', self.renkler["input_bg"])])
        style.configure('TEntry',
            fieldbackground=self.renkler["input_bg"],
            foreground=self.renkler["yazi_rengi"],
            insertcolor=self.renkler["yazi_rengi"],
            padding=[12, 9],
            borderwidth=1,
            relief='flat',
            bordercolor=self.renkler["kenarlik"],
            lightcolor=self.renkler["kenarlik"],
            darkcolor=self.renkler["kenarlik"])
        style.configure('Vertical.TScrollbar',
            background=self.renkler["gri"],
            troughcolor=self.renkler["kart_arkaplan"],
            borderwidth=0, arrowcolor=self.renkler["yazi_rengi"], relief='flat')
        style.configure('Horizontal.TScrollbar',
            background=self.renkler["gri"],
            troughcolor=self.renkler["kart_arkaplan"],
            borderwidth=0, arrowcolor=self.renkler["yazi_rengi"], relief='flat')
        style.configure('TScrollbar',
            background=self.renkler["gri"],
            troughcolor=self.renkler["kart_arkaplan"],
            borderwidth=0,
            arrowcolor=self.renkler["yazi_rengi"],
            relief='flat')
        self.root.option_add('*TCombobox*Listbox.background', self.renkler["kart_arkaplan"])
        self.root.option_add('*TCombobox*Listbox.foreground', self.renkler["yazi_rengi"])
        self.root.option_add('*TCombobox*Listbox.selectBackground', self.renkler["button_primary_bg"])
        self.root.option_add('*TCombobox*Listbox.selectForeground', '#FFFFFF')

    def _hex_to_rgb(self, hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def _rgb_to_hex(self, rgb):
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

    def _create_rounded_rect(self, canvas, x1, y1, x2, y2, radius=25, **kwargs):
        x2 -= 1
        y2 -= 1
        o1 = canvas.create_oval(x1, y1, x1+2*radius, y1+2*radius, **kwargs, outline="")
        o2 = canvas.create_oval(x2-2*radius, y1, x2, y1+2*radius, **kwargs, outline="")
        o3 = canvas.create_oval(x1, y2-2*radius, x1+2*radius, y2, **kwargs, outline="")
        o4 = canvas.create_oval(x2-2*radius, y2-2*radius, x2, y2, **kwargs, outline="")
        r1 = canvas.create_rectangle(x1+radius, y1, x2-radius, y2, **kwargs, outline="")
        r2 = canvas.create_rectangle(x1, y1+radius, x2, y2-radius, **kwargs, outline="")
        return [o1, o2, o3, o4, r1, r2]

    def _animate_canvas_bg(self, canvas, parts, current_rgb, target_rgb, step=0, total_steps=6):
        if not canvas.winfo_exists(): return
        if step > total_steps:
            hex_col = self._rgb_to_hex(target_rgb)
            for p in parts:
                canvas.itemconfig(p, fill=hex_col)
            return
        
        r = int(current_rgb[0] + (target_rgb[0] - current_rgb[0]) * (step / total_steps))
        g = int(current_rgb[1] + (target_rgb[1] - current_rgb[1]) * (step / total_steps))
        b = int(current_rgb[2] + (target_rgb[2] - current_rgb[2]) * (step / total_steps))
        
        hex_col = self._rgb_to_hex((r, g, b))
        for p in parts:
            canvas.itemconfig(p, fill=hex_col)

        self._track_after(canvas, 15, lambda: self._animate_canvas_bg(canvas, parts, current_rgb, target_rgb, step + 1, total_steps))

    def modern_buton(self, parent, text, command, purpose='default', width=None, small=False, tab=False):
        bg_color = self.renkler.get(f"button_{purpose}_bg", self.renkler["button_default_bg"])
        fg_color = self.renkler.get(f"button_{purpose}_fg", self.renkler["button_default_fg"])
        hover_color = self._lighten_color(bg_color, 25) if self.theme_mode == 'dark' else self.koyu_renk(bg_color)
        _ = hover_color  # hover_color kullanımı canvas içindeki get_colors()'da dinamik olarak yapılıyor
        
        if tab:
            pad_x = 18
            pad_y = 9
            font_size = 10
        else:
            pad_x = 12 if small else 30
            pad_y = 7 if small else 12
            font_size = 9 if small else 11
        font_spec = ('Segoe UI', font_size, 'bold')
        
        dummy = tk.Label(parent, text=text, font=font_spec)
        req_w = dummy.winfo_reqwidth() + pad_x * 2
        req_h = dummy.winfo_reqheight() + pad_y * 2
        dummy.destroy()
        
        if width:
            req_w = width * 10 
            
        try:
            parent_bg = parent.cget('bg')
        except tk.TclError:
            parent_bg = self.renkler["arkaplan"]
        canvas = tk.Canvas(parent, width=req_w, height=req_h, bg=parent_bg, highlightthickness=0, bd=0)
        
        radius = 10
        border_color = self.renkler.get("kenarlik", self.renkler["gri"])
        border_parts = self._create_rounded_rect(canvas, 0, 0, req_w, req_h, radius=radius, fill=border_color)
        parts = self._create_rounded_rect(canvas, 1, 1, req_w - 1, req_h - 1, radius=max(6, radius - 1), fill=bg_color)
        
        text_id = canvas.create_text(req_w/2, req_h/2, text=text, fill=fg_color, font=font_spec, justify='center')
        
        canvas.border_parts = border_parts
        canvas.button_parts = parts
        canvas.text_item = text_id
        canvas.purpose = purpose
        canvas.command = command
        canvas.enabled = True
        
        def get_colors():
            bg_hex = self.renkler.get(f"button_{canvas.purpose}_bg", self.renkler["button_default_bg"])
            hover_hex = self._lighten_color(bg_hex, 25) if self.theme_mode == 'dark' else self.koyu_renk(bg_hex)
            return self._hex_to_rgb(bg_hex), self._hex_to_rgb(hover_hex), hover_hex
            
        def on_enter(e):
            if canvas.winfo_exists():
                canvas.config(cursor="hand2")
                bg_rgb, hover_rgb, _ = get_colors()
                self._animate_canvas_bg(canvas, parts, bg_rgb, hover_rgb)
            
        def on_leave(e):
            if canvas.winfo_exists():
                bg_rgb, hover_rgb, _ = get_colors()
                self._animate_canvas_bg(canvas, parts, hover_rgb, bg_rgb)
            
        def on_click(e):
            komut = getattr(canvas, "command", None)
            if komut and getattr(canvas, "enabled", True):
                bg_rgb, hover_rgb, hover_hex = get_colors()
                click_color = self._lighten_color(hover_hex, 30) if self.theme_mode == 'dark' else self.koyu_renk(hover_hex)
                for p in parts: canvas.itemconfig(p, fill=click_color)
                canvas.update_idletasks()
                self._track_after(canvas, 50, lambda: self._animate_canvas_bg(canvas, parts, self._hex_to_rgb(click_color), hover_rgb))
                self._track_after(canvas, 100, komut)
                
        # Bindings only on the canvas widget to prevent event bubbling/double-firing
        canvas.bind("<Enter>", on_enter)
        canvas.bind("<Leave>", on_leave)
        canvas.bind("<Button-1>", on_click)
        
        self.themed_buttons.append((canvas, purpose))
        return canvas

    def responsive_buton_grubu(self, parent, butonlar, gap=8, align="left"):
        """Butonlari pencere genisligine gore satir kirarak yerlestirir."""
        olusan_butonlar = []
        for metin, komut, amac in butonlar:
            btn = self.modern_buton(parent, metin, komut, purpose=amac, small=True)
            olusan_butonlar.append(btn)

        def yerlestir(event=None):
            try:
                if not parent.winfo_exists():
                    return
                kullanilabilir = max(parent.winfo_width() - 12, 120)
                satir = 0
                sutun = 0
                kullanilan = 0
                for btn in olusan_butonlar:
                    btn.grid_forget()
                if align == "right":
                    parent.columnconfigure(0, weight=1)
                for btn in olusan_butonlar:
                    genislik = btn.winfo_reqwidth() + gap
                    if sutun and kullanilan + genislik > kullanilabilir:
                        satir += 1
                        sutun = 0
                        kullanilan = 0
                    sticky = "e" if align == "right" else "w"
                    col_index = sutun + 1 if align == "right" else sutun
                    btn.grid(row=satir, column=col_index, padx=(0, gap), pady=(3, 7), sticky=sticky)
                    kullanilan += genislik
                    sutun += 1
            except tk.TclError:
                return

        parent.bind("<Configure>", yerlestir)
        self._track_after(self.root, 50, yerlestir)
        return olusan_butonlar

    def _track_after(self, widget, delay_ms, callback):
        after_ref = {"id": None}

        def guarded_callback():
            try:
                kayitlar = getattr(self, "_tracked_after_ids", [])
                if after_ref["id"] is not None:
                    self._tracked_after_ids = [
                        item for item in kayitlar
                        if not (item[0] is widget and item[1] == after_ref["id"])
                    ]
                if getattr(self, "_kapanis_istegi", False):
                    return
                if hasattr(widget, "winfo_exists") and not widget.winfo_exists():
                    return
                callback()
            except tk.TclError:
                return

        try:
            after_id = widget.after(delay_ms, guarded_callback)
            after_ref["id"] = after_id
            if hasattr(self, "_tracked_after_ids"):
                self._tracked_after_ids.append((widget, after_id))
            return after_id
        except tk.TclError:
            return None

    def _cancel_tracked_afters(self):
        for widget, after_id in list(getattr(self, "_tracked_after_ids", [])):
            try:
                if widget.winfo_exists():
                    widget.after_cancel(after_id)
            except tk.TclError:
                pass
        self._tracked_after_ids = []

    def kaydirilabilir_sayfa(self, parent, padx=28, pady=22):
        kapsayici = tk.Frame(parent, bg=self.renkler["arkaplan"])
        kapsayici.pack(fill='both', expand=True)
        self.themed_widgets.append((kapsayici, 'arkaplan'))

        canvas = tk.Canvas(kapsayici, bg=self.renkler["arkaplan"], highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(
            kapsayici,
            orient='vertical',
            command=canvas.yview,
            bg=self.renkler["kart_ikincil"],
            troughcolor=self.renkler["arkaplan"],
            activebackground=self.renkler["button_primary_bg"],
            highlightthickness=0,
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side='left', fill='both', expand=True)

        sayfa = tk.Frame(canvas, bg=self.renkler["arkaplan"], padx=padx, pady=pady)
        self.themed_widgets.append((sayfa, 'arkaplan'))
        pencere = canvas.create_window((0, 0), window=sayfa, anchor='nw')

        def bolge_guncelle(event=None):
            try:
                canvas.configure(scrollregion=canvas.bbox("all"))
                bbox = canvas.bbox("all")
                gerekli = bool(bbox and bbox[3] > canvas.winfo_height())
                if gerekli and not scrollbar.winfo_ismapped():
                    scrollbar.pack(side='right', fill='y')
                elif not gerekli and scrollbar.winfo_ismapped():
                    scrollbar.pack_forget()
            except tk.TclError:
                pass

        def genislik_guncelle(event):
            try:
                canvas.itemconfigure(pencere, width=event.width)
                bolge_guncelle()
            except tk.TclError:
                pass

        def mousewheel(event):
            try:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except tk.TclError:
                pass

        def mousewheel_ac(event=None):
            canvas.bind_all("<MouseWheel>", mousewheel)

        def mousewheel_kapat(event=None):
            try:
                canvas.unbind_all("<MouseWheel>")
            except tk.TclError:
                pass

        sayfa.bind("<Configure>", bolge_guncelle)
        canvas.bind("<Configure>", genislik_guncelle)
        canvas.bind("<Enter>", mousewheel_ac)
        canvas.bind("<Leave>", mousewheel_kapat)
        return sayfa

    def _sayfa_basligi(self, parent, baslik, alt_metin=None):
        alan = tk.Frame(parent, bg=self.renkler["arkaplan"])
        alan.pack(fill='x', pady=(0, 14))
        self.themed_widgets.append((alan, 'arkaplan'))
        baslik_lbl = tk.Label(
            alan,
            text=baslik,
            font=('Segoe UI', 22, 'bold'),
            bg=self.renkler["arkaplan"],
            fg=self.renkler["yazi_rengi"],
        )
        baslik_lbl.pack(anchor='w')
        self.themed_widgets.append((baslik_lbl, 'label'))
        if alt_metin:
            alt_lbl = tk.Label(
                alan,
                text=alt_metin,
                font=('Segoe UI', 10),
                bg=self.renkler["arkaplan"],
                fg=self.renkler["muted"],
            )
            alt_lbl.pack(anchor='w', pady=(3, 0))
            self.themed_widgets.append((alt_lbl, 'muted_label'))
        return alan

    def koyu_renk(self, hex_color):
        try:
            rgb = self._hex_to_rgb(hex_color)
            return self._rgb_to_hex(tuple(max(0, c - 30) for c in rgb))
        except:
            return hex_color

    def _lighten_color(self, hex_color, amount=20):
        try:
            rgb = self._hex_to_rgb(hex_color)
            return self._rgb_to_hex(tuple(min(255, c + amount) for c in rgb))
        except:
            return hex_color

    def modern_kart(self, parent, accent=None):
        """Modern kart: ince çerçeveli, isteğe bağlı üst accent çizgili panel."""
        kart = tk.Frame(
            parent,
            bg=self.renkler["kart_arkaplan"],
            highlightthickness=1,
            highlightbackground=self.renkler.get("kenarlik", self.renkler["gri"]),
            bd=0
        )
        self.themed_widgets.append((kart, 'kart'))
        if accent:
            accent_bar = tk.Frame(kart, bg=accent, height=4)
            accent_bar.pack(fill='x', side='top')
        return kart

    def uygula_pencere_ikonu(self, pencere):
        """PDF kaynakli dark ICO'yu Windows titlebar/kisayol ikonuna uygula."""
        try:
            if getattr(self, "icon_ico_path", None) and os.path.exists(self.icon_ico_path):
                pencere.iconbitmap(self.icon_ico_path)
        except Exception:
            pass
        try:
            if getattr(self, "logo_ikon", None):
                pencere.iconphoto(True, self.logo_ikon)
        except Exception:
            pass

    def modern_popup(self, baslik, genislik=520, yukseklik=420, parent=None):
        parent = parent if parent is not None else self.root
        pencere = tk.Toplevel(parent)
        pencere.title(baslik)
        pencere.geometry(f"{genislik}x{yukseklik}")
        pencere.minsize(min(genislik, 420), min(yukseklik, 320))
        pencere.configure(bg=self.renkler["arkaplan"])
        pencere.transient(parent)
        self.uygula_pencere_ikonu(pencere)
        kart = self.modern_kart(pencere, accent=self.renkler["button_primary_bg"])
        kart.pack(fill="both", expand=True, padx=18, pady=18)
        return pencere, kart

    def popup_buton_bar(self, parent):
        bar = tk.Frame(parent, bg=self.renkler["kart_arkaplan"])
        bar.pack(fill="x", side="bottom", padx=20, pady=(8, 18))
        self.themed_widgets.append((bar, 'kart'))
        return bar

    def pencere_ortala(self, pencere, parent=None):
        try:
            pencere.update_idletasks()
            genislik = pencere.winfo_width()
            yukseklik = pencere.winfo_height()
            hedef = parent if parent is not None and parent.winfo_exists() else pencere
            x = max(hedef.winfo_rootx() + (hedef.winfo_width() - genislik) // 2, 0)
            y = max(hedef.winfo_rooty() + (hedef.winfo_height() - yukseklik) // 2, 0)
            pencere.geometry(f"{genislik}x{yukseklik}+{x}+{y}")
        except tk.TclError:
            pass

    def foto_data_olustur(self, dosya_yolu, max_size=(900, 900), quality=82):
        if not PIL_AVAILABLE:
            raise ValueError("Fotoğraf seçmek için Pillow kütüphanesi gerekli.")
        with Image.open(dosya_yolu) as img:
            img = ImageOps.exif_transpose(img).convert("RGB")
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality, optimize=True)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"

    def foto_referansi_url_mu(self, foto):
        raw = str(foto or "").strip()
        return raw.startswith("http://") or raw.startswith("https://")

    def foto_storage_path_from_ref(self, foto):
        raw = str(foto or "").strip()
        if not raw:
            return None
        if raw.startswith("http://") or raw.startswith("https://"):
            parsed = urllib.parse.urlparse(raw)
            path = parsed.path or ""
            markers = (
                "/storage/v1/object/public/",
                "/storage/v1/object/sign/",
                "/storage/v1/object/authenticated/",
                "/storage/v1/object/",
            )
            for marker in markers:
                if marker in path:
                    tail = path.split(marker, 1)[1]
                    parts = tail.split("/", 1)
                    if len(parts) == 2:
                        return urllib.parse.unquote(parts[1]).strip("/")
            return None
        if raw.startswith("storage://"):
            tail = raw[len("storage://"):]
            if "/" in tail:
                return tail.split("/", 1)[1].strip("/")
            return tail.strip("/")
        if raw.startswith("data:"):
            return None
        if "/" in raw and len(raw) < 260:
            return raw.strip("/")
        return None

    def foto_cache_identity(self, foto):
        raw = str(foto or "").strip()
        path = self.foto_storage_path_from_ref(raw)
        if path:
            return f"path:{path}"
        return raw

    def foto_cache_dosya_yolu(self, foto):
        identity = self.foto_cache_identity(foto)
        if not identity:
            return None
        cache_dir = getattr(self, "foto_cache_dir", None)
        if not cache_dir:
            cache_dir = os.path.join(getattr(self, "data_dir", os.getcwd()), "foto_onbellek")
            self.foto_cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        ad = hashlib.sha256(identity.encode("utf-8")).hexdigest() + ".jpg"
        return os.path.join(cache_dir, ad)

    def foto_cache_oku(self, foto):
        yol = self.foto_cache_dosya_yolu(foto)
        if not yol or not os.path.exists(yol):
            return None
        try:
            if os.path.getsize(yol) > 6 * 1024 * 1024:
                return None
            with open(yol, "rb") as f:
                return f.read()
        except Exception:
            return None

    def foto_cache_yaz(self, foto, data):
        if not data:
            return
        yol = self.foto_cache_dosya_yolu(foto)
        if not yol:
            return
        try:
            tmp = yol + ".tmp"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, yol)
        except Exception:
            pass

    def foto_referans_bytes_cached(self, foto):
        if not foto:
            return None
        raw = str(foto).strip()
        try:
            identity = self.foto_cache_identity(raw)
            storage_path = self.foto_storage_path_from_ref(raw)
            if self.foto_referansi_url_mu(raw) or storage_path:
                cache = getattr(self, "_foto_url_cache", {})
                with getattr(self, "_foto_cache_lock", threading.Lock()):
                    if identity in cache:
                        return cache[identity]
                    if raw in cache:
                        return cache[raw]
                data = self.foto_cache_oku(raw)
                if data:
                    with getattr(self, "_foto_cache_lock", threading.Lock()):
                        cache[identity] = data
                        self._foto_url_cache = cache
                    return data
                return None
            if "," in raw:
                raw = raw.split(",", 1)[1]
            return base64.b64decode(raw)
        except Exception:
            return None

    def foto_referans_bytes(self, foto):
        if not foto:
            return None
        raw = str(foto).strip()
        try:
            cached = self.foto_referans_bytes_cached(raw)
            if cached:
                return cached
            if self.foto_referansi_url_mu(raw):
                req = urllib.request.Request(raw, headers={"User-Agent": "ALP-Ziraat-Hayvan-Takip/1.0"})
                with urllib.request.urlopen(req, timeout=12) as resp:
                    data = resp.read(5 * 1024 * 1024)
                identity = self.foto_cache_identity(raw)
                cache = getattr(self, "_foto_url_cache", {})
                with getattr(self, "_foto_cache_lock", threading.Lock()):
                    cache[identity] = data
                    self._foto_url_cache = cache
                self.foto_cache_yaz(raw, data)
                return data
            return None
        except Exception:
            return None

    def foto_url_arka_planda_yukle(self, foto, tamam_callback=None):
        raw = str(foto or "").strip()
        if not raw:
            return
        cached = self.foto_referans_bytes_cached(raw)
        if cached:
            if tamam_callback:
                try:
                    self.root.after(0, lambda: tamam_callback(cached))
                except tk.TclError:
                    pass
            return
        if not self.foto_referansi_url_mu(raw):
            if tamam_callback:
                try:
                    self.root.after(0, lambda: tamam_callback(None))
                except tk.TclError:
                    pass
            return

        identity = self.foto_cache_identity(raw)
        lock = getattr(self, "_foto_cache_lock", threading.Lock())
        with lock:
            loading = getattr(self, "_foto_loading_urls", set())
            callbacks = getattr(self, "_foto_loading_callbacks", {})
            if identity in loading:
                if tamam_callback:
                    callbacks.setdefault(identity, []).append(tamam_callback)
                    self._foto_loading_callbacks = callbacks
                return
            loading.add(identity)
            self._foto_loading_urls = loading
            if tamam_callback:
                callbacks.setdefault(identity, []).append(tamam_callback)
                self._foto_loading_callbacks = callbacks

        def worker():
            data = None
            try:
                req = urllib.request.Request(raw, headers={"User-Agent": "ALP-Ziraat-Hayvan-Takip/1.0"})
                with urllib.request.urlopen(req, timeout=12) as resp:
                    data = resp.read(5 * 1024 * 1024)
                cache = getattr(self, "_foto_url_cache", {})
                with lock:
                    cache[identity] = data
                    self._foto_url_cache = cache
                self.foto_cache_yaz(raw, data)
            except Exception:
                data = None

            def finish():
                try:
                    with lock:
                        getattr(self, "_foto_loading_urls", set()).discard(identity)
                        callbacks = getattr(self, "_foto_loading_callbacks", {}).pop(identity, [])
                    for callback in callbacks:
                        try:
                            callback(data)
                        except Exception:
                            pass
                except tk.TclError:
                    pass

            try:
                self.root.after(0, finish)
            except tk.TclError:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def foto_data_to_image(self, foto_data, max_size=(180, 140)):
        if not (PIL_AVAILABLE and foto_data):
            return None
        try:
            data = self.foto_referans_bytes(foto_data)
            if not data:
                return None
            img = Image.open(io.BytesIO(data)).convert("RGB")
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception:
            return None

    def foto_data_to_image_cached(self, foto_data, max_size=(180, 140)):
        if not (PIL_AVAILABLE and foto_data):
            return None
        try:
            data = self.foto_referans_bytes_cached(foto_data)
            if not data:
                return None
            img = Image.open(io.BytesIO(data)).convert("RGB")
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception:
            return None

    def foto_data_to_cover_image(self, foto_data, size=(160, 90)):
        if not (PIL_AVAILABLE and foto_data):
            return None
        try:
            size = (max(int(size[0]), 1), max(int(size[1]), 1))
            data = self.foto_referans_bytes(foto_data)
            if not data:
                return None
            img = Image.open(io.BytesIO(data)).convert("RGB")
            img = ImageOps.fit(img, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
            return ImageTk.PhotoImage(img)
        except Exception:
            return None

    def foto_data_to_cover_image_cached(self, foto_data, size=(160, 90)):
        if not (PIL_AVAILABLE and foto_data):
            return None
        try:
            size = (max(int(size[0]), 1), max(int(size[1]), 1))
            data = self.foto_referans_bytes_cached(foto_data)
            if not data:
                return None
            img = Image.open(io.BytesIO(data)).convert("RGB")
            img = ImageOps.fit(img, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
            return ImageTk.PhotoImage(img)
        except Exception:
            return None

    def foto_onizleme_guncelle(self, label, foto_data, max_size=(180, 140), bos_metin="Fotoğraf yok"):
        img = self.foto_data_to_image(foto_data, max_size=max_size)
        if img:
            label.configure(image=img, text="")
            label.image = img
            self._foto_referanslari.append(img)
        else:
            label.configure(image="", text=bos_metin)
            label.image = None

    def foto_slot_canvas_ciz(self, canvas, foto_data, slot_no, remove_callback=None, max_size=(154, 86), bind_resize=True, open_callback=None):
        try:
            canvas._alp_foto_slot_payload = (foto_data, slot_no, remove_callback, max_size, open_callback)
            if bind_resize and not getattr(canvas, "_alp_foto_resize_bound", False):
                def yeniden_ciz(event=None, hedef=canvas):
                    payload = getattr(hedef, "_alp_foto_slot_payload", None)
                    if payload:
                        foto, no, kaldir, boyut, ac = payload
                        self.foto_slot_canvas_ciz(hedef, foto, no, kaldir, boyut, bind_resize=False, open_callback=ac)

                canvas.bind("<Configure>", yeniden_ciz)
                canvas._alp_foto_resize_bound = True
                try:
                    eski_after = getattr(canvas, "_alp_foto_after_id", None)
                    if eski_after:
                        canvas.after_cancel(eski_after)
                except tk.TclError:
                    pass
                canvas._alp_foto_after_id = canvas.after_idle(yeniden_ciz)

            canvas.delete("all")
            w = max(canvas.winfo_width(), int(canvas.cget("width")), 1)
            h = max(canvas.winfo_height(), int(canvas.cget("height")), 1)
            canvas.configure(bg=self.renkler["input_bg"], highlightbackground=self.renkler["kenarlik"])
            img = self.foto_data_to_cover_image_cached(foto_data, size=(w, h))
            yukleniyor = bool(foto_data and not img and self.foto_referansi_url_mu(foto_data))
            if yukleniyor:
                def tamamlandi(_data, hedef=canvas, beklenen=foto_data):
                    try:
                        payload = getattr(hedef, "_alp_foto_slot_payload", None)
                        if payload and payload[0] == beklenen:
                            foto, no, kaldir, boyut, ac = payload
                            self.foto_slot_canvas_ciz(hedef, foto, no, kaldir, boyut, bind_resize=False, open_callback=ac)
                    except tk.TclError:
                        pass

                self.foto_url_arka_planda_yukle(foto_data, tamamlandi)
            if img:
                canvas.image = img
                self._foto_referanslari.append(img)
                canvas.create_image(0, 0, image=img, anchor="nw")
                canvas.create_rectangle(0, h - 24, w, h, fill="#020817", outline="#020817", stipple="gray50")
                if remove_callback:
                    canvas.create_rectangle(w - 24, 2, w - 4, 22, fill=self.renkler["button_danger_bg"], outline=self.renkler["button_danger_bg"])
                    canvas.create_text(w - 14, 12, text="X", fill=self.renkler["button_danger_fg"], font=("Segoe UI", 9, "bold"))
                canvas.create_text(8, h - 12, text=f"{slot_no}. fotoğraf", fill=self.renkler["yazi_rengi"], font=("Segoe UI", 8, "bold"), anchor="w")

                def click(event):
                    if event.x >= w - 28 and event.y <= 26 and remove_callback:
                        remove_callback()
                    elif open_callback:
                        open_callback()

                canvas.configure(cursor="hand2" if remove_callback or open_callback else "")
                canvas.bind("<Button-1>", click)
            elif yukleniyor:
                canvas.image = None
                canvas.configure(cursor="")
                canvas.unbind("<Button-1>")
                canvas.create_text(
                    w // 2,
                    h // 2,
                    text="Yukleniyor...",
                    fill=self.renkler["muted"],
                    font=("Segoe UI", 9, "bold"),
                )
                canvas.create_rectangle(0, h - 22, w, h, fill="#020817", outline="#020817", stipple="gray50")
                canvas.create_text(8, h - 11, text=f"{slot_no}. fotograf", fill=self.renkler["yazi_rengi"], font=("Segoe UI", 8, "bold"), anchor="w")
            else:
                canvas.image = None
                canvas.configure(cursor="")
                canvas.unbind("<Button-1>")
                canvas.create_text(
                    w // 2,
                    h // 2,
                    text=f"{slot_no}. slot boş",
                    fill=self.renkler["muted"],
                    font=("Segoe UI", 9, "bold"),
                )
        except tk.TclError:
            pass

    def fotograf_buyut_penceresi(self, foto_data, baslik="Fotoğraf", parent=None):
        parent = parent or self.root
        img = self.foto_data_to_image_cached(foto_data, max_size=(980, 680))
        if not img and not self.foto_referansi_url_mu(foto_data):
            return messagebox.showerror("Fotoğraf", "Fotoğraf görüntülenemedi.", parent=parent)

        pencere = tk.Toplevel(parent)
        pencere.title(baslik)
        pencere.geometry("1040x760")
        pencere.minsize(720, 520)
        pencere.configure(bg=self.renkler["arkaplan"])
        pencere.transient(parent)
        self.uygula_pencere_ikonu(pencere)

        kart = self.modern_kart(pencere, accent=self.renkler["button_primary_bg"])
        kart.pack(fill="both", expand=True, padx=18, pady=18)
        ust = tk.Frame(kart, bg=self.renkler["kart_arkaplan"], padx=18, pady=14)
        ust.pack(fill="x")
        tk.Label(
            ust,
            text=baslik,
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["yazi_rengi"],
            font=("Segoe UI", 15, "bold"),
        ).pack(side="left")
        self.modern_buton(ust, "Kapat", pencere.destroy, purpose='default', small=True).pack(side="right")

        govde = tk.Frame(kart, bg=self.renkler["input_bg"], padx=10, pady=10)
        govde.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        foto_lbl = tk.Label(
            govde,
            image=img if img else "",
            text="" if img else "Yukleniyor...",
            bg=self.renkler["input_bg"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 11, "bold"),
        )
        foto_lbl.image = img
        if img:
            self._foto_referanslari.append(img)
        foto_lbl.pack(fill="both", expand=True)
        if not img and self.foto_referansi_url_mu(foto_data):
            def yukleme_bitti(_data):
                try:
                    yeni_img = self.foto_data_to_image_cached(foto_data, max_size=(980, 680))
                    if yeni_img:
                        foto_lbl.configure(image=yeni_img, text="")
                        foto_lbl.image = yeni_img
                        self._foto_referanslari.append(yeni_img)
                    else:
                        foto_lbl.configure(text="Fotograf goruntulenemedi.")
                except tk.TclError:
                    pass

            self.foto_url_arka_planda_yukle(foto_data, yukleme_bitti)
        self.pencere_ortala(pencere, parent)
        pencere.lift(parent)
        pencere.focus_force()
        return pencere

    def hayvan_fotograflari(self, hayvan):
        fotograflar = []
        for foto in hayvan.get('foto_urls') or []:
            if foto and foto not in fotograflar:
                fotograflar.append(foto)
        eski_url = hayvan.get('foto_url')
        if eski_url and eski_url not in fotograflar:
            fotograflar.append(eski_url)
        for foto in hayvan.get('foto_paths') or []:
            if foto and foto not in fotograflar:
                fotograflar.append(foto)
        eski_path = hayvan.get('foto_path')
        if eski_path and eski_path not in fotograflar:
            fotograflar.append(eski_path)
        for foto in hayvan.get('foto_datas') or []:
            if foto and foto not in fotograflar:
                fotograflar.append(foto)
        eski_foto = hayvan.get('foto_data')
        if eski_foto and eski_foto not in fotograflar:
            fotograflar.append(eski_foto)
        return fotograflar[:3]

    def hayvan_fotograflari_ata(self, hayvan, fotograflar):
        temiz = []
        for foto in fotograflar or []:
            if foto and foto not in temiz:
                temiz.append(foto)
            if len(temiz) >= 3:
                break
        path_liste = []
        url_liste = []
        data_liste = []
        for foto in temiz:
            path = self.foto_storage_path_from_ref(foto)
            if path and path not in path_liste:
                path_liste.append(path)
            if self.foto_referansi_url_mu(foto):
                url_liste.append(foto)
            elif not path:
                data_liste.append(foto)
        hayvan['foto_paths'] = path_liste
        hayvan['foto_path'] = path_liste[0] if path_liste else None
        hayvan['foto_urls'] = url_liste
        hayvan['foto_url'] = url_liste[0] if url_liste else None
        hayvan['foto_datas'] = data_liste
        hayvan['foto_data'] = data_liste[0] if data_liste else None
        return temiz

    def hayvan_gorunen_kupe(self, h_id, hayvan):
        return (hayvan or {}).get('ciftlik_kupe_no') or (hayvan or {}).get('resmi_kupe_no') or str(h_id)

    def yavru_gorunen_kupe(self, yavru):
        return (yavru or {}).get('ciftlik_kupe_no') or (yavru or {}).get('resmi_kupe_no') or (yavru or {}).get('kupe') or "-"

    def yavru_hayvan_id_bul(self, yavru, aktif_olsun=False):
        for alan in ('hayvan_id', 'id', 'ciftlik_kupe_no', 'resmi_kupe_no', 'kupe'):
            ref = str((yavru or {}).get(alan) or '').strip()
            if not ref or ref == "-":
                continue
            hayvan_id = self.hayvan_referans_coz(ref, aktif_olsun=aktif_olsun)
            if hayvan_id:
                return hayvan_id
        return None

    def dogum_gorunur_yavrular(self, dogum):
        gorunur = []
        for yavru in (dogum or {}).get('yavrular') or []:
            if self.yavru_hayvan_id_bul(yavru):
                gorunur.append(yavru)
        return gorunur

    def dogum_gecmisi_gosterilmeli_mi(self, dogum):
        yavrular = (dogum or {}).get('yavrular') or []
        if yavrular and not self.dogum_gorunur_yavrular(dogum) and self.dogum_kaydi_otomatik_yavru_baglantisi_mi(dogum):
            return False
        return True

    def hayvan_referans_anahtarlari(self, h_id, hayvan):
        anahtarlar = {self.kupe_arama_temizle(h_id)}
        for alan in ('id', 'kupe_no', 'resmi_kupe_no', 'ciftlik_kupe_no'):
            anahtar = self.kupe_arama_temizle((hayvan or {}).get(alan))
            if anahtar:
                anahtarlar.add(anahtar)
        anahtarlar.discard("")
        return anahtarlar

    def yavru_referans_anahtarlari(self, yavru):
        anahtarlar = set()
        for alan in ('hayvan_id', 'id', 'kupe', 'resmi_kupe_no', 'ciftlik_kupe_no'):
            anahtar = self.kupe_arama_temizle((yavru or {}).get(alan))
            if anahtar:
                anahtarlar.add(anahtar)
        return anahtarlar

    def dogum_kaydi_otomatik_yavru_baglantisi_mi(self, dogum):
        not_metni = str((dogum or {}).get('not') or '').lower()
        return "anne" in not_metni and "otomatik" in not_metni

    def silinen_hayvan_dogum_referanslarini_temizle(self, silinen_id, silinen_hayvan):
        silinen_anahtarlar = self.hayvan_referans_anahtarlari(silinen_id, silinen_hayvan)
        if not silinen_anahtarlar:
            return [], 0

        degisen_idler = []
        temizlenen_yavru = 0
        for anne_id, anne in list(self.hayvanlar.items()):
            if str(anne_id) == str(silinen_id):
                continue
            dogumlar = anne.get('dogumlar') or []
            if not dogumlar:
                continue

            degisti = False
            yeni_dogumlar = []
            for dogum in dogumlar:
                dogum_kopya = dict(dogum or {})
                yavrular = dogum_kopya.get('yavrular') or []
                if not yavrular:
                    yeni_dogumlar.append(dogum_kopya)
                    continue

                kalan_yavrular = []
                for yavru in yavrular:
                    if silinen_anahtarlar.intersection(self.yavru_referans_anahtarlari(yavru)):
                        temizlenen_yavru += 1
                        degisti = True
                        continue
                    kalan_yavrular.append(yavru)

                dogum_kopya['yavrular'] = kalan_yavrular
                if not kalan_yavrular and self.dogum_kaydi_otomatik_yavru_baglantisi_mi(dogum_kopya):
                    continue
                yeni_dogumlar.append(dogum_kopya)

            if degisti:
                anne['dogumlar'] = yeni_dogumlar
                anne['son_guncelleme'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                degisen_idler.append(str(anne_id))

        return degisen_idler, temizlenen_yavru

    #  ANİMASYON METODLARı 
    def _puls_zamanlayici_iptal_et(self):
        after_id = getattr(self, "_puls_after_id", None)
        if after_id:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
            self._puls_after_id = None

    def _puls_animasyon(self):
        """Indicator bar rengini ABA... şeklinde animasyonla değiştirir."""
        self._puls_after_id = None
        if getattr(self, "_kapanis_istegi", False):
            return
        if not hasattr(self, 'uyari_indicator') or not self.uyari_indicator.winfo_exists():
            return
        # Sadece kritik modda çalışsın
        if not hasattr(self, '_puls_aktif') or not self._puls_aktif:
            return
        try:
            renk1 = self.renkler["ana_kirmizi"]
            renk2 = self.renkler["koyu_kirmizi"]
            current = self.uyari_indicator.cget('bg')
            next_renk = renk2 if current == renk1 else renk1
            self.uyari_indicator.config(bg=next_renk)
            self._puls_after_id = self.root.after(600, self._puls_animasyon)
        except tk.TclError:
            pass

    def modern_form_satir(self, parent, label_text, widget_class, row, col=0, **kwargs):
        """Form satırı: küçük üst-etiket + widget — modern input görünümü."""
        container = tk.Frame(parent, bg=self.renkler["kart_arkaplan"])
        lbl = tk.Label(container, text=label_text.upper(),
                       font=('Segoe UI', 9, 'bold'),
                       bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"])
        lbl.pack(anchor='w', padx=2, pady=(0, 2))
        widget = widget_class(container, **kwargs)
        widget.pack(fill='x', pady=(0, 0), ipady=3)
        container.grid(row=row, column=col, sticky='ew', padx=12, pady=10)
        self.themed_widgets.append((container, 'kart'))
        self.themed_widgets.append((lbl, 'muted_label'))
        return widget

    def tarih_secici_ekle(self, entry):
        if getattr(entry, "_alp_tarih_secici_var", False):
            return entry
        container = entry.master
        mevcut_deger = entry.get()
        try:
            entry.destroy()
        except tk.TclError:
            return entry

        satir = tk.Frame(container, bg=self.renkler["kart_arkaplan"])
        satir.pack(fill="x")
        satir.grid_columnconfigure(0, weight=1)
        self.themed_widgets.append((satir, 'kart'))

        entry_kutu = tk.Frame(
            satir,
            bg=self.renkler["input_bg"],
            width=160,
            height=35,
            highlightthickness=1,
            highlightbackground=self.renkler["kenarlik"],
            highlightcolor=self.renkler["button_primary_bg"],
            bd=0,
        )
        entry_kutu.grid(row=0, column=0, sticky="ew")
        entry_kutu.pack_propagate(False)
        self.themed_widgets.append((entry_kutu, 'input_frame'))
        date_entry = tk.Entry(
            entry_kutu,
            bg=self.renkler["input_bg"],
            fg=self.renkler["yazi_rengi"],
            insertbackground=self.renkler["yazi_rengi"],
            relief="flat",
            bd=0,
            font=("Segoe UI", 11),
            justify="center",
        )
        date_entry.insert(0, mevcut_deger)
        date_entry.pack(fill="x", expand=True, padx=10, pady=6, ipady=4)
        date_entry.bind('<KeyRelease>', self.tarih_formatlama)
        date_entry._alp_tarih_secici_var = True
        btn = self.modern_buton(
            satir,
            "Takvim",
            lambda e=date_entry: self.tarih_secici_ac(e),
            purpose='default',
            width=7,
            small=True,
        )
        btn.grid(row=0, column=1, sticky="e", padx=(8, 0))
        return date_entry

    def _tarih_secici_entry_yaz(self, entry, tarih):
        entry.delete(0, tk.END)
        entry.insert(0, tarih.strftime("%d/%m/%Y"))
        try:
            entry.event_generate("<KeyRelease>")
        except tk.TclError:
            pass

    def _tarih_secici_modern_ac(self, entry):
        try:
            secili = datetime.strptime(entry.get().strip(), "%d/%m/%Y")
        except (ValueError, TypeError):
            secili = datetime.now()

        popup = tk.Toplevel(self.root)
        popup.title("Tarih Seç")
        popup.configure(bg=self.renkler["arkaplan"])
        popup.transient(self.root)
        popup.resizable(False, False)
        popup.geometry("560x520")

        durum = {"yil": secili.year, "ay": secili.month, "gun": secili.day}
        ay_adlari = [
            "",
            "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
            "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
        ]
        hafta_gunleri = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]

        kart = self.modern_kart(popup, accent=self.renkler["button_primary_bg"])
        kart.pack(fill="both", expand=True, padx=14, pady=14)
        kart.configure(padx=14, pady=14)

        baslik = tk.Frame(kart, bg=self.renkler["kart_arkaplan"])
        baslik.pack(fill="x", pady=(0, 10))
        self.themed_widgets.append((baslik, 'kart'))
        tk.Label(
            baslik,
            text="Tarih Seç",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["yazi_rengi"],
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w")
        tk.Label(
            baslik,
            text="Günü seçin veya ay/yılı hızlıca değiştirin.",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(2, 0))

        kontrol = tk.Frame(kart, bg=self.renkler["kart_arkaplan"])
        kontrol.pack(fill="x", pady=(0, 10))
        self.themed_widgets.append((kontrol, 'kart'))

        ay_var = tk.StringVar(value=ay_adlari[durum["ay"]])
        yil_var = tk.StringVar(value=str(durum["yil"]))
        ay_combo = ttk.Combobox(
            kontrol,
            values=ay_adlari[1:],
            textvariable=ay_var,
            state="readonly",
            width=12,
            font=("Segoe UI", 10),
            style='TCombobox',
        )
        yil_spin = tk.Spinbox(
            kontrol,
            from_=1900,
            to=2100,
            textvariable=yil_var,
            width=6,
            font=("Segoe UI", 10, "bold"),
            bg=self.renkler["input_bg"],
            fg=self.renkler["yazi_rengi"],
            insertbackground=self.renkler["yazi_rengi"],
            buttonbackground=self.renkler["kart_ikincil"],
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=self.renkler["kenarlik"],
            highlightcolor=self.renkler["button_primary_bg"],
        )
        donem_band = tk.Frame(
            kart,
            bg=self.renkler["kart_ikincil"],
            padx=12,
            pady=7,
            highlightthickness=1,
            highlightbackground=self.renkler["kenarlik"],
            bd=0,
        )
        donem_band.pack(fill="x", pady=(0, 10))
        self.themed_widgets.append((donem_band, 'soft_panel'))
        donem_label = tk.Label(
            donem_band,
            text="",
            bg=self.renkler["kart_ikincil"],
            fg=self.renkler["yazi_rengi"],
            font=("Segoe UI", 11, "bold"),
        )
        donem_label.pack(side="left")
        self.themed_widgets.append((donem_label, 'label'))
        secili_label = tk.Label(
            donem_band,
            text="",
            bg=self.renkler["kart_ikincil"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 9, "bold"),
        )
        secili_label.pack(side="right")
        self.themed_widgets.append((secili_label, 'muted_label'))

        gunler = tk.Frame(kart, bg=self.renkler["kart_arkaplan"])
        gunler.pack(fill="x")
        self.themed_widgets.append((gunler, 'kart'))

        def gun_sinirla():
            son_gun = calendar.monthrange(durum["yil"], durum["ay"])[1]
            durum["gun"] = min(max(1, int(durum.get("gun") or 1)), son_gun)

        def secimi_goster():
            gun_sinirla()
            donem_label.config(text=f"{ay_adlari[durum['ay']]} {durum['yil']}")
            secili_label.config(
                text=f"Seçili tarih: {datetime(durum['yil'], durum['ay'], durum['gun']).strftime('%d/%m/%Y')}"
            )

        def tarih_yaz(gun):
            durum["gun"] = int(gun)
            self._tarih_secici_entry_yaz(entry, datetime(durum["yil"], durum["ay"], durum["gun"]))
            popup.destroy()

        def ay_degistir(delta):
            ay = durum["ay"] + delta
            yil = durum["yil"]
            if ay < 1:
                ay = 12
                yil -= 1
            elif ay > 12:
                ay = 1
                yil += 1
            durum["ay"] = ay
            durum["yil"] = yil
            ay_var.set(ay_adlari[durum["ay"]])
            yil_var.set(str(durum["yil"]))
            takvimi_ciz()

        def kontrol_degisince(event=None):
            try:
                yeni_ay = ay_adlari.index(ay_var.get())
            except ValueError:
                yeni_ay = durum["ay"]
            try:
                yeni_yil = int(yil_var.get())
            except ValueError:
                yeni_yil = durum["yil"]
            durum["ay"] = max(1, min(12, yeni_ay))
            durum["yil"] = max(1900, min(2100, yeni_yil))
            yil_var.set(str(durum["yil"]))
            takvimi_ciz()

        def bugune_git():
            bugun = datetime.now()
            durum["yil"] = bugun.year
            durum["ay"] = bugun.month
            durum["gun"] = bugun.day
            self._tarih_secici_entry_yaz(entry, bugun)
            popup.destroy()

        def temizle():
            entry.delete(0, tk.END)
            try:
                entry.event_generate("<KeyRelease>")
            except tk.TclError:
                pass
            popup.destroy()

        def takvimi_ciz():
            for child in gunler.winfo_children():
                child.destroy()
            secimi_goster()
            for idx, ad in enumerate(hafta_gunleri):
                tk.Label(
                    gunler,
                    text=ad,
                    bg=self.renkler["kart_arkaplan"],
                    fg=self.renkler["muted"],
                    font=("Segoe UI", 9, "bold"),
                    width=3,
                ).grid(row=0, column=idx, padx=2, pady=(0, 6), sticky="nsew")
                gunler.grid_columnconfigure(idx, weight=1, uniform="tarih_gun")

            bugun = datetime.now()
            cal = calendar.Calendar(firstweekday=0)
            for row, hafta in enumerate(cal.monthdayscalendar(durum["yil"], durum["ay"]), 1):
                for col, gun in enumerate(hafta):
                    if not gun:
                        bos = tk.Label(gunler, text="", bg=self.renkler["kart_arkaplan"], width=3)
                        bos.grid(row=row, column=col, padx=2, pady=3, sticky="nsew")
                        continue
                    aktif = gun == durum["gun"]
                    bugun_mu = gun == bugun.day and durum["ay"] == bugun.month and durum["yil"] == bugun.year
                    bg = self.renkler["button_primary_bg"] if aktif else self.renkler["kart_ikincil"]
                    fg = "#FFFFFF" if aktif else (self.renkler["button_success_bg"] if bugun_mu else self.renkler["yazi_rengi"])
                    tk.Button(
                        gunler,
                        text=str(gun),
                        command=lambda g=gun: tarih_yaz(g),
                        bg=bg,
                        fg=fg,
                        activebackground=self.renkler["button_primary_bg"],
                        activeforeground="#FFFFFF",
                        relief="flat",
                        bd=0,
                        highlightthickness=1,
                        highlightbackground=self.renkler["button_success_bg"] if bugun_mu and not aktif else self.renkler["kenarlik"],
                        width=2,
                        pady=8,
                        font=("Segoe UI", 9, "bold"),
                        cursor="hand2",
                    ).grid(row=row, column=col, padx=2, pady=3, sticky="nsew")

        onceki = self.modern_buton(kontrol, "<", lambda: ay_degistir(-1), purpose='default', width=4, small=True)
        sonraki = self.modern_buton(kontrol, ">", lambda: ay_degistir(1), purpose='default', width=4, small=True)
        onceki.pack(side="left", padx=(0, 6))
        ay_combo.pack(side="left", padx=(0, 6), ipady=4)
        yil_spin.pack(side="left", padx=(0, 6), ipady=5)
        sonraki.pack(side="left", padx=(6, 0))
        ay_combo.bind("<<ComboboxSelected>>", kontrol_degisince)
        yil_spin.config(command=kontrol_degisince)
        yil_spin.bind("<Return>", kontrol_degisince)
        yil_spin.bind("<FocusOut>", kontrol_degisince)

        alt = tk.Frame(kart, bg=self.renkler["kart_arkaplan"])
        alt.pack(fill="x", pady=(12, 0))
        self.themed_widgets.append((alt, 'kart'))
        self.modern_buton(alt, "Bugün", bugune_git, purpose='primary', width=8, small=True).pack(side="left")
        self.modern_buton(alt, "Temizle", temizle, purpose='default', width=8, small=True).pack(side="left", padx=(8, 0))
        self.modern_buton(alt, "Kapat", popup.destroy, purpose='default', width=8, small=True).pack(side="right")

        takvimi_ciz()
        popup.update_idletasks()
        try:
            x = entry.winfo_rootx()
            y = entry.winfo_rooty() + entry.winfo_height() + 6
            popup_w = popup.winfo_width()
            popup_h = popup.winfo_height()
            ekran_w = popup.winfo_screenwidth()
            ekran_h = popup.winfo_screenheight()
            x = min(max(8, x), max(8, ekran_w - popup_w - 8))
            if y + popup_h > ekran_h:
                y = max(8, entry.winfo_rooty() - popup_h - 8)
            popup.geometry(f"+{x}+{y}")
        except tk.TclError:
            self.pencere_ortala(popup, self.root)
        popup.bind("<Escape>", lambda _event: popup.destroy())
        popup.bind("<Left>", lambda _event: ay_degistir(-1))
        popup.bind("<Right>", lambda _event: ay_degistir(1))
        popup.grab_set()

    def tarih_secici_ac(self, entry):
        try:
            return self._tarih_secici_modern_ac(entry)
        except Exception as hata:
            print(f"Tarih seçici modern açılamadı: {hata}")
            return self._tarih_secici_klasik_ac(entry)

    def _tarih_secici_klasik_ac(self, entry):
        try:
            secili = datetime.strptime(entry.get().strip(), "%d/%m/%Y")
        except (ValueError, TypeError):
            secili = datetime.now()

        popup = tk.Toplevel(self.root)
        popup.title("Tarih Seç")
        popup.configure(bg=self.renkler["arkaplan"])
        popup.transient(self.root)
        popup.resizable(False, False)

        durum = {"yil": secili.year, "ay": secili.month}
        ay_adlari = [
            "",
            "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
            "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
        ]
        hafta_gunleri = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]

        kart = self.modern_kart(popup, accent=self.renkler["button_primary_bg"])
        kart.pack(fill="both", expand=True, padx=10, pady=10)
        kart.configure(padx=10, pady=10)

        baslik = tk.Frame(kart, bg=self.renkler["kart_arkaplan"])
        baslik.pack(fill="x", pady=(0, 8))
        self.themed_widgets.append((baslik, 'kart'))

        ay_label = tk.Label(
            baslik,
            text="",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["yazi_rengi"],
            font=("Segoe UI", 12, "bold"),
            width=18,
        )
        self.themed_widgets.append((ay_label, 'label'))

        gunler = tk.Frame(kart, bg=self.renkler["kart_arkaplan"])
        gunler.pack(fill="both")
        self.themed_widgets.append((gunler, 'kart'))

        def tarih_yaz(gun):
            secilen = datetime(durum["yil"], durum["ay"], gun)
            entry.delete(0, tk.END)
            entry.insert(0, secilen.strftime("%d/%m/%Y"))
            try:
                entry.event_generate("<KeyRelease>")
            except tk.TclError:
                pass
            popup.destroy()

        def ay_degistir(delta):
            ay = durum["ay"] + delta
            yil = durum["yil"]
            if ay < 1:
                ay = 12
                yil -= 1
            elif ay > 12:
                ay = 1
                yil += 1
            durum["ay"] = ay
            durum["yil"] = yil
            takvimi_ciz()

        def bugune_git():
            bugun = datetime.now()
            durum["ay"] = bugun.month
            durum["yil"] = bugun.year
            entry.delete(0, tk.END)
            entry.insert(0, bugun.strftime("%d/%m/%Y"))
            takvimi_ciz()

        def takvimi_ciz():
            for child in gunler.winfo_children():
                child.destroy()
            ay_label.config(text=f"{ay_adlari[durum['ay']]} {durum['yil']}")
            for idx, ad in enumerate(hafta_gunleri):
                tk.Label(
                    gunler,
                    text=ad,
                    bg=self.renkler["kart_arkaplan"],
                    fg=self.renkler["muted"],
                    font=("Segoe UI", 8, "bold"),
                    width=5,
                ).grid(row=0, column=idx, padx=2, pady=(0, 4))

            bugun = datetime.now()
            cal = calendar.Calendar(firstweekday=0)
            for row, hafta in enumerate(cal.monthdayscalendar(durum["yil"], durum["ay"]), 1):
                for col, gun in enumerate(hafta):
                    if not gun:
                        tk.Label(gunler, text="", bg=self.renkler["kart_arkaplan"], width=5).grid(row=row, column=col, padx=2, pady=2)
                        continue
                    aktif = gun == secili.day and durum["ay"] == secili.month and durum["yil"] == secili.year
                    bugun_mu = gun == bugun.day and durum["ay"] == bugun.month and durum["yil"] == bugun.year
                    bg = self.renkler["button_primary_bg"] if aktif else self.renkler["kart_ikincil"]
                    fg = "#FFFFFF" if aktif else (self.renkler["button_success_bg"] if bugun_mu else self.renkler["yazi_rengi"])
                    tk.Button(
                        gunler,
                        text=str(gun),
                        command=lambda g=gun: tarih_yaz(g),
                        bg=bg,
                        fg=fg,
                        activebackground=self.renkler["button_primary_bg"],
                        activeforeground="#FFFFFF",
                        relief="flat",
                        width=5,
                        pady=5,
                        font=("Segoe UI", 9, "bold"),
                    ).grid(row=row, column=col, padx=2, pady=2)

        onceki = self.modern_buton(baslik, "<", lambda: ay_degistir(-1), purpose='default', width=4, small=True)
        sonraki = self.modern_buton(baslik, ">", lambda: ay_degistir(1), purpose='default', width=4, small=True)
        onceki.pack(side="left", padx=(0, 6))
        ay_label.pack(side="left", expand=True, fill="x")
        sonraki.pack(side="left", padx=(6, 0))

        alt = tk.Frame(kart, bg=self.renkler["kart_arkaplan"])
        alt.pack(fill="x", pady=(10, 0))
        self.themed_widgets.append((alt, 'kart'))
        self.modern_buton(alt, "Bugün", bugune_git, purpose='primary', width=8, small=True).pack(side="left")
        self.modern_buton(alt, "Kapat", popup.destroy, purpose='default', width=8, small=True).pack(side="right")

        takvimi_ciz()
        try:
            x = entry.winfo_rootx()
            y = entry.winfo_rooty() + entry.winfo_height() + 6
            popup.geometry(f"+{x}+{y}")
        except tk.TclError:
            self.pencere_ortala(popup, self.root)
        popup.grab_set()

    def hayvan_irk_secenekleri(self):
        return [
            "Simental",
            "Holstein",
            "Montofon",
            "Jersey",
            "Angus",
            "Hereford",
            "Şarole",
            "Limuzin",
            "Yerli Kara",
            "Boz Irk",
            "Melez",
            "Diğer",
        ]



    def veri_klasoru_hazirla(self):
        appdata = os.environ.get("APPDATA")
        if not appdata:
            appdata = os.path.join(os.path.expanduser("~"), "AppData", "Roaming")

        self.data_dir = os.path.join(appdata, "ALP Ziraat", "HayvanTakip")
        self.backup_dir = os.path.join(self.data_dir, "yedekler")
        os.makedirs(self.backup_dir, exist_ok=True)

        self.data_file = os.path.join(self.data_dir, "hayvan_verileri.json")
        self.uyari_file = os.path.join(self.data_dir, "okunan_uyarilar.json")
        self.islem_gecmisi_file = os.path.join(self.data_dir, "islem_gecmisi.json")
        self.islem_yedek_dir = os.path.join(self.data_dir, "islem_yedekleri")
        self.api_config_file = os.path.join(self.data_dir, "api_ayarlar.json")
        self.offline_auth_file = os.path.join(self.data_dir, "offline_oturum.json")
        self.remembered_session_file = os.path.join(self.data_dir, "taninan_bilgisayar.json")
        self.pending_sync_file = os.path.join(self.data_dir, "bekleyen_senkron.json")
        self.admin_cache_file = os.path.join(self.data_dir, "admin_onbellek.json")
        self.foto_cache_dir = os.path.join(self.data_dir, "foto_onbellek")
        os.makedirs(self.islem_yedek_dir, exist_ok=True)
        os.makedirs(self.foto_cache_dir, exist_ok=True)

        self.eski_veriyi_tasi("hayvan_verileri.json", self.data_file)
        self.eski_veriyi_tasi("okunan_uyarilar.json", self.uyari_file)
        self.api_url = self.api_url_yukle()
        self.api_modu = bool(self.api_url)
        self.api_cevrimdisi = False
        self.api_offline_oturum = False
        self._api_son_idler = set()
        self._api_base_versions = {}
        self._api_son_hata = None
        self._offline_kullanici_adi = None
        self._offline_sifre = None
        self.pending_update_notes_file = os.path.join(self.data_dir, "bekleyen_guncelleme_notu.json")
        self.bekleyen_senkron = self.bekleyen_senkron_yukle()
        self.admin_onbellek = self.admin_onbellek_yukle()

    def api_url_yukle(self):
        api_url = os.environ.get("ALP_API_URL", "").strip()
        if not api_url:
            if os.path.exists(getattr(self, "api_config_file", "")):
                try:
                    with open(self.api_config_file, "r", encoding="utf-8-sig") as f:
                        api_url = str((json.load(f) or {}).get("api_url", "")).strip()
                except Exception as e:
                    print(f"API ayarları okunamadı: {e}")
            else:
                api_url = VARSAYILAN_API_URL
        return api_url.rstrip("/")

    def api_ayarlarini_kaydet(self, api_url):
        api_url = str(api_url or "").strip().rstrip("/")
        self.api_url = api_url
        self.api_modu = bool(api_url)
        self.api_cevrimdisi = False
        self._api_son_hata = None
        return self.json_dosyasi_kaydet(
            self.api_config_file,
            {"api_url": api_url},
            "api_ayarlar",
            "API Ayar Kayıt Hatası"
        )

    def guncelleme_kontrolu_aktif_mi(self):
        if os.environ.get("ALP_SKIP_UPDATE_CHECK") == "1":
            return False
        if os.environ.get("ALP_FORCE_UPDATE_CHECK") == "1":
            return True
        return bool(getattr(sys, "frozen", False))

    def guncelleme_baslangic_akisi(self):
        if getattr(self, "_kapanis_istegi", False):
            return
        if self._pending_update_notes:
            self.guncelleme_notu_penceresi(self._pending_update_notes, on_close=self.guncelleme_kontrolunu_baslat)
        else:
            self.guncelleme_kontrolunu_baslat()

    def guncelleme_kontrolunu_baslat(self):
        if getattr(self, "_kapanis_istegi", False) or getattr(self, "_guncelleme_kontrol_edildi", False):
            return
        if not self.guncelleme_kontrolu_aktif_mi():
            return
        self._guncelleme_kontrol_edildi = True
        q = queue.Queue()

        def worker():
            try:
                release = self.guncelleme_latest_release_getir()
                q.put(("ok", release))
            except Exception as e:
                q.put(("hata", e))

        def poll():
            if getattr(self, "_kapanis_istegi", False):
                return
            try:
                durum, veri = q.get_nowait()
            except queue.Empty:
                self._track_after(self.root, 150, poll)
                return
            if durum == "hata":
                self.guncelleme_kontrol_hatasi_penceresi(veri)
                return
            if self.guncelleme_var_mi(veri):
                self.guncelleme_zorunlu_penceresi(veri)

        threading.Thread(target=worker, daemon=True).start()
        poll()

    def guncelleme_latest_release_getir(self, timeout=10):
        req = urllib.request.Request(
            GITHUB_LATEST_RELEASE_API,
            headers={
                "User-Agent": f"ALP-Ziraat-Suru-Takip/{APP_VERSION}",
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status >= 400:
                raise RuntimeError(f"GitHub release kontrolü başarısız: HTTP {response.status}")
            return json.loads(response.read().decode("utf-8"))

    def guncelleme_var_mi(self, release):
        if not isinstance(release, dict) or release.get("draft"):
            return False
        tag = release.get("tag_name") or release.get("name") or ""
        return surum_daha_yeni_mi(tag, APP_VERSION)

    def guncelleme_asset_bul(self, release):
        assets = release.get("assets") or []
        aranan_adlar = (UPDATE_SETUP_ASSET, *LEGACY_UPDATE_SETUP_ASSETS)
        for asset in assets:
            asset_adi = str(asset.get("name", "")).lower()
            if any(asset_adi == ad.lower() for ad in aranan_adlar):
                return asset
        for asset in assets:
            ad = str(asset.get("name", "")).lower()
            if ad.endswith(".exe") and "setup" in ad:
                return asset
        for asset in assets:
            if str(asset.get("name", "")).lower().endswith(".exe"):
                return asset
        return None

    def guncelleme_setup_indir(self, release):
        asset = self.guncelleme_asset_bul(release)
        if not asset:
            raise RuntimeError(
                "Son GitHub release içinde kurulum dosyası bulunamadı.\n"
                f"Release asset olarak {UPDATE_SETUP_ASSET} yüklenmeli."
            )
        url = asset.get("browser_download_url")
        if not url:
            raise RuntimeError("Release asset indirme bağlantısı boş.")

        hedef_klasor = os.path.join(tempfile.gettempdir(), "ALP_Ziraat_Update")
        os.makedirs(hedef_klasor, exist_ok=True)
        asset_adi = os.path.basename(str(asset.get("name") or UPDATE_SETUP_ASSET))
        if not asset_adi.lower().endswith(".exe"):
            asset_adi = UPDATE_SETUP_ASSET
        hedef = os.path.join(hedef_klasor, asset_adi)
        gecici = hedef + ".download"

        req = urllib.request.Request(url, headers={"User-Agent": f"ALP-Ziraat-Suru-Takip/{APP_VERSION}"})
        with urllib.request.urlopen(req, timeout=180) as response, open(gecici, "wb") as f:
            shutil.copyfileobj(response, f)
        if os.path.exists(hedef):
            os.remove(hedef)
        os.replace(gecici, hedef)
        return hedef

    def guncelleme_setup_calistir(self, setup_path):
        args = [setup_path, "--launch", "--wait-pid", str(os.getpid())]
        subprocess.Popen(args, cwd=os.path.dirname(setup_path), close_fds=True)

    def guncelleme_notu_kaydet(self, release):
        veri = {
            "version": release.get("tag_name") or release.get("name") or "",
            "title": release.get("name") or release.get("tag_name") or "Güncelleme",
            "body": release.get("body") or "Bu sürüm için açıklama girilmemiş.",
            "url": release.get("html_url") or "",
            "saved_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        }
        with open(self.pending_update_notes_file, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=2)

    def guncelleme_notu_yukle(self):
        yol = getattr(self, "pending_update_notes_file", "")
        if not yol or not os.path.exists(yol):
            return None
        try:
            with open(yol, "r", encoding="utf-8-sig") as f:
                veri = json.load(f) or {}
            if surum_parcalari(veri.get("version")) != surum_parcalari(APP_VERSION):
                return None
            return veri
        except Exception:
            return None

    def guncelleme_notu_temizle(self):
        try:
            if os.path.exists(getattr(self, "pending_update_notes_file", "")):
                os.remove(self.pending_update_notes_file)
        except Exception:
            pass

    def guncelleme_text_alani(self, parent, metin, yukseklik=12):
        frame = tk.Frame(parent, bg=self.renkler["kart_arkaplan"])
        frame.pack(fill="both", expand=True, padx=20, pady=(8, 12))
        text = tk.Text(
            frame,
            height=yukseklik,
            wrap="word",
            bg=self.renkler["input_bg"],
            fg=self.renkler["yazi_rengi"],
            insertbackground=self.renkler["yazi_rengi"],
            relief="flat",
            padx=12,
            pady=10,
            font=("Segoe UI", 10),
        )
        scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        text.insert("1.0", metin or "-")
        text.configure(state="disabled")
        return text

    def guncelleme_notu_penceresi(self, note, on_close=None):
        pencere = tk.Toplevel(self.root)
        pencere.title("Uygulama Güncellendi")
        pencere.geometry("720x520")
        pencere.minsize(560, 420)
        pencere.configure(bg=self.renkler["arkaplan"])
        pencere.transient(self.root)
        pencere.grab_set()
        self.pencere_ortala(pencere, self.root)

        kart = self.modern_kart(pencere, accent=self.renkler["button_success_bg"])
        kart.pack(fill="both", expand=True, padx=18, pady=18)
        tk.Label(
            kart,
            text=f"Güncelleme tamamlandı: {note.get('title') or note.get('version')}",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["yazi_rengi"],
            font=("Segoe UI", 18, "bold"),
            wraplength=640,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(18, 6))
        tk.Label(
            kart,
            text="Bu sürümde yapılan değişiklikler:",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=20)
        self.guncelleme_text_alani(kart, note.get("body") or "-", yukseklik=13)

        def kapat():
            self.guncelleme_notu_temizle()
            try:
                pencere.grab_release()
            except tk.TclError:
                pass
            pencere.destroy()
            if on_close:
                on_close()

        self.modern_buton(kart, "Tamam", kapat, purpose="primary", width=16).pack(anchor="e", padx=20, pady=(0, 18))
        pencere.protocol("WM_DELETE_WINDOW", kapat)

    def guncelleme_kontrol_hatasi_penceresi(self, hata):
        pencere = tk.Toplevel(self.root)
        pencere.title("Sürüm Kontrolü")
        pencere.geometry("560x320")
        pencere.configure(bg=self.renkler["arkaplan"])
        pencere.transient(self.root)
        pencere.grab_set()
        self.pencere_ortala(pencere, self.root)

        kart = self.modern_kart(pencere, accent=self.renkler["button_danger_bg"])
        kart.pack(fill="both", expand=True, padx=18, pady=18)
        tk.Label(kart, text="Sürüm kontrolü yapılamadı", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=("Segoe UI", 17, "bold")).pack(anchor="w", padx=20, pady=(18, 8))
        tk.Label(
            kart,
            text="Uygulamanın son sürüm olduğundan emin olmak için internet bağlantısı ve GitHub release kontrolü gerekli.",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 10),
            wraplength=500,
            justify="left",
        ).pack(anchor="w", padx=20)
        tk.Label(kart, text=str(hata), bg=self.renkler["kart_arkaplan"], fg=self.renkler["button_danger_bg"], font=("Segoe UI", 9), wraplength=500, justify="left").pack(anchor="w", padx=20, pady=(10, 0))

        alt = tk.Frame(kart, bg=self.renkler["kart_arkaplan"])
        alt.pack(fill="x", padx=20, pady=(22, 18))
        self.themed_widgets.append((alt, "kart"))

        def tekrar():
            try:
                pencere.grab_release()
            except tk.TclError:
                pass
            pencere.destroy()
            self._guncelleme_kontrol_edildi = False
            self.guncelleme_kontrolunu_baslat()

        def cik():
            self.uygulamayi_kapat()

        self.modern_buton(alt, "Çıkış", cik, purpose="danger", width=12, small=True).pack(side="right")
        self.modern_buton(alt, "Tekrar Dene", tekrar, purpose="primary", width=14, small=True).pack(side="right", padx=(0, 8))
        pencere.protocol("WM_DELETE_WINDOW", cik)

    def guncelleme_zorunlu_penceresi(self, release):
        tag = release.get("tag_name") or release.get("name") or "-"
        body = release.get("body") or "Bu sürüm için açıklama girilmemiş."

        pencere = tk.Toplevel(self.root)
        pencere.title("Zorunlu Güncelleme")
        pencere.geometry("760x560")
        pencere.minsize(600, 460)
        pencere.configure(bg=self.renkler["arkaplan"])
        pencere.transient(self.root)
        pencere.grab_set()
        self.pencere_ortala(pencere, self.root)

        kart = self.modern_kart(pencere, accent=self.renkler["button_warning_bg"])
        kart.pack(fill="both", expand=True, padx=18, pady=18)
        tk.Label(
            kart,
            text="Yeni sürüm var, güncellemeniz gerekiyor",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["yazi_rengi"],
            font=("Segoe UI", 18, "bold"),
            wraplength=680,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(18, 6))
        tk.Label(
            kart,
            text=f"Mevcut sürüm: v{APP_VERSION}    |    Yeni sürüm: {tag}",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", padx=20, pady=(0, 8))
        tk.Label(
            kart,
            text="Güncelleme yapılmadan uygulama kullanılmayacak. Güncelle'ye bastığınızda kurulum dosyası indirilip çalıştırılır.",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 10),
            wraplength=690,
            justify="left",
        ).pack(anchor="w", padx=20)
        self.guncelleme_text_alani(kart, body, yukseklik=12)

        durum_var = tk.StringVar(value="Hazır")
        durum = tk.Label(kart, textvariable=durum_var, bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 9), anchor="w")
        durum.pack(fill="x", padx=20, pady=(0, 8))

        alt = tk.Frame(kart, bg=self.renkler["kart_arkaplan"])
        alt.pack(fill="x", padx=20, pady=(0, 18))
        self.themed_widgets.append((alt, "kart"))

        q = queue.Queue()

        def indir_ve_kur():
            guncelle_btn.enabled = False
            guncelle_btn.itemconfig(guncelle_btn.text_item, text="İndiriliyor...")
            durum_var.set("Kurulum dosyası indiriliyor. Lütfen bekleyin.")

            def worker():
                try:
                    setup = self.guncelleme_setup_indir(release)
                    self.guncelleme_notu_kaydet(release)
                    self.guncelleme_setup_calistir(setup)
                    q.put(("ok", None))
                except Exception as e:
                    q.put(("hata", e))

            def poll():
                try:
                    sonuc, veri = q.get_nowait()
                except queue.Empty:
                    self._track_after(pencere, 150, poll)
                    return
                if sonuc == "ok":
                    durum_var.set("Kurulum başlatıldı. Uygulama kapanıyor.")
                    self._track_after(self.root, 700, self.uygulamayi_kapat)
                    return
                guncelle_btn.enabled = True
                guncelle_btn.itemconfig(guncelle_btn.text_item, text="Güncelle")
                durum_var.set(f"Güncelleme başlatılamadı: {veri}")

            threading.Thread(target=worker, daemon=True).start()
            poll()

        def cik():
            self.uygulamayi_kapat()

        self.modern_buton(alt, "Çıkış", cik, purpose="danger", width=12, small=True).pack(side="right")
        guncelle_btn = self.modern_buton(alt, "Güncelle", indir_ve_kur, purpose="primary", width=14, small=True)
        guncelle_btn.pack(side="right", padx=(0, 8))
        pencere.protocol("WM_DELETE_WINDOW", cik)

    def eski_veri_yollari(self, dosya_adi):
        adaylar = [
            os.path.abspath(dosya_adi),
            os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), dosya_adi),
        ]
        benzersiz = []
        for yol in adaylar:
            if yol not in benzersiz:
                benzersiz.append(yol)
        return benzersiz

    def eski_veriyi_tasi(self, dosya_adi, hedef_yol):
        if os.path.exists(hedef_yol):
            return
        for kaynak_yol in self.eski_veri_yollari(dosya_adi):
            if os.path.abspath(kaynak_yol) == os.path.abspath(hedef_yol):
                continue
            if os.path.exists(kaynak_yol):
                try:
                    shutil.copy2(kaynak_yol, hedef_yol)
                    return
                except Exception as e:
                    messagebox.showwarning("Veri Taşıma Hatası", f"Eski veri dosyası taşınamadı:\n{kaynak_yol}\n\n{e}")

    def yedek_olustur(self, dosya_yolu, etiket):
        if not os.path.exists(dosya_yolu) or os.path.getsize(dosya_yolu) == 0:
            return None
        zaman = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        yedek_yolu = os.path.join(self.backup_dir, f"{etiket}_{zaman}.json")
        shutil.copy2(dosya_yolu, yedek_yolu)
        self.eski_yedekleri_temizle(etiket)
        return yedek_yolu

    def eski_yedekleri_temizle(self, etiket, limit=30):
        try:
            yedekler = [
                os.path.join(self.backup_dir, ad)
                for ad in os.listdir(self.backup_dir)
                if ad.startswith(f"{etiket}_") and ad.endswith(".json")
            ]
            yedekler.sort(key=os.path.getmtime, reverse=True)
            for eski_yedek in yedekler[limit:]:
                os.remove(eski_yedek)
        except Exception as e:
            print(f"Yedek temizleme hatası: {e}")

    def json_dosyasi_yukle(self, dosya_yolu, varsayilan, etiket):
        if not os.path.exists(dosya_yolu):
            return varsayilan
        try:
            with open(dosya_yolu, 'r', encoding='utf-8-sig') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            zaman = datetime.now().strftime("%Y%m%d_%H%M%S")
            bozuk_yedek = os.path.join(self.backup_dir, f"{etiket}_bozuk_{zaman}.json")
            try:
                shutil.copy2(dosya_yolu, bozuk_yedek)
            except Exception:
                bozuk_yedek = "yedek alınamadı"
            messagebox.showwarning(
                "Veri Hatası",
                f"{os.path.basename(dosya_yolu)} okunamadı ve güvenlik için bozuk kopyası saklandı.\n"
                f"Yedek: {bozuk_yedek}\n\nHata: {e}"
            )
            return varsayilan
        except Exception as e:
            messagebox.showwarning("Veri Hatası", f"{os.path.basename(dosya_yolu)} okunurken hata oluştu: {e}")
            return varsayilan

    def json_dosyasi_kaydet(self, dosya_yolu, veri, etiket, hata_basligi):
        gecici_yol = f"{dosya_yolu}.tmp"
        try:
            os.makedirs(os.path.dirname(dosya_yolu), exist_ok=True)
            self.yedek_olustur(dosya_yolu, etiket)
            with open(gecici_yol, 'w', encoding='utf-8') as f:
                json.dump(veri, f, ensure_ascii=False, indent=4)
                f.flush()
                os.fsync(f.fileno())
            os.replace(gecici_yol, dosya_yolu)
            return True
        except Exception as e:
            try:
                if os.path.exists(gecici_yol):
                    os.remove(gecici_yol)
            except Exception:
                pass
            messagebox.showerror(hata_basligi, f"Veriler kaydedilemedi: {e}")
            return False

    def yerel_sifre_hashle(self, sifre):
        salt = secrets.token_hex(16)
        iterations = 210_000
        digest = hashlib.pbkdf2_hmac("sha256", str(sifre).encode("utf-8"), bytes.fromhex(salt), iterations)
        return f"pbkdf2_sha256${iterations}${salt}${digest.hex()}"

    def yerel_sifre_dogrula(self, sifre, sifre_hash):
        try:
            algoritma, iterations, salt_hex, digest_hex = str(sifre_hash or "").split("$", 3)
            if algoritma != "pbkdf2_sha256":
                return False
            digest = hashlib.pbkdf2_hmac(
                "sha256",
                str(sifre).encode("utf-8"),
                bytes.fromhex(salt_hex),
                int(iterations),
            )
            return hmac.compare_digest(digest.hex(), digest_hex)
        except Exception:
            return False

    def offline_auth_yukle(self):
        veri = self.json_dosyasi_yukle(self.offline_auth_file, {}, "offline_oturum")
        return veri if isinstance(veri, dict) else {}

    def offline_auth_kaydet(self, kullanici_adi, sifre, kullanici):
        veri = {
            "api_url": getattr(self, "api_url", ""),
            "kullanici_adi": str(kullanici_adi or "").strip().lower(),
            "sifre_hash": self.yerel_sifre_hashle(sifre),
            "kullanici": kullanici or {},
            "kayit_zamani": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        }
        return self.json_dosyasi_kaydet(
            self.offline_auth_file,
            veri,
            "offline_oturum",
            "Offline Oturum Kayit Hatası",
        )

    def offline_giris_dene(self, kullanici_adi, sifre, asil_hata):
        cache = self.offline_auth_yukle()
        beklenen_kullanici = str(cache.get("kullanici_adi") or "").strip().lower()
        girilen_kullanici = str(kullanici_adi or "").strip().lower()
        if not beklenen_kullanici or beklenen_kullanici != girilen_kullanici:
            raise ApiHatasi(f"Online giris yapilamadi ve bu kullanici icin offline oturum yok.\n{asil_hata}")
        cache_api_url = str(cache.get("api_url") or "").strip().rstrip("/")
        mevcut_api_url = str(getattr(self, "api_url", "") or "").strip().rstrip("/")
        if cache_api_url and mevcut_api_url and cache_api_url != mevcut_api_url:
            raise ApiHatasi("Offline oturum farkli bir API adresi icin kayitli.")
        if not self.yerel_sifre_dogrula(sifre, cache.get("sifre_hash")):
            raise ApiHatasi("Offline oturum sifresi hatali.")
        self.api_token = None
        self.api_kullanici = cache.get("kullanici") or {}
        self.api_cevrimdisi = True
        self.api_offline_oturum = True
        self._api_son_hata = str(asil_hata)
        self._offline_kullanici_adi = girilen_kullanici
        self._offline_sifre = sifre
        return True

    def taninan_bilgisayar_yukle(self):
        veri = self.json_dosyasi_yukle(
            getattr(self, "remembered_session_file", ""),
            {},
            "taninan_bilgisayar",
        )
        return veri if isinstance(veri, dict) else {}

    def taninan_bilgisayar_kaydet(self, device_token, kullanici):
        if not device_token:
            return False
        veri = {
            "api_url": getattr(self, "api_url", ""),
            "device_token": device_token,
            "kullanici": kullanici or {},
            "kayit_zamani": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        }
        return self.json_dosyasi_kaydet(
            self.remembered_session_file,
            veri,
            "taninan_bilgisayar",
            "Tanınan Bilgisayar Kayıt Hatası",
        )

    def taninan_bilgisayar_temizle(self):
        try:
            if os.path.exists(getattr(self, "remembered_session_file", "")):
                os.remove(self.remembered_session_file)
        except Exception as e:
            print(f"Tanınan bilgisayar temizlenemedi: {e}")

    def taninan_bilgisayar_token_al(self):
        try:
            yanit = self.api_istek("POST", "/api/auth/device-token", {}, timeout=20)
            return (yanit or {}).get("device_token")
        except ApiHatasi as e:
            print(f"Tanınan bilgisayar token alınamadı: {e}")
            return None

    def taninan_bilgisayar_giris_dene(self):
        if not getattr(self, "api_modu", False):
            return False
        cache = self.taninan_bilgisayar_yukle()
        device_token = cache.get("device_token")
        if not device_token:
            return False
        if cache.get("api_url") and cache.get("api_url") != getattr(self, "api_url", ""):
            return False
        try:
            yanit = self.api_istek(
                "POST",
                "/api/auth/device-login",
                {"device_token": device_token},
                timeout=25,
                auth=False,
            )
            token = (yanit or {}).get("access_token")
            if not token:
                return False
            self.api_token = token
            self.api_kullanici = (yanit or {}).get("kullanici") or cache.get("kullanici") or {}
            self.api_cevrimdisi = False
            self.api_offline_oturum = False
            self._api_son_hata = None
            self.taninan_bilgisayar_kaydet(device_token, self.api_kullanici)
            return True
        except ApiHatasi as e:
            if e.status in (400, 401, 403):
                self.taninan_bilgisayar_temizle()
            elif cache.get("kullanici"):
                self.api_token = None
                self.api_kullanici = cache.get("kullanici") or {}
                self.api_cevrimdisi = True
                self.api_offline_oturum = True
                self._api_son_hata = str(e)
                return True
            print(f"Tanınan bilgisayar girişi başarısız: {e}")
            return False

    def bekleyen_senkron_yukle(self):
        veri = self.json_dosyasi_yukle(
            getattr(self, "pending_sync_file", ""),
            {"upserts": {}, "deletes": {}, "updated_at": None},
            "bekleyen_senkron",
        )
        if not isinstance(veri, dict):
            veri = {}
        veri.setdefault("upserts", {})
        veri.setdefault("deletes", {})
        veri.setdefault("updated_at", None)
        return veri

    def bekleyen_senkron_kaydet(self):
        self.bekleyen_senkron["updated_at"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        return self.json_dosyasi_kaydet(
            self.pending_sync_file,
            self.bekleyen_senkron,
            "bekleyen_senkron",
            "Bekleyen Senkron Kayit Hatası",
        )

    def bekleyen_senkron_sayisi(self):
        veri = getattr(self, "bekleyen_senkron", {}) or {}
        return len(veri.get("upserts", {}) or {}) + len(veri.get("deletes", {}) or {})

    def bekleyen_senkron_var(self):
        return self.bekleyen_senkron_sayisi() > 0

    def bekleyen_senkron_upsert(self, h_id, veri):
        h_id = str(h_id)
        self.bekleyen_senkron.setdefault("deletes", {}).pop(h_id, None)
        onceki = (self.bekleyen_senkron.get("upserts", {}) or {}).get(h_id) or {}
        base_version = onceki.get("base_son_guncelleme") or getattr(
            self, "_api_base_versions", {}
        ).get(h_id)
        kayit = copy.deepcopy(self.hayvan_kayit_tamamla(h_id, veri))
        kayit["id"] = h_id
        if base_version:
            kayit["base_son_guncelleme"] = base_version
        self.bekleyen_senkron.setdefault("upserts", {})[h_id] = kayit

    def bekleyen_senkron_delete(self, h_id):
        h_id = str(h_id)
        self.bekleyen_senkron.setdefault("upserts", {}).pop(h_id, None)
        self.bekleyen_senkron.setdefault("deletes", {})[h_id] = {
            "id": h_id,
            "zaman": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "base_son_guncelleme": getattr(self, "_api_base_versions", {}).get(h_id),
        }

    def bekleyen_senkron_snapshot_guncelle(self, hedef_id=None):
        onceki_idler = set(getattr(self, "_api_son_idler", set()))
        if hedef_id is not None:
            h_id = str(hedef_id)
            hayvanlar = getattr(self, "hayvanlar", {}) or {}
            if h_id in hayvanlar:
                self.bekleyen_senkron_upsert(h_id, hayvanlar[h_id])
            elif h_id in onceki_idler:
                self.bekleyen_senkron_delete(h_id)
            return self.bekleyen_senkron_kaydet()

        mevcut_idler = {str(h_id) for h_id in getattr(self, "hayvanlar", {}).keys()}
        for silinen_id in sorted(onceki_idler - mevcut_idler):
            self.bekleyen_senkron_delete(silinen_id)
        for h_id, veri in getattr(self, "hayvanlar", {}).items():
            self.bekleyen_senkron_upsert(h_id, veri)
        return self.bekleyen_senkron_kaydet()

    def admin_onbellek_yukle(self):
        veri = self.json_dosyasi_yukle(
            getattr(self, "admin_cache_file", ""),
            {"ciftlikler": [], "kullanicilar": [], "updated_at": None},
            "admin_onbellek",
        )
        if not isinstance(veri, dict):
            veri = {}
        veri.setdefault("ciftlikler", [])
        veri.setdefault("kullanicilar", [])
        veri.setdefault("updated_at", None)
        return veri

    def admin_onbellek_kaydet(self, ciftlikler=None, kullanicilar=None):
        onbellek = copy.deepcopy(getattr(self, "admin_onbellek", {}) or {})
        if ciftlikler is not None:
            onbellek["ciftlikler"] = ciftlikler if isinstance(ciftlikler, list) else []
        if kullanicilar is not None:
            onbellek["kullanicilar"] = kullanicilar if isinstance(kullanicilar, list) else []
        onbellek["updated_at"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.admin_onbellek = onbellek
        return self.json_dosyasi_kaydet(
            self.admin_cache_file,
            onbellek,
            "admin_onbellek",
            "Admin Onbellek Kayit Hatasi",
        )

    def api_ref(self, deger):
        return urllib.parse.quote(str(deger), safe="")

    def api_istek(self, method, path, payload=None, timeout=12, auth=True):
        if not getattr(self, "api_url", ""):
            raise ApiHatasi("API adresi ayarlı değil.")
        data = None
        headers = {"Accept": "application/json"}
        if auth and getattr(self, "api_token", None):
            headers["Authorization"] = f"Bearer {self.api_token}"
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        try:
            request = urllib.request.Request(
                f"{self.api_url}{path}",
                data=data,
                headers=headers,
                method=method,
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            detay = e.read().decode("utf-8", errors="replace")
            mesaj = detay
            try:
                parsed = json.loads(detay)
                mesaj = parsed.get("detail", detay) if isinstance(parsed, dict) else detay
            except Exception:
                pass
            raise ApiHatasi(f"API {e.code}: {mesaj}", status=e.code) from e
        except urllib.error.URLError as e:
            raise ApiHatasi(f"API bağlantısı kurulamadı: {e.reason}") from e
        except socket.timeout as e:
            raise ApiHatasi("API isteği zaman aşımına uğradı.") from e
        except TimeoutError as e:
            raise ApiHatasi("API isteği zaman aşımına uğradı.") from e
        except Exception as e:
            raise ApiHatasi(f"API isteği tamamlanamadı: {e}") from e

    def api_giris_yap(self, kullanici_adi, sifre, bu_bilgisayari_tani=False):
        try:
            yanit = self.api_istek(
                "POST",
                "/api/auth/login",
                {"kullanici_adi": kullanici_adi, "sifre": sifre},
                timeout=60,
                auth=False
            )
        except ApiHatasi as e:
            if e.status in (400, 401, 403):
                raise
            return self.offline_giris_dene(kullanici_adi, sifre, e)
        token = (yanit or {}).get("access_token")
        if not token:
            raise ApiHatasi("API giriş yanıtında token yok.")
        self.api_token = token
        self.api_kullanici = (yanit or {}).get("kullanici") or {}
        self.api_cevrimdisi = False
        self.api_offline_oturum = False
        self._api_son_hata = None
        self._offline_kullanici_adi = str(kullanici_adi or "").strip().lower()
        self._offline_sifre = sifre
        self.offline_auth_kaydet(kullanici_adi, sifre, self.api_kullanici)
        if bu_bilgisayari_tani:
            device_token = self.taninan_bilgisayar_token_al()
            if device_token:
                self.taninan_bilgisayar_kaydet(device_token, self.api_kullanici)
        return True

    def api_online_oturum_ac(self):
        if getattr(self, "api_token", None) and not getattr(self, "api_offline_oturum", False):
            return True
        if self.taninan_bilgisayar_giris_dene() and getattr(self, "api_token", None):
            return True
        kullanici_adi = getattr(self, "_offline_kullanici_adi", None)
        sifre = getattr(self, "_offline_sifre", None)
        if not kullanici_adi or not sifre:
            cache = self.offline_auth_yukle()
            kullanici_adi = cache.get("kullanici_adi")
            if not kullanici_adi:
                raise ApiHatasi("Online oturum yenilenemedi: offline kullanici bilgisi yok.")
            raise ApiHatasi("Online oturum yenilemek icin once internet varken tekrar giris yapin.")
        yanit = self.api_istek(
            "POST",
            "/api/auth/login",
            {"kullanici_adi": kullanici_adi, "sifre": sifre},
            timeout=60,
            auth=False,
        )
        token = (yanit or {}).get("access_token")
        if not token:
            raise ApiHatasi("API giris yanitinda token yok.")
        self.api_token = token
        self.api_kullanici = (yanit or {}).get("kullanici") or {}
        self.api_cevrimdisi = False
        self.api_offline_oturum = False
        self._api_son_hata = None
        self.offline_auth_kaydet(kullanici_adi, sifre, self.api_kullanici)
        return True

    def offline_modda_mi(self):
        return bool(
            getattr(self, "api_modu", False)
            and (getattr(self, "api_cevrimdisi", False) or getattr(self, "api_offline_oturum", False))
        )

    def online_islem_gerekli(self, islem_adi, parent=None):
        if not self.offline_modda_mi():
            return True
        bekleyen = self.bekleyen_senkron_sayisi()
        ek = f"\n\nBekleyen hayvan degisikligi: {bekleyen}" if bekleyen else ""
        messagebox.showwarning(
            "Offline Mod",
            f"{islem_adi} internet yokken kapali.\n\nHayvan kayitlari yerel onbellekte calisir; ciftlik, kullanici, sifre ve gecmis islemleri icin API baglantisi gerekir.{ek}",
            parent=parent or getattr(self, "root", None),
        )
        return False

    def api_hayvan_kayit_gonder(self, h_id, veri, onceki_idler=None):
        h_id = str(h_id)
        onceki_idler = set(onceki_idler or set())
        payload = self.hayvan_kayit_tamamla(h_id, veri)
        payload["id"] = h_id
        base_version = payload.pop("base_son_guncelleme", None) or getattr(
            self, "_api_base_versions", {}
        ).get(h_id)
        if self.admin_mi() and getattr(self, "admin_aktif_ciftlik_id", None):
            payload["ciftlik_id"] = payload.get("ciftlik_id") or self.admin_aktif_ciftlik_id
            payload["ciftlik_ad"] = payload.get("ciftlik_ad") or self.admin_aktif_ciftlik_ad

        if h_id in onceki_idler:
            try:
                patch_path = f"/api/hayvanlar/{self.api_ref(h_id)}"
                if base_version:
                    patch_path += f"?beklenen_son_guncelleme={self.api_ref(base_version)}"
                kayit = self.api_istek("PATCH", patch_path, payload)
            except ApiHatasi as e:
                if e.status != 404:
                    raise
                kayit = self.api_istek("POST", "/api/hayvanlar", payload)
        else:
            try:
                kayit = self.api_istek("POST", "/api/hayvanlar", payload)
            except ApiHatasi as e:
                hata_metni = str(e).lower()
                if e.status == 409 and "eski offline" in hata_metni:
                    return h_id, None

                # Yeni kayitta 404 gibi gercek POST hatalarini PATCH ile maskelemeyelim.
                # Sadece ayni id zaten sunucuda varsa mevcut kaydi guncellemeyi dene.
                ayni_id_cakismasi = (
                    e.status in (400, 409)
                    and "id" in hata_metni
                    and ("zaten" in hata_metni or "kayit" in hata_metni or "kayıt" in hata_metni)
                )
                if not ayni_id_cakismasi:
                    raise
                patch_path = f"/api/hayvanlar/{self.api_ref(h_id)}"
                if base_version:
                    patch_path += f"?beklenen_son_guncelleme={self.api_ref(base_version)}"
                kayit = self.api_istek("PATCH", patch_path, payload)

        kayit_id = str((kayit or {}).get("id") or h_id)
        yeni_version = (kayit or {}).get("son_guncelleme")
        if yeni_version:
            self._api_base_versions.pop(h_id, None)
            self._api_base_versions[kayit_id] = yeni_version
        return kayit_id, self.hayvan_kayit_tamamla(kayit_id, kayit or payload)

    def bekleyen_senkron_gonder(self, sessiz=False, ui_guncelle=True):
        if not getattr(self, "api_modu", False):
            return True
        if not self.bekleyen_senkron_var():
            if not sessiz:
                messagebox.showinfo("Senkron", "Bekleyen degisiklik yok.", parent=getattr(self, "root", None))
            return True

        try:
            self.api_online_oturum_ac()
            bekleyen = copy.deepcopy(self.bekleyen_senkron)
            upserts = bekleyen.get("upserts", {}) or {}
            deletes = bekleyen.get("deletes", {}) or {}
            onceki_idler = set(getattr(self, "_api_son_idler", set()))

            for h_id in sorted(deletes.keys()):
                delete_info = deletes.get(h_id) or {}
                silme_zamani = delete_info.get("zaman")
                base_version = delete_info.get("base_son_guncelleme") or getattr(
                    self, "_api_base_versions", {}
                ).get(str(h_id))
                delete_path = f"/api/hayvanlar/{self.api_ref(h_id)}?kalici=true"
                if silme_zamani:
                    delete_path += f"&degisiklik_zamani={self.api_ref(silme_zamani)}"
                if base_version:
                    delete_path += f"&beklenen_son_guncelleme={self.api_ref(base_version)}"
                try:
                    sonuc = self.api_istek("DELETE", delete_path, timeout=20)
                except ApiHatasi as e:
                    if e.status != 404:
                        raise
                    sonuc = None
                if isinstance(sonuc, dict) and sonuc.get("status") == "skipped":
                    kayit = self.api_istek("GET", f"/api/hayvanlar/{self.api_ref(h_id)}", timeout=20)
                    kayit_id = str((kayit or {}).get("id") or h_id)
                    self.hayvanlar[kayit_id] = self.hayvan_kayit_tamamla(kayit_id, kayit or {})
                    onceki_idler.add(kayit_id)
                    continue
                onceki_idler.discard(str(h_id))
                self.hayvanlar.pop(str(h_id), None)
                self._api_base_versions.pop(str(h_id), None)

            for h_id, veri in upserts.items():
                kayit_id, tamamlanmis = self.api_hayvan_kayit_gonder(h_id, veri, onceki_idler)
                if tamamlanmis is None:
                    onceki_idler.discard(str(h_id))
                    self.hayvanlar.pop(str(h_id), None)
                    continue
                onceki_idler.discard(str(h_id))
                onceki_idler.add(kayit_id)
                if str(h_id) in self.hayvanlar and str(h_id) != kayit_id:
                    self.hayvanlar.pop(str(h_id), None)
                self.hayvanlar[kayit_id] = tamamlanmis

            self._api_son_idler = onceki_idler
            self.bekleyen_senkron = {"upserts": {}, "deletes": {}, "updated_at": None}
            self.bekleyen_senkron_kaydet()
            self.json_dosyasi_kaydet(self.data_file, self.hayvanlar, "hayvan_verileri", "API Onbellek Kayit Hatasi")
            self.api_cevrimdisi = False
            self.api_offline_oturum = False
            self._api_son_hata = None
            self.api_durum_guncelle()
            if not sessiz:
                messagebox.showinfo("Senkron", "Bekleyen degisiklikler API'ye gonderildi.", parent=getattr(self, "root", None))
            return True
        except ApiHatasi as e:
            self.api_cevrimdisi = True
            self._api_son_hata = str(e)
            self.api_durum_guncelle()
            if not sessiz:
                messagebox.showwarning(
                    "Senkron",
                    f"Senkron tamamlanamadi:\n{e}\n\nDegisiklikler yerel kuyrukta tutuluyor.",
                    parent=getattr(self, "root", None),
                )
            return False

    def bekleyen_senkron_gonder_ui(self):
        return self.api_senkronize_et_ui()

    def api_baglantiyi_yenile_sessiz(self):
        if not getattr(self, "api_modu", False):
            return False
        if not getattr(self, "api_token", None) or getattr(self, "api_offline_oturum", False):
            self.api_online_oturum_ac()
        if self.bekleyen_senkron_var() and not self.bekleyen_senkron_gonder(sessiz=True):
            hata = getattr(self, "_api_son_hata", None) or "Bekleyen offline degisiklikler senkronlanamadi."
            raise ApiHatasi(hata)
        self.hayvanlar = self.api_hayvanlari_yukle()
        self.json_dosyasi_kaydet(self.data_file, self.hayvanlar, "hayvan_verileri", "API Onbellek Kayit Hatasi")
        if hasattr(self, "notebook"):
            if hasattr(self, "notebook"):
                self.ekranlari_guncelle()
            self.header_ozet_guncelle()
        self.api_durum_guncelle()
        return True

    def api_senkronize_et_ui(self):
        if not getattr(self, "api_modu", False):
            return messagebox.showinfo("Senkronizasyon", "Uygulama yerel veri modunda.", parent=getattr(self, "root", None))
        bekleyen_once = self.bekleyen_senkron_sayisi()
        try:
            if self.api_baglantiyi_yenile_sessiz():
                if bekleyen_once:
                    mesaj = (
                        "API baglantisi yenilendi.\n"
                        f"{bekleyen_once} bekleyen degisiklik API'ye gonderildi.\n"
                        "Veriler guncellendi."
                    )
                else:
                    mesaj = "API baglantisi yenilendi ve veriler guncellendi."
                messagebox.showinfo("Senkronizasyon", mesaj, parent=getattr(self, "root", None))
        except ApiHatasi as e:
            self.api_cevrimdisi = True
            self._api_son_hata = str(e)
            self.api_durum_guncelle()
            messagebox.showwarning(
                "Senkronizasyon",
                f"API baglantisi kurulamadi:\n{e}\n\nBekleyen degisiklikler yerel kuyrukta tutuluyor.",
                parent=getattr(self, "root", None),
            )

    def api_baglantiyi_yenile_ui(self):
        return self.api_senkronize_et_ui()

    def api_oturumu_temizle(self):
        self.api_token = None
        self.api_kullanici = None
        self.admin_aktif_ciftlik_id = None
        self.admin_aktif_ciftlik_ad = None
        self.api_cevrimdisi = False
        self.api_offline_oturum = False
        self._api_son_hata = None

    def aktif_zamanlayicilari_durdur(self):
        self.uyari_thread_running = False
        self._cancel_tracked_afters()
        for after_attr in ("_uyari_after_id", "_saat_after_id", "_baslangic_after_id", "_puls_after_id", "_otomatik_baglanti_after_id"):
            after_id = getattr(self, after_attr, None)
            if after_id:
                try:
                    self.root.after_cancel(after_id)
                except tk.TclError:
                    pass
                setattr(self, after_attr, None)

    def login_akisini_baslat(self, otomatik_giris=True):
        while getattr(self, "api_modu", False):
            self._login_yeniden_iste = False
            self.api_oturumu_temizle()
            otomatik_giris_basarili = False
            if otomatik_giris:
                otomatik_giris_basarili = self.taninan_bilgisayar_giris_dene()
            if not otomatik_giris_basarili and not self.api_giris_penceresi():
                return False
            if not self.admin_mi():
                return True
            if self.admin_yonetim_merkezi():
                self.themed_widgets = []
                self.themed_buttons = []
                return True
            if getattr(self, "_login_yeniden_iste", False):
                self.taninan_bilgisayar_temizle()
                self._offline_kullanici_adi = None
                self._offline_sifre = None
                otomatik_giris = False
                continue
            return False
        return True

    def oturumu_kapat_ve_login(self, onay_iste=True):
        if not getattr(self, "api_modu", False):
            return self.uygulamayi_kapat()
        if onay_iste and not messagebox.askyesno("Çıkış Yap", "Oturum kapatılıp giriş ekranına dönülsün mü?", parent=self.root):
            return
        self.taninan_bilgisayar_temizle()
        self._offline_kullanici_adi = None
        self._offline_sifre = None
        self.aktif_zamanlayicilari_durdur()
        for child in self.root.winfo_children():
            child.destroy()
        self.themed_widgets = []
        self.themed_buttons = []
        if not self.login_akisini_baslat(otomatik_giris=False):
            return self.uygulamayi_kapat()
        self.hayvanlar = self.veri_yukle()
        self.geri_al_yigini = []
        self.okunan_uyarilar = self.okunan_uyarilar_yukle()
        self.islem_gecmisi = self.islem_gecmisi_yukle()
        self.uyari_thread_running = True
        self._kapanis_istegi = False
        self.ana_interface_olustur()
        self.uyari_sistemi_baslat()
        self.root.protocol("WM_DELETE_WINDOW", self.uygulamayi_kapat)

    def api_giris_penceresi(self):
        sonuc = {"ok": False}
        tamam = tk.BooleanVar(value=False)

        for child in self.root.winfo_children():
            child.destroy()

        self.root.title("ALP Ziraat - Giris")
        try:
            self.root.attributes("-fullscreen", False)
            self.root.state("normal")
        except tk.TclError:
            pass
        self.root.geometry("460x500")
        self.root.minsize(460, 500)
        self.root.resizable(False, False)
        self.root.configure(bg=self.renkler["arkaplan"])
        self.root.deiconify()
        self.root.lift()

        login_sayfa = tk.Frame(self.root, bg=self.renkler["arkaplan"])
        login_sayfa.pack(fill="both", expand=True)

        kutu = tk.Frame(
            login_sayfa,
            bg=self.renkler["kart_arkaplan"],
            padx=28,
            pady=26,
            highlightthickness=1,
            highlightbackground=self.renkler["kenarlik"],
        )
        kutu.pack(fill="both", expand=True, padx=26, pady=26)

        login_header = tk.Frame(kutu, bg=self.renkler["kart_arkaplan"])
        login_header.pack(fill="x", pady=(0, 16))
        self.themed_widgets.append((login_header, 'kart'))

        logo_kutu = tk.Frame(login_header, bg=self.renkler["kart_arkaplan"], padx=0, pady=0, highlightthickness=0)
        logo_kutu.pack(side="left")
        try:
            logo_img = Image.open(self.logo_path).convert("RGBA")
            logo_img.thumbnail((132, 54), Image.Resampling.LANCZOS)
            self.login_logo_gorsel = ImageTk.PhotoImage(logo_img)
            tk.Label(logo_kutu, image=self.login_logo_gorsel, bg=self.renkler["kart_arkaplan"]).pack()
        except Exception:
            tk.Label(logo_kutu, text="ALP", bg=self.renkler["kart_arkaplan"], fg=self.renkler["ana_kirmizi"], font=("Segoe UI", 18, "bold")).pack()

        baslik_kutu = tk.Frame(login_header, bg=self.renkler["kart_arkaplan"])
        baslik_kutu.pack(side="left", padx=(14, 0), fill="x", expand=True)
        self.themed_widgets.append((baslik_kutu, 'kart'))
        tk.Label(
            baslik_kutu,
            text="Çiftlik hesabınıza giriş yapın",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", pady=(16, 0))

        tk.Label(
            kutu,
            text="Kullanıcı adı",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")
        kullanici_entry = ttk.Entry(kutu, font=("Segoe UI", 11), style="TEntry")
        kullanici_entry.pack(fill="x", pady=(5, 12), ipady=6)

        tk.Label(
            kutu,
            text="Şifre",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")
        sifre_entry = ttk.Entry(kutu, font=("Segoe UI", 11), style="TEntry", show="*")
        sifre_entry.pack(fill="x", pady=(5, 10), ipady=6)

        beni_tani_var = tk.BooleanVar(value=False)
        beni_tani = tk.Checkbutton(
            kutu,
            text="Bu bilgisayarı tanı",
            variable=beni_tani_var,
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["muted"],
            selectcolor=self.renkler["input_bg"],
            activebackground=self.renkler["kart_arkaplan"],
            activeforeground=self.renkler["yazi_rengi"],
            font=("Segoe UI", 9),
            relief="flat",
            anchor="w",
        )
        beni_tani.pack(anchor="w", pady=(0, 8))

        durum_label = tk.Label(
            kutu,
            text="",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["ana_kirmizi"],
            font=("Segoe UI", 9),
            wraplength=350,
            justify="left",
        )
        durum_label.pack(anchor="w", fill="x", pady=(0, 6))

        login_state = {"running": False, "finished": False, "tick": 0}
        login_queue = queue.Queue()

        def bitir(ok, login_iste=False):
            login_state["finished"] = True
            sonuc["ok"] = ok
            self._login_yeniden_iste = bool(login_iste)
            try:
                tamam.set(True)
            except tk.TclError:
                pass

        def form_kilitli(kilitli):
            entry_state = "disabled" if kilitli else "normal"
            check_state = "disabled" if kilitli else "normal"
            cursor = "watch" if kilitli else "hand2"
            try:
                kullanici_entry.configure(state=entry_state)
                sifre_entry.configure(state=entry_state)
                beni_tani.configure(state=check_state)
                giris_btn.configure(cursor=cursor)
                giris_btn.enabled = not kilitli
                cikis_btn.configure(cursor="hand2")
                cikis_btn.enabled = True
            except tk.TclError:
                pass

        def giris_animasyonu():
            if not login_state.get("running") or login_state.get("finished"):
                return
            login_state["tick"] = login_state.get("tick", 0) + 1
            noktalar = "." * ((login_state["tick"] % 3) + 1)
            try:
                durum_label.config(text=f"Giris yapiliyor{noktalar}", fg=self.renkler["muted"])
                self._track_after(self.root, 350, giris_animasyonu)
            except tk.TclError:
                pass

        def giris_sonuc_kontrol():
            if login_state.get("finished"):
                return
            try:
                hata = login_queue.get_nowait()
            except queue.Empty:
                if login_state.get("running"):
                    self._track_after(self.root, 100, giris_sonuc_kontrol)
                return

            login_state["running"] = False
            form_kilitli(False)
            if hata:
                durum_label.config(text=hata, fg=self.renkler["ana_kirmizi"])
                try:
                    sifre_entry.configure(state="normal")
                    sifre_entry.delete(0, tk.END)
                    sifre_entry.focus_force()
                except tk.TclError:
                    pass
                return
            bitir(True)

        def giris():
            if login_state.get("running"):
                return
            kullanici_adi = kullanici_entry.get().strip()
            sifre = sifre_entry.get()
            if not kullanici_adi or not sifre:
                durum_label.config(text="Kullanıcı adı ve şifre zorunludur.")
                return
            bu_bilgisayari_tani = bool(beni_tani_var.get())
            login_state["running"] = True
            login_state["tick"] = 0
            form_kilitli(True)
            durum_label.config(text="Giris yapiliyor...", fg=self.renkler["muted"])
            giris_animasyonu()

            def login_worker():
                hata = None
                try:
                    self.api_giris_yap(kullanici_adi, sifre, bu_bilgisayari_tani=bu_bilgisayari_tani)
                except ApiHatasi as e:
                    hata = str(e)
                except Exception as e:
                    hata = f"Beklenmeyen giris hatasi: {e}"
                login_queue.put(hata)

            threading.Thread(target=login_worker, daemon=True).start()
            self._track_after(self.root, 100, giris_sonuc_kontrol)

        def iptal():
            bitir(False)

        btn_frame = tk.Frame(kutu, bg=self.renkler["kart_arkaplan"])
        btn_frame.pack(fill="x", pady=(0, 0))
        self.themed_widgets.append((btn_frame, 'kart'))
        giris_btn = self.modern_buton(btn_frame, "Giriş", giris, purpose='primary', width=13, small=True)
        giris_btn.pack(side="left", padx=(0, 10))
        cikis_btn = self.modern_buton(btn_frame, "Çıkış", iptal, purpose='default', width=13, small=True)
        cikis_btn.pack(side="left")

        def pencereyi_ortala():
            self.root.update_idletasks()
            genislik = self.root.winfo_width()
            yukseklik = self.root.winfo_height()
            x = max((self.root.winfo_screenwidth() - genislik) // 2, 0)
            y = max((self.root.winfo_screenheight() - yukseklik) // 2, 0)
            self.root.geometry(f"{genislik}x{yukseklik}+{x}+{y}")

        self.root.protocol("WM_DELETE_WINDOW", iptal)
        self.root.bind("<Escape>", lambda event: iptal())
        sifre_entry.bind("<Return>", lambda event: giris())
        kullanici_entry.bind("<Return>", lambda event: sifre_entry.focus_set())
        pencereyi_ortala()
        self._track_after(self.root, 100, kullanici_entry.focus_force)

        try:
            self.root.wait_variable(tamam)
        except tk.TclError:
            return False

        self._cancel_tracked_afters()
        for child in self.root.winfo_children():
            child.destroy()
        self.root.unbind("<Escape>")

        if not sonuc["ok"]:
            return False

        self.root.title("ALP Ziraat - Sürü Takip Sistemi")
        self.root.geometry("1500x900")
        self.root.minsize(1000, 700)
        self.root.resizable(True, True)
        self.root.configure(bg=self.renkler["arkaplan"])
        self.root.update_idletasks()
        self.root.lift()
        return True

    def admin_mi(self):
        return (getattr(self, "api_kullanici", None) or {}).get("rol") == "admin"

    def api_ciftlikleri_yukle(self):
        ciftlikler = self.api_istek("GET", "/api/ciftlikler?aktif_dahil=true", timeout=20)
        ciftlikler = ciftlikler if isinstance(ciftlikler, list) else []
        self.admin_onbellek_kaydet(ciftlikler=ciftlikler)
        return ciftlikler

    def api_kullanicilari_yukle(self):
        kullanicilar = self.api_istek("GET", "/api/kullanicilar", timeout=20)
        kullanicilar = kullanicilar if isinstance(kullanicilar, list) else []
        self.admin_onbellek_kaydet(kullanicilar=kullanicilar)
        return kullanicilar

    def api_islem_gecmisi_yukle(self, limit=100, **filtreler):
        params = {"limit": int(limit)}
        for anahtar, deger in filtreler.items():
            if deger is None:
                continue
            deger = str(deger).strip()
            if deger:
                params[anahtar] = deger
        query = urllib.parse.urlencode(params)
        kayitlar = self.api_istek("GET", f"/api/islem-gecmisi?{query}", timeout=20)
        return kayitlar if isinstance(kayitlar, list) else []

    def admin_online_yedek_indir(self, parent=None):
        parent = parent or self.root
        if not self.admin_mi():
            return messagebox.showerror("Yedek", "Bu islem icin admin yetkisi gerekir.", parent=parent)
        if not self.online_islem_gerekli("Online yedek alma", parent):
            return
        zaman = datetime.now().strftime("%Y%m%d_%H%M%S")
        varsayilan_ad = f"alp_online_yedek_{zaman}.json"
        dosya = filedialog.asksaveasfilename(
            parent=parent,
            title="Online Yedek Kaydet",
            defaultextension=".json",
            initialfile=varsayilan_ad,
            filetypes=[("JSON", "*.json"), ("Tum dosyalar", "*.*")],
        )
        if not dosya:
            return

        pencere = tk.Toplevel(parent)
        pencere.title("Online Yedek İndiriliyor")
        pencere.configure(bg=self.renkler["kart_arkaplan"])
        pencere.resizable(False, False)
        pencere.transient(parent)
        pencere.protocol("WM_DELETE_WINDOW", lambda: None)

        govde = tk.Frame(pencere, bg=self.renkler["kart_arkaplan"], padx=22, pady=18)
        govde.pack(fill="both", expand=True)
        tk.Label(
            govde,
            text="Online yedek hazırlanıyor...",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["yazi_rengi"],
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")
        durum_label = tk.Label(
            govde,
            text="Render servisi uyanıyorsa bu işlem 1-2 dakika sürebilir.",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 9),
            wraplength=360,
            justify="left",
        )
        durum_label.pack(anchor="w", pady=(6, 12))
        progress = ttk.Progressbar(govde, mode="indeterminate", length=360)
        progress.pack(fill="x")
        progress.start(12)
        self.pencere_ortala(pencere, parent)
        pencere.grab_set()

        sonuc_kuyrugu = queue.Queue()

        def worker():
            try:
                try:
                    self.api_istek("GET", "/api/health", timeout=20, auth=False)
                except Exception:
                    pass
                yedek = None
                son_hata = None
                for deneme in range(2):
                    try:
                        yedek = self.api_istek("GET", "/api/yedek", timeout=180)
                        break
                    except ApiHatasi as e:
                        son_hata = e
                        if deneme == 0:
                            continue
                if yedek is None:
                    raise son_hata or ApiHatasi("Online yedek cevabı boş geldi.")
                with open(dosya, "w", encoding="utf-8") as f:
                    json.dump(yedek, f, ensure_ascii=False, indent=2)
                sonuc_kuyrugu.put(("ok", dosya))
            except Exception as e:
                sonuc_kuyrugu.put(("hata", str(e)))

        def poll():
            try:
                durum, veri = sonuc_kuyrugu.get_nowait()
            except queue.Empty:
                if pencere.winfo_exists():
                    self._track_after(pencere, 150, poll)
                return

            try:
                progress.stop()
                pencere.grab_release()
                pencere.destroy()
            except tk.TclError:
                pass

            if durum == "ok":
                messagebox.showinfo("Yedek", f"Online yedek kaydedildi:\n{veri}", parent=parent)
            else:
                messagebox.showerror("Yedek", f"Online yedek alınamadı:\n{veri}", parent=parent)

        threading.Thread(target=worker, daemon=True).start()
        self._track_after(pencere, 150, poll)

    def admin_sistem_durumu_penceresi(self, parent=None):
        parent = parent or self.root
        if not self.admin_mi():
            return messagebox.showerror("Sistem Durumu", "Bu islem icin admin yetkisi gerekir.", parent=parent)
        if not self.online_islem_gerekli("Sistem durumu", parent):
            return
        try:
            durum = self.api_istek("GET", "/api/sistem-durumu", timeout=25)
        except ApiHatasi as e:
            return messagebox.showerror("Sistem Durumu", f"Sistem durumu alinamadi:\n{e}", parent=parent)

        pencere = tk.Toplevel(parent)
        pencere.title("Sistem Durumu")
        pencere.geometry("760x620")
        pencere.minsize(620, 480)
        pencere.configure(bg=self.renkler["arkaplan"])
        pencere.transient(parent)
        self.uygula_pencere_ikonu(pencere)

        sayfa = self.kaydirilabilir_sayfa(pencere, padx=20, pady=18)
        tk.Label(
            sayfa,
            text="Sistem Durumu",
            bg=self.renkler["arkaplan"],
            fg=self.renkler["yazi_rengi"],
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor="w")
        tk.Label(
            sayfa,
            text="Veritabanı, Storage ve kayıt sayıları.",
            bg=self.renkler["arkaplan"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(2, 14))

        def kart(baslik, accent=None):
            k = self.modern_kart(sayfa, accent=accent or self.renkler["button_primary_bg"])
            k.pack(fill="x", pady=(0, 12))
            ic = tk.Frame(k, bg=self.renkler["kart_arkaplan"], padx=18, pady=14)
            ic.pack(fill="both", expand=True)
            tk.Label(
                ic,
                text=baslik,
                bg=self.renkler["kart_arkaplan"],
                fg=self.renkler["yazi_rengi"],
                font=("Segoe UI", 14, "bold"),
            ).pack(anchor="w", pady=(0, 10))
            return ic

        def satir(parent_frame, etiket, deger, renk=None):
            f = tk.Frame(parent_frame, bg=self.renkler["kart_arkaplan"])
            f.pack(fill="x", pady=3)
            tk.Label(
                f,
                text=etiket,
                bg=self.renkler["kart_arkaplan"],
                fg=self.renkler["muted"],
                font=("Segoe UI", 9, "bold"),
                width=24,
                anchor="w",
            ).pack(side="left")
            tk.Label(
                f,
                text=str(deger),
                bg=self.renkler["kart_arkaplan"],
                fg=renk or self.renkler["yazi_rengi"],
                font=("Segoe UI", 10, "bold"),
                anchor="w",
            ).pack(side="left", fill="x", expand=True)

        database = durum.get("database") or {}
        storage = durum.get("storage") or {}
        sayilar = durum.get("kayit_sayilari") or {}
        fotograflar = durum.get("fotograflar") or {}

        db_kart = kart("Veritabanı", self.renkler["button_primary_bg"])
        db_mb = database.get("boyut_mb")
        db_limit = database.get("limit_mb")
        yuzde = database.get("kullanim_yuzde")
        satir(db_kart, "Altyapı", database.get("backend") or "-")
        satir(db_kart, "Kullanım", f"{db_mb if db_mb is not None else '-'} MB / {db_limit} MB")
        satir(db_kart, "Doluluk", f"%{yuzde}" if yuzde is not None else "-")

        storage_kart = kart("Fotoğraf Storage", self.renkler["button_success_bg"])
        storage_renk = self.renkler["yesil"] if storage.get("aktif") else self.renkler["uyari"]
        satir(storage_kart, "Durum", "Aktif" if storage.get("aktif") else "Pasif", storage_renk)
        satir(storage_kart, "Bucket", storage.get("bucket") or "-")
        satir(storage_kart, "Planlanan limit", f"{storage.get('limit_mb', '-')} MB")
        satir(storage_kart, "Tahmini kapasite", f"{storage.get('tahmini_foto_kapasitesi', '-')} fotoğraf")

        foto_kart = kart("Fotoğraflar", self.renkler["uyari"])
        satir(foto_kart, "Fotoğraflı hayvan", fotograflar.get("fotografli_hayvan", 0))
        satir(foto_kart, "Storage dosya", fotograflar.get("storage_path_adet", fotograflar.get("storage_url_adet", 0)))
        satir(foto_kart, "DB içindeki foto", fotograflar.get("database_base64_adet", 0))
        satir(foto_kart, "DB foto boyutu", f"{fotograflar.get('database_base64_mb', 0)} MB")

        kayit_kart = kart("Kayıt Sayıları", self.renkler["button_default_bg"])
        for etiket, anahtar in [
            ("Çiftlik", "ciftlik"),
            ("Kullanıcı", "kullanici"),
            ("Hayvan", "hayvan"),
            ("Aktif hayvan", "aktif_hayvan"),
            ("Arşivli hayvan", "arsivli_hayvan"),
            ("Tohumlama", "tohumlama"),
            ("Aşı/prosedür", "asi_prosedur"),
            ("İşlem geçmişi", "islem_gecmisi"),
        ]:
            satir(kayit_kart, etiket, sayilar.get(anahtar, 0))

        alt = tk.Frame(sayfa, bg=self.renkler["arkaplan"])
        alt.pack(fill="x", pady=(4, 12))
        self.modern_buton(alt, "Kapat", pencere.destroy, purpose="default", small=True).pack(side="right")
        self.pencere_ortala(pencere, parent)
        pencere.lift(parent)

    def admin_veri_sagligi_penceresi(self, parent=None):
        parent = parent or self.root
        if not self.admin_mi():
            return messagebox.showerror("Veri Sağlığı", "Bu işlem için admin yetkisi gerekir.", parent=parent)
        if not self.online_islem_gerekli("Veri sağlığı", parent):
            return

        pencere = tk.Toplevel(parent)
        pencere.title("Veri Sağlığı")
        pencere.geometry("980x680")
        pencere.minsize(760, 520)
        pencere.configure(bg=self.renkler["arkaplan"])
        pencere.transient(parent)
        self.uygula_pencere_ikonu(pencere)

        ana = tk.Frame(pencere, bg=self.renkler["arkaplan"], padx=18, pady=16)
        ana.pack(fill="both", expand=True)

        ust = tk.Frame(ana, bg=self.renkler["arkaplan"])
        ust.pack(fill="x", pady=(0, 12))
        tk.Label(
            ust,
            text="Veri Sağlığı",
            bg=self.renkler["arkaplan"],
            fg=self.renkler["yazi_rengi"],
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor="w")
        tk.Label(
            ust,
            text="Çiftlik, kullanıcı, küpe, tarih ve fotoğraf kayıtlarını canlı veri üzerinde denetler. Bu ekran veri silmez.",
            bg=self.renkler["arkaplan"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 10),
            wraplength=860,
            justify="left",
        ).pack(anchor="w", pady=(2, 0))

        ozet_frame = tk.Frame(
            ana,
            bg=self.renkler["kart_arkaplan"],
            padx=14,
            pady=12,
            highlightthickness=1,
            highlightbackground=self.renkler["kenarlik"],
        )
        ozet_frame.pack(fill="x", pady=(0, 12))

        durum_label = tk.Label(
            ozet_frame,
            text="Kontrol bekleniyor.",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        )
        durum_label.pack(fill="x", pady=(0, 8))

        rozet_satiri = tk.Frame(ozet_frame, bg=self.renkler["kart_arkaplan"])
        rozet_satiri.pack(fill="x")
        rozetler = {}

        def rozet(anahtar, baslik, renk):
            kutu = tk.Frame(rozet_satiri, bg=self.renkler["kart_ikincil"], padx=12, pady=8, highlightthickness=1, highlightbackground=self.renkler["kenarlik"])
            kutu.pack(side="left", padx=(0, 8), fill="x", expand=True)
            tk.Label(kutu, text=baslik, bg=self.renkler["kart_ikincil"], fg=self.renkler["muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
            lbl = tk.Label(kutu, text="0", bg=self.renkler["kart_ikincil"], fg=renk, font=("Segoe UI", 16, "bold"))
            lbl.pack(anchor="w")
            rozetler[anahtar] = lbl

        rozet("kritik", "Kritik", self.renkler["ana_kirmizi"])
        rozet("uyari", "Uyarı", self.renkler["uyari"])
        rozet("bilgi", "Bilgi", self.renkler["muted"])
        rozet("hayvan", "Hayvan", self.renkler["button_primary_bg"])

        orta = tk.Frame(ana, bg=self.renkler["arkaplan"])
        orta.pack(fill="both", expand=True)
        orta.rowconfigure(0, weight=1)
        orta.columnconfigure(0, weight=1)

        tree_frame = tk.Frame(orta, bg=self.renkler["kart_arkaplan"], highlightthickness=1, highlightbackground=self.renkler["kenarlik"])
        tree_frame.grid(row=0, column=0, sticky="nsew")
        kolonlar = ("seviye", "baslik", "adet", "mesaj")
        tree = ttk.Treeview(tree_frame, columns=kolonlar, show="headings", style="Modern.Treeview")
        v_scroll = tk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=v_scroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        for col, baslik, genislik in [
            ("seviye", "Seviye", 90),
            ("baslik", "Kontrol", 220),
            ("adet", "Adet", 70),
            ("mesaj", "Mesaj", 520),
        ]:
            tree.heading(col, text=baslik)
            tree.column(col, width=genislik, anchor="w" if col != "adet" else "center", stretch=(col == "mesaj"))
        tree.tag_configure("kritik", foreground=self.renkler["ana_kirmizi"])
        tree.tag_configure("uyari", foreground=self.renkler["uyari"])
        tree.tag_configure("bilgi", foreground=self.renkler["muted"])

        detay_frame = tk.Frame(ana, bg=self.renkler["kart_arkaplan"], padx=12, pady=10, highlightthickness=1, highlightbackground=self.renkler["kenarlik"])
        detay_frame.pack(fill="x", pady=(12, 0))
        tk.Label(detay_frame, text="Seçili kontrol detayı", bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
        detay_text = tk.Text(
            detay_frame,
            height=6,
            bg=self.renkler["input_bg"],
            fg=self.renkler["yazi_rengi"],
            relief="flat",
            wrap="word",
            font=("Segoe UI", 9),
        )
        detay_text.pack(fill="x", pady=(4, 0))
        detay_text.configure(state="disabled")

        son_kontroller = []

        def detay_yaz(metin):
            detay_text.configure(state="normal")
            detay_text.delete("1.0", tk.END)
            detay_text.insert("1.0", metin)
            detay_text.configure(state="disabled")

        def secili_detay(event=None):
            secim = tree.selection()
            if not secim:
                detay_yaz("")
                return
            index = int(secim[0])
            if index < 0 or index >= len(son_kontroller):
                detay_yaz("")
                return
            kayit = son_kontroller[index]
            satirlar = [
                f"Seviye: {kayit.get('seviye', '-')}",
                f"Kontrol: {kayit.get('baslik', '-')}",
                f"Adet: {kayit.get('adet', 0)}",
                "",
                kayit.get("mesaj") or "",
            ]
            if kayit.get("onerilen_islem"):
                satirlar.extend(["", f"Önerilen işlem: {kayit.get('onerilen_islem')}"])
            ornekler = kayit.get("ornekler") or []
            if ornekler:
                satirlar.extend(["", "Örnekler:"])
                satirlar.extend(f"- {ornek}" for ornek in ornekler)
            detay_yaz("\n".join(satirlar))

        tree.bind("<<TreeviewSelect>>", secili_detay)

        def liste_yenile():
            nonlocal son_kontroller
            durum_label.config(text="Veri sağlığı kontrol ediliyor...", fg=self.renkler["muted"])
            pencere.update_idletasks()
            try:
                rapor = self.api_istek("GET", "/api/admin/veri-sagligi", timeout=60)
            except ApiHatasi as e:
                durum_label.config(text="Veri sağlığı alınamadı.", fg=self.renkler["ana_kirmizi"])
                return messagebox.showerror("Veri Sağlığı", f"Kontrol çalıştırılamadı:\n{e}", parent=pencere)

            son_kontroller = rapor.get("kontroller") or []
            for item in tree.get_children():
                tree.delete(item)
            for idx, kayit in enumerate(son_kontroller):
                seviye = kayit.get("seviye") or "bilgi"
                tree.insert(
                    "",
                    "end",
                    iid=str(idx),
                    values=(
                        seviye.upper(),
                        kayit.get("baslik") or "-",
                        kayit.get("adet", 0),
                        kayit.get("mesaj") or "",
                    ),
                    tags=(seviye,),
                )

            ozet = rapor.get("ozet") or {}
            sayilar = rapor.get("sayilar") or {}
            for anahtar in ("kritik", "uyari", "bilgi"):
                rozetler[anahtar].config(text=str(ozet.get(anahtar, 0)))
            rozetler["hayvan"].config(text=str(sayilar.get("hayvan", 0)))

            genel = rapor.get("genel_durum") or "bilinmiyor"
            renk = self.renkler["yesil"] if genel == "saglikli" else (self.renkler["ana_kirmizi"] if genel == "kritik" else self.renkler["uyari"])
            durum_label.config(
                text=f"Genel durum: {genel.upper()}  |  Oluşturma: {rapor.get('olusturma_zamani', '-')}",
                fg=renk,
            )
            if son_kontroller:
                tree.selection_set("0")
                tree.focus("0")
                secili_detay()
            else:
                detay_yaz("Kontrol sonucu bulunamadı.")

        alt = tk.Frame(ana, bg=self.renkler["arkaplan"])
        alt.pack(fill="x", pady=(12, 0))
        self.modern_buton(alt, "Yenile", liste_yenile, purpose="primary", small=True).pack(side="left")
        self.modern_buton(alt, "Sistem Durumu", lambda: self.admin_sistem_durumu_penceresi(pencere), purpose="default", small=True).pack(side="left", padx=8)
        self.modern_buton(alt, "Kapat", pencere.destroy, purpose="default", small=True).pack(side="right")

        self.pencere_ortala(pencere, parent)
        pencere.lift(parent)
        liste_yenile()

    def sifre_degistir_penceresi(self, parent=None):
        parent = parent or self.root
        if not self.online_islem_gerekli("Sifre degistirme", parent):
            return
        eski = simpledialog.askstring("Sifre Degistir", "Mevcut sifre:", show="*", parent=parent)
        if eski is None:
            return
        yeni = simpledialog.askstring("Sifre Degistir", "Yeni sifre (en az 8 karakter):", show="*", parent=parent)
        if yeni is None:
            return
        tekrar = simpledialog.askstring("Sifre Degistir", "Yeni sifre tekrar:", show="*", parent=parent)
        if tekrar is None:
            return
        if yeni != tekrar:
            return messagebox.showerror("Sifre Degistir", "Yeni sifreler ayni degil.", parent=parent)
        try:
            self.api_istek(
                "POST",
                "/api/auth/change-password",
                {"eski_sifre": eski, "yeni_sifre": yeni},
                timeout=20,
            )
            messagebox.showinfo("Sifre Degistir", "Sifreniz degistirildi.", parent=parent)
        except ApiHatasi as e:
            messagebox.showerror("Sifre Degistir", str(e), parent=parent)

    def admin_islem_gecmisi_penceresi(self):
        if not self.online_islem_gerekli("Islem gecmisi", self.root):
            return
        pencere = tk.Toplevel(self.root)
        baslik = "Son Islemler" if self.admin_mi() else "Islem Gecmisim"
        pencere.title(baslik)
        pencere.geometry("1180x680")
        pencere.configure(bg=self.renkler["arkaplan"])
        pencere.transient(self.root)
        pencere.grab_set()
        son_kayitlar = []

        ana = tk.Frame(pencere, bg=self.renkler["arkaplan"], padx=16, pady=16)
        ana.pack(fill="both", expand=True)
        tk.Label(
            ana,
            text=baslik,
            bg=self.renkler["arkaplan"],
            fg=self.renkler["yazi_rengi"],
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w", pady=(0, 12))

        filtre = tk.Frame(ana, bg=self.renkler["kart_arkaplan"], padx=12, pady=10, highlightthickness=1, highlightbackground=self.renkler["kenarlik"])
        filtre.pack(fill="x", pady=(0, 12))
        for col in range(6):
            filtre.columnconfigure(col, weight=1)

        def filtre_entry(label, row, col, width=16):
            tk.Label(filtre, text=label, bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 8, "bold")).grid(row=row, column=col, sticky="w", padx=5)
            entry = ttk.Entry(filtre, style="TEntry", width=width)
            entry.grid(row=row + 1, column=col, sticky="ew", padx=5, pady=(2, 8))
            return entry

        arama_entry = filtre_entry("Arama", 0, 0)
        kullanici_entry = filtre_entry("Kullanici", 0, 1)
        tip_entry = filtre_entry("Islem tipi", 0, 2)
        ciftlik_entry = filtre_entry("Ciftlik ID", 0, 3)
        hedef_tipi_entry = filtre_entry("Hedef tipi", 0, 4)
        hedef_id_entry = filtre_entry("Hedef ID", 0, 5)
        baslangic_entry = filtre_entry("Baslangic (GG/AA/YYYY)", 2, 0)
        bitis_entry = filtre_entry("Bitis (GG/AA/YYYY)", 2, 1)
        limit_entry = filtre_entry("Limit", 2, 2)
        limit_entry.insert(0, "200")

        tree = ttk.Treeview(
            ana,
            columns=("zaman", "kullanici", "tip", "ciftlik", "hedef_tipi", "hedef_id", "detay"),
            show="headings",
            style="Modern.Treeview",
        )
        for col, baslik, genislik in [
            ("zaman", "Zaman", 150),
            ("kullanici", "Kullanici", 130),
            ("tip", "Islem", 130),
            ("ciftlik", "Ciftlik", 140),
            ("hedef_tipi", "Hedef", 110),
            ("hedef_id", "Hedef ID", 150),
            ("detay", "Detay", 360),
        ]:
            tree.heading(col, text=baslik)
            tree.column(col, width=genislik, anchor="w")
        tree.pack(fill="both", expand=True)

        detay_frame = tk.Frame(ana, bg=self.renkler["kart_arkaplan"], padx=10, pady=8, highlightthickness=1, highlightbackground=self.renkler["kenarlik"])
        detay_frame.pack(fill="x", pady=(10, 0))
        tk.Label(detay_frame, text="Seçili işlem detayı", bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
        detay_text = tk.Text(detay_frame, height=3, bg=self.renkler["input_bg"], fg=self.renkler["yazi_rengi"], relief="flat", wrap="word", font=("Segoe UI", 9))
        detay_text.pack(fill="x", pady=(4, 0))
        detay_text.configure(state="disabled")

        def secili_filtreler():
            try:
                limit = int(limit_entry.get().strip() or "200")
            except ValueError:
                limit = 200
            limit = max(1, min(limit, 500))
            return {
                "limit": limit,
                "q": arama_entry.get(),
                "kullanici_adi": kullanici_entry.get(),
                "islem_tipi": tip_entry.get(),
                "ciftlik_id": ciftlik_entry.get(),
                "hedef_tipi": hedef_tipi_entry.get(),
                "hedef_id": hedef_id_entry.get(),
                "tarih_baslangic": baslangic_entry.get(),
                "tarih_bitis": bitis_entry.get(),
            }

        def liste_yenile():
            nonlocal son_kayitlar
            try:
                filtreler = secili_filtreler()
                limit = filtreler.pop("limit")
                kayitlar = self.api_islem_gecmisi_yukle(limit, **filtreler)
            except ApiHatasi as e:
                return messagebox.showerror("Son Islemler", str(e), parent=pencere)
            son_kayitlar = kayitlar
            for item in tree.get_children():
                tree.delete(item)
            for kayit in kayitlar:
                tree.insert(
                    "",
                    "end",
                    values=(
                        kayit.get("zaman") or "",
                        kayit.get("kullanici_adi") or "-",
                        kayit.get("islem_tipi") or "-",
                        kayit.get("ciftlik_id") or "-",
                        kayit.get("hedef_tipi") or "-",
                        kayit.get("hedef_id") or "-",
                        kayit.get("detay") or "",
                    ),
                )
            detay_text.configure(state="normal")
            detay_text.delete("1.0", tk.END)
            detay_text.configure(state="disabled")

        def secili_detay_goster(event=None):
            secim = tree.selection()
            detay_text.configure(state="normal")
            detay_text.delete("1.0", tk.END)
            if secim:
                values = tree.item(secim[0], "values")
                detay = values[6] if len(values) > 6 else ""
                detay_text.insert("1.0", detay or "Detay yok.")
            detay_text.configure(state="disabled")

        tree.bind("<<TreeviewSelect>>", secili_detay_goster)

        def filtre_temizle():
            for entry in (arama_entry, kullanici_entry, tip_entry, ciftlik_entry, hedef_tipi_entry, hedef_id_entry, baslangic_entry, bitis_entry):
                entry.delete(0, tk.END)
            limit_entry.delete(0, tk.END)
            limit_entry.insert(0, "200")
            liste_yenile()

        def export_rows():
            return [
                (
                    kayit.get("zaman") or "",
                    kayit.get("kullanici_adi") or "-",
                    kayit.get("islem_tipi") or "-",
                    kayit.get("ciftlik_id") or "-",
                    kayit.get("hedef_tipi") or "-",
                    kayit.get("hedef_id") or "-",
                    kayit.get("detay") or "",
                )
                for kayit in son_kayitlar
            ]

        def excel_aktar():
            if not son_kayitlar:
                return messagebox.showwarning("Disari Aktar", "Once listeyi yenileyin.", parent=pencere)
            dosya = filedialog.asksaveasfilename(parent=pencere, title="Islem Gecmisini Excel Aktar", defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
            if not dosya:
                return
            try:
                export_rows_to_excel(dosya, "ALP Ziraat Islem Gecmisi", ["Zaman", "Kullanici", "Islem", "Ciftlik", "Hedef Tipi", "Hedef ID", "Detay"], export_rows())
                messagebox.showinfo("Disari Aktar", f"Excel kaydedildi:\n{dosya}", parent=pencere)
            except Exception as e:
                messagebox.showerror("Disari Aktar", str(e), parent=pencere)

        def pdf_aktar():
            if not son_kayitlar:
                return messagebox.showwarning("Disari Aktar", "Once listeyi yenileyin.", parent=pencere)
            dosya = filedialog.asksaveasfilename(parent=pencere, title="Islem Gecmisini PDF Aktar", defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
            if not dosya:
                return
            try:
                export_rows_to_pdf(dosya, "ALP Ziraat Islem Gecmisi", ["Zaman", "Kullanici", "Islem", "Ciftlik", "Hedef Tipi", "Hedef ID", "Detay"], export_rows())
                messagebox.showinfo("Disari Aktar", f"PDF kaydedildi:\n{dosya}", parent=pencere)
            except Exception as e:
                messagebox.showerror("Disari Aktar", str(e), parent=pencere)

        alt = tk.Frame(ana, bg=self.renkler["arkaplan"])
        alt.pack(fill="x", pady=(12, 0))
        tk.Button(alt, text="Yenile", command=liste_yenile, bg=self.renkler["button_primary_bg"], fg="#FFFFFF", relief="flat", padx=14, pady=8).pack(side="left")
        tk.Button(alt, text="Filtreleri Temizle", command=filtre_temizle, bg=self.renkler["button_default_bg"], fg=self.renkler["button_default_fg"], relief="flat", padx=14, pady=8).pack(side="left", padx=8)
        tk.Button(alt, text="Excel", command=excel_aktar, bg=self.renkler["button_success_bg"], fg="#FFFFFF", relief="flat", padx=14, pady=8).pack(side="left", padx=8)
        tk.Button(alt, text="PDF", command=pdf_aktar, bg=self.renkler["button_success_bg"], fg="#FFFFFF", relief="flat", padx=14, pady=8).pack(side="left")
        tk.Button(alt, text="Kapat", command=pencere.destroy, bg=self.renkler["button_default_bg"], fg=self.renkler["button_default_fg"], relief="flat", padx=14, pady=8).pack(side="right")
        liste_yenile()
        pencere.wait_window()

    def admin_yonetim_merkezi(self):
        sonuc = {"ok": False}
        tamam = tk.BooleanVar(value=False)
        state = {"ciftlikler": [], "kullanicilar": [], "offline_cache": False, "cache_time": None, "son_hata": None}

        def admin_onbellekten_yukle():
            onbellek = self.admin_onbellek_yukle()
            self.admin_onbellek = onbellek
            state["ciftlikler"] = onbellek.get("ciftlikler") or []
            state["kullanicilar"] = onbellek.get("kullanicilar") or []
            state["offline_cache"] = True
            state["cache_time"] = onbellek.get("updated_at")

        def verileri_yenile(sessiz=False):
            try:
                if not getattr(self, "api_token", None) or getattr(self, "api_offline_oturum", False):
                    self.api_online_oturum_ac()
                ciftlikler = self.api_istek("GET", "/api/ciftlikler?aktif_dahil=true", timeout=20)
                kullanicilar = self.api_istek("GET", "/api/kullanicilar", timeout=20)
                state["ciftlikler"] = ciftlikler if isinstance(ciftlikler, list) else []
                state["kullanicilar"] = kullanicilar if isinstance(kullanicilar, list) else []
                state["offline_cache"] = False
                state["cache_time"] = None
                state["son_hata"] = None
                self.api_cevrimdisi = False
                self.api_offline_oturum = False
                self._api_son_hata = None
                self.admin_onbellek_kaydet(state["ciftlikler"], state["kullanicilar"])
                return True
            except ApiHatasi as e:
                self.api_cevrimdisi = True
                self._api_son_hata = str(e)
                state["son_hata"] = str(e)
                admin_onbellekten_yukle()
                if not sessiz:
                    if state["ciftlikler"] or state["kullanicilar"]:
                        messagebox.showwarning(
                            "Admin Merkezi",
                            f"API bağlantısı kurulamadı; son kayıtlı yönetim listesi gösteriliyor.\n\n{e}",
                            parent=self.root,
                        )
                    else:
                        messagebox.showerror("Admin Merkezi", f"Yönetim verileri alınamadı:\n{e}", parent=self.root)
                return False

        verileri_yenile(sessiz=True)

        for child in self.root.winfo_children():
            child.destroy()

        self.root.title("ALP Ziraat - Admin Merkezi")
        self.root.geometry("960x720")
        self.root.minsize(820, 600)
        self.root.resizable(True, True)
        self.root.configure(bg=self.renkler["arkaplan"])
        self.root.deiconify()
        self.root.lift()

        scroll_kapsayici = tk.Frame(self.root, bg=self.renkler["arkaplan"])
        scroll_kapsayici.pack(fill="both", expand=True)
        admin_canvas = tk.Canvas(scroll_kapsayici, bg=self.renkler["arkaplan"], highlightthickness=0, bd=0)
        admin_scroll = tk.Scrollbar(
            scroll_kapsayici,
            orient="vertical",
            command=admin_canvas.yview,
            bg=self.renkler["kart_ikincil"],
            troughcolor=self.renkler["arkaplan"],
            activebackground=self.renkler["button_primary_bg"],
            highlightthickness=0,
        )
        admin_canvas.configure(yscrollcommand=admin_scroll.set)
        admin_scroll.pack(side="right", fill="y")
        admin_canvas.pack(side="left", fill="both", expand=True)

        sayfa = tk.Frame(admin_canvas, bg=self.renkler["arkaplan"], padx=28, pady=24)
        sayfa_pencere = admin_canvas.create_window((0, 0), window=sayfa, anchor="nw")

        def admin_scroll_bolgesi_guncelle(event=None):
            admin_canvas.configure(scrollregion=admin_canvas.bbox("all"))

        def admin_canvas_genislik_guncelle(event):
            admin_canvas.itemconfigure(sayfa_pencere, width=event.width)

        def admin_mousewheel(event):
            if admin_canvas.winfo_exists():
                admin_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        sayfa.bind("<Configure>", admin_scroll_bolgesi_guncelle)
        admin_canvas.bind("<Configure>", admin_canvas_genislik_guncelle)
        self.root.bind_all("<MouseWheel>", admin_mousewheel)

        ust = tk.Frame(sayfa, bg=self.renkler["arkaplan"])
        ust.pack(fill="x")
        tk.Label(
            ust,
            text="Admin Merkezi",
            bg=self.renkler["arkaplan"],
            fg=self.renkler["yazi_rengi"],
            font=("Segoe UI", 24, "bold"),
        ).pack(anchor="w")
        tk.Label(
            ust,
            text="Çiftlikleri, kullanıcıları ve sürü verilerini tek yerden yönetin.",
            bg=self.renkler["arkaplan"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(2, 18))

        ozet = tk.Frame(sayfa, bg=self.renkler["kart_arkaplan"], padx=18, pady=14, highlightthickness=1, highlightbackground=self.renkler["kenarlik"])
        ozet.pack(fill="x", pady=(0, 18))
        ozet_label = tk.Label(ozet, text="", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=("Segoe UI", 11, "bold"))
        ozet_label.pack(anchor="w")
        admin_durum_label = tk.Label(ozet, text="", bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 9))
        admin_durum_label.pack(anchor="w", pady=(4, 0))

        govde = tk.Frame(sayfa, bg=self.renkler["arkaplan"])
        govde.pack(fill="both", expand=True)
        govde.columnconfigure(0, weight=1)
        govde.columnconfigure(1, weight=1)
        govde.rowconfigure(0, weight=1)
        govde.rowconfigure(1, weight=1)

        sol = tk.Frame(govde, bg=self.renkler["kart_arkaplan"], padx=18, pady=18, highlightthickness=1, highlightbackground=self.renkler["kenarlik"])
        sag = tk.Frame(govde, bg=self.renkler["kart_arkaplan"], padx=18, pady=18, highlightthickness=1, highlightbackground=self.renkler["kenarlik"])

        def admin_govde_yerlestir(event=None):
            genislik = govde.winfo_width()
            sol.grid_forget()
            sag.grid_forget()
            if genislik and genislik < 760:
                govde.columnconfigure(0, weight=1)
                govde.columnconfigure(1, weight=0)
                sol.grid(row=0, column=0, sticky="nsew", padx=0, pady=(0, 12))
                sag.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
            else:
                govde.columnconfigure(0, weight=1)
                govde.columnconfigure(1, weight=1)
                sol.grid(row=0, column=0, sticky="nsew", padx=(0, 9), pady=0)
                sag.grid(row=0, column=1, sticky="nsew", padx=(9, 0), pady=0)

        govde.bind("<Configure>", admin_govde_yerlestir)
        self._track_after(self.root, 50, admin_govde_yerlestir)

        tk.Label(sol, text="Sürüye Giriş", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=("Segoe UI", 15, "bold")).pack(anchor="w")
        tk.Label(sol, text="Tüm kayıtları görebilir veya belirli bir çiftliğe odaklanabilirsiniz.", bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 9), wraplength=320, justify="left").pack(anchor="w", pady=(4, 14))

        ciftlik_combo = ttk.Combobox(sol, state="readonly", font=("Segoe UI", 10), style="TCombobox")
        ciftlik_combo.pack(fill="x", pady=(0, 12), ipady=4)
        ciftlik_liste = tk.Listbox(
            sol,
            height=7,
            bg=self.renkler["input_bg"],
            fg=self.renkler["yazi_rengi"],
            selectbackground=self.renkler["button_primary_bg"],
            selectforeground="#FFFFFF",
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.renkler["kenarlik"],
            font=("Segoe UI", 10),
        )
        ciftlik_liste.pack(fill="both", expand=True, pady=(0, 12))

        def admin_buton(parent, metin, komut, renk=None):
            return tk.Button(
                parent,
                text=metin,
                command=komut,
                bg=renk or self.renkler["button_default_bg"],
                fg=self.renkler["button_default_fg"] if renk is None else "#FFFFFF",
                activebackground=renk or self.renkler["button_default_bg"],
                activeforeground=self.renkler["button_default_fg"] if renk is None else "#FFFFFF",
                relief="flat",
                padx=14,
                pady=10,
                anchor="w",
                font=("Segoe UI", 10, "bold"),
            )

        def bitir(ok, login_iste=False):
            sonuc["ok"] = ok
            self._login_yeniden_iste = bool(login_iste)
            try:
                tamam.set(True)
            except tk.TclError:
                pass

        def aktif_ciftlikler():
            return [c for c in state["ciftlikler"] if c.get("aktif", True)]

        def secili_ciftlik():
            liste = aktif_ciftlikler()
            idx = ciftlik_combo.current()
            if idx < 0 or idx >= len(liste):
                return None
            return liste[idx]

        def tum_suruye_gir():
            if state.get("offline_cache"):
                messagebox.showwarning(
                    "Admin Merkezi",
                    "Offline modda tüm sürü verisi güvenli şekilde yenilenemez. İnternet gelince Senkronize Et ile tekrar deneyin.",
                    parent=self.root,
                )
                return
            self.admin_aktif_ciftlik_id = None
            self.admin_aktif_ciftlik_ad = None
            bitir(True)

        def secili_suruye_gir():
            if state.get("offline_cache"):
                messagebox.showwarning(
                    "Admin Merkezi",
                    "Offline modda çiftlik değiştirmek yerine sadece son kayıtlı çiftlik listesi gösterilir. İnternet gelince Senkronize Et ile sürüye girin.",
                    parent=self.root,
                )
                return
            ciftlik = secili_ciftlik()
            if not ciftlik:
                messagebox.showwarning("Admin Merkezi", "Önce bir çiftlik seçin.", parent=self.root)
                return
            self.admin_aktif_ciftlik_id = ciftlik.get("id")
            self.admin_aktif_ciftlik_ad = ciftlik.get("ad")
            bitir(True)

        def listeden_ciftlik_sec(event=None):
            secim = ciftlik_liste.curselection()
            if not secim:
                return
            idx = secim[0]
            if idx < len(aktif_ciftlikler()):
                ciftlik_combo.current(idx)

        def combodan_ciftlik_sec(event=None):
            idx = ciftlik_combo.current()
            if idx < 0:
                return
            ciftlik_liste.selection_clear(0, tk.END)
            ciftlik_liste.selection_set(idx)
            ciftlik_liste.see(idx)

        ciftlik_liste.bind("<<ListboxSelect>>", listeden_ciftlik_sec)
        ciftlik_liste.bind("<Double-Button-1>", lambda event: (listeden_ciftlik_sec(event), secili_suruye_gir()))
        ciftlik_liste.bind("<Return>", lambda event: secili_suruye_gir())
        ciftlik_combo.bind("<<ComboboxSelected>>", combodan_ciftlik_sec)
        ciftlik_combo.bind("<Return>", lambda event: secili_suruye_gir())

        admin_buton(sol, "Tüm çiftliklerin sürü takibine gir", tum_suruye_gir, self.renkler["button_primary_bg"]).pack(fill="x", pady=5)
        admin_buton(sol, "Seçili çiftliğin sürüsüne gir", secili_suruye_gir, self.renkler["button_success_bg"]).pack(fill="x", pady=5)

        tk.Label(sag, text="Yönetim", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=("Segoe UI", 15, "bold")).pack(anchor="w")
        tk.Label(sag, text="Yeni çiftlik açın, kullanıcı atayın veya mevcut yetkileri düzenleyin.", bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 9), wraplength=320, justify="left").pack(anchor="w", pady=(4, 14))

        def ekrani_yenile():
            ciftlikler = aktif_ciftlikler()
            ciftlik_combo["values"] = [f"{c.get('ad', '-')} ({c.get('id', '-')})" for c in ciftlikler]
            ciftlik_liste.delete(0, tk.END)
            for c in ciftlikler:
                ciftlik_liste.insert(tk.END, f"{c.get('ad', '-')} ({c.get('id', '-')})")
            if ciftlikler:
                mevcut_id = getattr(self, "admin_aktif_ciftlik_id", None)
                secim = next((i for i, c in enumerate(ciftlikler) if c.get("id") == mevcut_id), 0)
                ciftlik_combo.current(secim)
                ciftlik_liste.selection_clear(0, tk.END)
                ciftlik_liste.selection_set(secim)
                ciftlik_liste.see(secim)
            else:
                ciftlik_combo.set("")
            ozet_label.config(
                text=f"{len(state['ciftlikler'])} çiftlik  |  {len(state['kullanicilar'])} kullanıcı  |  Admin: {(self.api_kullanici or {}).get('kullanici_adi', '-')}"
            )
            if state.get("offline_cache"):
                zaman = state.get("cache_time") or "bilinmiyor"
                admin_durum_label.config(
                    text=f"Offline: son kayıtlı liste gösteriliyor. Son güncelleme: {zaman}",
                    fg=self.renkler["uyari"],
                )
            else:
                admin_durum_label.config(text="Online: yönetim listesi güncel.", fg=self.renkler["yesil"])

        def ciftlikleri_yonet():
            self.admin_ciftlik_yonetim_penceresi()
            verileri_yenile(sessiz=True)
            ekrani_yenile()

        def kullanicilari_yonet(yeni=False):
            self.admin_kullanici_yonetim_penceresi(yeni_kullanici=yeni)
            verileri_yenile(sessiz=True)
            ekrani_yenile()

        def admin_senkronize_et():
            online = verileri_yenile(sessiz=False)
            ekrani_yenile()
            if online:
                messagebox.showinfo("Admin Merkezi", "API bağlantısı yenilendi ve yönetim listesi güncellendi.", parent=self.root)

        def admin_api_ayarlari():
            self.api_ayar_penceresi()
            verileri_yenile(sessiz=True)
            ekrani_yenile()

        admin_buton(sag, "Çiftlikleri yönet", ciftlikleri_yonet).pack(fill="x", pady=5)
        admin_buton(sag, "Kullanıcıları yönet", lambda: kullanicilari_yonet(False)).pack(fill="x", pady=5)
        admin_buton(sag, "Yeni kullanıcı oluştur", lambda: kullanicilari_yonet(True), self.renkler["button_success_bg"]).pack(fill="x", pady=5)
        admin_buton(sag, "Son işlemleri gör", self.admin_islem_gecmisi_penceresi).pack(fill="x", pady=5)
        admin_buton(sag, "Sistem durumu", lambda: self.admin_sistem_durumu_penceresi(self.root), self.renkler["button_primary_bg"]).pack(fill="x", pady=5)
        admin_buton(sag, "Veri Sağlığı", lambda: self.admin_veri_sagligi_penceresi(self.root), self.renkler["button_warning_bg"]).pack(fill="x", pady=5)
        admin_buton(sag, "Online yedek indir", lambda: self.admin_online_yedek_indir(self.root), self.renkler["button_primary_bg"]).pack(fill="x", pady=5)
        admin_buton(sag, "API ayarları", admin_api_ayarlari, self.renkler["button_primary_bg"]).pack(fill="x", pady=5)
        admin_buton(sag, "Şifremi değiştir", lambda: self.sifre_degistir_penceresi(self.root)).pack(fill="x", pady=5)
        admin_buton(sag, "Senkronize Et", admin_senkronize_et, self.renkler["button_primary_bg"]).pack(fill="x", pady=5)

        alt = tk.Frame(sayfa, bg=self.renkler["arkaplan"])
        alt.pack(fill="x", pady=(18, 0))
        admin_buton(alt, "Çıkış Yap", lambda: bitir(False, True), self.renkler["button_danger_bg"]).pack(side="right")

        self.root.protocol("WM_DELETE_WINDOW", lambda: bitir(False))
        self.root.bind("<Escape>", lambda event: bitir(False))
        ekrani_yenile()

        try:
            self.root.wait_variable(tamam)
        except tk.TclError:
            try:
                self.root.unbind_all("<MouseWheel>")
            except tk.TclError:
                pass
            return False

        self.root.unbind("<Escape>")
        try:
            self.root.unbind_all("<MouseWheel>")
        except tk.TclError:
            pass
        self._cancel_tracked_afters()
        for child in self.root.winfo_children():
            child.destroy()
        return sonuc["ok"]

    def admin_ciftlik_yonetim_penceresi(self):
        if not self.online_islem_gerekli("Çiftlik yönetimi", self.root):
            return
        pencere = tk.Toplevel(self.root)
        pencere.title("Çiftlik Yönetimi")
        pencere.geometry("1040x640")
        pencere.minsize(720, 460)
        pencere.configure(bg=self.renkler["arkaplan"])
        pencere.transient(self.root)
        self.uygula_pencere_ikonu(pencere)
        pencere.grab_set()

        ciftlikler = []
        secili = {"id": None}

        baslik_alan = tk.Frame(pencere, bg=self.renkler["arkaplan"], padx=22)
        baslik_alan.pack(fill="x", pady=(18, 8))
        self.themed_widgets.append((baslik_alan, 'arkaplan'))
        tk.Label(
            baslik_alan,
            text="Çiftlik Yönetimi",
            bg=self.renkler["arkaplan"],
            fg=self.renkler["yazi_rengi"],
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor="w")
        tk.Label(
            baslik_alan,
            text="Çiftlik açın, düzenleyin veya canlı veritabanından kalıcı olarak silin.",
            bg=self.renkler["arkaplan"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(4, 0))

        ana = tk.Frame(pencere, bg=self.renkler["arkaplan"], padx=22)
        ana.pack(fill="both", expand=True, pady=(8, 22))
        ana.columnconfigure(0, weight=3)
        ana.columnconfigure(1, weight=2)
        ana.rowconfigure(0, weight=1)
        self.themed_widgets.append((ana, 'arkaplan'))

        liste_panel = self.modern_kart(ana, accent=self.renkler["button_primary_bg"])
        liste_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        tk.Label(
            liste_panel,
            text="Çiftlikler",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["yazi_rengi"],
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w", padx=16, pady=(14, 8))

        tree_frame = tk.Frame(liste_panel, bg=self.renkler["kart_arkaplan"])
        tree_frame.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        self.themed_widgets.append((tree_frame, 'kart'))

        tree = ttk.Treeview(tree_frame, columns=("id", "ad", "aktif", "aciklama"), show="headings", style="Modern.Treeview")
        for col, baslik, genislik in [
            ("id", "ID", 170),
            ("ad", "Çiftlik", 180),
            ("aktif", "Durum", 80),
            ("aciklama", "Açıklama", 260),
        ]:
            tree.heading(col, text=baslik)
            tree.column(col, width=genislik, anchor="center")
        tree.grid(row=0, column=0, sticky="nsew")
        tree_sb_y = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree_sb_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=tree_sb_y.set, xscrollcommand=tree_sb_x.set)
        tree_sb_y.grid(row=0, column=1, sticky="ns")
        tree_sb_x.grid(row=1, column=0, sticky="ew")

        status_label = tk.Label(
            liste_panel,
            text="Liste yükleniyor...",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 9, "bold"),
        )
        status_label.pack(anchor="w", padx=16, pady=(0, 14))

        form = self.modern_kart(ana, accent=self.renkler["button_success_bg"])
        form.grid(row=0, column=1, sticky="nsew")
        form.configure(padx=16, pady=16)

        tk.Label(form, text="Çiftlik Bilgisi", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 12))
        tk.Label(form, text="ID (yeni kayıtta isteğe bağlı)", bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
        id_entry = ttk.Entry(form, font=("Segoe UI", 10), style="TEntry")
        id_entry.pack(fill="x", pady=(4, 10), ipady=4)
        tk.Label(form, text="Çiftlik adı", bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
        ad_entry = ttk.Entry(form, font=("Segoe UI", 10), style="TEntry")
        ad_entry.pack(fill="x", pady=(4, 10), ipady=4)
        tk.Label(form, text="Açıklama", bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
        aciklama_entry = ttk.Entry(form, font=("Segoe UI", 10), style="TEntry")
        aciklama_entry.pack(fill="x", pady=(4, 10), ipady=4)
        aktif_var = tk.BooleanVar(value=True)
        tk.Checkbutton(form, text="Aktif", variable=aktif_var, bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], selectcolor=self.renkler["input_bg"], activebackground=self.renkler["kart_arkaplan"]).pack(anchor="w", pady=(0, 12))

        def form_temizle():
            secili["id"] = None
            for entry in (id_entry, ad_entry, aciklama_entry):
                entry.delete(0, tk.END)
            aktif_var.set(True)
            tree.selection_remove(tree.selection())
            id_entry.focus_set()

        def liste_yenile():
            nonlocal ciftlikler
            ciftlikler = self.api_ciftlikleri_yukle()
            for item in tree.get_children():
                tree.delete(item)
            for c in ciftlikler:
                tree.insert("", "end", iid=c.get("id"), values=(c.get("id"), c.get("ad"), "Aktif" if c.get("aktif", True) else "Pasif", c.get("aciklama") or ""))
            status_label.config(text=f"{len(ciftlikler)} çiftlik listelendi.")

        def secimi_yukle(event=None):
            secim = tree.selection()
            if not secim:
                return
            ciftlik_id = secim[0]
            ciftlik = next((c for c in ciftlikler if c.get("id") == ciftlik_id), None)
            if not ciftlik:
                return
            secili["id"] = ciftlik_id
            id_entry.delete(0, tk.END)
            id_entry.insert(0, ciftlik.get("id") or "")
            ad_entry.delete(0, tk.END)
            ad_entry.insert(0, ciftlik.get("ad") or "")
            aciklama_entry.delete(0, tk.END)
            aciklama_entry.insert(0, ciftlik.get("aciklama") or "")
            aktif_var.set(bool(ciftlik.get("aktif", True)))

        def kaydet():
            ad = ad_entry.get().strip()
            if not ad:
                return messagebox.showerror("Çiftlik", "Çiftlik adı zorunludur.", parent=pencere)
            payload = {"ad": ad, "aciklama": aciklama_entry.get().strip() or None, "aktif": bool(aktif_var.get())}
            try:
                if secili["id"]:
                    self.api_istek("PATCH", f"/api/ciftlikler/{self.api_ref(secili['id'])}", payload, timeout=20)
                else:
                    yeni_id = id_entry.get().strip()
                    if yeni_id:
                        payload["id"] = yeni_id
                    self.api_istek("POST", "/api/ciftlikler", payload, timeout=20)
                liste_yenile()
                form_temizle()
            except ApiHatasi as e:
                messagebox.showerror("Çiftlik", str(e), parent=pencere)

        def ciftlik_hayvan_sayisi(ciftlik_id):
            try:
                kayitlar = self.api_istek(
                    "GET",
                    f"/api/hayvanlar?skip=0&limit=1000&arsiv_dahil=true&ciftlik_id={self.api_ref(ciftlik_id)}",
                    timeout=20,
                )
                return len(kayitlar) if isinstance(kayitlar, list) else None
            except ApiHatasi:
                return None

        def sil():
            if not secili["id"]:
                return messagebox.showwarning("Çiftlik Sil", "Silmek için listeden bir çiftlik seçin.", parent=pencere)
            ciftlik = next((c for c in ciftlikler if c.get("id") == secili["id"]), None)
            if not ciftlik:
                return messagebox.showerror("Çiftlik Sil", "Seçili çiftlik bulunamadı.", parent=pencere)
            hayvan_sayisi = ciftlik_hayvan_sayisi(secili["id"])
            try:
                kullanici_sayisi = len([
                    k for k in self.api_kullanicilari_yukle()
                    if k.get("ciftlik_id") == secili["id"]
                ])
            except ApiHatasi:
                kullanici_sayisi = None
            detaylar = []
            if hayvan_sayisi is not None:
                detaylar.append(f"{hayvan_sayisi} hayvan")
            if kullanici_sayisi is not None:
                detaylar.append(f"{kullanici_sayisi} kullanıcı")
            detay_metni = "\nSilinecek kayıtlar: " + ", ".join(detaylar) if detaylar else ""
            onay = messagebox.askyesno(
                "Çiftlik Sil",
                (
                    f"{ciftlik.get('ad') or secili['id']} çiftliği kalıcı olarak silinecek."
                    f"{detay_metni}\n\nBu işlem geri alınamaz. Emin misiniz?"
                ),
                parent=pencere,
                icon="warning",
            )
            if not onay:
                return
            yazili_onay = simpledialog.askstring(
                "Kalıcı Silme Onayı",
                "Devam etmek için SIL yazın:",
                parent=pencere,
            )
            if (yazili_onay or "").strip().upper() != "SIL":
                return messagebox.showinfo("Çiftlik Sil", "Silme işlemi iptal edildi.", parent=pencere)
            try:
                sonuc = self.api_istek("DELETE", f"/api/ciftlikler/{self.api_ref(secili['id'])}", timeout=30)
                if getattr(self, "admin_aktif_ciftlik_id", None) == secili["id"]:
                    self.admin_aktif_ciftlik_id = None
                    self.admin_aktif_ciftlik_ad = None
                    self.hayvanlar = {}
                messagebox.showinfo("Çiftlik Sil", sonuc.get("message", "Çiftlik silindi."), parent=pencere)
                liste_yenile()
                form_temizle()
            except ApiHatasi as e:
                messagebox.showerror("Çiftlik Sil", str(e), parent=pencere)

        tree.bind("<<TreeviewSelect>>", secimi_yukle)
        btnler = tk.Frame(form, bg=self.renkler["kart_arkaplan"])
        btnler.pack(fill="x", pady=(8, 0))
        self.themed_widgets.append((btnler, 'kart'))
        self.responsive_buton_grubu(
            btnler,
            [
                ("Yeni", form_temizle, "default"),
                ("Kaydet", kaydet, "success"),
                ("Sil", sil, "danger"),
                ("Kapat", pencere.destroy, "default"),
            ],
            align="left",
        )

        def yerlesim_guncelle(event=None):
            try:
                dar = ana.winfo_width() < 820
                liste_panel.grid_forget()
                form.grid_forget()
                if dar:
                    ana.columnconfigure(0, weight=1)
                    ana.columnconfigure(1, weight=0)
                    liste_panel.grid(row=0, column=0, sticky="nsew", padx=0, pady=(0, 12))
                    form.grid(row=1, column=0, sticky="ew")
                    ana.rowconfigure(0, weight=1)
                    ana.rowconfigure(1, weight=0)
                else:
                    ana.columnconfigure(0, weight=3)
                    ana.columnconfigure(1, weight=2)
                    liste_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
                    form.grid(row=0, column=1, sticky="nsew")
                    ana.rowconfigure(0, weight=1)
                    ana.rowconfigure(1, weight=0)
            except tk.TclError:
                pass

        ana.bind("<Configure>", yerlesim_guncelle)
        self._track_after(pencere, 80, yerlesim_guncelle)

        try:
            liste_yenile()
        except ApiHatasi as e:
            messagebox.showerror("Çiftlik", str(e), parent=pencere)
        pencere.wait_window()

    def admin_kullanici_yonetim_penceresi(self, yeni_kullanici=False):
        if not self.online_islem_gerekli("Kullanıcı yönetimi", self.root):
            return
        pencere = tk.Toplevel(self.root)
        pencere.title("Kullanıcı Yönetimi")
        pencere.geometry("1080x660")
        pencere.minsize(760, 500)
        pencere.configure(bg=self.renkler["arkaplan"])
        pencere.transient(self.root)
        self.uygula_pencere_ikonu(pencere)
        pencere.grab_set()

        kullanicilar = []
        ciftlikler = self.api_ciftlikleri_yukle()
        secili = {"id": None}

        baslik_alan = tk.Frame(pencere, bg=self.renkler["arkaplan"], padx=22)
        baslik_alan.pack(fill="x", pady=(18, 8))
        self.themed_widgets.append((baslik_alan, 'arkaplan'))
        tk.Label(
            baslik_alan,
            text="Kullanıcı Yönetimi",
            bg=self.renkler["arkaplan"],
            fg=self.renkler["yazi_rengi"],
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor="w")
        tk.Label(
            baslik_alan,
            text="Admin ve çiftlik kullanıcılarını yönetin, yetki ve çiftlik atamalarını düzenleyin.",
            bg=self.renkler["arkaplan"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(4, 0))

        ana = tk.Frame(pencere, bg=self.renkler["arkaplan"], padx=22)
        ana.pack(fill="both", expand=True, pady=(8, 22))
        ana.columnconfigure(0, weight=3)
        ana.columnconfigure(1, weight=2)
        ana.rowconfigure(0, weight=1)
        self.themed_widgets.append((ana, 'arkaplan'))

        liste_panel = self.modern_kart(ana, accent=self.renkler["button_primary_bg"])
        liste_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        tk.Label(
            liste_panel,
            text="Kullanıcılar",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["yazi_rengi"],
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w", padx=16, pady=(14, 8))

        tree_frame = tk.Frame(liste_panel, bg=self.renkler["kart_arkaplan"])
        tree_frame.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        self.themed_widgets.append((tree_frame, 'kart'))

        tree = ttk.Treeview(tree_frame, columns=("id", "kullanici", "rol", "ciftlik", "aktif"), show="headings", style="Modern.Treeview")
        for col, baslik, genislik in [
            ("id", "ID", 130),
            ("kullanici", "Kullanıcı", 150),
            ("rol", "Rol", 90),
            ("ciftlik", "Çiftlik", 170),
            ("aktif", "Durum", 80),
        ]:
            tree.heading(col, text=baslik)
            tree.column(col, width=genislik, anchor="center")
        tree.grid(row=0, column=0, sticky="nsew")
        tree_sb_y = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree_sb_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=tree_sb_y.set, xscrollcommand=tree_sb_x.set)
        tree_sb_y.grid(row=0, column=1, sticky="ns")
        tree_sb_x.grid(row=1, column=0, sticky="ew")

        status_label = tk.Label(
            liste_panel,
            text="Liste yükleniyor...",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 9, "bold"),
        )
        status_label.pack(anchor="w", padx=16, pady=(0, 14))

        form = self.modern_kart(ana, accent=self.renkler["button_success_bg"])
        form.grid(row=0, column=1, sticky="nsew")
        form.configure(padx=16, pady=16)
        tk.Label(form, text="Kullanıcı Bilgisi", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 12))

        tk.Label(form, text="Kullanıcı adı", bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
        ad_entry = ttk.Entry(form, font=("Segoe UI", 10), style="TEntry")
        ad_entry.pack(fill="x", pady=(4, 10), ipady=4)
        tk.Label(form, text="Şifre (güncellemede boş kalabilir)", bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
        sifre_entry = ttk.Entry(form, font=("Segoe UI", 10), style="TEntry", show="*")
        sifre_entry.pack(fill="x", pady=(4, 10), ipady=4)
        tk.Label(form, text="Rol", bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
        rol_combo = ttk.Combobox(form, values=["ciftlik", "admin"], state="readonly", font=("Segoe UI", 10), style="TCombobox")
        rol_combo.pack(fill="x", pady=(4, 10), ipady=4)
        rol_combo.set("ciftlik")
        tk.Label(form, text="Çiftlik", bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
        farm_combo = ttk.Combobox(form, state="readonly", font=("Segoe UI", 10), style="TCombobox")
        farm_combo.pack(fill="x", pady=(4, 10), ipady=4)
        aktif_var = tk.BooleanVar(value=True)
        tk.Checkbutton(form, text="Aktif", variable=aktif_var, bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], selectcolor=self.renkler["input_bg"], activebackground=self.renkler["kart_arkaplan"]).pack(anchor="w", pady=(0, 12))

        farm_ids = [None] + [c.get("id") for c in ciftlikler]
        farm_combo["values"] = ["Yok / admin"] + [f"{c.get('ad', '-')} ({c.get('id', '-')})" for c in ciftlikler]
        farm_combo.current(0)

        def secili_farm_id():
            idx = farm_combo.current()
            if idx < 0 or idx >= len(farm_ids):
                return None
            return farm_ids[idx]

        def farm_index(ciftlik_id):
            try:
                return farm_ids.index(ciftlik_id)
            except ValueError:
                return 0

        def form_temizle():
            secili["id"] = None
            ad_entry.delete(0, tk.END)
            sifre_entry.delete(0, tk.END)
            rol_combo.set("ciftlik")
            farm_combo.current(1 if len(farm_ids) > 1 else 0)
            aktif_var.set(True)
            tree.selection_remove(tree.selection())
            ad_entry.focus_set()

        def liste_yenile():
            nonlocal kullanicilar
            kullanicilar = self.api_kullanicilari_yukle()
            for item in tree.get_children():
                tree.delete(item)
            for k in kullanicilar:
                ciftlik_ad = (k.get("ciftlik") or {}).get("ad") or ("Tüm çiftlikler" if k.get("rol") == "admin" else "-")
                tree.insert("", "end", iid=k.get("id"), values=(k.get("id"), k.get("kullanici_adi"), k.get("rol"), ciftlik_ad, "Aktif" if k.get("aktif", True) else "Pasif"))
            status_label.config(text=f"{len(kullanicilar)} kullanıcı listelendi.")

        def secimi_yukle(event=None):
            secim = tree.selection()
            if not secim:
                return
            kullanici_id = secim[0]
            kullanici = next((k for k in kullanicilar if k.get("id") == kullanici_id), None)
            if not kullanici:
                return
            secili["id"] = kullanici_id
            ad_entry.delete(0, tk.END)
            ad_entry.insert(0, kullanici.get("kullanici_adi") or "")
            sifre_entry.delete(0, tk.END)
            rol_combo.set(kullanici.get("rol") or "ciftlik")
            farm_combo.current(farm_index(kullanici.get("ciftlik_id")))
            aktif_var.set(bool(kullanici.get("aktif", True)))

        def kaydet():
            kullanici_adi = ad_entry.get().strip().lower()
            sifre = sifre_entry.get()
            rol = rol_combo.get() or "ciftlik"
            ciftlik_id = None if rol == "admin" else secili_farm_id()
            if not kullanici_adi:
                return messagebox.showerror("Kullanıcı", "Kullanıcı adı zorunludur.", parent=pencere)
            if not secili["id"] and not sifre:
                return messagebox.showerror("Kullanıcı", "Yeni kullanıcı için şifre zorunludur.", parent=pencere)
            if rol != "admin" and not ciftlik_id:
                return messagebox.showerror("Kullanıcı", "Çiftlik kullanıcısı için çiftlik seçilmelidir.", parent=pencere)
            payload = {"kullanici_adi": kullanici_adi, "rol": rol, "ciftlik_id": ciftlik_id, "aktif": bool(aktif_var.get())}
            if sifre:
                payload["sifre"] = sifre
            try:
                if secili["id"]:
                    self.api_istek("PATCH", f"/api/kullanicilar/{self.api_ref(secili['id'])}", payload, timeout=20)
                else:
                    self.api_istek("POST", "/api/kullanicilar", payload, timeout=20)
                liste_yenile()
                form_temizle()
            except ApiHatasi as e:
                messagebox.showerror("Kullanıcı", str(e), parent=pencere)

        def sil():
            if not secili["id"]:
                return messagebox.showwarning("Kullanıcı Sil", "Silmek için listeden bir kullanıcı seçin.", parent=pencere)
            kullanici = next((k for k in kullanicilar if k.get("id") == secili["id"]), None)
            if not kullanici:
                return messagebox.showerror("Kullanıcı Sil", "Seçili kullanıcı bulunamadı.", parent=pencere)
            aktif_id = (self.api_kullanici or {}).get("id")
            if aktif_id and aktif_id == secili["id"]:
                return messagebox.showerror("Kullanıcı Sil", "Kendi admin kullanıcınızı silemezsiniz.", parent=pencere)
            onay = messagebox.askyesno(
                "Kullanıcı Sil",
                (
                    f"{kullanici.get('kullanici_adi') or secili['id']} kullanıcısı kalıcı olarak silinecek.\n\n"
                    "Bu işlem geri alınamaz. Emin misiniz?"
                ),
                parent=pencere,
                icon="warning",
            )
            if not onay:
                return
            try:
                sonuc = self.api_istek("DELETE", f"/api/kullanicilar/{self.api_ref(secili['id'])}", timeout=20)
                messagebox.showinfo("Kullanıcı Sil", sonuc.get("message", "Kullanıcı silindi."), parent=pencere)
                liste_yenile()
                form_temizle()
            except ApiHatasi as e:
                messagebox.showerror("Kullanıcı Sil", str(e), parent=pencere)

        def sifre_sifirla():
            if not secili["id"]:
                return messagebox.showwarning("Şifre Sıfırla", "Şifresini değiştirmek için listeden bir kullanıcı seçin.", parent=pencere)
            kullanici = next((k for k in kullanicilar if k.get("id") == secili["id"]), None)
            if not kullanici:
                return messagebox.showerror("Şifre Sıfırla", "Seçili kullanıcı bulunamadı.", parent=pencere)
            yeni = simpledialog.askstring("Şifre Sıfırla", "Yeni şifre (en az 8 karakter):", show="*", parent=pencere)
            if yeni is None:
                return
            tekrar = simpledialog.askstring("Şifre Sıfırla", "Yeni şifre tekrar:", show="*", parent=pencere)
            if tekrar is None:
                return
            if yeni != tekrar:
                return messagebox.showerror("Şifre Sıfırla", "Yeni şifreler aynı değil.", parent=pencere)
            try:
                sonuc = self.api_istek(
                    "POST",
                    f"/api/kullanicilar/{self.api_ref(secili['id'])}/sifre-sifirla",
                    {"yeni_sifre": yeni},
                    timeout=20,
                )
                messagebox.showinfo("Şifre Sıfırla", sonuc.get("message", "Şifre sıfırlandı."), parent=pencere)
                sifre_entry.delete(0, tk.END)
            except ApiHatasi as e:
                messagebox.showerror("Şifre Sıfırla", str(e), parent=pencere)

        tree.bind("<<TreeviewSelect>>", secimi_yukle)
        btnler = tk.Frame(form, bg=self.renkler["kart_arkaplan"])
        btnler.pack(fill="x", pady=(8, 0))
        self.themed_widgets.append((btnler, 'kart'))
        self.responsive_buton_grubu(
            btnler,
            [
                ("Yeni", form_temizle, "default"),
                ("Kaydet", kaydet, "success"),
                ("Sil", sil, "danger"),
                ("Şifre", sifre_sifirla, "warning"),
                ("Kapat", pencere.destroy, "default"),
            ],
            align="left",
        )

        def yerlesim_guncelle(event=None):
            try:
                dar = ana.winfo_width() < 860
                liste_panel.grid_forget()
                form.grid_forget()
                if dar:
                    ana.columnconfigure(0, weight=1)
                    ana.columnconfigure(1, weight=0)
                    liste_panel.grid(row=0, column=0, sticky="nsew", padx=0, pady=(0, 12))
                    form.grid(row=1, column=0, sticky="ew")
                    ana.rowconfigure(0, weight=1)
                    ana.rowconfigure(1, weight=0)
                else:
                    ana.columnconfigure(0, weight=3)
                    ana.columnconfigure(1, weight=2)
                    liste_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
                    form.grid(row=0, column=1, sticky="nsew")
                    ana.rowconfigure(0, weight=1)
                    ana.rowconfigure(1, weight=0)
            except tk.TclError:
                pass

        ana.bind("<Configure>", yerlesim_guncelle)
        self._track_after(pencere, 80, yerlesim_guncelle)

        try:
            liste_yenile()
            if yeni_kullanici:
                form_temizle()
        except ApiHatasi as e:
            messagebox.showerror("Kullanıcı", str(e), parent=pencere)
        pencere.wait_window()

    def admin_merkeze_don(self):
        if not self.admin_mi():
            return
        eski_ciftlik_id = getattr(self, "admin_aktif_ciftlik_id", None)
        eski_ciftlik_ad = getattr(self, "admin_aktif_ciftlik_ad", None)
        self.aktif_zamanlayicilari_durdur()
        for child in self.root.winfo_children():
            child.destroy()
        self.themed_widgets = []
        self.themed_buttons = []
        if not self.admin_yonetim_merkezi():
            if getattr(self, "_login_yeniden_iste", False):
                self._login_yeniden_iste = False
                return self.oturumu_kapat_ve_login(onay_iste=False)
            self.admin_aktif_ciftlik_id = eski_ciftlik_id
            self.admin_aktif_ciftlik_ad = eski_ciftlik_ad
        try:
            self.hayvanlar = self.veri_yukle()
        except Exception as e:
            messagebox.showerror("Admin Merkezi", f"Suru verisi yuklenemedi:\n{e}", parent=self.root)
        self.uyari_thread_running = True
        self.ana_interface_olustur()
        self.uyari_sistemi_baslat()
        self.root.protocol("WM_DELETE_WINDOW", self.uygulamayi_kapat)

    def api_hayvanlari_yukle(self):
        hayvanlar_dict = {}
        limit = 500
        skip = 0
        while True:
            path = f"/api/hayvanlar?skip={skip}&limit={limit}&arsiv_dahil=true"
            if self.admin_mi() and getattr(self, "admin_aktif_ciftlik_id", None):
                path += f"&ciftlik_id={self.api_ref(self.admin_aktif_ciftlik_id)}"
            kayitlar = self.api_istek("GET", path, timeout=20)
            if not isinstance(kayitlar, list):
                raise ApiHatasi("API hayvan listesi beklenen formatta değil.")
            for kayit in kayitlar:
                h_id = str(kayit.get("id") or uuid.uuid4().hex)
                hayvanlar_dict[h_id] = self.hayvan_kayit_tamamla(h_id, kayit)
            if len(kayitlar) < limit:
                break
            skip += limit
        self._api_son_idler = set(hayvanlar_dict.keys())
        self._api_base_versions = {
            h_id: veri.get("son_guncelleme")
            for h_id, veri in hayvanlar_dict.items()
            if veri.get("son_guncelleme")
        }
        self.api_cevrimdisi = False
        self.api_offline_oturum = False
        self._api_son_hata = None
        return hayvanlar_dict

    def api_hayvan_detayini_yukle(self, h_id):
        if not getattr(self, "api_modu", False) or self.offline_modda_mi():
            return str(h_id)
        h_id = str(h_id)
        try:
            kayit = self.api_istek("GET", f"/api/hayvanlar/{self.api_ref(h_id)}", timeout=20)
            if not isinstance(kayit, dict):
                return h_id
            kayit_id = str(kayit.get("id") or h_id)
            tamamlanmis = self.hayvan_kayit_tamamla(kayit_id, kayit)
            if kayit_id != h_id:
                self.hayvanlar.pop(h_id, None)
            self.hayvanlar[kayit_id] = tamamlanmis
            onceki_idler = set(getattr(self, "_api_son_idler", set()))
            onceki_idler.discard(h_id)
            onceki_idler.add(kayit_id)
            self._api_son_idler = onceki_idler
            self._api_base_versions.pop(h_id, None)
            if tamamlanmis.get("son_guncelleme"):
                self._api_base_versions[kayit_id] = tamamlanmis["son_guncelleme"]
            self.json_dosyasi_kaydet(self.data_file, self.hayvanlar, "hayvan_verileri", "API Onbellek Kayit Hatasi")
            return kayit_id
        except ApiHatasi as e:
            self._api_son_hata = str(e)
            return h_id

    def api_hayvanlari_kaydet(self):
        if self.offline_modda_mi():
            raise ApiHatasi("API offline modda; kayitlar yerel senkron kuyruguna alinacak.")
        if self.bekleyen_senkron_var() and not self.bekleyen_senkron_gonder(sessiz=True):
            hata = getattr(self, "_api_son_hata", None) or "Bekleyen offline degisiklikler senkronlanamadi."
            raise ApiHatasi(f"Bekleyen offline degisiklikler senkronlanamadi.\n\nDetay: {hata}")

        onceki_idler = set(getattr(self, "_api_son_idler", set()))
        mevcut_idler = {str(h_id) for h_id in self.hayvanlar.keys()}

        for silinen_id in sorted(onceki_idler - mevcut_idler):
            delete_path = f"/api/hayvanlar/{self.api_ref(silinen_id)}?kalici=true"
            base_version = getattr(self, "_api_base_versions", {}).get(silinen_id)
            if base_version:
                delete_path += f"&beklenen_son_guncelleme={self.api_ref(base_version)}"
            self.api_istek("DELETE", delete_path)
            self._api_base_versions.pop(silinen_id, None)

        guncel_hayvanlar = {}
        for h_id, veri in list(self.hayvanlar.items()):
            h_id = str(h_id)
            kayit_id, tamamlanmis = self.api_hayvan_kayit_gonder(h_id, veri, onceki_idler)
            if tamamlanmis is None:
                continue
            if h_id in self.hayvanlar and isinstance(self.hayvanlar[h_id], dict):
                self.hayvanlar[h_id].clear()
                self.hayvanlar[h_id].update(tamamlanmis)
                guncel_hayvanlar[kayit_id] = self.hayvanlar[h_id]
            else:
                guncel_hayvanlar[kayit_id] = tamamlanmis

        self.hayvanlar = guncel_hayvanlar
        self._api_son_idler = set(guncel_hayvanlar.keys())
        self.api_cevrimdisi = False
        self.api_offline_oturum = False
        self._api_son_hata = None
        return self.json_dosyasi_kaydet(self.data_file, self.hayvanlar, "hayvan_verileri", "API Önbellek Kayıt Hatası")

    def api_hayvan_kaydet_tekil(self, h_id, ui_guncelle=True):
        if self.offline_modda_mi():
            raise ApiHatasi("API offline modda; kayit yerel senkron kuyruguna alinacak.")
        if self.bekleyen_senkron_var() and not self.bekleyen_senkron_gonder(sessiz=True, ui_guncelle=ui_guncelle):
            hata = getattr(self, "_api_son_hata", None) or "Bekleyen offline degisiklikler senkronlanamadi."
            raise ApiHatasi(f"Bekleyen offline degisiklikler senkronlanamadi.\n\nDetay: {hata}")

        h_id = str(h_id)
        onceki_idler = set(getattr(self, "_api_son_idler", set()))
        if h_id not in self.hayvanlar:
            if h_id in onceki_idler:
                delete_path = f"/api/hayvanlar/{self.api_ref(h_id)}?kalici=true"
                base_version = getattr(self, "_api_base_versions", {}).get(h_id)
                if base_version:
                    delete_path += f"&beklenen_son_guncelleme={self.api_ref(base_version)}"
                self.api_istek("DELETE", delete_path)
                onceki_idler.discard(h_id)
                self._api_base_versions.pop(h_id, None)
                self._api_son_idler = onceki_idler
            self.api_cevrimdisi = False
            self.api_offline_oturum = False
            self._api_son_hata = None
            return self.json_dosyasi_kaydet(self.data_file, self.hayvanlar, "hayvan_verileri", "API Önbellek Kayıt Hatası")

        kayit_id, tamamlanmis = self.api_hayvan_kayit_gonder(h_id, self.hayvanlar[h_id], onceki_idler)
        if tamamlanmis is None:
            self.hayvanlar.pop(h_id, None)
            onceki_idler.discard(h_id)
        else:
            if h_id != kayit_id:
                self.hayvanlar.pop(h_id, None)
            self.hayvanlar[kayit_id] = tamamlanmis
            onceki_idler.discard(h_id)
            onceki_idler.add(kayit_id)

        self._api_son_idler = onceki_idler
        self.api_cevrimdisi = False
        self.api_offline_oturum = False
        self._api_son_hata = None
        return self.json_dosyasi_kaydet(self.data_file, self.hayvanlar, "hayvan_verileri", "API Önbellek Kayıt Hatası")

    def api_verilerini_yenile(self, sessiz=False):
        if not getattr(self, "api_modu", False):
            self.hayvan_listesini_guncelle()
            return True
        try:
            if self.bekleyen_senkron_var() and not self.bekleyen_senkron_gonder(sessiz=sessiz):
                return False
            if getattr(self, "api_offline_oturum", False):
                self.api_online_oturum_ac()
            self.hayvanlar = self.api_hayvanlari_yukle()
            self.json_dosyasi_kaydet(self.data_file, self.hayvanlar, "hayvan_verileri", "API Önbellek Kayıt Hatası")
            self.ekranlari_guncelle()
            self.header_ozet_guncelle()
            self.api_durum_guncelle()
            if not sessiz:
                messagebox.showinfo("Yenile", "Online veriler yenilendi.", parent=self.root)
            return True
        except ApiHatasi as e:
            self.api_cevrimdisi = True
            self._api_son_hata = str(e)
            self.api_durum_guncelle()
            if not sessiz:
                messagebox.showerror("Yenile", f"Online veriler yenilenemedi:\n{e}", parent=self.root)
            return False

    def veritabani_hazirla(self):
        from database import Base, SessionLocal, engine, ensure_postgres_schema_updates, ensure_postgres_security, ensure_sqlite_schema
        import models
        _ = models.Hayvan
        Base.metadata.create_all(bind=engine)
        ensure_sqlite_schema()
        ensure_postgres_schema_updates()
        ensure_postgres_security()
        return SessionLocal

    def bos_yoksa_none(self, deger):
        if deger is None:
            return None
        deger = str(deger).strip()
        return deger or None

    def turkce_metin_onar(self, deger):
        if deger is None:
            return ""
        metin_degeri = str(deger).strip()
        onarimlar = {
            "Sa?mal ?nek": "Sa\u011fmal \u0130nek",
            "Sagmal Inek": "Sa\u011fmal \u0130nek",
            "sagmal": "Sa\u011fmal \u0130nek",
            "D?ve": "D\u00fcve",
            "Duve": "D\u00fcve",
            "duve": "D\u00fcve",
            "Kuru ?nek": "Kuru \u0130nek",
            "Kuru Inek": "Kuru \u0130nek",
            "Di?i Buza??": "Di\u015fi Buza\u011f\u0131",
            "Disi Buzagi": "Di\u015fi Buza\u011f\u0131",
            "Erkek Buza??": "Erkek Buza\u011f\u0131",
            "Erkek Buzagi": "Erkek Buza\u011f\u0131",
            "Sat?ld?": "Sat\u0131ld\u0131",
            "Ar?ivli": "Ar\u015fivli",
        }
        return onarimlar.get(metin_degeri, metin_degeri)

    def hayvan_yas_gun_hesapla(self, veri):
        try:
            dogum_tarihi = veri.get('dogum_tarihi')
            if not dogum_tarihi:
                return int(veri.get('yas_gun', 0) or 0)
            return (datetime.now() - datetime.strptime(dogum_tarihi, "%d/%m/%Y")).days
        except Exception:
            return int(veri.get('yas_gun', 0) or 0)

    def hayvan_kayit_tamamla(self, h_id, veri):
        veri = dict(veri or {})
        eski_kupe = str(veri.get('kupe_no') or h_id or "").strip().upper()
        resmi = str(veri.get('resmi_kupe_no') or "").strip().upper()
        ciftlik = str(veri.get('ciftlik_kupe_no') or "").strip().upper()

        if not resmi and not ciftlik and eski_kupe and eski_kupe not in {"BILINMIYOR", "BİLİNMİYOR"}:
            ciftlik = eski_kupe

        veri['resmi_kupe_no'] = resmi
        veri['ciftlik_kupe_no'] = ciftlik
        veri['kupe_no'] = ciftlik or resmi or eski_kupe or str(h_id)
        veri['dogum_tarihi'] = veri.get('dogum_tarihi') or ""
        veri['cins'] = self.turkce_metin_onar(veri.get('cins')) or "Bilinmiyor"
        veri['irk'] = self.turkce_metin_onar(veri.get('irk'))
        veri['yas_gun'] = self.hayvan_yas_gun_hesapla(veri)
        veri['durum'] = self.turkce_metin_onar(veri.get('durum')) or self.durum_hesapla(veri.get('cins'), veri.get('yas_gun', 0))
        veri['tohumlamalar'] = list(veri.get('tohumlamalar') or [])
        veri['dogumlar'] = list(veri.get('dogumlar') or [])
        veri['asi_prosedurler'] = list(veri.get('asi_prosedurler') or [])
        veri['gebe_mi'] = bool(veri.get('gebe_mi', False))
        veri['olu'] = bool(veri.get('olu', False))
        veri['kesildi'] = bool(veri.get('kesildi', False))
        veri['arsivli'] = bool(veri.get('arsivli', False))
        veri['satildi'] = bool(veri.get('satildi', False))
        if veri['satildi']:
            veri['durum'] = "Satıldı"
            veri['gebe_mi'] = False
            veri['gebelik_tarihi'] = None
            veri['aktif_tohumlama_id'] = None
        veri.setdefault('anne_kupe', "")
        veri.setdefault('ciftlik_id', None)
        veri.setdefault('ciftlik_ad', None)
        veri.setdefault('kayit_tarihi', "")
        veri.setdefault('gebelik_tarihi', None)
        veri.setdefault('aktif_tohumlama_id', None)
        veri.setdefault('olum_tarihi', None)
        veri.setdefault('kesim_bilgisi', None)
        veri.setdefault('arsiv_tarihi', None)
        veri.setdefault('satis_tarihi', None)
        veri.setdefault('satis_bilgisi', None)
        veri.setdefault('foto_data', None)
        veri.setdefault('foto_url', None)
        veri.setdefault('foto_datas', [])
        veri.setdefault('foto_urls', [])
        veri.setdefault('foto_path', None)
        veri.setdefault('foto_paths', [])
        self.hayvan_fotograflari_ata(veri, self.hayvan_fotograflari(veri))
        veri.setdefault('son_guncelleme', "")
        return veri

    def hayvan_kimlikleri(self, h_id, veri):
        kimlikler = {str(h_id).strip().upper()}
        for alan in ('kupe_no', 'resmi_kupe_no', 'ciftlik_kupe_no'):
            deger = str(veri.get(alan) or "").strip().upper()
            if deger:
                kimlikler.add(deger)
        kimlikler.discard("")
        return kimlikler

    def kupe_arama_temizle(self, deger):
        return re.sub(r"[^A-Z0-9]", "", str(deger or "").upper())

    def kupe_arama_rakamlar(self, deger):
        return re.sub(r"\D", "", str(deger or ""))

    def resmi_kupe_kisaltma_eslesir(self, arama, resmi_kupe):
        eslesme = re.fullmatch(r"\s*([A-Z]{2})\s+(\d{4,5})\s*", str(arama or "").upper())
        if not eslesme:
            return False
        resmi_temiz = self.kupe_arama_temizle(resmi_kupe)
        if not resmi_temiz.startswith(eslesme.group(1)):
            return False
        return eslesme.group(2) in self.kupe_arama_rakamlar(resmi_temiz)

    def hayvan_arama_eslesir(self, h_id, hayvan, arama, kaynak="normal"):
        arama_metin = str(arama or "").strip().upper()
        arama_temiz = self.kupe_arama_temizle(arama_metin)
        arama_rakam = self.kupe_arama_rakamlar(arama_metin)
        if not arama_metin:
            return True

        resmi = str((hayvan or {}).get("resmi_kupe_no") or "").strip().upper()
        ciftlik = str((hayvan or {}).get("ciftlik_kupe_no") or "").strip().upper()
        kupe_no = str((hayvan or {}).get("kupe_no") or "").strip().upper()
        kimlikler = [str(h_id).strip().upper(), kupe_no, resmi, ciftlik]
        kimlikler = [k for k in kimlikler if k]
        temiz_kimlikler = [self.kupe_arama_temizle(k) for k in kimlikler]
        ciftlik_rakam = self.kupe_arama_rakamlar(ciftlik)

        if str(kaynak or "normal").lower() == "kamera":
            resmi_temiz = self.kupe_arama_temizle(resmi)
            if arama_temiz and resmi_temiz and arama_temiz == resmi_temiz:
                return True
            if len(arama_rakam) >= 6 and ciftlik_rakam and ciftlik_rakam.endswith(arama_rakam[-6:]):
                return True
            return False

        birlesik = " ".join(kimlikler)
        if arama_metin in birlesik:
            return True
        if arama_temiz and any(arama_temiz in temiz for temiz in temiz_kimlikler):
            return True
        if len(arama_rakam) == 6 and ciftlik_rakam.endswith(arama_rakam):
            return True
        if self.resmi_kupe_kisaltma_eslesir(arama_metin, resmi):
            return True
        return False

    def hayvan_arama_idleri(self, arama, aktif_olsun=False, haric_id=None, kaynak="normal"):
        haric_id = str(haric_id) if haric_id is not None else None
        eslesenler = []
        for h_id, hayvan in self.hayvanlar.items():
            if haric_id is not None and str(h_id) == haric_id:
                continue
            if aktif_olsun and (hayvan.get('arsivli') or hayvan.get('olu') or hayvan.get('kesildi') or hayvan.get('satildi')):
                continue
            if self.hayvan_arama_eslesir(h_id, hayvan, arama, kaynak=kaynak):
                eslesenler.append(h_id)
        return eslesenler

    def hayvan_referans_coz(self, kupe_girdi, aktif_olsun=False):
        hayvan_id = self.hayvan_id_bul(kupe_girdi, aktif_olsun=aktif_olsun)
        if hayvan_id:
            return hayvan_id
        eslesenler = self.hayvan_arama_idleri(kupe_girdi, aktif_olsun=aktif_olsun)
        return eslesenler[0] if len(eslesenler) == 1 else None

    def hayvan_id_bul(self, kupe_girdi, aktif_olsun=False, haric_id=None):
        aranan = str(kupe_girdi or "").strip().upper()
        if not aranan:
            return None
        haric_id = str(haric_id) if haric_id is not None else None
        for h_id, hayvan in self.hayvanlar.items():
            if haric_id is not None and str(h_id) == haric_id:
                continue
            if aktif_olsun and (hayvan.get('arsivli') or hayvan.get('olu') or hayvan.get('kesildi') or hayvan.get('satildi')):
                continue
            if aranan in self.hayvan_kimlikleri(h_id, hayvan):
                return h_id
        return None

    def kupe_cakismasi_var(self, resmi_kupe, ciftlik_kupe, haric_id=None, ciftlik_id=None):
        kupeler = {str(k or "").strip().upper() for k in (resmi_kupe, ciftlik_kupe) if k}
        if not kupeler:
            return False
        haric_id = str(haric_id) if haric_id is not None else None
        hedef_ciftlik_id = str(ciftlik_id) if ciftlik_id else None
        for h_id, hayvan in self.hayvanlar.items():
            if haric_id is not None and str(h_id) == haric_id:
                continue
            if hedef_ciftlik_id and str(hayvan.get("ciftlik_id") or "") != hedef_ciftlik_id:
                continue
            if kupeler.intersection(self.hayvan_kimlikleri(h_id, hayvan)):
                return True
        return False

    def db_hayvandan_sozluk(self, h):
        if getattr(h, "veri_json", None):
            try:
                veri = json.loads(h.veri_json)
                if isinstance(veri, dict):
                    return self.hayvan_kayit_tamamla(h.id, veri)
            except json.JSONDecodeError:
                self._veri_migrasyonu_gerekli = True

        tohumlamalar = [
            {
                'id': t.id,
                'tarih': t.tarih,
                'sekil': t.sekil,
                'suni_isim': t.suni_isim,
                'gebe_mi': t.gebe_mi,
                'kontrol_tarihi': t.kontrol_tarihi,
                'gebelik_suresi': 283,
            }
            for t in h.tohumlamalar
        ]
        aktif_tohumlama = next((t for t in reversed(tohumlamalar) if t.get('gebe_mi') is True), None)
        yas_gun = (h.yas_yil or 0) * 365 + (h.yas_ay or 0) * 30
        veri = {
            'kupe_no': h.ciftlik_kupe_no or h.resmi_kupe_no or h.id,
            'resmi_kupe_no': h.resmi_kupe_no or "",
            'ciftlik_kupe_no': h.ciftlik_kupe_no or "",
            'ad': h.ad,
            'dogum_tarihi': h.dogum_tarihi or "",
            'cins': h.cins or "Bilinmiyor",
            'yas_gun': yas_gun,
            'durum': h.durum_notu or "",
            'gebe_mi': aktif_tohumlama is not None,
            'gebelik_tarihi': aktif_tohumlama.get('tarih') if aktif_tohumlama else None,
            'aktif_tohumlama_id': aktif_tohumlama.get('id') if aktif_tohumlama else None,
            'olu': bool(h.olu),
            'olum_tarihi': h.olum_tarihi,
            'kesildi': bool(h.kesildi),
            'kesim_bilgisi': {'tarih': h.kesim_tarihi} if h.kesim_tarihi else None,
            'arsivli': bool(h.arsivli),
            'arsiv_tarihi': h.arsiv_tarihi,
            'son_guncelleme': h.son_guncelleme or "",
            'tohumlamalar': tohumlamalar,
            'dogumlar': [],
            'asi_prosedurler': [
                {
                    'id': a.id,
                    'ad': a.ad,
                    'tarih': a.tarih,
                    'sonraki_tarih': a.sonraki_tarih,
                    'not': a.not_,
                }
                for a in h.asi_prosedurler
            ],
        }
        self._veri_migrasyonu_gerekli = True
        return self.hayvan_kayit_tamamla(h.id, veri)

    def json_kayitlarini_birlestir(self, hayvanlar_dict):
        json_veri = self.json_dosyasi_yukle(self.data_file, {}, "hayvan_verileri")
        if not isinstance(json_veri, dict):
            return

        mevcut_kimlikler = set()
        for h_id, veri in hayvanlar_dict.items():
            mevcut_kimlikler.update(self.hayvan_kimlikleri(h_id, veri))

        for h_id, veri in json_veri.items():
            tamamlanmis = self.hayvan_kayit_tamamla(h_id, veri)
            kimlikler = self.hayvan_kimlikleri(h_id, tamamlanmis)
            if str(h_id) in hayvanlar_dict or mevcut_kimlikler.intersection(kimlikler):
                continue
            hayvanlar_dict[str(h_id)] = tamamlanmis
            mevcut_kimlikler.update(kimlikler)
            self._veri_migrasyonu_gerekli = True

    def veri_yukle(self):
        self._veri_migrasyonu_gerekli = False
        if getattr(self, "api_modu", False) and not getattr(self, "api_offline_oturum", False):
            try:
                hayvanlar_dict = self.api_hayvanlari_yukle()
                self.json_dosyasi_kaydet(self.data_file, hayvanlar_dict, "hayvan_verileri", "API Önbellek Kayıt Hatası")
                return hayvanlar_dict
            except ApiHatasi as e:
                self.api_cevrimdisi = True
                self._api_son_hata = str(e)
                self.bekleyen_senkron_snapshot_guncelle()
                self.api_durum_guncelle()
                messagebox.showwarning(
                    "API Bağlantı Hatası",
                    f"Merkezi API'ye bağlanılamadı.\n\n{e}\n\nSon yerel önbellek açılacak; bağlantı düzelince kayıtlar tekrar API'ye gönderilir."
                )

        if getattr(self, "api_modu", False) and getattr(self, "api_offline_oturum", False):
            self.api_cevrimdisi = True

        hayvanlar_dict = {}
        db = None
        try:
            SessionLocal = self.veritabani_hazirla()
            from models import Hayvan
            db = SessionLocal()
            for h in db.query(Hayvan).all():
                hayvanlar_dict[h.id] = self.db_hayvandan_sozluk(h)
        except Exception as e:
            print(f"Veritabanı yükleme hatası: {e}")
        finally:
            if db is not None:
                db.close()

        self.json_kayitlarini_birlestir(hayvanlar_dict)
        if getattr(self, "api_modu", False):
            self._api_son_idler = set(hayvanlar_dict.keys())
        return hayvanlar_dict

    def veri_kaydet(self, kupe_no=None, hata_mesaji_goster=True, ui_guncelle=True):
        if getattr(self, "api_modu", False):
            if self.offline_modda_mi():
                self.bekleyen_senkron_snapshot_guncelle(kupe_no)
                if ui_guncelle:
                    self.api_durum_guncelle()
                return self.json_dosyasi_kaydet(self.data_file, self.hayvanlar, "hayvan_verileri", "Veri Kayit Hatasi")
            try:
                if kupe_no is not None:
                    return self.api_hayvan_kaydet_tekil(kupe_no, ui_guncelle=ui_guncelle)
                return self.api_hayvanlari_kaydet()
            except ApiHatasi as e:
                self.api_cevrimdisi = True
                self._api_son_hata = str(e)
                self.bekleyen_senkron_snapshot_guncelle(kupe_no)
                if ui_guncelle:
                    self.api_durum_guncelle()
                print(f"API kaydetme hatası: {e}")
                if hata_mesaji_goster:
                    messagebox.showerror(
                        "API Kayıt Hatası",
                        f"Merkezi API'ye kayıt gönderilemedi:\n{e}\n\nVeri yerel önbelleğe kaydedilecek."
                    )
                return self.json_dosyasi_kaydet(self.data_file, self.hayvanlar, "hayvan_verileri", "Veri Kayıt Hatası")

        db = None
        try:
            SessionLocal = self.veritabani_hazirla()
            from models import Hayvan, Tohumlama, AsiProsedur
            db = SessionLocal()
            mevcut_idler = {str(h_id) for h_id in self.hayvanlar.keys()}

            for db_hayvan in db.query(Hayvan).all():
                if db_hayvan.id not in mevcut_idler:
                    db.delete(db_hayvan)
            db.flush()

            for h_id, veri in self.hayvanlar.items():
                h_id = str(h_id)
                veri = self.hayvan_kayit_tamamla(h_id, veri)
                self.hayvanlar[h_id] = veri

                db_hayvan = db.query(Hayvan).filter(Hayvan.id == h_id).first()
                if not db_hayvan:
                    db_hayvan = Hayvan(id=h_id)
                    db.add(db_hayvan)

                yas_gun = max(int(veri.get('yas_gun', 0) or 0), 0)
                kesim_bilgisi = veri.get('kesim_bilgisi') or {}
                db_hayvan.resmi_kupe_no = self.bos_yoksa_none(veri.get('resmi_kupe_no'))
                db_hayvan.ciftlik_kupe_no = self.bos_yoksa_none(veri.get('ciftlik_kupe_no'))
                db_hayvan.ad = self.bos_yoksa_none(veri.get('ad'))
                db_hayvan.yas_yil = yas_gun // 365
                db_hayvan.yas_ay = (yas_gun % 365) // 30
                db_hayvan.cins = veri.get('cins') or "Bilinmiyor"
                db_hayvan.cinsiyet = "Erkek" if db_hayvan.cins in ["Erkek Buzağı", "Dana"] else "Dişi"
                db_hayvan.durum_notu = veri.get('durum') or ""
                db_hayvan.dogum_tarihi = self.bos_yoksa_none(veri.get('dogum_tarihi'))
                db_hayvan.ek_notlar = self.bos_yoksa_none(veri.get('ek_notlar'))
                db_hayvan.olu = bool(veri.get('olu', False))
                db_hayvan.kesildi = bool(veri.get('kesildi', False))
                db_hayvan.arsivli = bool(veri.get('arsivli', False))
                db_hayvan.olum_tarihi = self.bos_yoksa_none(veri.get('olum_tarihi'))
                db_hayvan.kesim_tarihi = self.bos_yoksa_none(kesim_bilgisi.get('tarih'))
                db_hayvan.arsiv_tarihi = self.bos_yoksa_none(veri.get('arsiv_tarihi'))
                db_hayvan.son_guncelleme = self.bos_yoksa_none(veri.get('son_guncelleme'))
                db_hayvan.veri_json = json.dumps(veri, ensure_ascii=False)

                db.query(Tohumlama).filter(Tohumlama.hayvan_id == h_id).delete()
                for t in veri.get('tohumlamalar', []):
                    db.add(Tohumlama(
                        id=t.get('id') or uuid.uuid4().hex[:12],
                        hayvan_id=h_id,
                        tarih=t.get('tarih') or "",
                        sekil=t.get('sekil') or "",
                        suni_isim=t.get('suni_isim') or "",
                        gebe_mi=t.get('gebe_mi'),
                        kontrol_tarihi=t.get('kontrol_tarihi'),
                    ))

                db.query(AsiProsedur).filter(AsiProsedur.hayvan_id == h_id).delete()
                for a in veri.get('asi_prosedurler', []):
                    db.add(AsiProsedur(
                        id=a.get('id') or uuid.uuid4().hex[:12],
                        hayvan_id=h_id,
                        ad=a.get('ad') or "",
                        tarih=a.get('tarih') or "",
                        sonraki_tarih=a.get('sonraki_tarih'),
                        not_=a.get('not') or "",
                    ))

            db.commit()
        except Exception as e:
            if db is not None:
                db.rollback()
            print(f"Veritabanı kaydetme hatası: {e}")
            return False
        finally:
            if db is not None:
                db.close()

        return self.json_dosyasi_kaydet(self.data_file, self.hayvanlar, "hayvan_verileri", "Veri Kayıt Hatası")

    def veri_kaydet_coklu(self, kupe_nolari, hata_mesaji_goster=True, ui_guncelle=True):
        if not getattr(self, "api_modu", False):
            return self.veri_kaydet(hata_mesaji_goster=hata_mesaji_goster, ui_guncelle=ui_guncelle)

        temiz_idler = []
        for kupe_no in kupe_nolari or []:
            if kupe_no is None:
                continue
            kupe_no = str(kupe_no)
            if kupe_no and kupe_no not in temiz_idler:
                temiz_idler.append(kupe_no)
        if not temiz_idler:
            return self.veri_kaydet(hata_mesaji_goster=hata_mesaji_goster, ui_guncelle=ui_guncelle)

        basarili = True
        for kupe_no in temiz_idler:
            if not self.veri_kaydet(kupe_no=kupe_no, hata_mesaji_goster=hata_mesaji_goster, ui_guncelle=False):
                basarili = False
        if ui_guncelle:
            try:
                self.api_durum_guncelle()
            except Exception:
                pass
        return basarili

    def okunan_uyarilar_yukle(self):
        return self.json_dosyasi_yukle(self.uyari_file, {}, "okunan_uyarilar")

    def okunan_uyarilar_kaydet(self):
        return self.json_dosyasi_kaydet(self.uyari_file, self.okunan_uyarilar, "okunan_uyarilar", "Uyarı Kayıt Hatası")

    def islem_gecmisi_yukle(self):
        try:
            from database import SessionLocal
            from models import IslemGecmisi
            db = SessionLocal()
            gecmis = [{'id': g.id, 'zaman': g.zaman, 'aciklama': g.detay} for g in db.query(IslemGecmisi).all()]
            db.close()
            return gecmis
        except:
            return []

    def islem_kaydi_baslat(self, aciklama, geri_alinabilir=True, geri_alinamaz_neden=None):
        if hasattr(self, "hayvanlar"):
            try:
                self.geri_al_yigini.append({
                    "zaman": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    "aciklama": aciklama,
                    "geri_alinabilir": bool(geri_alinabilir),
                    "geri_alinamaz_neden": geri_alinamaz_neden or "",
                    "hayvanlar": copy.deepcopy(self.hayvanlar),
                })
                if len(self.geri_al_yigini) > 10:
                    self.geri_al_yigini.pop(0)
            except Exception:
                pass
        try:
            from database import SessionLocal
            from models import IslemGecmisi
            import uuid
            db = SessionLocal()
            zaman_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            yeni = IslemGecmisi(id=uuid.uuid4().hex, zaman=zaman_str, detay=aciklama)
            db.add(yeni)
            db.commit()
            db.close()
            self.islem_gecmisi.insert(0, {'zaman': zaman_str, 'aciklama': aciklama})
            if len(self.islem_gecmisi) > 500:
                self.islem_gecmisi.pop()
        except:
            pass

    def geri_al_islemi_uygun_mu(self, kayit):
        if not kayit:
            return False, "İşlem kaydı okunamadı."
        if kayit.get("geri_alinabilir") is False:
            return False, kayit.get("geri_alinamaz_neden") or "Bu işlem geri alınamaz."
        aciklama = str(kayit.get("aciklama") or "").casefold()
        kontrol = aciklama.replace("ı", "i").replace("İ", "i")
        if ("kalici" in kontrol or "kal?c" in kontrol) and "sil" in kontrol:
            return False, "Kalıcı silinen hayvan geri getirilemez."
        return True, ""

    def geri_al_farki_hesapla(self, onceki, sonraki):
        onceki = onceki or {}
        sonraki = sonraki or {}
        onceki_idler = {str(k) for k in onceki.keys()}
        sonraki_idler = {str(k) for k in sonraki.keys()}
        geri_yuklenecek = {}
        for h_id in sorted(onceki_idler):
            if h_id not in sonraki_idler or onceki.get(h_id) != sonraki.get(h_id):
                geri_yuklenecek[h_id] = copy.deepcopy(onceki.get(h_id))
        silinecek = sorted(sonraki_idler - onceki_idler)
        return {
            "geri_yuklenecek": geri_yuklenecek,
            "silinecek": silinecek,
            "toplam": len(geri_yuklenecek) + len(silinecek),
        }

    def geri_al_sonraki_durum(self, index):
        if index + 1 < len(self.geri_al_yigini):
            return self.geri_al_yigini[index + 1].get("hayvanlar", {})
        return getattr(self, "hayvanlar", {}) or {}

    def geri_al_api_sil(self, h_id):
        h_id = str(h_id)
        if not getattr(self, "api_modu", False):
            return True
        if self.offline_modda_mi():
            self.bekleyen_senkron_delete(h_id)
            self.bekleyen_senkron_kaydet()
            return True
        try:
            self.api_istek("DELETE", f"/api/hayvanlar/{self.api_ref(h_id)}?kalici=true", timeout=30)
            onceki_idler = set(getattr(self, "_api_son_idler", set()))
            onceki_idler.discard(h_id)
            self._api_son_idler = onceki_idler
            return True
        except ApiHatasi as e:
            if getattr(e, "status", None) == 404:
                return True
            self.api_cevrimdisi = True
            self._api_son_hata = str(e)
            self.bekleyen_senkron_delete(h_id)
            self.bekleyen_senkron_kaydet()
            return False

    def geri_al_kaydi_uygula(self, index, parent=None):
        if not (0 <= index < len(getattr(self, "geri_al_yigini", []))):
            messagebox.showerror("Geri Al", "Seçilen işlem bulunamadı.", parent=parent or self.root)
            return

        kayit = self.geri_al_yigini[index]
        uygun, neden = self.geri_al_islemi_uygun_mu(kayit)
        if not uygun:
            messagebox.showwarning("Geri Al", neden, parent=parent or self.root)
            return

        fark = self.geri_al_farki_hesapla(kayit.get("hayvanlar", {}), self.geri_al_sonraki_durum(index))
        if fark["toplam"] == 0:
            messagebox.showinfo("Geri Al", "Bu işlem için geri alınacak kayıt farkı bulunamadı.", parent=parent or self.root)
            return

        aciklama = kayit.get("aciklama", "-")
        mesaj = (
            f"Seçili işlem geri alınacak:\n\n{aciklama}\n\n"
            f"Geri yüklenecek/düzeltilecek kayıt: {len(fark['geri_yuklenecek'])}\n"
            f"Silinecek yeni kayıt: {len(fark['silinecek'])}\n\n"
            "Bu işlemden daha yeni geri alma kayıtları güvenlik için temizlenecek.\n"
            "Devam edilsin mi?"
        )
        if not messagebox.askyesno("Geri Al", mesaj, parent=parent or self.root):
            return

        hedef = parent or self.root
        try:
            hedef.config(cursor="watch")
            hedef.update_idletasks()
        except Exception:
            pass

        basarili = True
        try:
            for h_id in fark["silinecek"]:
                self.hayvanlar.pop(h_id, None)
                if not self.geri_al_api_sil(h_id):
                    basarili = False

            for h_id, veri in fark["geri_yuklenecek"].items():
                if veri is not None:
                    self.hayvanlar[h_id] = copy.deepcopy(veri)

            if getattr(self, "api_modu", False):
                self.json_dosyasi_kaydet(self.data_file, self.hayvanlar, "hayvan_verileri", "API Önbellek Kayıt Hatası")
                if fark["geri_yuklenecek"]:
                    basarili = self.veri_kaydet_coklu(fark["geri_yuklenecek"].keys(), ui_guncelle=False) and basarili
                else:
                    self.api_durum_guncelle()
            else:
                basarili = self.veri_kaydet(ui_guncelle=False) and basarili

            if basarili:
                del self.geri_al_yigini[index:]
                zaman_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                self.islem_gecmisi.insert(0, {"zaman": zaman_str, "aciklama": f"Geri alındı: {aciklama}"})
                if len(self.islem_gecmisi) > 500:
                    self.islem_gecmisi.pop()
                self.ekranlari_guncelle()
                self.header_ozet_guncelle()
                self.api_durum_guncelle()
                messagebox.showinfo("Geri Al", "Seçili işlem geri alındı.", parent=parent or self.root)
                try:
                    if parent is not None and parent.winfo_exists():
                        parent.destroy()
                except Exception:
                    pass
            else:
                self.ekranlari_guncelle()
                self.header_ozet_guncelle()
                self.api_durum_guncelle()
                messagebox.showwarning(
                    "Geri Al",
                    "Geri alma yerel olarak uygulandı; API bağlantısı sorunlu olduğu için bazı değişiklikler senkron kuyruğuna alındı.",
                    parent=parent or self.root,
                )
        finally:
            try:
                hedef.config(cursor="")
            except Exception:
                pass

    def son_islemi_geri_al(self):
        if not getattr(self, "geri_al_yigini", None):
            messagebox.showinfo("Geri Al", "Geri alınabilecek işlem yok.", parent=self.root)
            return
        pencere = tk.Toplevel(self.root)
        pencere.title("Geri Al")
        pencere.geometry("980x520")
        pencere.minsize(780, 420)
        pencere.configure(bg=self.renkler["arkaplan"])
        pencere.transient(self.root)

        baslik = tk.Frame(pencere, bg=self.renkler["arkaplan"])
        baslik.pack(fill="x", padx=20, pady=(18, 8))
        tk.Label(
            baslik,
            text="Geri Al",
            bg=self.renkler["arkaplan"],
            fg=self.renkler["yazi_rengi"],
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w")
        tk.Label(
            baslik,
            text="Son 10 işlemden birini seçin. Kalıcı silme işlemleri güvenlik nedeniyle geri alınamaz.",
            bg=self.renkler["arkaplan"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(4, 0))

        tablo_frame = tk.Frame(pencere, bg=self.renkler["arkaplan"])
        tablo_frame.pack(fill="both", expand=True, padx=20, pady=8)
        kolonlar = ("zaman", "islem", "durum", "etki")
        tree = ttk.Treeview(tablo_frame, columns=kolonlar, show="headings", style="Modern.Treeview", height=10)
        tree.heading("zaman", text="Zaman")
        tree.heading("islem", text="İşlem")
        tree.heading("durum", text="Durum")
        tree.heading("etki", text="Etkilenen")
        tree.column("zaman", width=155, anchor="center", stretch=False)
        tree.column("islem", width=500, anchor="w")
        tree.column("durum", width=150, anchor="center", stretch=False)
        tree.column("etki", width=120, anchor="center", stretch=False)
        scroll = ttk.Scrollbar(tablo_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        tree.tag_configure("pasif", foreground=self.renkler["muted"])
        tree.tag_configure("uygun", foreground=self.renkler["yazi_rengi"])

        baslangic = max(0, len(self.geri_al_yigini) - 10)
        for index in range(len(self.geri_al_yigini) - 1, baslangic - 1, -1):
            kayit = self.geri_al_yigini[index]
            uygun, neden = self.geri_al_islemi_uygun_mu(kayit)
            fark = self.geri_al_farki_hesapla(kayit.get("hayvanlar", {}), self.geri_al_sonraki_durum(index))
            durum = "Geri alınabilir" if uygun else f"Geri alınamaz: {neden}"
            tree.insert(
                "",
                "end",
                iid=str(index),
                values=(kayit.get("zaman", "-"), kayit.get("aciklama", "-"), durum, fark["toplam"]),
                tags=("uygun" if uygun else "pasif",),
            )

        alt = tk.Frame(pencere, bg=self.renkler["arkaplan"])
        alt.pack(fill="x", padx=20, pady=(8, 18))

        def secili_geri_al():
            secim = tree.selection()
            if not secim:
                messagebox.showwarning("Geri Al", "Lütfen geri alınacak işlemi seçin.", parent=pencere)
                return
            self.geri_al_kaydi_uygula(int(secim[0]), parent=pencere)

        tree.bind("<Double-1>", lambda event: secili_geri_al())
        self.modern_buton(alt, "Seçili İşlemi Geri Al", secili_geri_al, purpose="warning", small=True).pack(side="left")
        self.modern_buton(alt, "Kapat", pencere.destroy, purpose="default", small=True).pack(side="right")

        ilk = tree.get_children()
        if ilk:
            tree.selection_set(ilk[0])
            tree.focus(ilk[0])

    def islem_gecmisi_penceresi(self):
        if getattr(self, "api_modu", False):
            return self.admin_islem_gecmisi_penceresi()

        pencere = tk.Toplevel(self.root)
        pencere.title("İşlem Geçmişi")
        pencere.geometry("850x500")
        pencere.configure(bg=self.renkler["arkaplan"])
        pencere.transient(self.root)

        columns = ("Zaman", "İşlem")
        tree = ttk.Treeview(pencere, columns=columns, show="headings", style='Modern.Treeview')
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=220 if col == "Zaman" else 580, anchor='center')
        tree.pack(fill='both', expand=True, padx=15, pady=15)
        for kayit in self.islem_gecmisi:
            tree.insert('', 'end', values=(kayit.get('zaman', '-'), kayit.get('aciklama', '-')))

        self.modern_buton(pencere, "GERİ AL PENCERESİ", self.son_islemi_geri_al, purpose='warning').pack(pady=(0, 15))

    def gorunen_hayvan_satirlari(self):
        columns = list(self.hayvan_tree["columns"])
        rows = [self.hayvan_tree.item(item, "values") for item in self.hayvan_tree.get_children()]
        if columns and columns[0] == "ID":
            columns = columns[1:]
            rows = [tuple(row[1:]) for row in rows]
        if columns and columns[0] == "Seç":
            columns = columns[1:]
            rows = [tuple(row[1:]) for row in rows]
        return columns, rows

    def export_metadata_olustur(self, kayit_tipi=None):
        kullanici = (getattr(self, "api_kullanici", None) or {}).get("kullanici_adi") or "-"
        ciftlik = (
            getattr(self, "admin_aktif_ciftlik_ad", None)
            or ((getattr(self, "api_kullanici", None) or {}).get("ciftlik") or {}).get("ad")
            or ("Tüm çiftlikler" if self.admin_mi() else "Yerel veri")
        )
        baglanti = "Offline" if self.offline_modda_mi() else ("Online" if getattr(self, "api_modu", False) else "Yerel")
        bilgiler = [
            ("Kullanıcı", kullanici),
            ("Çalışılan alan", ciftlik),
            ("Bağlantı", baglanti),
        ]
        if kayit_tipi:
            bilgiler.append(("Rapor türü", kayit_tipi))
        return bilgiler

    def disa_aktar_penceresi(self):
        pencere = tk.Toplevel(self.root)
        pencere.title("Dışa Aktar")
        pencere.geometry("420x260")
        pencere.configure(bg=self.renkler["arkaplan"])
        pencere.transient(self.root)

        tk.Label(pencere, text="Hayvan listesindeki mevcut görünüm dışa aktarılır.", bg=self.renkler["arkaplan"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 12, 'bold'), wraplength=360).pack(pady=25)
        self.modern_buton(pencere, "EXCEL (.xlsx)", self.excel_disa_aktar, purpose='success', width=22).pack(pady=8)
        self.modern_buton(pencere, "PDF", self.pdf_disa_aktar, purpose='default', width=22).pack(pady=8)

    def excel_disa_aktar(self):
        columns, rows = self.gorunen_hayvan_satirlari()
        if not rows:
            return messagebox.showinfo("Dışa Aktar", "Dışa aktarılacak kayıt yok.")
        dosya_yolu = filedialog.asksaveasfilename(
            title="Excel olarak kaydet",
            defaultextension=".xlsx",
            filetypes=[("Excel Dosyası", "*.xlsx")]
        )
        if not dosya_yolu:
            return
        try:
            metadata = self.export_metadata_olustur("Hayvan listesi")
            if hasattr(self, "filtre_combo"):
                metadata.append(("Filtre", self.filtre_combo.get() or "Tümü"))
            if hasattr(self, "arama_entry"):
                metadata.append(("Arama", self.arama_entry.get().strip() or "-"))
            export_rows_to_excel(
                dosya_yolu,
                "ALP Ziraat Hayvan Listesi",
                columns,
                rows,
                subtitle="Hayvan listesindeki mevcut görünüm",
                metadata=metadata,
                sheet_name="Hayvan Listesi",
            )
            messagebox.showinfo("Başarılı", f"Excel dosyası oluşturuldu:\n{dosya_yolu}")
        except Exception as e:
            messagebox.showerror("Dışa Aktar", f"Excel çıktısı oluşturulamadı:\n{e}")

    def pdf_disa_aktar(self):
        columns, rows = self.gorunen_hayvan_satirlari()
        if not rows:
            return messagebox.showinfo("Dışa Aktar", "Dışa aktarılacak kayıt yok.")
        dosya_yolu = filedialog.asksaveasfilename(
            title="PDF olarak kaydet",
            defaultextension=".pdf",
            filetypes=[("PDF Dosyası", "*.pdf")]
        )
        if not dosya_yolu:
            return
        try:
            metadata = self.export_metadata_olustur("Hayvan listesi")
            if hasattr(self, "filtre_combo"):
                metadata.append(("Filtre", self.filtre_combo.get() or "Tümü"))
            if hasattr(self, "arama_entry"):
                metadata.append(("Arama", self.arama_entry.get().strip() or "-"))
            export_rows_to_pdf(
                dosya_yolu,
                "ALP Ziraat Hayvan Listesi",
                columns,
                rows,
                subtitle="Hayvan listesindeki mevcut görünüm",
                metadata=metadata,
                sheet_name="Hayvan Listesi",
            )
            messagebox.showinfo("Başarılı", f"PDF dosyası oluşturuldu:\n{dosya_yolu}")
        except Exception as e:
            messagebox.showerror("Dışa Aktar", f"PDF çıktısı oluşturulamadı:\n{e}")

    def ekranlari_guncelle(self):
        if hasattr(self, 'dashboard_frame'):
            self.dashboard_guncelle()
        self.hayvan_listesini_guncelle()
        self.uyarilari_guncelle()
        self.raporlari_guncelle()
        if hasattr(self, 'asi_tree'):
            self.asi_prosedur_listesini_guncelle()

    def tarih_coz(self, tarih, alan_adi, parent=None, gelecege_izin_ver=False):
        try:
            sonuc = datetime.strptime(tarih, "%d/%m/%Y")
        except ValueError:
            messagebox.showerror("Hata", f"{alan_adi} geçersiz tarih formatında! (GG/AA/YYYY)", parent=parent)
            return None

        if not gelecege_izin_ver and sonuc.date() > datetime.now().date():
            messagebox.showerror("Hata", f"{alan_adi} gelecekte olamaz.", parent=parent)
            return None

        return sonuc

    def uyari_esigi(self, kalan_gun):
        return is_uyari_esigi(kalan_gun)

    def uyari_key_olustur(self, kupe_no, uyari_tipi, aktif_tohumlama_id, kalan_gun):
        esik = self.uyari_esigi(kalan_gun)
        if not esik:
            return None
        return f"{kupe_no}_{uyari_tipi}_{aktif_tohumlama_id}_{esik}"

    # --- Arayüz Oluşturma Fonksiyonları ---
    def ana_interface_olustur(self):
        try:
            self.root.title("ALP Ziraat - Sürü Takip Sistemi")
        except tk.TclError:
            pass

        #  ÜST BAŞLIK (HEADER) 
        # Header: net, düşük gürültülü operasyon barı
        header_accentstrip = tk.Frame(self.root, bg=self.renkler["ana_kirmizi"], height=4)
        header_accentstrip.pack(fill='x')

        self.baslik_frame = tk.Frame(self.root, bg=self.renkler["siyah"], height=96)
        self.baslik_frame.pack(fill='x')
        self.baslik_frame.pack_propagate(False)
        self.themed_widgets.append((self.baslik_frame, 'baslik_frame'))

        #  Sol: logo + baslik
        sol_grup = tk.Frame(self.baslik_frame, bg=self.renkler["siyah"])
        sol_grup.pack(side='left', fill='y', padx=(16, 0))

        logo_pill = tk.Frame(
            sol_grup,
            bg=self.renkler["siyah"],
            padx=0,
            pady=0,
            highlightthickness=0,
            bd=0
        )
        logo_pill.pack(side='left', fill='y', pady=8, padx=(0, 14))
        try:
            logo_image = Image.open(self.logo_path).convert("RGBA")
            logo_image.thumbnail((190, 74), Image.Resampling.LANCZOS)
            self.logo_gorsel = ImageTk.PhotoImage(logo_image)
            tk.Label(logo_pill, image=self.logo_gorsel, bg=self.renkler["siyah"]).pack()
        except Exception as e:
            print(f"Logo yüklenemedi: {e}")
            tk.Label(logo_pill, text="ALP\nZİRAAT", font=('Segoe UI', 11, 'bold'),
                     bg=self.renkler["siyah"], fg=self.renkler["ana_kirmizi"]).pack(padx=6)

        # Başlık + tagline grubu
        baslik_metin_grup = tk.Frame(sol_grup, bg=self.renkler["siyah"])
        baslik_metin_grup.pack(side='left', fill='y')

        baslik_label = tk.Label(baslik_metin_grup, text="SÜRÜ TAKİP SİSTEMİ",
                                bg=self.renkler["siyah"], fg='#F1F5F9',
                                font=('Segoe UI', 18, 'bold'), anchor='w')
        baslik_label.pack(anchor='w', pady=(22, 0))
        self.themed_widgets.append((baslik_label, 'baslik_label'))

        alt_baslik = tk.Label(baslik_metin_grup, text="Hayvan Yönetim Platformu",
                              bg=self.renkler["siyah"], fg=self.renkler["muted"],
                              font=('Segoe UI', 9), anchor='w')
        alt_baslik.pack(anchor='w')
        self.themed_widgets.append((alt_baslik, 'baslik_muted_label'))

        self.header_stats_pill = tk.Frame(
            self.baslik_frame,
            bg=self.renkler["kart_ikincil"],
            padx=14,
            pady=7,
            highlightthickness=1,
            highlightbackground=self.renkler.get("kenarlik", self.renkler["gri"]),
            bd=0
        )
        self.header_stats_pill.pack(side='left', padx=(22, 0), pady=25)
        self.themed_widgets.append((self.header_stats_pill, 'soft_panel'))
        self.header_stats_label = tk.Label(
            self.header_stats_pill,
            text="",
            bg=self.renkler["kart_ikincil"],
            fg=self.renkler["yazi_rengi"],
            font=('Segoe UI', 9, 'bold')
        )
        self.header_stats_label.pack()
        self.themed_widgets.append((self.header_stats_label, 'label'))
        self.header_ozet_guncelle()

        self.api_status_pill = tk.Frame(
            self.baslik_frame,
            bg=self.renkler["kart_ikincil"],
            padx=12,
            pady=5,
            highlightthickness=1,
            highlightbackground=self.renkler.get("kenarlik", self.renkler["gri"]),
            bd=0
        )
        self.api_status_pill.pack(side='left', padx=(10, 0), pady=25)
        self.themed_widgets.append((self.api_status_pill, 'soft_panel'))
        self.api_status_label = tk.Label(
            self.api_status_pill,
            text="",
            bg=self.renkler["kart_ikincil"],
            fg=self.renkler["muted"],
            font=('Segoe UI', 9, 'bold')
        )
        self.api_status_label.pack()
        self.themed_widgets.append((self.api_status_label, 'muted_label'))
        self.api_version_label = tk.Label(
            self.api_status_pill,
            text=f"v{APP_VERSION}",
            bg=self.renkler["kart_ikincil"],
            fg=self.renkler["muted"],
            font=('Segoe UI', 8, 'bold')
        )
        self.api_version_label.pack(pady=(1, 0))
        self.themed_widgets.append((self.api_version_label, 'muted_label'))
        self.api_durum_guncelle()

        # Dikey ayırıcı
        header_ayirici = tk.Frame(self.baslik_frame, bg=self.renkler["kenarlik"], width=1)
        header_ayirici.pack(
            side='left', fill='y', padx=18, pady=12)
        self.themed_widgets.append((header_ayirici, 'divider'))

        # Sağ: işlem butonları geniş ekranda başlıkta, dar ekranda alt satırda görünür.
        self.header_action_group = tk.Frame(self.baslik_frame, bg=self.renkler["siyah"], padx=8, pady=0)
        self.header_action_group.pack(side='right', fill='y', padx=(8, 14), pady=17)
        self.themed_widgets.append((self.header_action_group, 'baslik_frame'))

        self.header_action_fallback = tk.Frame(self.root, bg=self.renkler["siyah"], padx=12, pady=3)
        self.themed_widgets.append((self.header_action_fallback, 'baslik_frame'))

        aksiyonlar = [
            ("Dışa Aktar", self.disa_aktar_penceresi, 'success'),
            ("Geçmiş", self.islem_gecmisi_penceresi, 'default'),
            ("Geri Al", self.son_islemi_geri_al, 'warning'),
        ]
        if self.admin_mi():
            aksiyonlar.append(("Admin", self.admin_merkeze_don, 'primary'))
        if getattr(self, "api_modu", False):
            aksiyonlar.extend([
                ("Senkronize", self.api_senkronize_et_ui, 'primary'),
                ("Şifre", self.sifre_degistir_penceresi, 'default'),
                ("Çıkış Yap", self.oturumu_kapat_ve_login, 'danger'),
            ])

        self.header_action_buttons = []
        for metin, komut, amac in reversed(aksiyonlar):
            btn = self.modern_buton(self.header_action_group, metin, komut, purpose=amac, small=True)
            btn.pack(side='right', padx=(4, 0), pady=0)
            self.header_action_buttons.append(btn)
        self.fallback_action_buttons = self.responsive_buton_grubu(self.header_action_fallback, aksiyonlar, align="left")
        self.theme_toggle_button = None

        def header_aksiyon_yerlestir(event=None):
            try:
                genis_ekran = self.root.state() == "zoomed" or self.root.winfo_width() >= 1450
                if genis_ekran:
                    if not self.header_action_group.winfo_ismapped():
                        self.header_action_group.pack(side='right', fill='y', padx=(8, 14), pady=17)
                    if self.header_action_fallback.winfo_ismapped():
                        self.header_action_fallback.pack_forget()
                else:
                    if self.header_action_group.winfo_ismapped():
                        self.header_action_group.pack_forget()
                    if not self.header_action_fallback.winfo_ismapped():
                        self.header_action_fallback.pack(fill='x', after=self.baslik_frame)
            except tk.TclError:
                return

        self.root.bind("<Configure>", header_aksiyon_yerlestir, add="+")
        self._track_after(self.root, 80, header_aksiyon_yerlestir)

        #  BİLDİRİM BANDI 
        self.uyari_frame = tk.Frame(self.root, bg=self.renkler["band_normal_bg"], height=38)
        self.uyari_frame.pack(fill='x')
        self.uyari_frame.pack_propagate(False)

        self.uyari_indicator = tk.Frame(self.uyari_frame, bg=self.renkler["yesil"], width=5)
        self.uyari_indicator.pack(side='left', fill='y')

        # İkon
        self._uyari_ikon_lbl = tk.Label(self.uyari_frame, text="",
                                         bg=self.renkler["band_normal_bg"], fg=self.renkler["band_normal_fg"],
                                         font=('Segoe UI', 11))
        self._uyari_ikon_lbl.pack(side='left', padx=(8, 4))

        self.uyari_label = tk.Label(self.uyari_frame, text="",
                                    bg=self.renkler["band_normal_bg"], fg=self.renkler["band_normal_fg"],
                                    font=('Segoe UI', 10, 'bold'), anchor='w')
        self.uyari_label.pack(side='left', expand=True, fill='x')

        self._saat_label = tk.Label(self.uyari_frame, text="",
                                     bg=self.renkler["band_normal_bg"], fg=self.renkler["band_normal_fg"],
                                     font=('Segoe UI', 9))
        self._saat_label.pack(side='right', padx=14)
        self._saati_guncelle()

        #  NOTEBOOK 
        self.notebook = ttk.Notebook(self.root, style='Modern.TNotebook')

        self.dashboard_sekmesi()
        self.hayvan_kayit_sekmesi()
        self.tohumlama_sekmesi()
        self.hayvan_listesi_sekmesi()
        self.raporlama_sekmesi()
        self.asi_prosedur_sekmesi()
        self.uyari_sekmesi()
        
        # Sekmeleri (native tabs) gizle ve özel sekme butonları oluştur
        style = ttk.Style()
        style.layout('Modern.TNotebook.Tab', [])
        
        self.custom_tab_bar = tk.Frame(self.root, bg=self.renkler["arkaplan"])
        self.custom_tab_bar.pack(fill='x', padx=12, pady=(10, 0))
        self.themed_widgets.append((self.custom_tab_bar, 'arkaplan'))

        self.tab_buttons = []
        for i, tab_id in enumerate(self.notebook.tabs()):
            text = self.notebook.tab(tab_id, "text")
            btn = self.modern_buton(self.custom_tab_bar, text, command=lambda idx=i: self._select_tab(idx), purpose='theme', tab=True)
            self.tab_buttons.append(btn)

        self.notebook.pack(fill='both', expand=True, padx=12, pady=(4, 12))

        def tablari_yerlestir(event=None):
            try:
                genislik = max(self.custom_tab_bar.winfo_width() - 12, 120)
                satir = 0
                sutun = 0
                kullanilan = 0
                for btn in self.tab_buttons:
                    btn.grid_forget()
                for btn in self.tab_buttons:
                    try:
                        btn_genislik = int(btn.cget("width")) + 8
                    except (tk.TclError, ValueError):
                        btn_genislik = btn.winfo_reqwidth() + 8
                    if sutun and kullanilan + btn_genislik > genislik:
                        satir += 1
                        sutun = 0
                        kullanilan = 0
                    btn.grid(row=satir, column=sutun, padx=(0, 8), pady=(0, 6), sticky="w")
                    kullanilan += btn_genislik
                    sutun += 1
            except tk.TclError:
                return

        self.custom_tab_bar.bind("<Configure>", tablari_yerlestir)
        self._track_after(self.root, 50, tablari_yerlestir)
            
        self.notebook.bind('<<NotebookTabChanged>>', self._update_custom_tabs)
        self._update_custom_tabs() # Başlangıçta ilk sekmeyi renklendir

        self._baslangic_after_id = self.root.after(500, self.baslangic_guncellemesi)
        self.otomatik_baglanti_kontrol_baslat()

    def header_ozet_guncelle(self):
        if not hasattr(self, 'header_stats_label'):
            return
        try:
            if not self.header_stats_label.winfo_exists():
                return
        except tk.TclError:
            return
        aktif = 0
        gebe = 0
        arsivli = 0
        for hayvan in self.hayvanlar.values():
            if hayvan.get('arsivli'):
                arsivli += 1
            if not hayvan.get('arsivli') and not hayvan.get('olu') and not hayvan.get('kesildi') and not hayvan.get('satildi'):
                aktif += 1
            if hayvan.get('gebe_mi') and not hayvan.get('arsivli') and not hayvan.get('olu') and not hayvan.get('kesildi') and not hayvan.get('satildi'):
                gebe += 1
        self.header_stats_label.config(text=f"{aktif} aktif  ·  {gebe} gebe  ·  {arsivli} arşiv")
        ozet_label_map = {
            "aktif": aktif,
            "gebe": gebe,
            "arsivli": arsivli,
        }
        for anahtar, deger in ozet_label_map.items():
            lbl = getattr(self, f"kayit_ozet_{anahtar}_label", None)
            if lbl and lbl.winfo_exists():
                lbl.config(text=str(deger))
        if hasattr(self, "dashboard_frame"):
            self.dashboard_guncelle()

    def api_durum_guncelle(self):
        if not hasattr(self, 'api_status_label'):
            return
        try:
            if not self.api_status_label.winfo_exists():
                return
        except tk.TclError:
            return
        ciftlik_ad = (
            getattr(self, "admin_aktif_ciftlik_ad", None)
            or ((getattr(self, "api_kullanici", None) or {}).get("ciftlik") or {}).get("ad")
            or ""
        )
        if getattr(self, "api_modu", False):
            bekleyen = self.bekleyen_senkron_sayisi()
            bekleyen_metin = f" | {bekleyen} bekliyor" if bekleyen else ""
            if getattr(self, "api_cevrimdisi", False):
                metin = "Offline"
                renk = self.renkler["uyari"]
            else:
                metin = "Online"
                renk = self.renkler["yesil"]
            if bekleyen_metin:
                metin += bekleyen_metin
        else:
            metin = "Yerel veri"
            renk = self.renkler["muted"]
        if ciftlik_ad:
            metin = f"{ciftlik_ad} - {metin}"
        self.api_status_label.config(text=metin, fg=renk, bg=self.api_status_pill.cget("bg"))
        if hasattr(self, "api_version_label"):
            self.api_version_label.config(text=f"v{APP_VERSION}", bg=self.api_status_pill.cget("bg"))

    def api_ayar_penceresi(self):
        if getattr(self, "api_kullanici", None) and not self.admin_mi():
            messagebox.showwarning(
                "Yetki Yok",
                "Merkezi API adresini sadece admin kullanicilar degistirebilir.",
                parent=self.root,
            )
            return
        mevcut_url = getattr(self, "api_url", "")
        yeni_url = simpledialog.askstring(
            "Merkezi API",
            "Merkezi API adresi:\nBoş bırakırsanız uygulama yerel veri moduna döner.",
            initialvalue=mevcut_url,
            parent=self.root
        )
        if yeni_url is None:
            return
        yeni_url = yeni_url.strip().rstrip("/")
        if yeni_url and not yeni_url.startswith(("http://", "https://")):
            yeni_url = "http://" + yeni_url

        yerel_kopya = dict(getattr(self, "hayvanlar", {}) or {})
        if not self.api_ayarlarini_kaydet(yeni_url):
            return

        if not self.api_modu:
            self.hayvanlar = self.veri_yukle()
            if hasattr(self, "notebook"):
                self.ekranlari_guncelle()
            self.header_ozet_guncelle()
            self.api_durum_guncelle()
            messagebox.showinfo("Merkezi API", "Yerel veri moduna geçildi.")
            return

        try:
            if not self.api_giris_penceresi():
                return
            api_verisi = self.api_hayvanlari_yukle()
            if not api_verisi and yerel_kopya:
                if messagebox.askyesno(
                    "Merkezi API",
                    "API bağlantısı kuruldu ama merkezde kayıt bulunamadı.\n\nMevcut yerel kayıtlar merkeze gönderilsin mi?",
                    parent=self.root
                ):
                    self.hayvanlar = yerel_kopya
                    self._api_son_idler = set()
                    self.veri_kaydet()
                else:
                    self.hayvanlar = api_verisi
            else:
                self.hayvanlar = api_verisi
                self.json_dosyasi_kaydet(self.data_file, self.hayvanlar, "hayvan_verileri", "API Önbellek Kayıt Hatası")
            self.ekranlari_guncelle()
            self.header_ozet_guncelle()
            self.api_durum_guncelle()
            messagebox.showinfo("Merkezi API", "API modu etkinleştirildi ve veri eşitlendi.", parent=self.root)
        except ApiHatasi as e:
            self.api_cevrimdisi = True
            self._api_son_hata = str(e)
            self.api_durum_guncelle()
            messagebox.showerror("Merkezi API", f"API bağlantısı kurulamadı:\n{e}", parent=self.root)

    def _select_tab(self, idx):
        self.notebook.select(idx)
        
    def _update_custom_tabs(self, event=None):
        if not hasattr(self, 'tab_buttons'): return
        try:
            current_idx = self.notebook.index(self.notebook.select())
            for i, btn in enumerate(self.tab_buttons):
                if i == current_idx:
                    btn.purpose = 'primary'
                else:
                    btn.purpose = 'theme'
                
                # Rengi hemen uygula
                bg_hex = self.renkler.get(f"button_{btn.purpose}_bg", self.renkler["button_default_bg"])
                fg_hex = self.renkler.get(f"button_{btn.purpose}_fg", self.renkler["button_default_fg"])
                if btn.winfo_exists():
                    for p in getattr(btn, 'border_parts', []):
                        btn.itemconfig(p, fill=self.renkler.get("kenarlik", self.renkler["gri"]))
                    for p in btn.button_parts:
                        btn.itemconfig(p, fill=bg_hex)
                    btn.itemconfig(btn.text_item, fill=fg_hex)
        except Exception:
            pass

    def _saati_guncelle(self):
        """Sağ üst köşe saatini her dakika günceller."""
        if getattr(self, "_kapanis_istegi", False):
            return
        zaman = datetime.now().strftime("%d %b %Y  ·  %H:%M")
        if hasattr(self, '_saat_label') and self._saat_label.winfo_exists():
            self._saat_label.config(text=zaman)
            self._saat_after_id = self.root.after(60000, self._saati_guncelle)

    def baslangic_guncellemesi(self):
        self.dashboard_guncelle()
        self.header_ozet_guncelle()
        self.api_durum_guncelle()
        self.hayvan_listesini_guncelle()
        self.uyarilari_guncelle()
        self.asi_prosedur_listesini_guncelle()
        self.raporlari_guncelle()

    def otomatik_baglanti_kontrol_gerekli(self):
        return bool(
            getattr(self, "api_modu", False)
            and (
                getattr(self, "api_cevrimdisi", False)
                or getattr(self, "api_offline_oturum", False)
                or self.bekleyen_senkron_var()
            )
        )

    def otomatik_baglanti_kontrol_baslat(self, ilk_gecikme_ms=None):
        if not getattr(self, "api_modu", False) or getattr(self, "_kapanis_istegi", False):
            return
        try:
            onceki = getattr(self, "_otomatik_baglanti_after_id", None)
            if onceki:
                self.root.after_cancel(onceki)
        except tk.TclError:
            pass
        gecikme = ilk_gecikme_ms or getattr(self, "otomatik_baglanti_ilk_gecikme_ms", 30000)
        try:
            self._otomatik_baglanti_after_id = self.root.after(gecikme, self.otomatik_baglanti_kontrol)
        except tk.TclError:
            self._otomatik_baglanti_after_id = None

    def otomatik_baglanti_kontrol(self):
        self._otomatik_baglanti_after_id = None
        if getattr(self, "_kapanis_istegi", False) or not getattr(self, "api_modu", False):
            return
        if getattr(self, "_otomatik_baglanti_kontrol_ediliyor", False):
            self.otomatik_baglanti_kontrol_baslat(getattr(self, "otomatik_baglanti_araligi_ms", 60000))
            return

        if self.otomatik_baglanti_kontrol_gerekli():
            self._otomatik_baglanti_kontrol_ediliyor = True
            onceki_bekleyen = self.bekleyen_senkron_sayisi()
            onceki_offline = self.offline_modda_mi()
            try:
                self.api_istek("GET", "/api/health", timeout=10, auth=False)
                if self.api_baglantiyi_yenile_sessiz():
                    self.api_durum_guncelle()
                    if onceki_offline or onceki_bekleyen:
                        self.otomatik_baglanti_bildir(onceki_bekleyen)
            except ApiHatasi as e:
                self.api_cevrimdisi = True
                self._api_son_hata = str(e)
                self.api_durum_guncelle()
            finally:
                self._otomatik_baglanti_kontrol_ediliyor = False

        self.otomatik_baglanti_kontrol_baslat(getattr(self, "otomatik_baglanti_araligi_ms", 60000))

    def otomatik_baglanti_bildir(self, onceki_bekleyen=0):
        if not hasattr(self, "api_status_label"):
            return
        try:
            metin = self.api_status_label.cget("text")
            ek = " | otomatik yenilendi"
            if onceki_bekleyen:
                ek = f" | {onceki_bekleyen} kayit otomatik senkronlandi"
            self.api_status_label.config(text=f"{metin}{ek}", fg=self.renkler["yesil"])
        except tk.TclError:
            pass
    
    def dashboard_ozeti_hesapla(self):
        bugun = datetime.now()
        aktif = gebe = arsiv = bekleyen_kontrol = yaklasan_dogum = kritik = 0
        yaklasan_isler = []
        for h_id, hayvan in self.hayvanlar.items():
            if hayvan.get('arsivli'):
                arsiv += 1
            aktif_mi = not hayvan.get('arsivli') and not hayvan.get('olu') and not hayvan.get('kesildi') and not hayvan.get('satildi')
            if aktif_mi:
                aktif += 1
            if hayvan.get('gebe_mi') and aktif_mi:
                gebe += 1
                try:
                    g_tarihi = datetime.strptime(hayvan.get('gebelik_tarihi', ''), "%d/%m/%Y")
                    dogum_tarihi = g_tarihi + timedelta(days=283)
                    kalan = (dogum_tarihi - bugun).days
                    if kalan <= 30:
                        yaklasan_dogum += 1
                        if kalan <= 7:
                            kritik += 1
                        gorunen = hayvan.get('ciftlik_kupe_no') or hayvan.get('resmi_kupe_no') or h_id
                        yaklasan_isler.append((kalan, "Doğum", gorunen, dogum_tarihi.strftime("%d/%m/%Y")))
                except Exception:
                    pass
            if aktif_mi:
                for toh in hayvan.get('tohumlamalar', []):
                    if toh.get('gebe_mi') is not None:
                        continue
                    kontrol = toh.get('kontrol_tarihi')
                    if not kontrol:
                        continue
                    try:
                        kontrol_tarihi = datetime.strptime(kontrol, "%d/%m/%Y")
                    except Exception:
                        continue
                    kalan = (kontrol_tarihi - bugun).days
                    if kalan <= 7:
                        bekleyen_kontrol += 1
                        if kalan < 0:
                            kritik += 1
                        gorunen = hayvan.get('ciftlik_kupe_no') or hayvan.get('resmi_kupe_no') or h_id
                        yaklasan_isler.append((kalan, "Gebelik kontrol", gorunen, kontrol))
        yaklasan_isler.sort(key=lambda item: item[0])
        return {
            "aktif": aktif,
            "gebe": gebe,
            "arsiv": arsiv,
            "bekleyen_kontrol": bekleyen_kontrol,
            "yaklasan_dogum": yaklasan_dogum,
            "kritik": kritik,
            "yaklasan_isler": yaklasan_isler[:12],
        }

    def dashboard_metric_kart(self, parent, baslik, deger, renk):
        kart = self.modern_kart(parent)
        kart.configure(bg=self.renkler["kart_ikincil"])
        kart.configure(width=176, height=76)
        kart.pack_propagate(False)
        self.themed_widgets.append((kart, 'soft_panel'))
        ic = tk.Frame(kart, bg=self.renkler["kart_ikincil"], padx=14, pady=8)
        ic.pack(fill="both", expand=True)
        self.themed_widgets.append((ic, 'soft_panel'))
        tk.Label(ic, text=baslik, bg=self.renkler["kart_ikincil"], fg=self.renkler["muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
        lbl = tk.Label(ic, text=str(deger), bg=self.renkler["kart_ikincil"], fg=renk, font=("Segoe UI", 20, "bold"))
        lbl.pack(anchor="w", pady=(4, 0))
        return kart, lbl

    def dashboard_metric_grid_yerlestir(self, parent, widgets):
        def duzenle(event=None):
            try:
                root_genisligi = max(self.root.winfo_width(), 1)
                width = min(max(parent.winfo_width(), 1), max(root_genisligi - 90, 1))
                hedef_genislik = 186
                bosluk = 10
                maks_kolon = len(widgets)
                cols = max(1, min(len(widgets), maks_kolon, (width + bosluk) // (hedef_genislik + bosluk)))
                for widget in widgets:
                    widget.grid_forget()
                for idx, widget in enumerate(widgets):
                    col = idx % cols
                    row = idx // cols
                    widget.grid(row=row, column=col, sticky="w", padx=(0 if col == 0 else 10, 0), pady=(0, 10))
                for col in range(6):
                    parent.grid_columnconfigure(col, weight=0, uniform="")
            except tk.TclError:
                pass

        parent.bind("<Configure>", duzenle)
        parent.after_idle(duzenle)

    def dashboard_sekmesi(self):
        self.dashboard_frame = ttk.Frame(self.notebook, style='TFrame')
        self.notebook.add(self.dashboard_frame, text="Dashboard")
        sayfa = self.kaydirilabilir_sayfa(self.dashboard_frame, padx=28, pady=22)
        self._sayfa_basligi(sayfa, "Dashboard", "Çiftliğin anlık durumu, yaklaşan işler ve son hareketler.")

        metric_grid = tk.Frame(sayfa, bg=self.renkler["arkaplan"])
        metric_grid.pack(fill="x", pady=(0, 16))
        self.themed_widgets.append((metric_grid, 'arkaplan'))

        metric_defs = [
            ("aktif", "Aktif Hayvan", self.renkler["button_success_bg"]),
            ("gebe", "Gebe", self.renkler["button_primary_bg"]),
            ("arsiv", "Arşiv", self.renkler["muted"]),
            ("bekleyen_kontrol", "Gebelik Kontrol", self.renkler["uyari"]),
            ("yaklasan_dogum", "Yaklaşan Doğum", self.renkler["button_warning_bg"]),
            ("kritik", "Kritik", self.renkler["button_danger_bg"]),
        ]
        self.dashboard_metric_labels = {}
        metric_widgets = []
        for key, title, color in metric_defs:
            kart, lbl = self.dashboard_metric_kart(metric_grid, title, 0, color)
            metric_widgets.append(kart)
            self.dashboard_metric_labels[key] = lbl
        self.dashboard_metric_grid_yerlestir(metric_grid, metric_widgets)

        alt_grid = tk.Frame(sayfa, bg=self.renkler["arkaplan"])
        alt_grid.pack(fill="both", expand=True)
        alt_grid.columnconfigure(0, weight=3)
        alt_grid.columnconfigure(1, weight=2)
        alt_grid.rowconfigure(0, weight=1)
        self.themed_widgets.append((alt_grid, 'arkaplan'))

        isler_card = self.modern_kart(alt_grid, accent=self.renkler["button_primary_bg"])
        isler_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        tk.Label(isler_card, text="Yaklaşan İşler", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=18, pady=(16, 8))
        self.dashboard_isler_tree = ttk.Treeview(isler_card, columns=("tip", "hayvan", "tarih", "kalan"), show="headings", height=8, style="Modern.Treeview")
        for col, title, width in [("tip", "İşlem", 160), ("hayvan", "Hayvan", 160), ("tarih", "Tarih", 120), ("kalan", "Kalan", 100)]:
            self.dashboard_isler_tree.heading(col, text=title)
            self.dashboard_isler_tree.column(col, width=width, anchor="w")
        self.dashboard_isler_tree.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        sag_kolon = tk.Frame(alt_grid, bg=self.renkler["arkaplan"])
        sag_kolon.grid(row=0, column=1, sticky="nsew")
        sag_kolon.rowconfigure(1, weight=1)
        sag_kolon.columnconfigure(0, weight=1)
        self.themed_widgets.append((sag_kolon, 'arkaplan'))

        oncelik_card = self.modern_kart(sag_kolon, accent=self.renkler["uyari"])
        oncelik_card.grid(row=0, column=0, sticky="ew")
        tk.Label(oncelik_card, text="Öncelik Özeti", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=18, pady=(16, 4))
        self.dashboard_ciftlik_label = tk.Label(
            oncelik_card,
            text="-",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 9),
            justify="left",
            anchor="w",
        )
        self.dashboard_ciftlik_label.pack(anchor="w", fill="x", padx=18, pady=(0, 8))
        self.dashboard_risk_label = tk.Label(
            oncelik_card,
            text="-",
            bg=self.renkler["kart_ikincil"],
            fg=self.renkler["yazi_rengi"],
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=8,
            anchor="w",
            justify="left",
        )
        self.dashboard_risk_label.pack(fill="x", padx=18, pady=(0, 16))

        def oncelik_metni_sar(event=None):
            try:
                wrap = max(oncelik_card.winfo_width() - 42, 220)
                self.dashboard_ciftlik_label.configure(wraplength=wrap)
                self.dashboard_risk_label.configure(wraplength=wrap)
            except tk.TclError:
                pass

        oncelik_card.bind("<Configure>", oncelik_metni_sar)
        oncelik_card.after_idle(oncelik_metni_sar)

        son_card = self.modern_kart(alt_grid, accent=self.renkler["button_success_bg"])
        son_card.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        tk.Label(son_card, text="Son İşlemler", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=18, pady=(16, 8))
        self.dashboard_son_list = tk.Listbox(
            son_card,
            height=7,
            bg=self.renkler["input_bg"],
            fg=self.renkler["yazi_rengi"],
            selectbackground=self.renkler["button_primary_bg"],
            selectforeground="#FFFFFF",
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.renkler["kenarlik"],
            font=("Segoe UI", 9),
        )
        self.dashboard_son_list.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        def alt_yerlesim(event=None):
            try:
                dar = alt_grid.winfo_width() < 980
                isler_card.grid_forget()
                sag_kolon.grid_forget()
                son_card.grid_forget()
                if dar:
                    alt_grid.columnconfigure(0, weight=1)
                    alt_grid.columnconfigure(1, weight=0)
                    isler_card.grid(row=0, column=0, sticky="nsew")
                    sag_kolon.grid(row=1, column=0, sticky="ew", pady=(12, 0))
                    son_card.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
                else:
                    alt_grid.columnconfigure(0, weight=3)
                    alt_grid.columnconfigure(1, weight=2)
                    isler_card.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 12))
                    sag_kolon.grid(row=0, column=1, sticky="ew")
                    son_card.grid(row=1, column=1, sticky="nsew", pady=(12, 0))
            except tk.TclError:
                pass

        alt_grid.bind("<Configure>", alt_yerlesim)
        alt_grid.after_idle(alt_yerlesim)
        self.dashboard_guncelle()

    def dashboard_guncelle(self):
        if not hasattr(self, "dashboard_metric_labels"):
            return
        ozet = self.dashboard_ozeti_hesapla()
        for key, lbl in self.dashboard_metric_labels.items():
            if lbl.winfo_exists():
                lbl.config(text=str(ozet.get(key, 0)))
        if hasattr(self, "dashboard_isler_tree") and self.dashboard_isler_tree.winfo_exists():
            for item in self.dashboard_isler_tree.get_children():
                self.dashboard_isler_tree.delete(item)
            for kalan, tip, hayvan, tarih in ozet.get("yaklasan_isler", []):
                kalan_metin = "Bugün" if kalan == 0 else (f"{abs(kalan)} gün geçti" if kalan < 0 else f"{kalan} gün")
                self.dashboard_isler_tree.insert("", "end", values=(tip, hayvan, tarih, kalan_metin))
            if not ozet.get("yaklasan_isler"):
                self.dashboard_isler_tree.insert("", "end", values=("Bekleyen iş yok", "-", "-", "-"))
        if hasattr(self, "dashboard_son_list") and self.dashboard_son_list.winfo_exists():
            self.dashboard_son_list.delete(0, tk.END)
            for kayit in (self.islem_gecmisi[:8] if isinstance(self.islem_gecmisi, list) else []):
                self.dashboard_son_list.insert(tk.END, f"{kayit.get('zaman', '-')}  {kayit.get('aciklama', '-')}")
            if self.dashboard_son_list.size() == 0:
                self.dashboard_son_list.insert(tk.END, "Henüz işlem kaydı yok.")
        if hasattr(self, "dashboard_ciftlik_label") and self.dashboard_ciftlik_label.winfo_exists():
            kullanici = getattr(self, "api_kullanici", None) or {}
            ciftlik = (
                getattr(self, "admin_aktif_ciftlik_ad", None)
                or (kullanici.get("ciftlik") or {}).get("ad")
                or ("Tüm çiftlikler" if kullanici.get("rol") == "admin" else "Yerel veri")
            )
            senkron = self.bekleyen_senkron_sayisi() if hasattr(self, "bekleyen_senkron_sayisi") else 0
            api_durum = "Offline" if self.offline_modda_mi() else ("Online" if getattr(self, "api_modu", False) else "Yerel")
            self.dashboard_ciftlik_label.config(text=f"Çalışılan alan: {ciftlik}\nBağlantı: {api_durum} · Bekleyen senkron: {senkron}")
        if hasattr(self, "dashboard_risk_label") and self.dashboard_risk_label.winfo_exists():
            kritik = ozet.get("kritik", 0)
            bekleyen = ozet.get("bekleyen_kontrol", 0)
            dogum = ozet.get("yaklasan_dogum", 0)
            if kritik:
                self.dashboard_risk_label.config(
                    text=f"{kritik} kritik · Kontrol {bekleyen} · Doğum {dogum}",
                    fg=self.renkler["button_danger_bg"],
                    bg=self.renkler["kart_ikincil"],
                )
            else:
                self.dashboard_risk_label.config(
                    text=f"Kritik yok · Kontrol {bekleyen} · Doğum {dogum}",
                    fg=self.renkler["button_success_bg"],
                    bg=self.renkler["kart_ikincil"],
                )

    # #################################################################
    # ### GÜNCELLENMİŞ FONKSİYON: hayvan_kayit_sekmesi
    # #################################################################
    def hayvan_kayit_sekmesi(self):
        kayit_frame = ttk.Frame(self.notebook, style='TFrame')
        self.notebook.add(kayit_frame, text="Hayvan Kaydı")

        sayfa = self.kaydirilabilir_sayfa(kayit_frame, padx=24, pady=14)

        self._sayfa_basligi(
            sayfa,
            "Yeni Hayvan Kaydı",
            "Küpe, doğum ve sürü bilgilerini tek ekranda kaydedin."
        )

        govde = tk.Frame(sayfa, bg=self.renkler["arkaplan"])
        govde.pack(fill='x')
        govde.columnconfigure(0, weight=1)
        self.themed_widgets.append((govde, 'arkaplan'))

        main_card = self.modern_kart(govde, accent=self.renkler["button_success_bg"])
        main_card.grid(row=0, column=0, sticky='nsew', padx=(0, 18))

        header = tk.Frame(main_card, bg=self.renkler["kart_arkaplan"], pady=12)
        header.pack(fill='x', padx=24)
        self.themed_widgets.append((header, 'kart'))

        baslik_lbl = tk.Label(header, text="Hayvan Bilgileri",
                               font=('Segoe UI', 16, 'bold'),
                               bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"])
        baslik_lbl.pack(side='left')
        self.themed_widgets.append((baslik_lbl, 'label'))

        kaydet_btn = self.modern_buton(header, "HAYVANI KAYDET", self.hayvan_kaydet, purpose='success', width=22, small=True)
        self.hayvan_kaydet_btn = kaydet_btn
        kaydet_btn.pack(side='right')

        sep = tk.Frame(main_card, bg=self.renkler["kenarlik"], height=1)
        sep.pack(fill='x', padx=24)
        self.themed_widgets.append((sep, 'divider'))

        form_frame = tk.Frame(main_card, bg=self.renkler["kart_arkaplan"], padx=24, pady=14)
        form_frame.pack(fill='x')
        form_frame.columnconfigure((0, 1), weight=1)
        self.themed_widgets.append((form_frame, 'kart'))

        # --- Row 0 ---
        self.resmi_kupe_no_entry = self.modern_form_satir(form_frame, "Resmi Küpe No", ttk.Entry, row=0, col=0, font=('Segoe UI', 11), style='TEntry')
        self.ciftlik_kupe_no_entry = self.modern_form_satir(form_frame, "Çiftlik Küpe No", ttk.Entry, row=0, col=1, font=('Segoe UI', 11), style='TEntry')
        self.resmi_kupe_no_entry.master.grid_configure(pady=6)
        self.ciftlik_kupe_no_entry.master.grid_configure(pady=6)

        # --- Row 1 ---
        self.dogum_tarihi_entry = self.modern_form_satir(form_frame, "Doğum Tarihi (GG/AA/YYYY)", ttk.Entry, row=1, col=0, font=('Segoe UI', 11), style='TEntry')
        self.dogum_tarihi_entry = self.tarih_secici_ekle(self.dogum_tarihi_entry)
        self.cins_combo = self.modern_form_satir(form_frame, "Cinsi", ttk.Combobox, row=1, col=1, values=["Dişi Buzağı", "Erkek Buzağı", "Dana", "Düve", "Sağmal İnek", "Kuru İnek"], font=('Segoe UI', 11), style='TCombobox')
        self.dogum_tarihi_entry.master.grid_configure(pady=6)
        self.cins_combo.master.grid_configure(pady=6)

        # --- Row 2 ---
        self.irk_combo = self.modern_form_satir(form_frame, "Irk", ttk.Combobox, row=2, col=0, values=self.hayvan_irk_secenekleri(), font=('Segoe UI', 11), style='TCombobox')
        self.anne_kupe_entry = self.modern_form_satir(form_frame, "Anne Resmi Küpe No", ttk.Entry, row=2, col=1, font=('Segoe UI', 11), style='TEntry')
        self.irk_combo.master.grid_configure(pady=6)
        self.anne_kupe_entry.master.grid_configure(pady=6)

        foto_container = tk.Frame(form_frame, bg=self.renkler["kart_arkaplan"])
        foto_container.grid(row=3, column=0, columnspan=2, sticky='ew', padx=12, pady=6)
        foto_container.columnconfigure(0, weight=1)
        self.themed_widgets.append((foto_container, 'kart'))
        tk.Label(
            foto_container,
            text="FOTOĞRAF",
            font=('Segoe UI', 9, 'bold'),
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["muted"],
        ).pack(anchor='w', padx=2, pady=(0, 4))
        foto_panel = tk.Frame(
            foto_container,
            bg=self.renkler["kart_ikincil"],
            highlightthickness=1,
            highlightbackground=self.renkler["kenarlik"],
            padx=10,
            pady=8,
        )
        foto_panel.pack(fill="x")
        self.themed_widgets.append((foto_panel, 'soft_panel'))
        foto_preview_grid = tk.Frame(foto_panel, bg=self.renkler["kart_ikincil"])
        foto_preview_grid.pack(side="left", fill="both", expand=True)
        foto_preview_grid.columnconfigure((0, 1, 2), weight=1)
        self.themed_widgets.append((foto_preview_grid, 'soft_panel'))
        self.yeni_hayvan_foto_previews = []
        for idx in range(3):
            preview = tk.Canvas(
                foto_preview_grid,
                width=126,
                height=68,
                bg=self.renkler["input_bg"],
                bd=0,
                highlightthickness=1,
                highlightbackground=self.renkler["kenarlik"],
            )
            preview.grid(row=0, column=idx, sticky="nsew", padx=(0 if idx == 0 else 6, 0))
            self.yeni_hayvan_foto_previews.append(preview)
        self.yeni_hayvan_foto_sayac_label = tk.Label(
            foto_preview_grid,
            text="0/3 fotoğraf",
            bg=self.renkler["kart_ikincil"],
            fg=self.renkler["muted"],
            font=('Segoe UI', 8, 'bold'),
        )
        self.yeni_hayvan_foto_sayac_label.grid(row=1, column=0, columnspan=3, sticky="w", pady=(7, 0))
        foto_btnler = tk.Frame(foto_panel, bg=self.renkler["kart_ikincil"])
        foto_btnler.pack(side="right", padx=(10, 0))
        self.themed_widgets.append((foto_btnler, 'soft_panel'))

        self.yeni_hayvan_foto_datas = []

        def yeni_foto_onizleme_guncelle():
            fotograflar = list(getattr(self, "yeni_hayvan_foto_datas", []) or [])[:3]
            self.yeni_hayvan_foto_datas = fotograflar
            self.yeni_hayvan_foto_data = fotograflar[0] if fotograflar else None
            for idx, preview in enumerate(getattr(self, "yeni_hayvan_foto_previews", [])):
                foto = fotograflar[idx] if idx < len(fotograflar) else None
                self.foto_slot_canvas_ciz(
                    preview,
                    foto,
                    idx + 1,
                    remove_callback=lambda i=idx: yeni_foto_kaldir_index(i),
                    max_size=(126, 68),
                )
            if hasattr(self, "yeni_hayvan_foto_sayac_label"):
                self.yeni_hayvan_foto_sayac_label.config(text=f"{len(fotograflar)}/3 fotoğraf")

        self.yeni_hayvan_foto_onizleme_guncelle = yeni_foto_onizleme_guncelle

        def yeni_foto_kaldir_index(index):
            fotograflar = list(getattr(self, "yeni_hayvan_foto_datas", []) or [])
            if 0 <= index < len(fotograflar):
                fotograflar.pop(index)
                self.yeni_hayvan_foto_datas = fotograflar
                yeni_foto_onizleme_guncelle()

        def yeni_foto_sec():
            mevcut_fotograflar = list(getattr(self, "yeni_hayvan_foto_datas", []) or [])[:3]
            if len(mevcut_fotograflar) >= 3:
                return messagebox.showwarning("Fotoğraf", "Yeni hayvan kaydında en fazla 3 fotoğraf eklenebilir.", parent=self.root)
            dosyalar = filedialog.askopenfilenames(
                title="Hayvan fotoğrafları seç",
                parent=self.root,
                filetypes=[("Görsel dosyaları", "*.jpg *.jpeg *.png *.webp *.bmp"), ("Tüm dosyalar", "*.*")]
            )
            if not dosyalar:
                return
            try:
                kalan = 3 - len(mevcut_fotograflar)
                for dosya in list(dosyalar)[:kalan]:
                    mevcut_fotograflar.append(self.foto_data_olustur(dosya))
                self.yeni_hayvan_foto_datas = mevcut_fotograflar[:3]
                yeni_foto_onizleme_guncelle()
                if len(dosyalar) > kalan:
                    messagebox.showwarning("Fotoğraf", "En fazla 3 fotoğraf eklenebilir; fazla seçimler alınmadı.", parent=self.root)
            except Exception as e:
                messagebox.showerror("Fotoğraf", f"Fotoğraf eklenemedi:\n{e}", parent=self.root)

        self.modern_buton(foto_btnler, "Fotoğraf Ekle", yeni_foto_sec, purpose='primary', width=12, small=True).pack()
        yeni_foto_onizleme_guncelle()

        # --- Row 4 (Dinamik Gizli Alanlar) ---
        self.laktasyon_container = tk.Frame(form_frame, bg=self.renkler["kart_arkaplan"])
        self.laktasyon_container.grid(row=4, column=0, columnspan=2, sticky='ew')
        self.laktasyon_container.columnconfigure((0, 1), weight=1)
        self.themed_widgets.append((self.laktasyon_container, 'kart'))

        self.laktasyon_no_entry = self.modern_form_satir(self.laktasyon_container, "Laktasyon Numarası", ttk.Entry, row=0, col=0, font=('Segoe UI', 11), style='TEntry')
        self.son_dogum_tarihi_entry = self.modern_form_satir(self.laktasyon_container, "Son Doğum Tarihi", ttk.Entry, row=0, col=1, font=('Segoe UI', 11), style='TEntry')
        self.son_dogum_tarihi_entry = self.tarih_secici_ekle(self.son_dogum_tarihi_entry)

        self.laktasyon_container.grid_remove() # Başlangıçta gizli

        self.cins_combo.bind('<<ComboboxSelected>>', self._on_cins_change)

        ozet_card = self.modern_kart(govde)
        ozet_card.grid(row=0, column=1, sticky='nsew')
        ozet_card.configure(width=280)
        ozet_card.grid_propagate(False)
        tk.Label(
            ozet_card,
            text="Sürü Özeti",
            font=('Segoe UI', 15, 'bold'),
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["yazi_rengi"],
        ).pack(anchor='w', padx=20, pady=(20, 4))
        tk.Label(
            ozet_card,
            text="Seçili çiftlikteki anlık durum",
            font=('Segoe UI', 9),
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["muted"],
        ).pack(anchor='w', padx=20, pady=(0, 14))

        def ozet_satir(anahtar, baslik, renk):
            satir = tk.Frame(ozet_card, bg=self.renkler["kart_ikincil"], padx=14, pady=12,
                             highlightthickness=1, highlightbackground=self.renkler["kenarlik"])
            satir.pack(fill='x', padx=20, pady=6)
            self.themed_widgets.append((satir, 'soft_panel'))
            tk.Label(satir, text=baslik, font=('Segoe UI', 9, 'bold'),
                     bg=self.renkler["kart_ikincil"], fg=self.renkler["muted"]).pack(anchor='w')
            deger = tk.Label(satir, text="0", font=('Segoe UI', 22, 'bold'),
                             bg=self.renkler["kart_ikincil"], fg=renk)
            deger.pack(anchor='w')
            setattr(self, f"kayit_ozet_{anahtar}_label", deger)

        ozet_satir("aktif", "AKTİF HAYVAN", self.renkler["button_success_bg"])
        ozet_satir("gebe", "GEBE", self.renkler["button_primary_bg"])
        ozet_satir("arsivli", "ARŞİV", self.renkler["muted"])
        self.header_ozet_guncelle()

    # #################################################################
    # ### YENİ FONKSİYON: _on_cins_change
    # #################################################################
    def _on_cins_change(self, event=None):
        """Cins combobox'ı değiştiğinde laktasyon alanlarını gösterir/gizler."""
        secilen_cins = self.cins_combo.get()
        if secilen_cins in ["Sağmal İnek", "Kuru İnek"]:
            self.laktasyon_container.grid()
        else:
            self.laktasyon_container.grid_remove()

    def tohumlama_sekmesi(self):
        tohumlama_frame = ttk.Frame(self.notebook, style='TFrame')
        self.notebook.add(tohumlama_frame, text="Tohumlama")

        sayfa = self.kaydirilabilir_sayfa(tohumlama_frame, padx=28, pady=22)

        self._sayfa_basligi(
            sayfa,
            "Tohumlama",
            "Yeni tohumlama kaydı ve gebelik sonucu işlemleri."
        )

        main_card = self.modern_kart(sayfa, accent=self.renkler["button_primary_bg"])
        main_card.pack(fill='x')

        #  Bölüm Başlığı 
        header = tk.Frame(main_card, bg=self.renkler["kart_arkaplan"], pady=18)
        header.pack(fill='x', padx=28)
        self.themed_widgets.append((header, 'kart'))

        baslik_lbl = tk.Label(header, text="İşlem Bilgileri",
                               font=('Segoe UI', 16, 'bold'),
                               bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"])
        baslik_lbl.pack(side='left')
        self.themed_widgets.append((baslik_lbl, 'label'))

        sep = tk.Frame(main_card, bg=self.renkler["kenarlik"], height=1)
        sep.pack(fill='x', padx=28)
        self.themed_widgets.append((sep, 'divider'))

        # Form Container
        form_frame = tk.Frame(main_card, bg=self.renkler["kart_arkaplan"], padx=28, pady=22)
        form_frame.pack(fill='x')
        form_frame.columnconfigure((0, 1), weight=1)
        self.themed_widgets.append((form_frame, 'kart'))

        # --- Row 0 ---
        self.tohumlama_hayvan_combo = self.modern_form_satir(form_frame, "Hayvan Küpe No", ttk.Combobox, row=0, col=0, font=('Segoe UI', 11), style='TCombobox')
        self.tohumlama_hayvan_combo.bind('<KeyRelease>', self.hayvan_ara)
        self.tohumlama_hayvanlarini_guncelle()
        
        self.tohumlama_sekli_combo = self.modern_form_satir(form_frame, "Tohumlama Şekli", ttk.Combobox, row=0, col=1, values=["Suni", "Boğa"], font=('Segoe UI', 11), style='TCombobox')
        self.tohumlama_sekli_combo.bind('<<ComboboxSelected>>', self.tohumlama_sekli_degisti)

        # --- Row 1 ---
        self.suni_container = tk.Frame(form_frame, bg=self.renkler["kart_arkaplan"])
        self.suni_container.grid(row=1, column=0, sticky='ew', padx=0, pady=0)
        self.suni_container.columnconfigure(0, weight=1)
        self.themed_widgets.append((self.suni_container, 'kart'))
        self.suni_entry = self.modern_form_satir(self.suni_container, "Suni Tohumlama İsmi", ttk.Entry, row=0, col=0, font=('Segoe UI', 11), style='TEntry')
        
        self.tohumlama_tarih_entry = self.modern_form_satir(form_frame, "Tohumlama Tarihi (GG/AA/YYYY)", ttk.Entry, row=1, col=1, font=('Segoe UI', 11), style='TEntry')
        self.tohumlama_tarih_entry.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.tohumlama_tarih_entry = self.tarih_secici_ekle(self.tohumlama_tarih_entry)

        # Buton Container
        btn_frame = tk.Frame(form_frame, bg=self.renkler["kart_arkaplan"])
        btn_frame.grid(row=2, column=0, columnspan=2, pady=(28, 4), sticky='e')
        self.themed_widgets.append((btn_frame, 'kart'))

        self.modern_buton(btn_frame, "TOHUMLAMA KAYDET", self.tohumlama_kaydet, purpose='primary', width=22).pack(side='left', padx=(0, 10))
        sonuc_notu = tk.Label(
            btn_frame,
            text="Gebelik sonucu hayvan profilindeki 'Tohumlamayı Sonuçla' butonundan işlenir.",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["muted"],
            font=('Segoe UI', 9, 'italic'),
        )
        sonuc_notu.pack(side='left', padx=(10, 0))
        self.themed_widgets.append((sonuc_notu, 'muted_label'))


    def hayvan_listesi_sekmesi(self):
        liste_frame = ttk.Frame(self.notebook, style='TFrame')
        self.notebook.add(liste_frame, text="Hayvan Listesi")

        #  TOOLBAR
        toolbar = tk.Frame(
            liste_frame,
            bg=self.renkler["kart_arkaplan"],
            highlightthickness=1,
            highlightbackground=self.renkler["kenarlik"],
            bd=0
        )
        toolbar.pack(fill='x', padx=12, pady=(12, 0))
        toolbar.columnconfigure(1, weight=1)
        self.themed_widgets.append((toolbar, 'kart'))

        filtre_grup = tk.Frame(toolbar, bg=self.renkler["kart_arkaplan"])
        filtre_grup.grid(row=0, column=0, sticky="w", padx=(16, 10), pady=10)
        self.themed_widgets.append((filtre_grup, 'kart'))
        filtre_lbl = tk.Label(filtre_grup, text="FİLTRE", font=('Segoe UI', 8, 'bold'),
                              bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"])
        filtre_lbl.pack(anchor='w', pady=(0, 4))
        self.filtre_combo = ttk.Combobox(filtre_grup,
            values=["Aktif", "Tümü", "Dişi Buzağı", "Erkek Buzağı", "Dana",
                    "Düve", "Sağmal İnek", "Kuru İnek", "Gebe", "Ölü", "Kesildi", "Satıldı", "Arşivli"],
            width=16, font=('Segoe UI', 11), state="readonly", style='TCombobox')
        self.filtre_combo.set("Aktif")
        self.filtre_combo.pack(anchor='w')
        self.filtre_combo.bind('<<ComboboxSelected>>', self.filtre_degisti)
        self.themed_widgets.append((filtre_lbl, 'muted_label'))

        ara_grup = tk.Frame(toolbar, bg=self.renkler["kart_arkaplan"])
        ara_grup.grid(row=0, column=1, sticky="ew", padx=10, pady=10)
        ara_grup.columnconfigure(0, weight=1)
        self.themed_widgets.append((ara_grup, 'kart'))
        ara_lbl = tk.Label(ara_grup, text="ARA - KUPE / SON 6 / KISALTMA", font=('Segoe UI', 8, 'bold'),
                           bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"])
        ara_lbl.grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.arama_entry = ttk.Entry(ara_grup, font=('Segoe UI', 11), style='TEntry')
        self.arama_entry.grid(row=1, column=0, sticky="ew")
        self.arama_entry.bind('<KeyRelease>', self.arama_degisti)
        self.modern_buton(
            ara_grup,
            "Ortalama Yaş Hesapla",
            self.secili_hayvan_yas_ortalamasi,
            purpose='primary',
            small=True,
        ).grid(row=1, column=1, sticky="e", padx=(10, 0))
        self.themed_widgets.append((ara_lbl, 'muted_label'))

        sag = tk.Frame(toolbar, bg=self.renkler["kart_arkaplan"])
        sag.grid(row=0, column=2, sticky="e", padx=(10, 16), pady=10)
        self.themed_widgets.append((sag, 'kart'))
        self.responsive_buton_grubu(
            sag,
            [
                ("Temizle", self.filtreleri_temizle, "danger"),
                ("Yenile", self.api_verilerini_yenile, "success"),
            ],
            align="left",
        )

        def toolbar_yerlesim(event=None):
            try:
                genislik = toolbar.winfo_width()
                filtre_grup.grid_forget()
                ara_grup.grid_forget()
                sag.grid_forget()
                if genislik < 640:
                    toolbar.columnconfigure(0, weight=1)
                    toolbar.columnconfigure(1, weight=1)
                    toolbar.columnconfigure(2, weight=1)
                    filtre_grup.grid(row=0, column=0, columnspan=3, sticky="ew", padx=16, pady=(10, 4))
                    ara_grup.grid(row=1, column=0, columnspan=3, sticky="ew", padx=16, pady=4)
                    sag.grid(row=2, column=0, columnspan=3, sticky="ew", padx=16, pady=(4, 10))
                elif genislik < 1320:
                    toolbar.columnconfigure(0, weight=0)
                    toolbar.columnconfigure(1, weight=1)
                    toolbar.columnconfigure(2, weight=0)
                    filtre_grup.grid(row=0, column=0, sticky="w", padx=(16, 10), pady=(10, 4))
                    ara_grup.grid(row=0, column=1, sticky="ew", padx=10, pady=(10, 4))
                    sag.grid(row=1, column=0, columnspan=3, sticky="ew", padx=16, pady=(4, 10))
                else:
                    toolbar.columnconfigure(0, weight=0)
                    toolbar.columnconfigure(1, weight=1)
                    toolbar.columnconfigure(2, weight=0)
                    filtre_grup.grid(row=0, column=0, sticky="w", padx=(16, 10), pady=10)
                    ara_grup.grid(row=0, column=1, sticky="ew", padx=10, pady=10)
                    sag.grid(row=0, column=2, sticky="e", padx=(10, 16), pady=10)
            except tk.TclError:
                pass

        toolbar.bind("<Configure>", toolbar_yerlesim)
        self._track_after(self.root, 80, toolbar_yerlesim)

        #  TABLO 
        liste_kart = self.modern_kart(liste_frame)
        liste_kart.pack(fill='both', expand=True, padx=12, pady=12)

        tree_frame = tk.Frame(liste_kart, bg=self.renkler["kart_arkaplan"])
        tree_frame.pack(fill='both', expand=True)
        self.themed_widgets.append((tree_frame, 'kart'))

        columns = ('ID', 'Seç', 'Resmi Küpe', 'Çiftlik Küpesi', 'Irk', 'Yaş', 'Cinsi', 'Durum', 'Son Tohumlama', 'Doğum Tahmini', 'Sağım Günü', 'Uyarılar')
        self.hayvan_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', style='Modern.Treeview')
        col_widths = {
            'ID': 0, 'Seç': 58, 'Resmi Küpe': 145, 'Çiftlik Küpesi': 120, 'Irk': 110, 'Yaş': 90, 'Cinsi': 140, 'Durum': 130,
            'Son Tohumlama': 145, 'Doğum Tahmini': 145, 'Sağım Günü': 120, 'Uyarılar': 240
        }
        
        self.hayvan_tree.heading('ID', text='ID')
        self.hayvan_tree.column('ID', width=0, stretch=tk.NO) # Hide ID column
        for col in columns[1:]:
            self.hayvan_tree.heading(col, text=col)
            min_width = 46 if col == 'Seç' else 80
            self.hayvan_tree.column(col, width=col_widths.get(col, 120), anchor='center', minwidth=min_width, stretch=(col != 'Seç'))

        sb_v = ttk.Scrollbar(tree_frame, orient='vertical', command=self.hayvan_tree.yview)
        sb_h = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.hayvan_tree.xview)
        self.hayvan_tree.configure(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)
        self.hayvan_tree.grid(row=0, column=0, sticky='nsew')
        sb_v.grid(row=0, column=1, sticky='ns')
        sb_h.grid(row=1, column=0, sticky='ew')
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.hayvan_tree.bind('<Double-Button-1>', self.hayvan_detay_ac)
        self.hayvan_tree.bind('<Button-1>', self.hayvan_secim_tiklandi, add='+')
        self.hayvan_tree.bind('<Button-3>', self.sag_tik_menu)

    def hayvan_secim_tiklandi(self, event):
        tree = getattr(self, "hayvan_tree", None)
        if tree is None:
            return
        try:
            if tree.identify("region", event.x, event.y) != "cell":
                return
            if tree.identify_column(event.x) != "#2":
                return
            satir = tree.identify_row(event.y)
            if not satir:
                return "break"
            degerler = list(tree.item(satir, "values") or [])
            if not degerler:
                return "break"
            hayvan_id = str(degerler[0])
            secimler = getattr(self, "hayvan_secimleri", set())
            if hayvan_id in secimler:
                secimler.remove(hayvan_id)
                degerler[1] = "☐"
            else:
                secimler.add(hayvan_id)
                degerler[1] = "☑"
            self.hayvan_secimleri = secimler
            tree.item(satir, values=tuple(degerler))
            return "break"
        except tk.TclError:
            return

    def hayvan_secimlerini_temizle(self, sadece_gorunen_idler=None):
        self.hayvan_secimleri = set()
        tree = getattr(self, "hayvan_tree", None)
        if tree is None:
            return
        gorunen = {str(x) for x in sadece_gorunen_idler} if sadece_gorunen_idler is not None else None
        try:
            for item in tree.get_children():
                degerler = list(tree.item(item, "values") or [])
                if len(degerler) < 2:
                    continue
                if gorunen is not None and str(degerler[0]) not in gorunen:
                    continue
                degerler[1] = "\u2610"
                tree.item(item, values=tuple(degerler))
        except tk.TclError:
            pass

    def secili_hayvan_yas_ortalamasi(self):
        tree = getattr(self, "hayvan_tree", None)
        if tree is None:
            return
        secili_idler = set(getattr(self, "hayvan_secimleri", set()))
        gorunen_idler = set()
        try:
            for item in tree.get_children():
                degerler = tree.item(item, "values") or []
                if degerler:
                    gorunen_idler.add(str(degerler[0]))
        except tk.TclError:
            gorunen_idler = set()
        hesaplanacak = [h_id for h_id in secili_idler if h_id in gorunen_idler and h_id in self.hayvanlar]
        if not hesaplanacak:
            messagebox.showwarning("Ortalama Yaş", "Yaş ortalaması için listeden en az bir hayvan seçin.", parent=self.root)
            return
        yaslar = []
        for h_id in hesaplanacak:
            try:
                yaslar.append(max(int(self.hayvanlar[h_id].get("yas_gun", 0) or 0), 0))
            except (ValueError, TypeError):
                pass
        if not yaslar:
            messagebox.showwarning("Ortalama Yaş", "Seçilen hayvanların yaş bilgisi hesaplanamadı.", parent=self.root)
            return
        ortalama = sum(yaslar) / len(yaslar)
        yil = int(ortalama // 365)
        ay = int((ortalama % 365) // 30)
        messagebox.showinfo(
            "Ortalama Yaş",
            f"Seçilen {len(yaslar)} hayvanın yaş ortalaması:\n\n{yil} yıl {ay} ay\n({ortalama:.0f} gün)",
            parent=self.root,
        )
        self.hayvan_secimlerini_temizle(gorunen_idler)


    def raporlama_sekmesi(self):
        rapor_sekme_frame = ttk.Frame(self.notebook, style='TFrame')
        self.notebook.add(rapor_sekme_frame, text="Raporlama")

        self.rapor_scroll_sayfa = self.kaydirilabilir_sayfa(rapor_sekme_frame, padx=16, pady=16)

        main_card = self.modern_kart(self.rapor_scroll_sayfa)
        main_card.pack(fill='both', expand=True)

        header = tk.Frame(main_card, bg=self.renkler["kart_arkaplan"], pady=16)
        header.pack(fill='x', padx=24)
        header.columnconfigure(0, weight=1)
        self.themed_widgets.append((header, 'kart'))

        baslik_alan = tk.Frame(header, bg=self.renkler["kart_arkaplan"])
        baslik_alan.grid(row=0, column=0, sticky="w")
        self.themed_widgets.append((baslik_alan, 'kart'))
        rapor_baslik_label = tk.Label(baslik_alan, text="Sürü Genel Durum Raporu", font=('Segoe UI', 18, 'bold'), bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"])
        rapor_baslik_label.pack(anchor='w')
        self.themed_widgets.append((rapor_baslik_label, 'label'))
        alt_label = tk.Label(
            baslik_alan,
            text="Sürü durumunu, uyarıları ve dağılımları tek ekranda izleyin.",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["muted"],
            font=('Segoe UI', 9),
        )
        alt_label.pack(anchor='w', pady=(4, 0))
        self.themed_widgets.append((alt_label, 'muted_label'))

        aksiyonlar = tk.Frame(header, bg=self.renkler["kart_arkaplan"])
        aksiyonlar.grid(row=0, column=1, sticky="e", padx=(12, 0))
        self.themed_widgets.append((aksiyonlar, 'kart'))

        rapor_aksiyonlar = [
            ("Raporları Yenile", self.raporlari_guncelle, 'primary'),
            ("Özet Excel", self.ozet_rapor_excel_aktar, 'success'),
            ("Özet PDF", self.ozet_rapor_pdf_aktar, 'default'),
        ]
        for metin, komut, amac in rapor_aksiyonlar:
            self.modern_buton(aksiyonlar, metin, komut, purpose=amac, small=True).pack(side="left", padx=(0, 6))

        def rapor_header_yerlestir(event=None):
            try:
                aksiyonlar.grid(row=1, column=0, sticky="w", padx=0, pady=(12, 0))
            except tk.TclError:
                pass

        header.bind("<Configure>", rapor_header_yerlestir)
        header.after_idle(rapor_header_yerlestir)

        cizgi = tk.Frame(main_card, bg=self.renkler["kenarlik"], height=1)
        cizgi.pack(fill='x', padx=24, pady=(0, 10))
        self.themed_widgets.append((cizgi, 'divider'))

        self.rapor_frame = tk.Frame(main_card, bg=self.renkler["kart_arkaplan"])
        self.rapor_frame.pack(fill='both', expand=True, padx=15, pady=15)
        self.themed_widgets.append((self.rapor_frame, 'kart'))

    def ozet_rapor_satirlari(self):
        ozet = self.dashboard_ozeti_hesapla()
        kullanici = (getattr(self, "api_kullanici", None) or {}).get("kullanici_adi") or "-"
        ciftlik = (
            getattr(self, "admin_aktif_ciftlik_ad", None)
            or ((getattr(self, "api_kullanici", None) or {}).get("ciftlik") or {}).get("ad")
            or "Tüm çiftlikler"
        )
        satirlar = [
            ("Çiftlik", ciftlik, ""),
            ("Kullanıcı", kullanici, ""),
            ("Aktif hayvan", ozet["aktif"], ""),
            ("Gebe", ozet["gebe"], ""),
            ("Arşiv", ozet["arsiv"], ""),
            ("Gebelik kontrol", ozet["bekleyen_kontrol"], "7 gün içinde veya gecikmiş"),
            ("Yaklaşan doğum", ozet["yaklasan_dogum"], "30 gün içinde"),
            ("Kritik uyarı", ozet["kritik"], ""),
        ]
        for kalan, tip, hayvan, tarih in ozet.get("yaklasan_isler", []):
            kalan_metin = "Bugün" if kalan == 0 else (f"{abs(kalan)} gün geçti" if kalan < 0 else f"{kalan} gün")
            satirlar.append((f"Yaklaşan: {tip}", hayvan, f"{tarih} / {kalan_metin}"))
        return satirlar

    def ozet_rapor_excel_aktar(self):
        dosya_yolu = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel Dosyası", "*.xlsx")],
            title="Özet raporu Excel olarak kaydet"
        )
        if not dosya_yolu:
            return
        try:
            export_rows_to_excel(
                dosya_yolu,
                "ALP Ziraat Sürü Özet Raporu",
                ["Başlık", "Değer", "Not"],
                self.ozet_rapor_satirlari(),
                subtitle="Sürü durumu, uyarılar ve yaklaşan işler özeti",
                metadata=self.export_metadata_olustur("Sürü özet raporu"),
                sheet_name="Sürü Özeti",
            )
            messagebox.showinfo("Rapor", f"Excel raporu kaydedildi:\n{dosya_yolu}", parent=self.root)
        except Exception as e:
            messagebox.showerror("Rapor", f"Excel raporu oluşturulamadı:\n{e}", parent=self.root)

    def ozet_rapor_pdf_aktar(self):
        dosya_yolu = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Dosyası", "*.pdf")],
            title="Özet raporu PDF olarak kaydet"
        )
        if not dosya_yolu:
            return
        try:
            export_rows_to_pdf(
                dosya_yolu,
                "ALP Ziraat Sürü Özet Raporu",
                ["Başlık", "Değer", "Not"],
                self.ozet_rapor_satirlari(),
                subtitle="Sürü durumu, uyarılar ve yaklaşan işler özeti",
                metadata=self.export_metadata_olustur("Sürü özet raporu"),
                sheet_name="Sürü Özeti",
            )
            messagebox.showinfo("Rapor", f"PDF raporu kaydedildi:\n{dosya_yolu}", parent=self.root)
        except Exception as e:
            messagebox.showerror("Rapor", f"PDF raporu oluşturulamadı:\n{e}", parent=self.root)

    def _rapor_responsive_grid(self, parent, widgets, min_width=300, max_cols=3, gap=12):
        def duzenle(event=None):
            try:
                width = max(parent.winfo_width(), 1)
                cols = 1
                for aday in range(min(max_cols, len(widgets)), 0, -1):
                    if aday * min_width + (aday - 1) * gap <= width:
                        cols = aday
                        break
                for idx, widget in enumerate(widgets):
                    col = idx % cols
                    row = idx // cols
                    widget.grid(
                        row=row,
                        column=col,
                        sticky="nsew",
                        padx=(0 if col == 0 else gap, 0),
                        pady=(0, gap),
                    )
                for col in range(max_cols):
                    parent.grid_columnconfigure(col, weight=1 if col < cols else 0, uniform="rapor_cols" if col < cols else "")
            except tk.TclError:
                pass

        parent.bind("<Configure>", duzenle)
        parent.after_idle(duzenle)

    def _rapor_ozet_karti(self, parent, baslik, deger, renk, alt_metin=""):
        kart = tk.Frame(
            parent,
            bg=self.renkler["kart_ikincil"],
            padx=16,
            pady=14,
            highlightthickness=1,
            highlightbackground=self.renkler["kenarlik"],
        )
        self.themed_widgets.append((kart, 'soft_panel'))
        tk.Label(
            kart,
            text=baslik,
            bg=self.renkler["kart_ikincil"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")
        tk.Label(
            kart,
            text=str(deger),
            bg=self.renkler["kart_ikincil"],
            fg=renk,
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor="w", pady=(6, 0))
        if alt_metin:
            tk.Label(
                kart,
                text=alt_metin,
                bg=self.renkler["kart_ikincil"],
                fg=self.renkler["muted"],
                font=("Segoe UI", 8),
            ).pack(anchor="w", pady=(4, 0))
        return kart

    def raporlari_guncelle(self):
        for widget in self.rapor_frame.winfo_children():
            widget.destroy()

        aktif_hayvanlar = {
            kupe: h for kupe, h in self.hayvanlar.items()
            if not h.get('arsivli', False)
            and not h.get('olu', False)
            and not h.get('kesildi', False)
            and not h.get('satildi', False)
        }

        cinsiyet_dagilimi = {'Dişi': 0, 'Erkek': 0}
        cins_dagilimi = {} 
        ozel_durum_dagilimi = {'Gebe': 0, 'Ölü': 0, 'Kesildi': 0, 'Satıldı': 0}
        erkek_cinsler = ["Erkek Buzağı", "Dana"]
        
        for hayvan in aktif_hayvanlar.values():
            cins = hayvan.get('cins', 'Bilinmiyor')

            if cins in erkek_cinsler:
                cinsiyet_dagilimi['Erkek'] += 1
            else:
                cinsiyet_dagilimi['Dişi'] += 1
            
            cins_dagilimi[cins] = cins_dagilimi.get(cins, 0) + 1
            if hayvan.get('gebe_mi', False):
                ozel_durum_dagilimi['Gebe'] += 1

        for hayvan in self.hayvanlar.values():
            if hayvan.get('olu', False):
                ozel_durum_dagilimi['Ölü'] += 1
            if hayvan.get('kesildi', False):
                ozel_durum_dagilimi['Kesildi'] += 1
            if hayvan.get('satildi', False):
                ozel_durum_dagilimi['Satıldı'] += 1

        arsivli_sayi = sum(1 for h in self.hayvanlar.values() if h.get('arsivli', False))
        ozet = self.dashboard_ozeti_hesapla()

        content = tk.Frame(self.rapor_frame, bg=self.renkler["kart_arkaplan"])
        content.pack(fill="both", expand=True, padx=8, pady=8)
        self.themed_widgets.append((content, 'kart'))

        toplam_hayvan_label = tk.Label(
            content,
            text=f"Aktif Hayvan: {len(aktif_hayvanlar)}  |  Arşivli: {arsivli_sayi}",
            font=('Segoe UI', 15, 'bold'),
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["yazi_rengi"],
        )
        toplam_hayvan_label.pack(anchor="w", pady=(0, 14))
        self.themed_widgets.append((toplam_hayvan_label, 'label'))

        ozet_frame = tk.Frame(content, bg=self.renkler["kart_arkaplan"])
        ozet_frame.pack(fill="x", pady=(0, 14))
        self.themed_widgets.append((ozet_frame, 'kart'))
        ozet_kartlari = [
            self._rapor_ozet_karti(ozet_frame, "Aktif hayvan", len(aktif_hayvanlar), self.renkler["button_primary_bg"], "Sürüde görünen kayıt"),
            self._rapor_ozet_karti(ozet_frame, "Gebelik kontrol", ozet["bekleyen_kontrol"], self.renkler["uyari"], "7 gün içinde veya geçmiş"),
            self._rapor_ozet_karti(ozet_frame, "Yaklaşan doğum", ozet["yaklasan_dogum"], self.renkler["button_warning_bg"], "30 gün içinde"),
            self._rapor_ozet_karti(ozet_frame, "Kritik uyarı", ozet["kritik"], self.renkler["button_danger_bg"], "Öncelikli takip"),
        ]
        self._rapor_responsive_grid(ozet_frame, ozet_kartlari, min_width=210, max_cols=4)

        charts_frame = tk.Frame(content, bg=self.renkler["kart_arkaplan"])
        charts_frame.pack(fill="both", expand=True, pady=(2, 0))
        self.themed_widgets.append((charts_frame, 'kart'))
        chart_cards = [
            self.create_pie_chart(charts_frame, cinsiyet_dagilimi, "Cinsiyet Dağılımı", 0, row=0),
            self.create_pie_chart(charts_frame, cins_dagilimi, "Sürüdeki Hayvan Tipleri", 1, row=0),
            self.create_pie_chart(charts_frame, ozel_durum_dagilimi, "Özel Durumlar", 2, row=0),
        ]
        self._rapor_responsive_grid(charts_frame, chart_cards, min_width=430, max_cols=3)


    def create_pie_chart(self, parent, data, title, column, row=1):
        filtered_data = {label: value for label, value in data.items() if value > 0}
        
        labels = list(filtered_data.keys())
        sizes = list(filtered_data.values())

        kart = tk.Frame(
            parent,
            bg=self.renkler["kart_ikincil"],
            padx=16,
            pady=14,
            highlightthickness=1,
            highlightbackground=self.renkler["kenarlik"],
        )
        self.themed_widgets.append((kart, 'soft_panel'))
        tk.Label(
            kart,
            text=title,
            bg=self.renkler["kart_ikincil"],
            fg=self.renkler["yazi_rengi"],
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")

        govde = tk.Frame(kart, bg=self.renkler["kart_ikincil"])
        govde.pack(fill="both", expand=True, pady=(12, 0))
        govde.grid_rowconfigure(0, weight=1)
        govde.grid_columnconfigure(0, weight=1, minsize=230)
        govde.grid_columnconfigure(1, weight=0, minsize=172)
        self.themed_widgets.append((govde, 'soft_panel'))
        canvas = tk.Canvas(govde, height=210, bg=self.renkler["kart_ikincil"], bd=0, highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        legend = tk.Frame(govde, bg=self.renkler["kart_ikincil"], width=172)
        legend.grid(row=0, column=1, sticky="nsw", padx=(12, 0))
        legend.grid_propagate(False)
        self.themed_widgets.append((legend, 'soft_panel'))

        renkler = [
            self.renkler["button_primary_bg"],
            self.renkler["button_success_bg"],
            self.renkler["button_warning_bg"],
            self.renkler["button_danger_bg"],
            self.renkler["muted"],
            "#8B5CF6",
        ]

        if labels:
            for idx, (label, value) in enumerate(zip(labels, sizes)):
                satir = tk.Frame(legend, bg=self.renkler["kart_ikincil"])
                satir.pack(anchor="w", fill="x", pady=3)
                renk = renkler[idx % len(renkler)]
                tk.Frame(satir, bg=renk, width=10, height=10).pack(side="left", padx=(0, 7))
                tk.Label(
                    satir,
                    text=f"{label} ({value})",
                    bg=self.renkler["kart_ikincil"],
                    fg=self.renkler["muted"],
                    font=("Segoe UI", 9),
                    wraplength=140,
                    justify="left",
                ).pack(side="left", anchor="w", fill="x", expand=True)
        else:
            tk.Label(
                legend,
                text="Veri yok",
                bg=self.renkler["kart_ikincil"],
                fg=self.renkler["muted"],
                font=("Segoe UI", 9, "bold"),
                wraplength=140,
                justify="left",
            ).pack(anchor="w")

        def ciz(event=None):
            try:
                canvas.delete("all")
                w = max(canvas.winfo_width(), 120)
                h = max(canvas.winfo_height(), 160)
                size = max(90, min(w, h) - 26)
                x0 = (w - size) // 2
                y0 = (h - size) // 2
                x1 = x0 + size
                y1 = y0 + size
                toplam = sum(sizes)
                if not toplam:
                    canvas.create_oval(x0, y0, x1, y1, outline=self.renkler["kenarlik"], width=18)
                    canvas.create_text(w // 2, h // 2, text="Veri yok", fill=self.renkler["muted"], font=("Segoe UI", 11, "bold"))
                    return
                baslangic = 90
                for idx, value in enumerate(sizes):
                    extent = -359.8 * (value / toplam)
                    canvas.create_arc(
                        x0,
                        y0,
                        x1,
                        y1,
                        start=baslangic,
                        extent=extent,
                        fill=renkler[idx % len(renkler)],
                        outline=self.renkler["kart_ikincil"],
                        width=2,
                    )
                    baslangic += extent
                ic_bosluk = int(size * 0.58)
                ix0 = (w - ic_bosluk) // 2
                iy0 = (h - ic_bosluk) // 2
                canvas.create_oval(ix0, iy0, ix0 + ic_bosluk, iy0 + ic_bosluk, fill=self.renkler["kart_ikincil"], outline=self.renkler["kart_ikincil"])
                canvas.create_text(w // 2, h // 2 - 8, text=str(toplam), fill=self.renkler["yazi_rengi"], font=("Segoe UI", 20, "bold"))
                canvas.create_text(w // 2, h // 2 + 18, text="toplam", fill=self.renkler["muted"], font=("Segoe UI", 9, "bold"))
            except tk.TclError:
                pass

        canvas.bind("<Configure>", ciz)
        canvas.after_idle(ciz)
        return kart

    def asi_prosedur_sekmesi(self):
        asi_frame = ttk.Frame(self.notebook, style='TFrame')
        self.notebook.add(asi_frame, text="Aşı/Prosedür")

        self.asi_scroll_sayfa = self.kaydirilabilir_sayfa(asi_frame, padx=16, pady=16)

        self.asi_main_card = self.modern_kart(self.asi_scroll_sayfa)
        self.asi_main_card.pack(fill='both', expand=True)

        header = tk.Frame(self.asi_main_card, bg=self.renkler["kart_arkaplan"], pady=20)
        header.pack(fill='x', padx=24)
        self.themed_widgets.append((header, 'kart'))

        baslik = tk.Label(header, text="Aşı ve Prosedür Takibi", font=('Segoe UI', 18, 'bold'), bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"])
        baslik.pack(side='left')
        self.themed_widgets.append((baslik, 'label'))
        
        def yeni_asi_dialog():
            dialog = tk.Toplevel(self.root)
            dialog.title("Yeni Aşı/Prosedür Ekle")
            dialog.geometry("350x200")
            dialog.configure(bg=self.renkler["arkaplan"])
            dialog.transient(self.root)
            dialog.grab_set()
            
            tk.Label(dialog, text="Hayvan Küpe No:", font=('Segoe UI', 12, 'bold'), bg=self.renkler["arkaplan"], fg=self.renkler["yazi_rengi"]).pack(pady=20)
            
            aktif_hayvanlar_map = {}
            for k, v in self.hayvanlar.items():
                if not v.get('arsivli') and not v.get('olu') and not v.get('kesildi') and not v.get('satildi'):
                    gorunen = v.get('ciftlik_kupe_no') or v.get('resmi_kupe_no') or k
                    aktif_hayvanlar_map[gorunen] = k
                    
            combo = ttk.Combobox(dialog, values=sorted(list(aktif_hayvanlar_map.keys())), font=('Segoe UI', 11), style='TCombobox')
            combo.pack(pady=10)
            
            def on_ok():
                secilen = combo.get().strip()
                secilen_id = aktif_hayvanlar_map.get(secilen) or self.hayvan_id_bul(secilen, aktif_olsun=True)
                            
                if secilen_id and secilen_id in self.hayvanlar:
                    dialog.destroy()
                    self.asi_prosedur_penceresi(secilen_id)
                else:
                    messagebox.showerror("Hata", "Geçerli bir aktif hayvan seçin.", parent=dialog)
            
            self.modern_buton(dialog, "SEÇ VE İLERLE", on_ok, purpose='success').pack(pady=10)

        self.modern_buton(header, "YENİ AŞI EKLE", yeni_asi_dialog, purpose='primary', small=True).pack(side='right', padx=(6, 0))
        self.modern_buton(header, "YENİLE", self.asi_prosedur_listesini_guncelle, purpose='success', small=True).pack(side='right', padx=6)

        cizgi = tk.Frame(self.asi_main_card, bg=self.renkler["kenarlik"], height=1)
        cizgi.pack(fill='x', padx=24, pady=(0, 10))
        self.themed_widgets.append((cizgi, 'divider'))

        tree_frame = tk.Frame(self.asi_main_card, bg=self.renkler["kart_arkaplan"])
        tree_frame.pack(fill='both', expand=True, padx=15, pady=15)
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        self.themed_widgets.append((tree_frame, 'kart'))

        columns = ("ID", "Küpe No", "Prosedür", "Uygulama Tarihi", "Sonraki Tarih", "Kalan Gün", "Not")
        self.asi_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', style='Modern.Treeview', height=16)
        
        self.asi_tree.heading("ID", text="ID")
        self.asi_tree.column("ID", width=0, stretch=tk.NO) # Hide ID column
        
        col_widths = {"Küpe No": 140, "Prosedür": 200, "Uygulama Tarihi": 130, "Sonraki Tarih": 130, "Kalan Gün": 100, "Not": 260}
        for col in columns[1:]:
            self.asi_tree.heading(col, text=col)
            self.asi_tree.column(col, width=col_widths.get(col, 150), anchor='center')

        self.asi_tree_scroll_v = ttk.Scrollbar(tree_frame, orient='vertical', command=self.asi_tree.yview)
        self.asi_tree_scroll_h = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.asi_tree.xview)
        self.asi_tree.configure(yscrollcommand=self.asi_tree_scroll_v.set, xscrollcommand=self.asi_tree_scroll_h.set)
        self.asi_tree.grid(row=0, column=0, sticky='nsew', padx=(1, 0), pady=(1, 0))
        self.asi_tree_scroll_v.grid(row=0, column=1, sticky='ns', pady=(1, 0))
        self.asi_tree_scroll_h.grid(row=1, column=0, sticky='ew', padx=(1, 0))
        self.asi_tree.bind('<Double-Button-1>', self.asi_prosedur_detay_ac)

    def asi_prosedur_listesini_guncelle(self):
        if not hasattr(self, 'asi_tree'):
            return
        for item in self.asi_tree.get_children():
            self.asi_tree.delete(item)

        bugun = datetime.now().date()
        satirlar = []
        for kupe_no, hayvan in self.hayvanlar.items():
            if hayvan.get('arsivli') or hayvan.get('olu') or hayvan.get('kesildi') or hayvan.get('satildi'):
                continue
            for kayit in hayvan.get('asi_prosedurler', []):
                sonraki = kayit.get('sonraki_tarih') or ""
                kalan = "-"
                tag = "normal"
                if sonraki:
                    try:
                        kalan_gun = (datetime.strptime(sonraki, "%d/%m/%Y").date() - bugun).days
                        kalan = kalan_gun
                        if kalan_gun < 0:
                            tag = "critical"
                        elif kalan_gun <= 7:
                            tag = "warning"
                    except ValueError:
                        kalan = "Hata"
                        tag = "critical"
                satirlar.append((kupe_no, kayit, kalan, tag))

        def sirala(item):
            kalan = item[2]
            return 99999 if kalan == "-" else 99998 if kalan == "Hata" else kalan

        for kupe_no, kayit, kalan, tag in sorted(satirlar, key=sirala):
            gorunen_kupe = self.hayvanlar[kupe_no].get('ciftlik_kupe_no') or self.hayvanlar[kupe_no].get('resmi_kupe_no') or "Bilinmiyor"
            self.asi_tree.insert('', 'end', values=(kupe_no, gorunen_kupe, kayit.get('ad', '-'), kayit.get('tarih', '-'), kayit.get('sonraki_tarih') or "-", kalan, kayit.get('not', '')), tags=(tag,))

        bg_critical = '#4C0519' if self.theme_mode == "dark" else '#FEE2E2'
        fg_critical = '#FECDD3' if self.theme_mode == "dark" else '#991B1B'
        self.asi_tree.tag_configure('critical', background=bg_critical, foreground=fg_critical)
        self.asi_tree.tag_configure('warning', foreground="#FFEE58")
        self.asi_tree.tag_configure('normal', foreground=self.renkler["yazi_rengi"])

    def asi_prosedur_detay_ac(self, event):
        secim = self.asi_tree.selection()
        if not secim:
            return
        item = self.asi_tree.item(secim[0])
        kupe_no = str(item['values'][0])
        if kupe_no in self.hayvanlar:
            self.asi_prosedur_penceresi(kupe_no)

    def asi_prosedur_penceresi(self, kupe_no, parent=None):
        if kupe_no not in self.hayvanlar:
            return
        hayvan = self.hayvanlar[kupe_no]
        hayvan.setdefault('asi_prosedurler', [])
        
        gorunen_kupe = hayvan.get('ciftlik_kupe_no') or hayvan.get('resmi_kupe_no') or kupe_no

        parent_pencere = parent if parent is not None and parent.winfo_exists() else self.root
        pencere = tk.Toplevel(parent_pencere)
        pencere.title(f"Aşı/Prosedür - {gorunen_kupe}")
        pencere.geometry("900x620")
        pencere.configure(bg=self.renkler["arkaplan"])
        pencere.transient(parent_pencere)
        try:
            parent_pencere.grab_release()
        except tk.TclError:
            pass

        def kapat():
            try:
                pencere.grab_release()
            except tk.TclError:
                pass
            try:
                pencere.destroy()
            except tk.TclError:
                pass
            if parent is not None:
                try:
                    if parent.winfo_exists():
                        parent.lift()
                        parent.grab_set()
                except tk.TclError:
                    pass

        pencere.protocol("WM_DELETE_WINDOW", kapat)
        pencere.grab_set()
        pencere.lift(parent_pencere)
        pencere.focus_force()

        form = tk.Frame(pencere, bg=self.renkler["arkaplan"], padx=20, pady=15)
        form.pack(fill='x')
        
        ad_entry = ttk.Entry(form, style='TEntry')
        tarih_entry = ttk.Entry(form, style='TEntry')
        tarih_entry.insert(0, datetime.now().strftime("%d/%m/%Y"))
        tarih_entry.bind('<KeyRelease>', self.tarih_formatlama)
        sonraki_entry = ttk.Entry(form, style='TEntry')
        sonraki_entry.bind('<KeyRelease>', self.tarih_formatlama)
        not_entry = ttk.Entry(form, style='TEntry')

        # Row 0
        tk.Label(form, text="Prosedür Adı", bg=self.renkler["arkaplan"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, sticky='w', padx=8)
        ad_entry.grid(row=1, column=0, sticky='ew', padx=8, pady=(5, 15))
        
        tk.Label(form, text="Uygulama Tarihi", bg=self.renkler["arkaplan"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 10, 'bold')).grid(row=0, column=1, sticky='w', padx=8)
        tarih_entry.grid(row=1, column=1, sticky='ew', padx=8, pady=(5, 15))

        # Row 2
        tk.Label(form, text="Sonraki Tarih", bg=self.renkler["arkaplan"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 10, 'bold')).grid(row=2, column=0, sticky='w', padx=8)
        sonraki_entry.grid(row=3, column=0, sticky='ew', padx=8, pady=5)
        
        tk.Label(form, text="Not", bg=self.renkler["arkaplan"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 10, 'bold')).grid(row=2, column=1, sticky='w', padx=8)
        not_entry.grid(row=3, column=1, sticky='ew', padx=8, pady=5)

        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)

        btn_frame = tk.Frame(pencere, bg=self.renkler["arkaplan"])
        btn_frame.pack(side='bottom', pady=12, fill='x')
        
        btn_inner = tk.Frame(btn_frame, bg=self.renkler["arkaplan"])
        btn_inner.pack(anchor='center')

        columns = ("#", "Prosedür", "Uygulama Tarihi", "Sonraki Tarih", "Not")
        tree = ttk.Treeview(pencere, columns=columns, show='headings', style='Modern.Treeview')
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120 if col != "Not" else 300, anchor='center')
        tree.pack(fill='both', expand=True, padx=20, pady=(10, 0))

        def temizle():
            ad_entry.delete(0, tk.END)
            tarih_entry.delete(0, tk.END)
            tarih_entry.insert(0, datetime.now().strftime("%d/%m/%Y"))
            sonraki_entry.delete(0, tk.END)
            not_entry.delete(0, tk.END)

        def yenile():
            for item in tree.get_children():
                tree.delete(item)
            for idx, kayit in enumerate(hayvan.get('asi_prosedurler', [])):
                tree.insert('', 'end', iid=str(idx), values=(idx + 1, kayit.get('ad', ''), kayit.get('tarih', ''), kayit.get('sonraki_tarih') or "-", kayit.get('not', '')))

        def secili_index():
            secim = tree.selection()
            if not secim:
                messagebox.showwarning("Uyarı", "Önce bir kayıt seçin.", parent=pencere)
                return None
            return int(secim[0])

        def seciliyi_forma_al(event=None):
            idx = secili_index()
            if idx is None:
                return
            kayit = hayvan['asi_prosedurler'][idx]
            temizle()
            ad_entry.delete(0, tk.END); ad_entry.insert(0, kayit.get('ad', ''))
            tarih_entry.delete(0, tk.END); tarih_entry.insert(0, kayit.get('tarih', ''))
            sonraki_entry.delete(0, tk.END); sonraki_entry.insert(0, kayit.get('sonraki_tarih') or "")
            not_entry.delete(0, tk.END); not_entry.insert(0, kayit.get('not', ''))

        def form_verisi(parent):
            ad = ad_entry.get().strip()
            tarih = tarih_entry.get().strip()
            sonraki = sonraki_entry.get().strip()
            if not ad or not tarih:
                messagebox.showerror("Hata", "Prosedür adı ve uygulama tarihi zorunludur.", parent=parent)
                return None
            tarih_dt = self.tarih_coz(tarih, "Uygulama tarihi", parent=parent)
            if tarih_dt is None:
                return None
            if sonraki:
                sonraki_dt = self.tarih_coz(sonraki, "Sonraki tarih", parent=parent, gelecege_izin_ver=True)
                if sonraki_dt is None:
                    return None
                if sonraki_dt < tarih_dt:
                    messagebox.showerror("Hata", "Sonraki tarih uygulama tarihinden önce olamaz.", parent=parent)
                    return None
            return {
                'ad': ad,
                'tarih': tarih,
                'sonraki_tarih': sonraki or None,
                'not': not_entry.get().strip()
            }

        def yeni_kaydet():
            veri = form_verisi(pencere)
            if veri is None:
                return
            self.islem_kaydi_baslat(f"Aşı/prosedür eklendi: {kupe_no}")
            veri['id'] = uuid.uuid4().hex[:12]
            veri['kayit_tarihi'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            hayvan['asi_prosedurler'].append(veri)
            hayvan['son_guncelleme'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            self.veri_kaydet(kupe_no=kupe_no)
            temizle()
            yenile()
            self.ekranlari_guncelle()

        def secili_guncelle():
            idx = secili_index()
            if idx is None:
                return
            veri = form_verisi(pencere)
            if veri is None:
                return
            self.islem_kaydi_baslat(f"Aşı/prosedür güncellendi: {kupe_no}")
            eski = hayvan['asi_prosedurler'][idx]
            veri['id'] = eski.get('id') or uuid.uuid4().hex[:12]
            veri['kayit_tarihi'] = eski.get('kayit_tarihi', datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
            hayvan['asi_prosedurler'][idx] = veri
            hayvan['son_guncelleme'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            self.veri_kaydet(kupe_no=kupe_no)
            yenile()
            self.ekranlari_guncelle()

        def secili_sil():
            idx = secili_index()
            if idx is None:
                return
            if not messagebox.askyesno("Sil", "Seçili aşı/prosedür kaydı silinsin mi?", parent=pencere):
                return
            self.islem_kaydi_baslat(f"Aşı/prosedür silindi: {kupe_no}")
            hayvan['asi_prosedurler'].pop(idx)
            hayvan['son_guncelleme'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            self.veri_kaydet(kupe_no=kupe_no)
            temizle()
            yenile()
            self.ekranlari_guncelle()

        tree.bind('<<TreeviewSelect>>', seciliyi_forma_al)
        
        import uuid
        
        self.modern_buton(btn_inner, "YENİ KAYDET", yeni_kaydet, purpose='success').pack(side='left', padx=8)
        self.modern_buton(btn_inner, "SEÇİLİYİ GÜNCELLE", secili_guncelle, purpose='default').pack(side='left', padx=8)
        self.modern_buton(btn_inner, "SEÇİLİYİ SİL", secili_sil, purpose='danger').pack(side='left', padx=8)
        self.modern_buton(btn_inner, "TEMİZLE", temizle, purpose='warning').pack(side='left', padx=8)
        self.modern_buton(btn_inner, "KAPAT", kapat, purpose='default').pack(side='left', padx=8)
        yenile()
    
    def uyari_sekmesi(self):
        uyari_frame = ttk.Frame(self.notebook, style='TFrame')
        self.notebook.add(uyari_frame, text="Uyarılar")
        
        main_card = self.modern_kart(uyari_frame)
        main_card.pack(fill='both', expand=True, padx=16, pady=16)

        header = tk.Frame(main_card, bg=self.renkler["kart_arkaplan"], pady=20)
        header.pack(fill='x', padx=24)
        self.themed_widgets.append((header, 'kart'))

        uyari_baslik_label = tk.Label(header, text="Aktif Uyarılar ve Bildirimler", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 18, 'bold'))
        uyari_baslik_label.pack(side='left')
        self.themed_widgets.append((uyari_baslik_label, 'label'))
        
        self.modern_buton(header, "TÜMÜNÜ OKUNDU İŞARETLE", self.uyarilari_okundu_isaretle, purpose='success', small=True).pack(side='right')
        
        cizgi = tk.Frame(main_card, bg=self.renkler["kenarlik"], height=1)
        cizgi.pack(fill='x', padx=24, pady=(0, 10))
        self.themed_widgets.append((cizgi, 'divider'))

        uyari_tree_frame = tk.Frame(main_card, bg=self.renkler["kart_arkaplan"])
        uyari_tree_frame.pack(fill='both', expand=True, padx=15, pady=15)
        self.themed_widgets.append((uyari_tree_frame, 'kart'))
        uyari_columns = ('Küpe No', 'Uyarı Tipi', 'Mesaj', 'Kalan/Geçen Gün', 'Önem Derecesi', 'Durum')
        self.uyari_tree = ttk.Treeview(uyari_tree_frame, columns=uyari_columns, show='headings', height=25, style='Modern.Treeview')
        for col in uyari_columns:
            self.uyari_tree.heading(col, text=col)
            self.uyari_tree.column(col, width=180, anchor='center')
        uyari_scrollbar = ttk.Scrollbar(uyari_tree_frame, orient='vertical', command=self.uyari_tree.yview)
        self.uyari_tree.configure(yscrollcommand=uyari_scrollbar.set)
        self.uyari_tree.grid(row=0, column=0, sticky='nsew')
        uyari_scrollbar.grid(row=0, column=1, sticky='ns')
        uyari_tree_frame.grid_rowconfigure(0, weight=1)
        uyari_tree_frame.grid_columnconfigure(0, weight=1)
        self.uyari_tree.bind('<Double-Button-1>', self.uyari_detay_ac)

    # --- Yardımcı Fonksiyonlar ---
    def tarih_formatlama(self, event):
        widget = event.widget
        text = widget.get()
        sadece_rakam = ''.join(filter(str.isdigit, text))
        if len(sadece_rakam) <= 2: formatted = sadece_rakam
        elif len(sadece_rakam) <= 4: formatted = sadece_rakam[:2] + '/' + sadece_rakam[2:]
        elif len(sadece_rakam) <= 8: formatted = sadece_rakam[:2] + '/' + sadece_rakam[2:4] + '/' + sadece_rakam[4:]
        else: formatted = sadece_rakam[:2] + '/' + sadece_rakam[2:4] + '/' + sadece_rakam[4:8]
        if text != formatted:
            widget.delete(0, tk.END)
            widget.insert(0, formatted)

    def hayvan_ara(self, event):
        text = self.tohumlama_hayvan_combo.get().strip().upper()
        if not text:
            self.tohumlama_hayvanlarini_guncelle()
            return
        eslesenler = []
        for h_id, hayvan in self.hayvanlar.items():
            if not self.hayvan_tohumlanabilir_mi(hayvan):
                continue
            if self.hayvan_arama_eslesir(h_id, hayvan, text):
                gorunen = hayvan.get('ciftlik_kupe_no') or hayvan.get('resmi_kupe_no') or h_id
                eslesenler.append(str(gorunen).upper())
        current_text = self.tohumlama_hayvan_combo.get()
        self.tohumlama_hayvan_combo['values'] = sorted(eslesenler)
        self.tohumlama_hayvan_combo.set(current_text)

    def aktif_hayvan_secim_degerleri(self):
        degerler = []
        for h_id, hayvan in self.hayvanlar.items():
            if not self.hayvan_tohumlanabilir_mi(hayvan):
                continue
            gorunen = hayvan.get('ciftlik_kupe_no') or hayvan.get('resmi_kupe_no') or h_id
            if gorunen:
                degerler.append(str(gorunen).upper())
        return sorted(set(degerler))

    def tohumlama_hayvanlarini_guncelle(self):
        if hasattr(self, 'tohumlama_hayvan_combo'):
            mevcut = self.tohumlama_hayvan_combo.get()
            self.tohumlama_hayvan_combo['values'] = self.aktif_hayvan_secim_degerleri()
            if mevcut:
                self.tohumlama_hayvan_combo.set(mevcut)

    def tohumlama_sekli_degisti(self, event):
        if self.tohumlama_sekli_combo.get() == "Suni":
            self.suni_container.grid()
        else:
            self.suni_container.grid_remove()

    def sekme_index_bul(self, sekme_adi):
        if not hasattr(self, "notebook"):
            return None
        try:
            for idx in range(self.notebook.index("end")):
                if self.notebook.tab(idx, "text") == sekme_adi:
                    return idx
        except tk.TclError:
            return None
        return None

    def hayvan_tohumlanabilir_mi(self, hayvan):
        if not hayvan:
            return False
        if hayvan.get('arsivli') or hayvan.get('olu') or hayvan.get('kesildi') or hayvan.get('satildi'):
            return False
        if self.hayvan_bekleyen_tohumlama(hayvan):
            return False
        if hayvan.get('gebe_mi', False):
            return False
        cins = str(hayvan.get('cins') or "")
        if cins == "Dana" or cins.startswith("Erkek"):
            return False
        return True

    def hayvan_bekleyen_tohumlama(self, hayvan):
        if not hayvan:
            return None
        tohumlamalar = hayvan.get('tohumlamalar') or []
        if not tohumlamalar:
            return None
        son_tohumlama = tohumlamalar[-1]
        return son_tohumlama if son_tohumlama.get('gebe_mi') is None else None

    def hayvan_tohumlama_sonuclanabilir_mi(self, hayvan):
        if not hayvan:
            return False
        if hayvan.get('arsivli') or hayvan.get('olu') or hayvan.get('kesildi') or hayvan.get('satildi'):
            return False
        cins = str(hayvan.get('cins') or "")
        if cins == "Dana" or cins.startswith("Erkek"):
            return False
        return self.hayvan_bekleyen_tohumlama(hayvan) is not None

    def tohumlama_ekranina_hayvanla_git(self, kupe_no, kaynak_pencere=None):
        hayvan_id = self.hayvan_referans_coz(kupe_no, aktif_olsun=True) or kupe_no
        if hayvan_id not in self.hayvanlar:
            return messagebox.showerror("Hata", f"Hayvan bulunamadı: {kupe_no}", parent=getattr(self, "root", None))
        hayvan = self.hayvanlar[hayvan_id]
        if not self.hayvan_tohumlanabilir_mi(hayvan):
            return messagebox.showerror("İşlem Başarısız", "Bu hayvan için tohumlama yapılamaz.", parent=kaynak_pencere or self.root)

        gorunen = hayvan.get('ciftlik_kupe_no') or hayvan.get('resmi_kupe_no') or hayvan_id
        if kaynak_pencere is not None:
            try:
                kaynak_pencere.grab_release()
                kaynak_pencere.destroy()
            except tk.TclError:
                pass

        idx = self.sekme_index_bul("Tohumlama")
        if idx is not None:
            self.notebook.select(idx)
            self._update_custom_tabs()
        self.tohumlama_hayvanlarini_guncelle()
        self.tohumlama_hayvan_combo.set(str(gorunen).upper())
        if not self.tohumlama_sekli_combo.get():
            self.tohumlama_sekli_combo.set("Suni")
            self.tohumlama_sekli_degisti(None)
        self.tohumlama_tarih_entry.delete(0, tk.END)
        self.tohumlama_tarih_entry.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.tohumlama_sekli_combo.focus_set()

    def filtre_degisti(self, event): self.hayvan_listesini_guncelle()
    def arama_degisti(self, event): self.hayvan_listesini_guncelle()
    def filtreleri_temizle(self):
        self.filtre_combo.set("Aktif")
        self.arama_entry.delete(0, tk.END)
        self.hayvan_listesini_guncelle()

    def hayvan_detay_ac(self, event):
        try:
            selection = self.hayvan_tree.selection()
            if not selection: return
            item = self.hayvan_tree.item(selection[0])
            if not item.get('values'): return
            kupe_no = str(item['values'][0]).strip()
            if kupe_no in self.hayvanlar:
                self.hayvan_detay_penceresi(kupe_no)
            else:
                messagebox.showerror("Hata", f"Hayvan bulunamadı: '{kupe_no}'")
        except Exception as e:
            messagebox.showerror("Hata", f"Detay açılırken hata oluştu: {str(e)}")

    def sag_tik_menu(self, event):
        item_id = self.hayvan_tree.identify_row(event.y)
        if item_id:
            self.hayvan_tree.selection_set(item_id)
            item = self.hayvan_tree.item(item_id)
            kupe_no = str((item.get('values') or [''])[0]).strip()
            hayvan = self.hayvanlar.get(kupe_no)
            popup = tk.Menu(self.root, tearoff=0, bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"])
            popup.add_command(label="Detayları Göster", command=lambda: self.hayvan_detay_ac(None))
            if self.hayvan_tohumlanabilir_mi(hayvan):
                popup.add_command(label="Tohumlama Yap", command=self.hizli_tohumlama)
            if hayvan and hayvan.get('arsivli') and not hayvan.get('olu') and not hayvan.get('kesildi') and not hayvan.get('satildi'):
                popup.add_command(label="Arşivden Çıkar", command=lambda h=kupe_no: self.hayvan_arsivden_cikar(h, self.root))
            popup.tk_popup(event.x_root, event.y_root)

    def hizli_tohumlama(self):
        try:
            selection = self.hayvan_tree.selection()
            if not selection: return messagebox.showwarning("Uyarı", "Önce bir hayvan seçin!")
            item = self.hayvan_tree.item(selection[0])
            kupe_no = str(item['values'][0]).strip()
            self.tohumlama_ekranina_hayvanla_git(kupe_no)
        except Exception as e:
            messagebox.showerror("Hata", f"Hızlı tohumlama hatası: {str(e)}")

    def uyarilari_okundu_isaretle(self):
        if not messagebox.askyesno("Onay", "Tüm aktif uyarıları okundu olarak işaretlemek istediğinizden emin misiniz?"):
            return

        aktif_uyari_keyleri = []
        for kupe_no, hayvan in self.hayvanlar.items():
            if hayvan.get('arsivli', False) or hayvan.get('olu', False) or hayvan.get('kesildi', False) or hayvan.get('satildi', False):
                continue
            aktif_tohumlama_id = hayvan.get('aktif_tohumlama_id')

            if hayvan.get('tohumlamalar'):
                son_tohumlama = hayvan['tohumlamalar'][-1]
                if son_tohumlama.get('gebe_mi') is None:
                    try:
                        t_tarihi = datetime.strptime(son_tohumlama['tarih'], "%d/%m/%Y")
                        kontrol_tarihi = t_tarihi + timedelta(days=21)
                        kalan_kontrol = (kontrol_tarihi - datetime.now()).days
                        if kalan_kontrol <= 7:
                            tohumlama_id = son_tohumlama.get('id') or "bekleyen"
                            uyari_key = self.uyari_key_olustur(kupe_no, "gebelik_kontrol", tohumlama_id, kalan_kontrol)
                            if uyari_key:
                                aktif_uyari_keyleri.append(uyari_key)
                    except: continue

            if aktif_tohumlama_id and hayvan.get('durum') == 'Sağmal İnek' and hayvan.get('gebe_mi', False):
                try:
                    g_tarihi = datetime.strptime(hayvan['gebelik_tarihi'], "%d/%m/%Y")
                    kalan_gun_doguma = (g_tarihi + timedelta(days=283) - datetime.now()).days
                    if kalan_gun_doguma <= 60:
                        uyari_key = self.uyari_key_olustur(kupe_no, "kuruya_al", aktif_tohumlama_id, kalan_gun_doguma)
                        if uyari_key:
                            aktif_uyari_keyleri.append(uyari_key)
                except: continue
            
            if aktif_tohumlama_id and hayvan.get('gebe_mi', False):
                try:
                    g_tarihi = datetime.strptime(hayvan['gebelik_tarihi'], "%d/%m/%Y")
                    kalan_gun = (g_tarihi + timedelta(days=283) - datetime.now()).days
                    uyari_key = self.uyari_key_olustur(kupe_no, "gebelik", aktif_tohumlama_id, kalan_gun)
                    if uyari_key:
                        aktif_uyari_keyleri.append(uyari_key)
                except: continue

            for prosedur in hayvan.get('asi_prosedurler', []):
                sonraki_tarih = prosedur.get('sonraki_tarih')
                if not sonraki_tarih:
                    continue
                try:
                    p_tarihi = datetime.strptime(sonraki_tarih, "%d/%m/%Y")
                    kalan_prosedur = (p_tarihi - datetime.now()).days
                    if kalan_prosedur <= 7:
                        prosedur_id = prosedur.get('id') or prosedur.get('ad', 'prosedur')
                        uyari_key = self.uyari_key_olustur(kupe_no, "asi_prosedur", prosedur_id, kalan_prosedur)
                        if uyari_key:
                            aktif_uyari_keyleri.append(uyari_key)
                except: continue

        for key in aktif_uyari_keyleri:
            self.okunan_uyarilar[key] = datetime.now().strftime("%d/%m/%Y")
        
        self.okunan_uyarilar_kaydet()
        self.uyarilari_guncelle()
        messagebox.showinfo("Başarılı", "Tüm aktif uyarılar okundu olarak işaretlendi.")

    def uyari_detay_ac(self, event):
        selection = self.uyari_tree.selection()
        if not selection: return
        
        item = self.uyari_tree.item(selection[0])
        if not item.get('values'): return
        
        kupe_no = str(item['values'][0]).strip()
        uyari_tipi = str(item['values'][1]).strip()
        mesaj = str(item['values'][2]).strip()
        try:
            kalan_gun = int(item['values'][3])
        except (ValueError, TypeError, IndexError):
            kalan_gun = 60

        hayvan_id = self.hayvan_id_bul(kupe_no)
        if hayvan_id:
            hayvan = self.hayvanlar[hayvan_id]
            aktif_tohumlama_id = hayvan.get('aktif_tohumlama_id')
            uyari_key = None

            if 'KURUYA ALINMALI' in uyari_tipi and aktif_tohumlama_id:
                uyari_key = self.uyari_key_olustur(hayvan_id, "kuruya_al", aktif_tohumlama_id, kalan_gun)
            elif 'GEBELİK KONTROL' in uyari_tipi and hayvan.get('tohumlamalar'):
                son_tohumlama = hayvan['tohumlamalar'][-1]
                tohumlama_id = son_tohumlama.get('id') or "bekleyen"
                uyari_key = self.uyari_key_olustur(hayvan_id, "gebelik_kontrol", tohumlama_id, kalan_gun)
            elif 'AŞI/PROSEDÜR' in uyari_tipi:
                for prosedur in hayvan.get('asi_prosedurler', []):
                    if prosedur.get('ad', '') in mesaj and (prosedur.get('sonraki_tarih') or '') in mesaj:
                        prosedur_id = prosedur.get('id') or prosedur.get('ad', 'prosedur')
                        uyari_key = self.uyari_key_olustur(hayvan_id, "asi_prosedur", prosedur_id, kalan_gun)
                        break
            elif aktif_tohumlama_id:
                uyari_key = self.uyari_key_olustur(hayvan_id, "gebelik", aktif_tohumlama_id, kalan_gun)

            if uyari_key:
                self.okunan_uyarilar[uyari_key] = datetime.now().strftime("%d/%m/%Y")
                self.okunan_uyarilar_kaydet()

            if 'AŞI/PROSEDÜR' in uyari_tipi:
                self.asi_prosedur_penceresi(hayvan_id)
            else:
                self.hayvan_detay_penceresi(hayvan_id)
            self.uyarilari_guncelle()

    def sagmal_laktasyon_eksik_mi(self, hayvan):
        if hayvan.get('cins') != 'Sağmal İnek' and hayvan.get('durum') != 'Sağmal İnek':
            return False
        dogumlar = hayvan.get('dogumlar') or []
        if not dogumlar:
            return True
        aktif_dogum = None
        for dogum in reversed(dogumlar):
            if dogum.get('laktasyon_bitis_tarihi') is None:
                aktif_dogum = dogum
                break
        son_dogum = aktif_dogum or dogumlar[-1]
        tarih = (son_dogum.get('tarih') or '').strip()
        if not tarih or tarih == 'Bilinmiyor':
            return True
        try:
            datetime.strptime(tarih, "%d/%m/%Y")
            return False
        except (ValueError, TypeError):
            return True

    def laktasyon_dogumlari_olustur(self, cins, laktasyon_no_str, son_dogum_tarihi, hayvan_dogum_dt, parent=None, bos_birakilabilir=True):
        laktasyon_no_str = (laktasyon_no_str or '').strip()
        son_dogum_tarihi = (son_dogum_tarihi or '').strip()
        if not laktasyon_no_str and not son_dogum_tarihi and bos_birakilabilir:
            return []
        if not laktasyon_no_str or not son_dogum_tarihi:
            messagebox.showerror("Hata", "Laktasyon numarası ve son doğum tarihi birlikte doldurulmalı ya da ikisi de boş bırakılmalı.", parent=parent)
            return None
        try:
            laktasyon_no = int(laktasyon_no_str)
            if laktasyon_no <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Hata", "Geçersiz laktasyon numarası. Lütfen pozitif bir sayı girin.", parent=parent)
            return None

        son_dogum_dt = self.tarih_coz(son_dogum_tarihi, "Son doğum tarihi", parent=parent)
        if son_dogum_dt is None:
            return None
        if hayvan_dogum_dt and son_dogum_dt < hayvan_dogum_dt:
            messagebox.showerror("Hata", "Son doğum tarihi, hayvanın doğum tarihinden önce olamaz.", parent=parent)
            return None

        dogumlar_listesi = []
        for _ in range(max(laktasyon_no - 1, 0)):
            dogumlar_listesi.append({
                'tarih': 'Bilinmiyor',
                'yavrular': [],
                'laktasyon_bitis_tarihi': 'Bilinmiyor',
                'not': 'Geçmiş kayıt, süre bilinmiyor'
            })
        aktif_dogum = {
            'tarih': son_dogum_tarihi,
            'yavrular': [],
            'laktasyon_bitis_tarihi': None,
            'not': 'Sisteme giriş yapılan laktasyon'
        }
        if cins == "Kuru İnek":
            aktif_dogum['laktasyon_bitis_tarihi'] = datetime.now().strftime("%d/%m/%Y")
        dogumlar_listesi.append(aktif_dogum)
        return dogumlar_listesi

    # --- Ana Veri İşleme Fonksiyonları ---
    # #################################################################
    # ### GÜNCELLENMİŞ FONKSİYON: hayvan_kaydet
    # #################################################################
    def hayvan_kaydet(self):
        import uuid
        if getattr(self, "_hayvan_kayit_devam_ediyor", False):
            return
        resmi_kupe = self.resmi_kupe_no_entry.get().strip().upper()
        ciftlik_kupe = self.ciftlik_kupe_no_entry.get().strip().upper()
        dogum_tarihi = self.dogum_tarihi_entry.get().strip()
        cins = self.cins_combo.get()
        irk = self.irk_combo.get().strip()
        anne_kupe = self.anne_kupe_entry.get().strip().upper()
        hedef_ciftlik_id = getattr(self, "admin_aktif_ciftlik_id", None) if self.admin_mi() else None
        hedef_ciftlik_ad = getattr(self, "admin_aktif_ciftlik_ad", None) if self.admin_mi() else None
        if self.admin_mi() and not hedef_ciftlik_id:
            return messagebox.showerror("Hata", "Yeni hayvan eklemek icin Admin Merkezi'nden once bir ciftlik secin.")
        
        if not (resmi_kupe or ciftlik_kupe): 
            return messagebox.showerror("Hata", "En az bir küpe numarası (Resmi veya Çiftlik) girilmelidir!")
        if not all([dogum_tarihi, cins]): 
            return messagebox.showerror("Hata", "Doğum Tarihi ve Cins alanları zorunludur!")
            
        if self.kupe_cakismasi_var(resmi_kupe, ciftlik_kupe, ciftlik_id=hedef_ciftlik_id):
            return messagebox.showerror("Hata", "Bu küpe numaralarından biri zaten sistemde kayıtlı!")
                
        dogum_dt = self.tarih_coz(dogum_tarihi, "Doğum tarihi")
        if dogum_dt is None:
            return
        
        yas_gun = (datetime.now() - dogum_dt).days
        gercek_cins = cins
        dogumlar_listesi = []

        # Sağmal/Kuru ineklerde laktasyon bilgisi sonradan tamamlanabilir.
        if cins in ["Sağmal İnek", "Kuru İnek"]:
            laktasyon_no_str = self.laktasyon_no_entry.get().strip()
            son_dogum_tarihi = self.son_dogum_tarihi_entry.get().strip()
            dogumlar_listesi = self.laktasyon_dogumlari_olustur(cins, laktasyon_no_str, son_dogum_tarihi, dogum_dt)
            if dogumlar_listesi is None:
                return
        
        yeni_id = uuid.uuid4().hex
        gorunen_kupe = ciftlik_kupe if ciftlik_kupe else resmi_kupe
        yeni_fotograflar = list(getattr(self, "yeni_hayvan_foto_datas", []) or [])[:3]
        self.islem_kaydi_baslat(f"Hayvan eklendi: {gorunen_kupe}")
        
        self.hayvanlar[yeni_id] = {
            'kupe_no': gorunen_kupe, # Geriye dönük uyumluluk
            'ciftlik_id': hedef_ciftlik_id,
            'ciftlik_ad': hedef_ciftlik_ad,
            'resmi_kupe_no': resmi_kupe,
            'ciftlik_kupe_no': ciftlik_kupe,
            'dogum_tarihi': dogum_tarihi, 
            'cins': gercek_cins, 
            'irk': irk,
            'anne_kupe': anne_kupe, 
            'kayit_tarihi': datetime.now().strftime("%d/%m/%Y %H:%M:%S"), 
            'yas_gun': yas_gun, 
            'tohumlamalar': [], 
            'dogumlar': dogumlar_listesi, 
            'durum': self.durum_hesapla(gercek_cins, yas_gun), 
            'gebe_mi': False, 'gebelik_tarihi': None, 'aktif_tohumlama_id': None,
            'olu': False, 'olum_tarihi': None,
            'kesildi': False, 'kesim_bilgisi': None,
            'satildi': False, 'satis_tarihi': None, 'satis_bilgisi': None,
            'asi_prosedurler': [],
            'arsivli': False, 'arsiv_tarihi': None,
            'foto_data': yeni_fotograflar[0] if yeni_fotograflar else None,
            'foto_datas': yeni_fotograflar,
            'son_guncelleme': datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        }
        if getattr(self, "api_modu", False) and not self.offline_modda_mi():
            self.hayvan_kaydet_arka_planda(yeni_id, gorunen_kupe)
            return

        self.veri_kaydet(yeni_id)
        self.hayvan_kayit_tamamlandi(gorunen_kupe)

    def hayvan_kaydet_buton_durum(self, kaydediyor=False):
        btn = getattr(self, "hayvan_kaydet_btn", None)
        if not btn:
            return
        try:
            btn.enabled = not kaydediyor
            btn.itemconfig(btn.text_item, text="KAYDEDİLİYOR..." if kaydediyor else "HAYVANI KAYDET")
        except tk.TclError:
            pass

    def hayvan_kayit_formunu_temizle(self):
        for entry in [
            self.resmi_kupe_no_entry,
            self.ciftlik_kupe_no_entry,
            self.dogum_tarihi_entry,
            self.anne_kupe_entry,
            self.laktasyon_no_entry,
            self.son_dogum_tarihi_entry,
        ]:
            try:
                entry.delete(0, tk.END)
            except tk.TclError:
                pass
        self.cins_combo.set('')
        self.irk_combo.set('')
        self.yeni_hayvan_foto_data = None
        self.yeni_hayvan_foto_datas = []
        if hasattr(self, "yeni_hayvan_foto_onizleme_guncelle"):
            self.yeni_hayvan_foto_onizleme_guncelle()
        self._on_cins_change()

    def hayvan_kayit_tamamlandi(self, gorunen_kupe, cevrimdisi=False):
        if cevrimdisi:
            messagebox.showinfo("Kaydedildi", f"Hayvan {gorunen_kupe} yerel önbelleğe kaydedildi; internet gelince senkronize edilecek.")
        else:
            messagebox.showinfo("Başarılı", f"Hayvan {gorunen_kupe} başarıyla kaydedildi!")
        self.hayvan_kayit_formunu_temizle()
        self.hayvan_listesini_guncelle()
        self.header_ozet_guncelle()
        self.raporlari_guncelle()
        self.api_durum_guncelle()

    def hayvan_kaydet_arka_planda(self, yeni_id, gorunen_kupe):
        self._hayvan_kayit_devam_ediyor = True
        self.hayvan_kaydet_buton_durum(True)

        def worker():
            sonuc = {"ok": False, "cevrimdisi": False, "hata": None}
            try:
                sonuc["ok"] = bool(self.veri_kaydet(yeni_id, hata_mesaji_goster=False, ui_guncelle=False))
                sonuc["cevrimdisi"] = self.offline_modda_mi()
            except Exception as e:
                sonuc["hata"] = e

            def tamamla():
                self._hayvan_kayit_devam_ediyor = False
                self.hayvan_kaydet_buton_durum(False)
                if sonuc["ok"]:
                    self.hayvan_kayit_tamamlandi(gorunen_kupe, cevrimdisi=sonuc["cevrimdisi"])
                else:
                    self.api_durum_guncelle()
                    mesaj = sonuc["hata"] or getattr(self, "_api_son_hata", None) or "Kayıt tamamlanamadı."
                    messagebox.showerror("Kayıt Hatası", f"Hayvan kaydedilemedi:\n{mesaj}")

            try:
                self.root.after(0, tamamla)
            except tk.TclError:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def otomatik_cins_guncelle(self, mevcut_cins, yas_gun):
        return is_otomatik_cins_guncelle(mevcut_cins, yas_gun)

    def durum_hesapla(self, cins, yas_gun):
        return is_durum_hesapla(cins, yas_gun)

    def tohumlama_kaydet(self):
        kupe_girdi = self.tohumlama_hayvan_combo.get().strip().upper()
        sekil = self.tohumlama_sekli_combo.get()
        tarih = self.tohumlama_tarih_entry.get().strip()
        if not all([kupe_girdi, sekil, tarih]): return messagebox.showerror("Hata", "Lütfen tüm alanları doldurun!")
        
        kupe_no = self.hayvan_referans_coz(kupe_girdi, aktif_olsun=True)
                
        if not kupe_no: return messagebox.showerror("Hata", f"'{kupe_girdi}' küpeli hayvan bulunamadı!")
        
        hayvan = self.hayvanlar[kupe_no]
        
        if hayvan.get('olu', False) or hayvan.get('kesildi', False) or hayvan.get('arsivli', False) or hayvan.get('satildi', False):
            messagebox.showerror("İşlem Başarısız", f"'{kupe_no}' küpeli hayvan sürüde aktif değil.")
            return

        cins = hayvan.get('cins', '')
        erkek_cinsler = ["Erkek Buzağı", "Dana"]
        disi_cinsler = ["Dişi Buzağı", "Düve", "Sağmal İnek", "Kuru İnek"]
        tarih_dt = self.tarih_coz(tarih, "Tohumlama tarihi")
        if tarih_dt is None:
            return
        dogum_dt = self.tarih_coz(hayvan.get('dogum_tarihi', ''), "Hayvan doğum tarihi")
        if dogum_dt is None:
            return
        if tarih_dt < dogum_dt:
            messagebox.showerror("İşlem Başarısız", "Tohumlama tarihi, hayvanın doğum tarihinden önce olamaz.")
            return

        if cins in erkek_cinsler:
            messagebox.showerror("İşlem Başarısız", f"'{kupe_no}' küpeli hayvan ERKEK olduğu için tohumlama yapılamaz.")
            return

        if cins in disi_cinsler:
            yas_gun_tohumlama = (tarih_dt - dogum_dt).days
            if yas_gun_tohumlama < 365:
                messagebox.showerror("İşlem Başarısız", f"'{kupe_no}' küpeli hayvan tohumlama tarihinde 12 aylıktan küçük olduğu için tohumlama yapılamaz.\nTohumlama tarihindeki yaşı: {yas_gun_tohumlama // 30} ay")
                return

        if hayvan.get('gebe_mi', False):
            messagebox.showerror("İşlem Başarısız", f"'{kupe_no}' küpeli hayvan zaten GEBE olarak kayıtlıdır.\nYeni bir tohumlama eklenemez.")
            return
        
        if hayvan.get('tohumlamalar'):
            son_tohumlama = hayvan['tohumlamalar'][-1]
            if son_tohumlama.get('gebe_mi') is None:
                messagebox.showwarning("Bekleyen Kayıt Var", 
                                     f"'{kupe_no}' küpeli hayvanın son tohumlama kaydının sonucu henüz girilmemiş.\n\n"
                                     f"Yeni bir tohumlama eklemek için önce mevcut kaydı 'Gebelik Pozitif' veya 'Gebelik Negatif' olarak işaretlemelisiniz.")
                return
            
        suni_isim = self.suni_entry.get().strip() if sekil == "Suni" else ""
        if sekil == "Suni" and not suni_isim: return messagebox.showerror("Hata", "Suni tohumlama ismi girilmelidir!")
        
        tohumlama_id = uuid.uuid4().hex[:12]
        tohumlama_bilgi = {'id': tohumlama_id, 'tarih': tarih, 'sekil': sekil, 'suni_isim': suni_isim, 'gebe_mi': None, 'kontrol_tarihi': None, 'gebelik_suresi': 283}
        
        self.islem_kaydi_baslat(f"Tohumlama kaydı eklendi: {kupe_no}")
        self.hayvanlar[kupe_no]['tohumlamalar'].append(tohumlama_bilgi)
        self.hayvanlar[kupe_no]['son_guncelleme'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        if not self.veri_kaydet(kupe_no=kupe_no, ui_guncelle=False):
            return
        messagebox.showinfo("Başarılı", f"Tohumlama kaydı başarılı!\nTohumlama ID: {tohumlama_id}")
        self.tohumlama_hayvan_combo.set('')
        self.suni_entry.delete(0, tk.END)
        self.tohumlama_sekli_combo.set('')
        self.hayvan_listesini_guncelle()

    def gebelik_sonucu_kaydet(self, kupe_no, sonuc, parent=None):
        kupe_no = self.hayvan_referans_coz(kupe_no, aktif_olsun=True) or kupe_no
        if not kupe_no or kupe_no not in self.hayvanlar:
            messagebox.showerror("Hata", "Geçerli bir hayvan bulunamadı.", parent=parent or self.root)
            return False

        hayvan = self.hayvanlar[kupe_no]
        son_tohumlama = self.hayvan_bekleyen_tohumlama(hayvan)
        gorunen = self.hayvan_gorunen_kupe(kupe_no, hayvan)
        if son_tohumlama is None:
            messagebox.showerror(
                "Hata",
                "Bu hayvan için bekleyen bir tohumlama sonucu bulunmamaktadır.",
                parent=parent or self.root,
            )
            return False

        sonuc_metin = "pozitif" if sonuc else "negatif"
        self.islem_kaydi_baslat(f"Gebelik {sonuc_metin} işlendi: {gorunen}")
        son_tohumlama.update({
            'gebe_mi': bool(sonuc),
            'kontrol_tarihi': datetime.now().strftime("%d/%m/%Y"),
        })

        if sonuc:
            hayvan.update({
                'gebe_mi': True,
                'gebelik_tarihi': son_tohumlama.get('tarih'),
                'aktif_tohumlama_id': son_tohumlama.get('id'),
            })
            if hayvan.get('durum') not in ['Sağmal İnek', 'Kuru İnek']:
                hayvan['durum'] = 'Gebe'
        else:
            yeni_durum = self.durum_hesapla(hayvan.get('cins'), hayvan.get('yas_gun'))
            hayvan.update({
                'gebe_mi': False,
                'gebelik_tarihi': None,
                'aktif_tohumlama_id': None,
                'durum': yeni_durum,
            })

        hayvan['son_guncelleme'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        if not self.veri_kaydet(kupe_no=kupe_no):
            return False

        messagebox.showinfo(
            "Başarılı",
            f"{gorunen} gebelik sonucu {sonuc_metin} olarak işlendi.",
            parent=parent or self.root,
        )
        self.hayvan_listesini_guncelle()
        self.uyarilari_guncelle()
        self.raporlari_guncelle()
        self.header_ozet_guncelle()
        return True

    def tohumlama_sonuc_penceresi(self, kupe_no, kaynak_pencere=None):
        hayvan_id = self.hayvan_referans_coz(kupe_no, aktif_olsun=True) or kupe_no
        if hayvan_id not in self.hayvanlar:
            return messagebox.showerror("Hata", f"Hayvan bulunamadı: {kupe_no}", parent=kaynak_pencere or self.root)

        hayvan = self.hayvanlar[hayvan_id]
        bekleyen = self.hayvan_bekleyen_tohumlama(hayvan)
        gorunen = self.hayvan_gorunen_kupe(hayvan_id, hayvan)
        if bekleyen is None:
            return messagebox.showinfo("Tohumlama Sonucu", f"{gorunen} için bekleyen tohumlama sonucu yok.", parent=kaynak_pencere or self.root)

        if kaynak_pencere is not None:
            try:
                kaynak_pencere.grab_release()
                kaynak_pencere.destroy()
            except tk.TclError:
                pass

        pencere = tk.Toplevel(self.root)
        pencere.title(f"Tohumlamayı Sonuçla - {gorunen}")
        pencere.geometry("620x420")
        pencere.minsize(560, 380)
        pencere.configure(bg=self.renkler["arkaplan"])
        pencere.transient(self.root)
        pencere.grab_set()

        kart = self.modern_kart(pencere, accent=self.renkler["button_primary_bg"])
        kart.pack(fill='both', expand=True, padx=22, pady=22)

        body = tk.Frame(kart, bg=self.renkler["kart_arkaplan"], padx=24, pady=22)
        body.pack(fill='both', expand=True)
        self.themed_widgets.append((body, 'kart'))

        tk.Label(
            body,
            text="Tohumlama Sonucu",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["yazi_rengi"],
            font=('Segoe UI', 20, 'bold'),
        ).pack(anchor='w')
        tk.Label(
            body,
            text=f"{gorunen} için bekleyen tohumlama sonucunu işaretleyin.",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["muted"],
            font=('Segoe UI', 10),
        ).pack(anchor='w', pady=(6, 18))

        bilgi = tk.Frame(body, bg=self.renkler["kart_ikincil"], padx=14, pady=12, highlightthickness=1, highlightbackground=self.renkler["kenarlik"])
        bilgi.pack(fill='x', pady=(0, 18))
        self.themed_widgets.append((bilgi, 'soft_panel'))
        satirlar = [
            ("Hayvan", gorunen),
            ("Tohumlama Tarihi", bekleyen.get('tarih') or "-"),
            ("Şekil", bekleyen.get('sekil') or "-"),
            ("Boğa/Sperma", bekleyen.get('suni_isim') or "-"),
        ]
        for idx, (etiket, deger) in enumerate(satirlar):
            tk.Label(bilgi, text=etiket, bg=self.renkler["kart_ikincil"], fg=self.renkler["muted"], font=('Segoe UI', 9, 'bold')).grid(row=idx, column=0, sticky='w', pady=4, padx=(0, 16))
            tk.Label(bilgi, text=str(deger), bg=self.renkler["kart_ikincil"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 10, 'bold')).grid(row=idx, column=1, sticky='w', pady=4)
        bilgi.columnconfigure(1, weight=1)

        btn_frame = tk.Frame(body, bg=self.renkler["kart_arkaplan"])
        btn_frame.pack(side='bottom', fill='x', pady=(18, 0))
        self.themed_widgets.append((btn_frame, 'kart'))

        def sonuc_sec(sonuc):
            if self.gebelik_sonucu_kaydet(hayvan_id, sonuc, parent=pencere):
                try:
                    pencere.destroy()
                except tk.TclError:
                    pass
                self._track_after(self.root, 80, lambda: self.hayvan_detay_penceresi(hayvan_id))

        def kapat_sonuc_penceresi():
            try:
                pencere.destroy()
            except tk.TclError:
                pass
            if kaynak_pencere is not None:
                self._track_after(self.root, 80, lambda: self.hayvan_detay_penceresi(hayvan_id))

        pencere.protocol("WM_DELETE_WINDOW", kapat_sonuc_penceresi)
        self.modern_buton(btn_frame, "GEBELİK POZİTİF", lambda: sonuc_sec(True), purpose='success', width=20).pack(side='left', padx=(0, 10))
        self.modern_buton(btn_frame, "GEBELİK NEGATİF", lambda: sonuc_sec(False), purpose='danger', width=20).pack(side='left', padx=10)
        self.modern_buton(btn_frame, "İPTAL", kapat_sonuc_penceresi, purpose='default', width=14).pack(side='right')

    def gebelik_pozitif(self):
        kupe_girdi = self.tohumlama_hayvan_combo.get().strip().upper()
        if not kupe_girdi:
            return messagebox.showerror("Hata", "Geçerli bir hayvan seçin veya tohumlama kaydı oluşturun!")
        self.gebelik_sonucu_kaydet(kupe_girdi, True)

    def gebelik_negatif(self):
        kupe_girdi = self.tohumlama_hayvan_combo.get().strip().upper()
        if not kupe_girdi:
            return messagebox.showerror("Hata", "Geçerli bir hayvan seçin veya tohumlama kaydı oluşturun!")
        self.gebelik_sonucu_kaydet(kupe_girdi, False)

    def _ask_calf_details(self, parent, calf_number):
        dialog, kart = self.modern_popup(f"{calf_number}. Yavru Bilgileri", 520, 430, parent=parent)
        result = {}

        main_frame = tk.Frame(kart, bg=self.renkler["kart_arkaplan"], padx=24, pady=22)
        main_frame.pack(fill="both", expand=True)
        self.themed_widgets.append((main_frame, 'kart'))

        tk.Label(main_frame, text=f"{calf_number}. Yavru Bilgileri", font=('Segoe UI', 16, 'bold'), bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"]).pack(anchor="w", pady=(0, 6))
        tk.Label(main_frame, text="Resmi ve çiftlik küpesi ayrı tutulur; en az bir küpe girebilirsiniz.", font=('Segoe UI', 9), bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], wraplength=440, justify="left").pack(anchor="w", pady=(0, 18))

        form = tk.Frame(main_frame, bg=self.renkler["kart_arkaplan"])
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        self.themed_widgets.append((form, 'kart'))

        cins_combo = ttk.Combobox(form, values=["Dişi Buzağı", "Erkek Buzağı"], font=('Segoe UI', 11), style='TCombobox', state="readonly")
        resmi_entry = ttk.Entry(form, font=('Segoe UI', 11), style='TEntry')
        ciftlik_entry = ttk.Entry(form, font=('Segoe UI', 11), style='TEntry')
        for row, (label_text, widget) in enumerate([
            ("Cinsi", cins_combo),
            ("Resmi Küpe No", resmi_entry),
            ("Çiftlik Küpe No", ciftlik_entry),
        ]):
            tk.Label(form, text=label_text, bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=('Segoe UI', 9, 'bold')).grid(row=row, column=0, sticky="w", pady=9, padx=(0, 14))
            widget.grid(row=row, column=1, sticky="ew", pady=9, ipady=4)
        cins_combo.focus_set()
        
        def on_ok():
            cins = cins_combo.get()
            if not cins:
                messagebox.showerror("Hata", "Lütfen yavrunun cinsini seçin.", parent=dialog)
                return
            resmi = resmi_entry.get().strip().upper()
            ciftlik = ciftlik_entry.get().strip().upper()
            result['cins'] = cins
            result['resmi_kupe_no'] = resmi
            result['ciftlik_kupe_no'] = ciftlik
            result['kupe'] = ciftlik or resmi
            dialog.destroy()
        
        def on_cancel():
            result['cins'] = None 
            dialog.destroy()

        btn_frame = self.popup_buton_bar(kart)
        self.modern_buton(btn_frame, "Tamam", on_ok, purpose='success', width=13, small=True).pack(side='right', padx=(8, 0))
        self.modern_buton(btn_frame, "İptal", on_cancel, purpose='default', width=13, small=True).pack(side='right')
        
        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        dialog.grab_set()
        self.pencere_ortala(dialog, parent)
        parent.wait_window(dialog)
        return result if result.get('cins') is not None else None

    def dogum_kayit_olustur(self, anne_kupe, detay_pencere):
        if detay_pencere:
            detay_pencere.destroy()
            
        hayvan = self.hayvanlar.get(anne_kupe, {})
        gorunen_kupe = hayvan.get('ciftlik_kupe_no') or hayvan.get('resmi_kupe_no') or anne_kupe
        
        dogum_window = tk.Toplevel(self.root)
        dogum_window.title(f"Doğum Kaydı - {gorunen_kupe}")
        dogum_window.geometry("760x680")
        dogum_window.minsize(620, 600)
        dogum_window.configure(bg=self.renkler["arkaplan"])
        dogum_window.transient(self.root)
        dogum_window.grab_set()

        title_frame = tk.Frame(dogum_window, bg=self.renkler["ana_kirmizi"], height=80)
        title_frame.pack(fill='x', expand=False)
        title_frame.pack_propagate(False)
        tk.Label(title_frame, text=f"{anne_kupe} - Yeni Doğum Kaydı", bg=self.renkler["ana_kirmizi"], fg=self.renkler["beyaz"], font=('Segoe UI', 18, 'bold')).pack(expand=True)
        
        body = self.kaydirilabilir_sayfa(dogum_window, padx=0, pady=0)
        form_kart = self.modern_kart(body)
        form_kart.pack(fill='both', expand=True, padx=25, pady=25)
        
        form_frame = tk.Frame(form_kart, bg=self.renkler["kart_arkaplan"], padx=40, pady=30)
        form_frame.pack(fill='both', expand=True)
        
        tk.Label(form_frame, text="DOĞUM BİLGİLERİ", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 16, 'bold')).pack(pady=10)
        
        tk.Label(form_frame, text="Doğum Tarihi:", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 12, 'bold')).pack(pady=(15, 5))
        dogum_tarih_entry = ttk.Entry(form_frame, font=('Segoe UI', 11), width=25, justify='center', style='TEntry')
        dogum_tarih_entry.pack(pady=5)
        dogum_tarih_entry.insert(0, datetime.now().strftime("%d/%m/%Y"))

        tk.Label(form_frame, text="Yavru Sayısı:", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 12, 'bold')).pack(pady=(15, 5))
        yavru_sayi_entry = ttk.Entry(form_frame, font=('Segoe UI', 11), width=25, justify='center', style='TEntry')
        yavru_sayi_entry.pack(pady=5)
        yavru_sayi_entry.insert(0, "1")
        
        tk.Label(form_frame, text="1. Yavru Cinsi:", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 12, 'bold')).pack(pady=(15, 5))
        yavru_cins_combo = ttk.Combobox(form_frame, values=["Dişi Buzağı", "Erkek Buzağı"], width=22, font=('Segoe UI', 11), justify='center', style='TCombobox')
        yavru_cins_combo.pack(pady=5)
        
        ilk_yavru_kimlik = tk.Frame(form_frame, bg=self.renkler["kart_arkaplan"])
        ilk_yavru_kimlik.pack(fill="x", pady=(15, 5))
        ilk_yavru_kimlik.columnconfigure((0, 1), weight=1)
        self.themed_widgets.append((ilk_yavru_kimlik, 'kart'))
        tk.Label(ilk_yavru_kimlik, text="1. Yavru Resmi Küpe No", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 11, 'bold')).grid(row=0, column=0, sticky="w", padx=(0, 10))
        tk.Label(ilk_yavru_kimlik, text="1. Yavru Çiftlik Küpe No", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 11, 'bold')).grid(row=0, column=1, sticky="w", padx=(10, 0))
        yavru_resmi_kupe_entry = ttk.Entry(ilk_yavru_kimlik, font=('Segoe UI', 11), style='TEntry')
        yavru_ciftlik_kupe_entry = ttk.Entry(ilk_yavru_kimlik, font=('Segoe UI', 11), style='TEntry')
        yavru_resmi_kupe_entry.grid(row=1, column=0, sticky="ew", padx=(0, 10), pady=(5, 0), ipady=3)
        yavru_ciftlik_kupe_entry.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(5, 0), ipady=3)
        
        btn_frame = tk.Frame(form_frame, bg=self.renkler["kart_arkaplan"])
        btn_frame.pack(pady=30)
        
        def dogum_kaydet():
            try:
                try:
                    yavru_sayisi = int(yavru_sayi_entry.get())
                    if yavru_sayisi < 1: raise ValueError
                except (ValueError, TypeError):
                    return messagebox.showerror("Hata", "Lütfen geçerli bir yavru sayısı girin (en az 1).", parent=dogum_window)

                yavrular_data = []
                
                ilk_yavru_cins = yavru_cins_combo.get()
                if not ilk_yavru_cins: return messagebox.showerror("Hata", "1. yavrunun cinsi zorunludur!", parent=dogum_window)
                yavrular_data.append({
                    'cins': ilk_yavru_cins,
                    'resmi_kupe_no': yavru_resmi_kupe_entry.get().strip().upper(),
                    'ciftlik_kupe_no': yavru_ciftlik_kupe_entry.get().strip().upper(),
                    'kupe': yavru_ciftlik_kupe_entry.get().strip().upper() or yavru_resmi_kupe_entry.get().strip().upper()
                })

                for i in range(2, yavru_sayisi + 1):
                    yavru_detaylari = self._ask_calf_details(dogum_window, i)
                    if yavru_detaylari is None:
                        return messagebox.showwarning("İptal Edildi", "Doğum kaydı işlemi iptal edildi.", parent=dogum_window)
                    yavrular_data.append(yavru_detaylari)
                
                dogum_tarihi = dogum_tarih_entry.get().strip()
                dogum_dt = self.tarih_coz(dogum_tarihi, "Doğum tarihi", parent=dogum_window)
                if dogum_dt is None:
                    return
                
                anne_hayvan = self.hayvanlar[anne_kupe]
                anne_dogum_dt = self.tarih_coz(anne_hayvan.get('dogum_tarihi', ''), "Anne doğum tarihi", parent=dogum_window)
                if anne_dogum_dt is None:
                    return
                if dogum_dt < anne_dogum_dt:
                    return messagebox.showerror("Hata", "Doğum tarihi, annenin doğum tarihinden önce olamaz.", parent=dogum_window)
                if anne_hayvan.get('gebelik_tarihi'):
                    gebelik_dt = self.tarih_coz(anne_hayvan['gebelik_tarihi'], "Gebelik başlangıç tarihi", parent=dogum_window)
                    if gebelik_dt is None:
                        return
                    if dogum_dt < gebelik_dt:
                        return messagebox.showerror("Hata", "Doğum tarihi, gebelik başlangıç tarihinden önce olamaz.", parent=dogum_window)
                
                temp_kupe_list = []
                for yavru in yavrular_data:
                    alanlar = ('resmi_kupe_no', 'ciftlik_kupe_no')
                    if not any(str(yavru.get(alan) or "").strip() for alan in alanlar):
                        alanlar = ('kupe',)
                    for alan in alanlar:
                        deger = str(yavru.get(alan) or "").strip().upper()
                        if deger:
                            temp_kupe_list.append(deger)
                if len(temp_kupe_list) != len(set(temp_kupe_list)):
                    return messagebox.showerror("Hata", "Yavrular için aynı küpe numarasını birden fazla kez girdiniz.", parent=dogum_window)

                for yavru in yavrular_data:
                    for alan in ('resmi_kupe_no', 'ciftlik_kupe_no'):
                        kupe = str(yavru.get(alan) or "").strip().upper()
                        if kupe and self.hayvan_id_bul(kupe):
                            return messagebox.showerror("Hata", f"Yavru küpe numarası '{kupe}' zaten başka bir hayvana kayıtlı!", parent=dogum_window)

                self.islem_kaydi_baslat(f"Doğum kaydı oluşturuldu: {anne_kupe}")
                kaydedilen_yavrular_bilgi = []
                degisen_hayvan_idleri = [anne_kupe]
                for i, yavru_data in enumerate(yavrular_data):
                    yeni_yavru_id = uuid.uuid4().hex
                    degisen_hayvan_idleri.append(yeni_yavru_id)
                    yavru_resmi = str(yavru_data.get('resmi_kupe_no') or "").strip().upper()
                    yavru_ciftlik = str(yavru_data.get('ciftlik_kupe_no') or "").strip().upper()
                    yavru_gorunen = yavru_ciftlik or yavru_resmi
                    self.hayvanlar[yeni_yavru_id] = {
                        'kupe_no': yavru_gorunen or yeni_yavru_id,
                        'resmi_kupe_no': yavru_resmi,
                        'ciftlik_kupe_no': yavru_ciftlik,
                        'dogum_tarihi': dogum_tarihi, 'cins': yavru_data['cins'], 'anne_kupe': anne_kupe,
                        'kayit_tarihi': datetime.now().strftime("%d/%m/%Y %H:%M:%S"), 'yas_gun': (datetime.now() - dogum_dt).days, 'tohumlamalar': [], 'dogumlar': [],
                        'durum': 'Buzağı', 'gebe_mi': False, 'gebelik_tarihi': None, 'aktif_tohumlama_id': None, 'olu': False, 'olum_tarihi': None,
                        'kesildi': False, 'kesim_bilgisi': None, 'satildi': False, 'satis_tarihi': None, 'satis_bilgisi': None,
                        'asi_prosedurler': [], 'arsivli': False, 'arsiv_tarihi': None, 'foto_data': None, 'son_guncelleme': datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    }
                    kaydedilen_yavrular_bilgi.append({
                        'kupe': yavru_gorunen or yeni_yavru_id,
                        'resmi_kupe_no': yavru_resmi,
                        'ciftlik_kupe_no': yavru_ciftlik,
                        'cins': yavru_data['cins'],
                    })
                
                dogum_bilgisi = {
                    'tarih': dogum_tarihi,
                    'yavrular': kaydedilen_yavrular_bilgi,
                    'laktasyon_bitis_tarihi': None
                }
                if 'dogumlar' not in anne_hayvan:
                    anne_hayvan['dogumlar'] = []
                anne_hayvan['dogumlar'].append(dogum_bilgisi)

                if not anne_hayvan.get('olu', False):
                    anne_hayvan.update({
                        'gebe_mi': False, 
                        'gebelik_tarihi': None, 
                        'aktif_tohumlama_id': None, 
                        'cins': 'Sağmal İnek', 
                        'durum': 'Sağmal İnek',
                    })
                
                self.veri_kaydet_coklu(degisen_hayvan_idleri)
                kaydedilen_kupeler = [y['kupe'] for y in kaydedilen_yavrular_bilgi]
                messagebox.showinfo("Başarılı", f"Doğum kaydı başarılı!\nKaydedilen Yavrular: {', '.join(kaydedilen_kupeler)}")
                dogum_window.destroy()
                self.hayvan_listesini_guncelle()
                self.raporlari_guncelle()

            except Exception as e:
                messagebox.showerror("Hata", f"Doğum kaydı sırasında bir hata oluştu: {str(e)}", parent=dogum_window)

        self.modern_buton(btn_frame, "DOĞUM KAYDET", dogum_kaydet, purpose='success').pack(side='left', padx=15)
        self.modern_buton(btn_frame, "İPTAL", dogum_window.destroy, purpose='danger').pack(side='left', padx=15)

    def kuruda_yap(self, kupe_no, pencere):
        if kupe_no not in self.hayvanlar: return
        
        hayvan = self.hayvanlar[kupe_no]
        self.islem_kaydi_baslat(f"Kuruya ayrıldı: {kupe_no}")

        if 'dogumlar' in hayvan and hayvan['dogumlar']:
            for dogum in reversed(hayvan['dogumlar']):
                if dogum.get('laktasyon_bitis_tarihi') is None:
                    dogum['laktasyon_bitis_tarihi'] = datetime.now().strftime("%d/%m/%Y")
                    break
        
        hayvan.update({
            'durum': 'Kuru İnek', 'cins': 'Kuru İnek',
        })
        
        self.veri_kaydet(kupe_no=kupe_no)
        messagebox.showinfo("Başarılı", f"{kupe_no} numaralı hayvan kuruya ayrıldı!")
        pencere.destroy()
        self.hayvan_listesini_guncelle()
        self.raporlari_guncelle()

    def hayvan_oldu(self, kupe_no, pencere):
        if messagebox.askyesno("Onay", f"{kupe_no} numaralı hayvanın öldüğünü onaylıyor musunuz?\nBu işlem geri alınamaz!"):
            self.islem_kaydi_baslat(f"Öldü işaretlendi: {kupe_no}")
            self.hayvanlar[kupe_no].update({
                'olu': True, 'olum_tarihi': datetime.now().strftime("%d/%m/%Y"), 'durum': 'Ölü', 'gebe_mi': False,
                'gebelik_tarihi': None, 'aktif_tohumlama_id': None,
                'son_guncelleme': datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            })
            self.veri_kaydet(kupe_no=kupe_no)
            messagebox.showinfo("Başarılı", f"{kupe_no} numaralı hayvan öldü olarak işaretlendi.")
            pencere.destroy()
            self.hayvan_listesini_guncelle()
            self.raporlari_guncelle()

    def hayvan_kesildi(self, kupe_no, pencere):
        if not messagebox.askyesno("Onay", f"'{kupe_no}' küpeli hayvanın kesildiğini kaydetmek istediğinizden emin misiniz?"):
            return
        
        kilo_str = simpledialog.askstring("Kesim Kilogramı", "Hayvanın kesildiği ağırlığı (kg) girin:", parent=pencere)
        
        if kilo_str:
            try:
                kilo = float(kilo_str.replace(',', '.'))
                if kilo <= 0: raise ValueError
            except (ValueError, TypeError):
                messagebox.showerror("Geçersiz Değer", "Lütfen geçerli bir kilo değeri girin.", parent=pencere)
                return
            
            hayvan = self.hayvanlar[kupe_no]
            self.islem_kaydi_baslat(f"Kesildi işaretlendi: {kupe_no}")
            kesim_yasi_gun = hayvan.get('yas_gun', 0)
            
            kesim_bilgisi = {"tarih": datetime.now().strftime("%d/%m/%Y"), "kilo": kilo, "yas_gun": kesim_yasi_gun}

            hayvan.update({
                'kesildi': True, 'durum': 'Kesildi', 'kesim_bilgisi': kesim_bilgisi, 'gebe_mi': False,
                'gebelik_tarihi': None, 'aktif_tohumlama_id': None,
                'son_guncelleme': datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            })

            self.veri_kaydet(kupe_no=kupe_no)
            messagebox.showinfo("Başarılı", f"{kupe_no} küpeli hayvan kesildi olarak kaydedildi.")
            pencere.destroy()
            self.hayvan_listesini_guncelle()
            self.raporlari_guncelle()

    def hayvan_satildi(self, kupe_no, pencere):
        if kupe_no not in self.hayvanlar:
            return
        gorunen = self.hayvan_gorunen_kupe(kupe_no, self.hayvanlar[kupe_no])
        if not messagebox.askyesno(
            "Satıldı",
            f"{gorunen} numaralı hayvan satıldı olarak işaretlensin mi?\n\nBu hayvan aktif sürüden çıkarılır ve sadece 'Satıldı' filtresinde görünür.",
            parent=pencere,
        ):
            return
        not_metin = simpledialog.askstring(
            "Satış Notu",
            "Satış notu veya fiyat bilgisi (isteğe bağlı):",
            parent=pencere,
        )
        bugun = datetime.now().strftime("%d/%m/%Y")
        hayvan = self.hayvanlar[kupe_no]
        self.islem_kaydi_baslat(f"Satıldı işaretlendi: {gorunen}")
        satis_bilgisi = {"tarih": bugun}
        if not_metin:
            satis_bilgisi["not"] = not_metin.strip()
        hayvan.update({
            'satildi': True,
            'satis_tarihi': bugun,
            'satis_bilgisi': satis_bilgisi,
            'durum': 'Satıldı',
            'gebe_mi': False,
            'gebelik_tarihi': None,
            'aktif_tohumlama_id': None,
            'son_guncelleme': datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        })
        self.veri_kaydet(kupe_no=kupe_no)
        messagebox.showinfo("Satıldı", f"{gorunen} satıldı olarak kaydedildi.", parent=pencere)
        pencere.destroy()
        self.hayvan_listesini_guncelle()
        self.raporlari_guncelle()

    def hayvan_sil_detay(self, kupe_no, pencere):
        if kupe_no not in self.hayvanlar:
            return
        hayvan = self.hayvanlar[kupe_no]
        if hayvan.get('olu') or hayvan.get('kesildi') or hayvan.get('satildi'):
            gorunen = self.hayvan_gorunen_kupe(kupe_no, hayvan)
            messagebox.showwarning(
                "Arşivlenemez",
                f"{gorunen} aktif sürüde olmadığı için arşive alınamaz.",
                parent=pencere or self.root,
            )
            return
        uyari = f"DİKKAT!\n\n{kupe_no} küpeli hayvan aktif sürüden arşive alınacak.\n\nKayıt geçmişi korunur; hayvan listesinde sadece 'Arşivli' filtresinde görünür."
        if messagebox.askyesno("Hayvan Arşivleme Onayı", uyari):
            self.islem_kaydi_baslat(f"Hayvan arşive alındı: {kupe_no}")
            self.hayvanlar[kupe_no].update({
                'arsivli': True,
                'arsiv_tarihi': datetime.now().strftime("%d/%m/%Y"),
                'durum': 'Arşivli',
                'gebe_mi': False,
                'gebelik_tarihi': None,
                'aktif_tohumlama_id': None,
                'son_guncelleme': datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            })
            self.veri_kaydet(kupe_no=kupe_no)
            messagebox.showinfo("Başarılı", f"{kupe_no} numaralı hayvan arşive alındı.")
            pencere.destroy()
            self.hayvan_listesini_guncelle()
            self.raporlari_guncelle()

    def hayvan_arsivden_cikar(self, kupe_no, pencere=None):
        if kupe_no not in self.hayvanlar:
            return
        hayvan = self.hayvanlar[kupe_no]
        gorunen = self.hayvan_gorunen_kupe(kupe_no, hayvan)
        if not hayvan.get('arsivli', False):
            return messagebox.showinfo("Arşivden Çıkar", f"{gorunen} zaten aktif listede.", parent=pencere or self.root)
        if hayvan.get('olu') or hayvan.get('kesildi') or hayvan.get('satildi'):
            return messagebox.showwarning(
                "Arşivden Çıkarılamaz",
                f"{gorunen} satılmış, kesilmiş veya ölü olduğu için aktif sürüye alınamaz.",
                parent=pencere or self.root,
            )
        if not messagebox.askyesno(
            "Arşivden Çıkar",
            f"{gorunen} arşivden çıkarılıp aktif sürü listesine alınsın mı?",
            parent=pencere or self.root,
        ):
            return
        self.islem_kaydi_baslat(f"Hayvan arşivden çıkarıldı: {gorunen}")
        hayvan['arsivli'] = False
        hayvan['arsiv_tarihi'] = None
        hayvan['son_guncelleme'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        if not hayvan.get('olu') and not hayvan.get('kesildi'):
            hayvan['durum'] = self.durum_hesapla(hayvan.get('cins'), hayvan.get('yas_gun', 0))
            self.hayvan_gebelik_durumunu_senkronla(kupe_no)
        self.veri_kaydet(kupe_no=kupe_no)
        messagebox.showinfo("Arşivden Çıkar", f"{gorunen} aktif sürü listesine alındı.", parent=pencere or self.root)
        if pencere is not None and pencere is not self.root:
            try:
                pencere.destroy()
            except tk.TclError:
                pass
        self.ekranlari_guncelle()

    def hayvan_fotograf_sec(self, kupe_no, pencere=None):
        if kupe_no not in self.hayvanlar:
            return
        parent = pencere or self.root
        hayvan = self.hayvanlar[kupe_no]
        mevcut_fotograflar = self.hayvan_fotograflari(hayvan)
        if len(mevcut_fotograflar) >= 3:
            messagebox.showwarning("Fotoğraf", "Bu hayvan için en fazla 3 fotoğraf eklenebilir.", parent=parent)
            return
        kalan_slot = 3 - len(mevcut_fotograflar)
        dosyalar = filedialog.askopenfilenames(
            title="Hayvan fotoğrafı seç",
            parent=parent,
            filetypes=[("Görsel dosyaları", "*.jpg *.jpeg *.png *.webp *.bmp"), ("Tüm dosyalar", "*.*")]
        )
        if not dosyalar:
            return
        gorunen = self.hayvan_gorunen_kupe(kupe_no, hayvan)
        try:
            yeni_fotograflar = []
            for dosya in list(dosyalar)[:kalan_slot]:
                yeni_fotograflar.append(self.foto_data_olustur(dosya))
            if not yeni_fotograflar:
                return
            self.hayvan_fotograflari_ata(hayvan, mevcut_fotograflar + yeni_fotograflar)
            hayvan['son_guncelleme'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            self.islem_kaydi_baslat(f"Hayvan fotoğrafı eklendi: {gorunen} ({len(yeni_fotograflar)} adet)")
            self.veri_kaydet(kupe_no=kupe_no)
            self.ekranlari_guncelle()
            if pencere is not None and pencere is not self.root:
                try:
                    pencere.destroy()
                except tk.TclError:
                    pass
                self._track_after(self.root, 60, lambda: self.hayvan_detay_penceresi(kupe_no))
            else:
                messagebox.showinfo("Fotoğraf", f"{gorunen} için {len(yeni_fotograflar)} fotoğraf eklendi.", parent=parent)
        except Exception as e:
            messagebox.showerror("Fotoğraf", f"Fotoğraf eklenemedi:\n{e}", parent=parent)

    def hayvan_fotograf_sil(self, kupe_no, foto_index, pencere=None):
        if kupe_no not in self.hayvanlar:
            return
        parent = pencere or self.root
        hayvan = self.hayvanlar[kupe_no]
        fotograflar = self.hayvan_fotograflari(hayvan)
        if foto_index < 0 or foto_index >= len(fotograflar):
            return
        gorunen = self.hayvan_gorunen_kupe(kupe_no, hayvan)
        if not messagebox.askyesno("Fotoğrafı Sil", f"{gorunen} için seçili fotoğraf silinsin mi?", parent=parent):
            return
        fotograflar.pop(foto_index)
        self.hayvan_fotograflari_ata(hayvan, fotograflar)
        hayvan['son_guncelleme'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.islem_kaydi_baslat(f"Hayvan fotoğrafı silindi: {gorunen}")
        self.veri_kaydet(kupe_no=kupe_no)
        self.ekranlari_guncelle()
        if pencere is not None and pencere is not self.root:
            try:
                pencere.destroy()
            except tk.TclError:
                pass
            self._track_after(self.root, 60, lambda: self.hayvan_detay_penceresi(kupe_no))

    def hayvan_kalici_sil(self, kupe_no, pencere):
        if kupe_no not in self.hayvanlar:
            return
        uyari = f"DİKKAT!\n\n{kupe_no} küpeli arşivli hayvan kalıcı olarak silinecek.\n\nBu işlem geri alınamaz."
        if not messagebox.askyesno("Kalıcı Silme Onayı", uyari, parent=pencere):
            return
        silinen_hayvan = copy.deepcopy(self.hayvanlar.get(kupe_no) or {})
        degisen_anne_idleri, temizlenen_yavru_sayisi = self.silinen_hayvan_dogum_referanslarini_temizle(kupe_no, silinen_hayvan)
        self.islem_kaydi_baslat(
            f"Arşivli hayvan kalıcı silindi: {kupe_no}",
            geri_alinabilir=False,
            geri_alinamaz_neden="Kalıcı silinen hayvan geri getirilemez.",
        )
        api_modu = getattr(self, "api_modu", False)
        offline_senkron_gerekiyor = False
        if api_modu:
            if self.offline_modda_mi():
                self.bekleyen_senkron_delete(kupe_no)
                offline_senkron_gerekiyor = True
            else:
                try:
                    self.api_istek("DELETE", f"/api/hayvanlar/{self.api_ref(kupe_no)}?kalici=true", timeout=30)
                    onceki_idler = set(getattr(self, "_api_son_idler", set()))
                    onceki_idler.discard(str(kupe_no))
                    self._api_son_idler = onceki_idler
                except ApiHatasi as e:
                    if getattr(e, "status", None) != 404:
                        self.api_cevrimdisi = True
                        self._api_son_hata = str(e)
                        self.bekleyen_senkron_delete(kupe_no)
                        offline_senkron_gerekiyor = True
        del self.hayvanlar[kupe_no]
        if api_modu:
            if offline_senkron_gerekiyor:
                for anne_id in degisen_anne_idleri:
                    if anne_id in self.hayvanlar:
                        self.bekleyen_senkron_upsert(anne_id, self.hayvanlar[anne_id])
                self.bekleyen_senkron_kaydet()
            self.json_dosyasi_kaydet(self.data_file, self.hayvanlar, "hayvan_verileri", "API Önbellek Kayıt Hatası")
            self.api_durum_guncelle()
        else:
            self.veri_kaydet(kupe_no=kupe_no)
        ek = f"\nAnne doğum geçmişinden {temizlenen_yavru_sayisi} yavru bağlantısı temizlendi." if temizlenen_yavru_sayisi else ""
        messagebox.showinfo("Başarılı", f"{kupe_no} kalıcı olarak silindi.{ek}", parent=pencere)
        pencere.destroy()
        self.ekranlari_guncelle()



    def hayvan_gebelik_durumunu_senkronla(self, kupe_no):
        hayvan = self.hayvanlar.get(kupe_no)
        if not hayvan:
            return
        tohumlamalar = hayvan.get('tohumlamalar', [])
        son_tohumlama = tohumlamalar[-1] if tohumlamalar else None
        is_male = hayvan.get('cins') in ["Erkek Buzağı", "Dana"]

        if son_tohumlama and son_tohumlama.get('gebe_mi') is True and not is_male and not hayvan.get('olu') and not hayvan.get('kesildi') and not hayvan.get('arsivli') and not hayvan.get('satildi'):
            hayvan['gebe_mi'] = True
            hayvan['gebelik_tarihi'] = son_tohumlama.get('tarih')
            hayvan['aktif_tohumlama_id'] = son_tohumlama.get('id')
            if hayvan.get('durum') not in ['Sağmal İnek', 'Kuru İnek']:
                hayvan['durum'] = 'Gebe'
        else:
            hayvan['gebe_mi'] = False
            hayvan['gebelik_tarihi'] = None
            hayvan['aktif_tohumlama_id'] = None
            if not hayvan.get('olu') and not hayvan.get('kesildi') and not hayvan.get('arsivli') and not hayvan.get('satildi'):
                hayvan['durum'] = self.durum_hesapla(hayvan.get('cins'), hayvan.get('yas_gun', 0))

    def hayvan_duzenle_penceresi(self, kupe_no, detay_pencere=None):
        if kupe_no not in self.hayvanlar:
            return
        hayvan = self.hayvanlar[kupe_no]
        
        gorunen_kupe = hayvan.get('ciftlik_kupe_no') or hayvan.get('resmi_kupe_no') or kupe_no

        pencere = tk.Toplevel(self.root)
        pencere.title(f"Kayıt Düzenle - {gorunen_kupe}")
        pencere.geometry("950x700")
        pencere.minsize(820, 560)
        pencere.configure(bg=self.renkler["arkaplan"])
        pencere.transient(self.root)
        pencere.grab_set()

        notebook = ttk.Notebook(pencere, style='Modern.TNotebook')
        notebook.pack(fill='both', expand=True, padx=15, pady=15)

        genel_frame = ttk.Frame(notebook, style='TFrame')
        notebook.add(genel_frame, text="Genel Bilgiler")
        genel_kart = self.modern_kart(genel_frame)
        genel_kart.pack(fill='both', expand=True, padx=15, pady=15)

        kaydet_footer = tk.Frame(genel_kart, bg=self.renkler["kart_arkaplan"], padx=30, pady=14)
        kaydet_footer.pack(side='bottom', fill='x')
        self.themed_widgets.append((kaydet_footer, 'kart'))

        genel_scroll_alan = tk.Frame(genel_kart, bg=self.renkler["kart_arkaplan"])
        genel_scroll_alan.pack(side='top', fill='both', expand=True)
        self.themed_widgets.append((genel_scroll_alan, 'kart'))

        genel_canvas = tk.Canvas(genel_scroll_alan, bg=self.renkler["kart_arkaplan"], highlightthickness=0)
        genel_scrollbar = ttk.Scrollbar(genel_scroll_alan, orient='vertical', command=genel_canvas.yview)
        genel_canvas.configure(yscrollcommand=genel_scrollbar.set)
        genel_scrollbar.pack(side='right', fill='y')
        genel_canvas.pack(side='left', fill='both', expand=True)

        form = tk.Frame(genel_canvas, bg=self.renkler["kart_arkaplan"], padx=30, pady=24)
        form_window = genel_canvas.create_window((0, 0), window=form, anchor='nw')

        def genel_form_scroll_guncelle(event=None):
            genel_canvas.configure(scrollregion=genel_canvas.bbox("all"))

        def genel_canvas_genislik_guncelle(event):
            genel_canvas.itemconfigure(form_window, width=event.width)

        def genel_form_mousewheel(event):
            genel_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        form.bind("<Configure>", genel_form_scroll_guncelle)
        genel_canvas.bind("<Configure>", genel_canvas_genislik_guncelle)
        genel_canvas.bind("<MouseWheel>", genel_form_mousewheel)
        form.bind("<MouseWheel>", genel_form_mousewheel)
        form.columnconfigure(1, weight=1)

        resmi_kupe_entry = ttk.Entry(form, width=25, font=('Segoe UI', 11), style='TEntry')
        resmi_kupe_entry.insert(0, hayvan.get('resmi_kupe_no', ''))
        ciftlik_kupe_entry = ttk.Entry(form, width=25, font=('Segoe UI', 11), style='TEntry')
        ciftlik_kupe_entry.insert(0, hayvan.get('ciftlik_kupe_no', ''))
        dogum_entry = ttk.Entry(form, width=25, font=('Segoe UI', 11), style='TEntry')
        dogum_entry.insert(0, hayvan.get('dogum_tarihi', ''))
        dogum_entry.bind('<KeyRelease>', self.tarih_formatlama)
        cins_combo = ttk.Combobox(form, values=["Dişi Buzağı", "Erkek Buzağı", "Dana", "Düve", "Sağmal İnek", "Kuru İnek"], width=25, font=('Segoe UI', 11), style='TCombobox')
        cins_combo.set(hayvan.get('cins', ''))
        irk_combo = ttk.Combobox(form, values=self.hayvan_irk_secenekleri(), width=25, font=('Segoe UI', 11), style='TCombobox')
        irk_combo.set(hayvan.get('irk', ''))
        anne_entry = ttk.Entry(form, width=25, font=('Segoe UI', 11), style='TEntry')
        anne_entry.insert(0, hayvan.get('anne_kupe', ''))

        def edit_sagmal_mi(cins_degeri=None):
            deger = (cins_degeri if cins_degeri is not None else cins_combo.get()).strip()
            return deger in ["Sağmal İnek", "Kuru İnek"]

        def mevcut_laktasyon_bilgisi():
            dogumlar = hayvan.get('dogumlar') or []
            laktasyon_no = str(len(dogumlar)) if dogumlar else ""
            son_dogum = ""
            for dogum in reversed(dogumlar):
                tarih = (dogum.get('tarih') or '').strip()
                if tarih and tarih != "Bilinmiyor":
                    son_dogum = tarih
                    break
            return laktasyon_no, son_dogum

        for row, (label_text, widget) in enumerate([
            ("Resmi Küpe No", resmi_kupe_entry),
            ("Çiftlik Küpe No", ciftlik_kupe_entry),
            ("Doğum Tarihi", dogum_entry),
            ("Cinsi", cins_combo),
            ("Irk", irk_combo),
            ("Anne Resmi Küpe No", anne_entry),
        ]):
            label = tk.Label(form, text=label_text, bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 12, 'bold'))
            label.grid(row=row, column=0, sticky='w', pady=12, padx=(0, 20))
            widget.grid(row=row, column=1, sticky='ew', pady=12)

        laktasyon_frame = tk.Frame(form, bg=self.renkler["kart_ikincil"], padx=14, pady=12, highlightthickness=1, highlightbackground=self.renkler["kenarlik"])
        laktasyon_frame.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(8, 10))
        laktasyon_frame.columnconfigure(1, weight=1)
        laktasyon_frame.columnconfigure(3, weight=1)
        self.themed_widgets.append((laktasyon_frame, 'kart2'))
        tk.Label(laktasyon_frame, text="Eksik sağmal bilgisi", bg=self.renkler["kart_ikincil"], fg=self.renkler["muted"], font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, columnspan=5, sticky='w', pady=(0, 8))

        mevcut_laktasyon_no, mevcut_son_dogum = mevcut_laktasyon_bilgisi()
        laktasyon_no_edit_entry = ttk.Entry(laktasyon_frame, width=12, font=('Segoe UI', 11), style='TEntry')
        laktasyon_no_edit_entry.insert(0, mevcut_laktasyon_no)
        son_dogum_edit_entry = ttk.Entry(laktasyon_frame, width=16, font=('Segoe UI', 11), style='TEntry')
        son_dogum_edit_entry.insert(0, mevcut_son_dogum)
        son_dogum_edit_entry.bind('<KeyRelease>', self.tarih_formatlama)

        tk.Label(laktasyon_frame, text="Laktasyon Numarası", bg=self.renkler["kart_ikincil"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 10, 'bold')).grid(row=1, column=0, sticky='w', padx=(0, 10))
        laktasyon_no_edit_entry.grid(row=1, column=1, sticky='ew', padx=(0, 18))
        tk.Label(laktasyon_frame, text="Son Doğum Tarihi", bg=self.renkler["kart_ikincil"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 10, 'bold')).grid(row=1, column=2, sticky='w', padx=(0, 10))
        son_dogum_edit_entry.grid(row=1, column=3, sticky='ew')
        self.modern_buton(laktasyon_frame, "Takvim", lambda: self.tarih_secici_ac(son_dogum_edit_entry), purpose='default', small=True).grid(row=1, column=4, sticky='e', padx=(10, 0))

        def laktasyon_panel_guncelle(event=None):
            if edit_sagmal_mi():
                laktasyon_frame.grid()
            else:
                laktasyon_frame.grid_remove()

        cins_combo.bind("<<ComboboxSelected>>", laktasyon_panel_guncelle, add="+")
        cins_combo.bind("<KeyRelease>", laktasyon_panel_guncelle, add="+")
        laktasyon_panel_guncelle()

        foto_frame = tk.Frame(form, bg=self.renkler["kart_arkaplan"])
        foto_frame.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        foto_frame.columnconfigure(1, weight=1)
        self.themed_widgets.append((foto_frame, 'kart'))
        tk.Label(foto_frame, text="Fotoğraf", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 12, 'bold')).grid(row=0, column=0, sticky="nw", padx=(0, 20))
        foto_preview = tk.Label(foto_frame, text="Fotoğraf yok", bg=self.renkler["kart_ikincil"], fg=self.renkler["muted"], width=22, height=5, highlightthickness=1, highlightbackground=self.renkler["kenarlik"])
        foto_preview.grid(row=0, column=1, sticky="w")
        duzenle_fotograflar = self.hayvan_fotograflari(hayvan)
        self.foto_onizleme_guncelle(foto_preview, duzenle_fotograflar[0] if duzenle_fotograflar else None, max_size=(160, 100))
        foto_sayac_label = tk.Label(foto_frame, text=f"{len(duzenle_fotograflar)}/3 fotoğraf", bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=('Segoe UI', 9, 'bold'))
        foto_sayac_label.grid(row=1, column=1, sticky="w", pady=(6, 0))
        foto_btn = tk.Frame(foto_frame, bg=self.renkler["kart_arkaplan"])
        foto_btn.grid(row=0, column=2, sticky="e", padx=(14, 0))
        self.themed_widgets.append((foto_btn, 'kart'))

        def duzenle_foto_onizleme():
            fotograflar = self.hayvan_fotograflari(hayvan)
            self.foto_onizleme_guncelle(foto_preview, fotograflar[0] if fotograflar else None, max_size=(160, 100))
            foto_sayac_label.config(text=f"{len(fotograflar)}/3 fotoğraf")

        def foto_sec():
            fotograflar = self.hayvan_fotograflari(hayvan)
            if len(fotograflar) >= 3:
                return messagebox.showwarning("Fotoğraf", "Bu hayvan için en fazla 3 fotoğraf eklenebilir.", parent=pencere)
            dosya = filedialog.askopenfilename(
                title="Hayvan fotoğrafı seç",
                parent=pencere,
                filetypes=[("Görsel dosyaları", "*.jpg *.jpeg *.png *.webp *.bmp"), ("Tüm dosyalar", "*.*")]
            )
            if not dosya:
                return
            try:
                self.hayvan_fotograflari_ata(hayvan, fotograflar + [self.foto_data_olustur(dosya)])
                hayvan['son_guncelleme'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                duzenle_foto_onizleme()
            except Exception as e:
                messagebox.showerror("Fotoğraf", f"Fotoğraf eklenemedi:\n{e}", parent=pencere)

        def foto_kaldir():
            self.hayvan_fotograflari_ata(hayvan, [])
            hayvan['son_guncelleme'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            duzenle_foto_onizleme()

        self.modern_buton(foto_btn, "Fotoğraf Ekle", foto_sec, purpose='primary', small=True).pack(pady=(0, 6))
        self.modern_buton(foto_btn, "Tümünü Kaldır", foto_kaldir, purpose='default', small=True).pack()

        def genel_kaydet():
            yeni_resmi = resmi_kupe_entry.get().strip().upper()
            yeni_ciftlik = ciftlik_kupe_entry.get().strip().upper()
            dogum_tarihi = dogum_entry.get().strip()
            yeni_cins = cins_combo.get().strip()
            yeni_irk = irk_combo.get().strip()
            anne_kupe = anne_entry.get().strip().upper()
            if not dogum_tarihi or not yeni_cins:
                return messagebox.showerror("Hata", "Doğum tarihi ve cins zorunludur.", parent=pencere)
            if not yeni_resmi and not yeni_ciftlik:
                return messagebox.showerror("Hata", "En az bir küpe numarası (Resmi veya Çiftlik) girmelisiniz.", parent=pencere)
            if self.kupe_cakismasi_var(yeni_resmi, yeni_ciftlik, haric_id=kupe_no, ciftlik_id=hayvan.get('ciftlik_id')):
                return messagebox.showerror("Hata", "Bu küpe numaralarından biri başka bir hayvanda kayıtlı.", parent=pencere)
                
            dogum_dt = self.tarih_coz(dogum_tarihi, "Doğum tarihi", parent=pencere)
            if dogum_dt is None:
                return

            yeni_dogumlar = None
            if yeni_cins in ["Sağmal İnek", "Kuru İnek"]:
                laktasyon_no_str = laktasyon_no_edit_entry.get().strip()
                son_dogum_tarihi = son_dogum_edit_entry.get().strip()
                if laktasyon_no_str or son_dogum_tarihi:
                    yeni_dogumlar = self.laktasyon_dogumlari_olustur(
                        yeni_cins,
                        laktasyon_no_str,
                        son_dogum_tarihi,
                        dogum_dt,
                        parent=pencere,
                        bos_birakilabilir=False
                    )
                    if yeni_dogumlar is None:
                        return

            self.islem_kaydi_baslat(f"Genel bilgiler düzenlendi: {kupe_no}")
            hayvan['resmi_kupe_no'] = yeni_resmi
            hayvan['ciftlik_kupe_no'] = yeni_ciftlik
            hayvan['dogum_tarihi'] = dogum_tarihi
            hayvan['cins'] = yeni_cins
            hayvan['irk'] = yeni_irk
            hayvan['anne_kupe'] = anne_kupe
            if yeni_dogumlar is not None:
                hayvan['dogumlar'] = yeni_dogumlar
            hayvan['yas_gun'] = (datetime.now() - dogum_dt).days
            if yeni_cins in ["Erkek Buzağı", "Dana"]:
                hayvan['gebe_mi'] = False
                hayvan['gebelik_tarihi'] = None
                hayvan['aktif_tohumlama_id'] = None
            self.hayvan_gebelik_durumunu_senkronla(kupe_no)
            hayvan['son_guncelleme'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            self.veri_kaydet(kupe_no=kupe_no)
            self.ekranlari_guncelle()
            messagebox.showinfo("Başarılı", "Genel bilgiler güncellendi.", parent=pencere)

        self.modern_buton(kaydet_footer, "GENEL BİLGİLERİ KAYDET", genel_kaydet, purpose='success').pack(side='right')

        tohumlama_frame = ttk.Frame(notebook, style='TFrame')
        notebook.add(tohumlama_frame, text="Tohumlama Geçmişi")
        toh_kart = self.modern_kart(tohumlama_frame)
        toh_kart.pack(fill='both', expand=True, padx=15, pady=15)

        toh_cols = ("#", "Tarih", "Şekil", "Suni İsim", "Sonuç")
        toh_tree = ttk.Treeview(toh_kart, columns=toh_cols, show='headings', style='Modern.Treeview')
        for col in toh_cols:
            toh_tree.heading(col, text=col)
            toh_tree.column(col, width=130, anchor='center')
        toh_tree.pack(fill='both', expand=True, padx=10, pady=10)

        def tohumlama_tree_yenile():
            for item in toh_tree.get_children():
                toh_tree.delete(item)
            for idx, tohumlama in enumerate(hayvan.get('tohumlamalar', [])):
                sonuc = "Beklemede"
                if tohumlama.get('gebe_mi') is True:
                    sonuc = "Pozitif"
                elif tohumlama.get('gebe_mi') is False:
                    sonuc = "Negatif"
                toh_tree.insert('', 'end', iid=str(idx), values=(idx + 1, tohumlama.get('tarih', ''), tohumlama.get('sekil', ''), tohumlama.get('suni_isim', ''), sonuc))

        def secili_tohumlama_index():
            secim = toh_tree.selection()
            if not secim:
                messagebox.showwarning("Uyarı", "Önce bir tohumlama kaydı seçin.", parent=pencere)
                return None
            return int(secim[0])

        def tohumlama_duzenle():
            idx = secili_tohumlama_index()
            if idx is None:
                return
            kayit = hayvan['tohumlamalar'][idx]
            dialog = tk.Toplevel(pencere)
            dialog.title("Tohumlama Düzenle")
            dialog.geometry("420x360")
            dialog.configure(bg=self.renkler["arkaplan"])
            dialog.transient(pencere)
            dialog.grab_set()

            alan = tk.Frame(dialog, bg=self.renkler["arkaplan"], padx=20, pady=20)
            alan.pack(fill='both', expand=True)
            tarih_entry = ttk.Entry(alan, style='TEntry')
            tarih_entry.insert(0, kayit.get('tarih', ''))
            tarih_entry.bind('<KeyRelease>', self.tarih_formatlama)
            sekil_combo = ttk.Combobox(alan, values=["Suni", "Boğa"], style='TCombobox')
            sekil_combo.set(kayit.get('sekil', ''))
            suni_entry = ttk.Entry(alan, style='TEntry')
            suni_entry.insert(0, kayit.get('suni_isim', ''))
            sonuc_combo = ttk.Combobox(alan, values=["Beklemede", "Pozitif", "Negatif"], style='TCombobox')
            sonuc_combo.set("Pozitif" if kayit.get('gebe_mi') is True else "Negatif" if kayit.get('gebe_mi') is False else "Beklemede")

            for row, (label_text, widget) in enumerate([("Tarih", tarih_entry), ("Şekil", sekil_combo), ("Suni İsim", suni_entry), ("Sonuç", sonuc_combo)]):
                tk.Label(alan, text=label_text, bg=self.renkler["arkaplan"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 11, 'bold')).grid(row=row, column=0, sticky='w', pady=8)
                widget.grid(row=row, column=1, sticky='ew', pady=8, padx=(12, 0))
            alan.columnconfigure(1, weight=1)

            def kaydet():
                tarih = tarih_entry.get().strip()
                tarih_dt = self.tarih_coz(tarih, "Tohumlama tarihi", parent=dialog)
                if tarih_dt is None:
                    return
                dogum_dt = self.tarih_coz(hayvan.get('dogum_tarihi', ''), "Hayvan doğum tarihi", parent=dialog)
                if dogum_dt is None:
                    return
                if tarih_dt < dogum_dt:
                    return messagebox.showerror("Hata", "Tohumlama tarihi doğum tarihinden önce olamaz.", parent=dialog)
                if hayvan.get('cins') in ["Dişi Buzağı", "Düve", "Sağmal İnek", "Kuru İnek"] and (tarih_dt - dogum_dt).days < 365:
                    return messagebox.showerror(
                        "Hata",
                        "Tohumlama tarihinde hayvan en az 12 aylık olmalıdır.",
                        parent=dialog,
                    )
                sekil = sekil_combo.get().strip()
                if sekil == "Suni" and not suni_entry.get().strip():
                    return messagebox.showerror("Hata", "Suni tohumlama ismi zorunludur.", parent=dialog)

                self.islem_kaydi_baslat(f"Tohumlama düzenlendi: {kupe_no}")
                kayit['tarih'] = tarih
                kayit['sekil'] = sekil
                kayit['suni_isim'] = suni_entry.get().strip() if sekil == "Suni" else ""
                sonuc = sonuc_combo.get()
                kayit['gebe_mi'] = True if sonuc == "Pozitif" else False if sonuc == "Negatif" else None
                kayit['kontrol_tarihi'] = datetime.now().strftime("%d/%m/%Y") if sonuc in ["Pozitif", "Negatif"] else None
                kayit['id'] = kayit.get('id') or uuid.uuid4().hex[:12]
                self.hayvan_gebelik_durumunu_senkronla(kupe_no)
                hayvan['son_guncelleme'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                self.veri_kaydet(kupe_no=kupe_no)
                tohumlama_tree_yenile()
                self.ekranlari_guncelle()
                dialog.destroy()

            self.modern_buton(alan, "KAYDET", kaydet, purpose='success').grid(row=5, column=0, columnspan=2, pady=18)

        def tohumlama_sil():
            idx = secili_tohumlama_index()
            if idx is None:
                return
            if not messagebox.askyesno("Sil", "Seçili tohumlama kaydı silinsin mi?", parent=pencere):
                return
            self.islem_kaydi_baslat(f"Tohumlama kaydı silindi: {kupe_no}")
            hayvan['tohumlamalar'].pop(idx)
            self.hayvan_gebelik_durumunu_senkronla(kupe_no)
            self.veri_kaydet(kupe_no=kupe_no)
            tohumlama_tree_yenile()
            self.ekranlari_guncelle()

        toh_btn = tk.Frame(toh_kart, bg=self.renkler["kart_arkaplan"])
        toh_btn.pack(pady=(0, 10))
        self.modern_buton(toh_btn, "DÜZENLE", tohumlama_duzenle, purpose='default').pack(side='left', padx=8)
        self.modern_buton(toh_btn, "SİL", tohumlama_sil, purpose='danger').pack(side='left', padx=8)
        tohumlama_tree_yenile()

        dogum_frame = ttk.Frame(notebook, style='TFrame')
        notebook.add(dogum_frame, text="Doğum/Laktasyon")
        dogum_kart = self.modern_kart(dogum_frame)
        dogum_kart.pack(fill='both', expand=True, padx=15, pady=15)
        dogum_cols = ("#", "Tarih", "Yavrular", "Laktasyon Bitiş")
        dogum_tree = ttk.Treeview(dogum_kart, columns=dogum_cols, show='headings', style='Modern.Treeview')
        for col in dogum_cols:
            dogum_tree.heading(col, text=col)
            dogum_tree.column(col, width=160 if col != "Yavrular" else 420, anchor='center')
        dogum_tree.pack(fill='both', expand=True, padx=10, pady=10)

        def dogum_tree_yenile():
            for item in dogum_tree.get_children():
                dogum_tree.delete(item)
            for idx, dogum in enumerate(hayvan.get('dogumlar', [])):
                if not self.dogum_gecmisi_gosterilmeli_mi(dogum):
                    continue
                yavrular = ", ".join([self.yavru_gorunen_kupe(y) for y in self.dogum_gorunur_yavrular(dogum)]) or "-"
                dogum_tree.insert('', 'end', iid=str(idx), values=(idx + 1, dogum.get('tarih', ''), yavrular, dogum.get('laktasyon_bitis_tarihi') or "Devam ediyor"))

        def secili_dogum_index():
            secim = dogum_tree.selection()
            if not secim:
                messagebox.showwarning("Uyarı", "Önce bir doğum kaydı seçin.", parent=pencere)
                return None
            return int(secim[0])

        def dogum_duzenle():
            idx = secili_dogum_index()
            if idx is None:
                return
            kayit = hayvan['dogumlar'][idx]
            dialog = tk.Toplevel(pencere)
            dialog.title("Doğum Düzenle")
            dialog.geometry("430x270")
            dialog.configure(bg=self.renkler["arkaplan"])
            dialog.transient(pencere)
            dialog.grab_set()
            alan = tk.Frame(dialog, bg=self.renkler["arkaplan"], padx=20, pady=20)
            alan.pack(fill='both', expand=True)
            tarih_entry = ttk.Entry(alan, style='TEntry')
            tarih_entry.insert(0, kayit.get('tarih', ''))
            tarih_entry.bind('<KeyRelease>', self.tarih_formatlama)
            bitis_entry = ttk.Entry(alan, style='TEntry')
            bitis_entry.insert(0, kayit.get('laktasyon_bitis_tarihi') or "")
            bitis_entry.bind('<KeyRelease>', self.tarih_formatlama)
            for row, (label_text, widget) in enumerate([("Doğum Tarihi", tarih_entry), ("Laktasyon Bitiş", bitis_entry)]):
                tk.Label(alan, text=label_text, bg=self.renkler["arkaplan"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 11, 'bold')).grid(row=row, column=0, sticky='w', pady=8)
                widget.grid(row=row, column=1, sticky='ew', pady=8, padx=(12, 0))
            alan.columnconfigure(1, weight=1)

            def kaydet():
                tarih = tarih_entry.get().strip()
                if tarih != "Bilinmiyor" and self.tarih_coz(tarih, "Doğum tarihi", parent=dialog) is None:
                    return
                bitis = bitis_entry.get().strip()
                if bitis and self.tarih_coz(bitis, "Laktasyon bitiş tarihi", parent=dialog) is None:
                    return
                anne_dogum = self.tarih_coz(
                    hayvan.get('dogum_tarihi', ''),
                    "Anne doğum tarihi",
                    parent=dialog,
                )
                yeni_dogum = (
                    self.tarih_coz(tarih, "Doğum tarihi", parent=dialog)
                    if tarih != "Bilinmiyor"
                    else None
                )
                yeni_bitis = (
                    self.tarih_coz(bitis, "Laktasyon bitiş tarihi", parent=dialog)
                    if bitis
                    else None
                )
                if anne_dogum and yeni_dogum and yeni_dogum < anne_dogum:
                    return messagebox.showerror(
                        "Hata",
                        "Doğum tarihi annenin doğum tarihinden önce olamaz.",
                        parent=dialog,
                    )
                if yeni_bitis and yeni_dogum and yeni_bitis < yeni_dogum:
                    return messagebox.showerror(
                        "Hata",
                        "Laktasyon bitiş tarihi doğum tarihinden önce olamaz.",
                        parent=dialog,
                    )
                self.islem_kaydi_baslat(f"Doğum kaydı düzenlendi: {kupe_no}")
                kayit['tarih'] = tarih
                kayit['laktasyon_bitis_tarihi'] = bitis or None
                hayvan['son_guncelleme'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                self.veri_kaydet(kupe_no=kupe_no)
                dogum_tree_yenile()
                self.ekranlari_guncelle()
                dialog.destroy()

            self.modern_buton(alan, "KAYDET", kaydet, purpose='success').grid(row=3, column=0, columnspan=2, pady=18)

        def dogum_sil():
            idx = secili_dogum_index()
            if idx is None:
                return
            if not messagebox.askyesno("Sil", "Seçili doğum/laktasyon kaydı silinsin mi? Yavru hayvan kayıtları silinmez.", parent=pencere):
                return
            self.islem_kaydi_baslat(f"Doğum kaydı silindi: {kupe_no}")
            hayvan['dogumlar'].pop(idx)
            self.veri_kaydet(kupe_no=kupe_no)
            dogum_tree_yenile()
            self.ekranlari_guncelle()

        def laktasyon_bilgisi_tamamla():
            if hayvan.get('cins') not in ["Sağmal İnek", "Kuru İnek"] and hayvan.get('durum') not in ["Sağmal İnek", "Kuru İnek"]:
                return messagebox.showinfo("Laktasyon", "Laktasyon bilgisi yalnızca sağmal veya kuru ineklerde kullanılır.", parent=pencere)

            dialog = tk.Toplevel(pencere)
            dialog.title("Laktasyon Bilgisi")
            dialog.geometry("460x300")
            dialog.configure(bg=self.renkler["arkaplan"])
            dialog.transient(pencere)
            dialog.grab_set()
            alan = tk.Frame(dialog, bg=self.renkler["arkaplan"], padx=22, pady=22)
            alan.pack(fill='both', expand=True)
            mevcut_dogumlar = hayvan.get('dogumlar') or []
            son_bilinen = ""
            for dogum in reversed(mevcut_dogumlar):
                tarih = (dogum.get('tarih') or '').strip()
                if tarih and tarih != "Bilinmiyor":
                    son_bilinen = tarih
                    break

            laktasyon_entry = ttk.Entry(alan, style='TEntry')
            laktasyon_entry.insert(0, str(len(mevcut_dogumlar)) if mevcut_dogumlar else "")
            son_dogum_entry = ttk.Entry(alan, style='TEntry')
            son_dogum_entry.insert(0, son_bilinen)
            son_dogum_entry.bind('<KeyRelease>', self.tarih_formatlama)

            for row, (label_text, widget) in enumerate([
                ("Laktasyon Numarası", laktasyon_entry),
                ("Son Doğum Tarihi", son_dogum_entry),
            ]):
                tk.Label(alan, text=label_text, bg=self.renkler["arkaplan"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 11, 'bold')).grid(row=row, column=0, sticky='w', pady=10)
                widget.grid(row=row, column=1, sticky='ew', pady=10, padx=(12, 0))
            self.modern_buton(alan, "Takvim", lambda: self.tarih_secici_ac(son_dogum_entry), purpose='default', small=True).grid(row=1, column=2, sticky='e', padx=(8, 0))
            alan.columnconfigure(1, weight=1)

            bilgi = tk.Label(
                alan,
                text="Eksik sağmal verisini tamamlamak için iki alanı birlikte doldurun.",
                bg=self.renkler["arkaplan"],
                fg=self.renkler["muted"],
                font=('Segoe UI', 9)
            )
            bilgi.grid(row=2, column=0, columnspan=2, sticky='w', pady=(2, 10))

            def kaydet():
                dogum_dt = self.tarih_coz(hayvan.get('dogum_tarihi', ''), "Hayvan doğum tarihi", parent=dialog)
                if dogum_dt is None:
                    return
                yeni_dogumlar = self.laktasyon_dogumlari_olustur(
                    hayvan.get('cins') or hayvan.get('durum'),
                    laktasyon_entry.get(),
                    son_dogum_entry.get(),
                    dogum_dt,
                    parent=dialog,
                    bos_birakilabilir=False
                )
                if yeni_dogumlar is None:
                    return
                if mevcut_dogumlar and not messagebox.askyesno(
                    "Laktasyon Bilgisi",
                    "Mevcut doğum/laktasyon kayıtları bu bilgiyle yeniden düzenlenecek. Devam edilsin mi?",
                    parent=dialog
                ):
                    return
                self.islem_kaydi_baslat(f"Laktasyon bilgisi tamamlandı: {kupe_no}")
                hayvan['dogumlar'] = yeni_dogumlar
                hayvan['son_guncelleme'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                self.veri_kaydet(kupe_no=kupe_no)
                dogum_tree_yenile()
                self.ekranlari_guncelle()
                dialog.destroy()

            self.modern_buton(alan, "LAKTASYON BİLGİSİNİ KAYDET", kaydet, purpose='success').grid(row=3, column=0, columnspan=2, pady=18)

        dogum_btn = tk.Frame(dogum_kart, bg=self.renkler["kart_arkaplan"])
        dogum_btn.pack(pady=(0, 10))
        self.modern_buton(dogum_btn, "BİLGİ TAMAMLA", laktasyon_bilgisi_tamamla, purpose='success').pack(side='left', padx=8)
        self.modern_buton(dogum_btn, "DÜZENLE", dogum_duzenle, purpose='default').pack(side='left', padx=8)
        self.modern_buton(dogum_btn, "SİL", dogum_sil, purpose='danger').pack(side='left', padx=8)
        dogum_tree_yenile()

    def profil_kart_olustur(self, parent, baslik=None, accent=None, padx=16, pady=14):
        kart = tk.Frame(
            parent,
            bg=self.renkler["kart_arkaplan"],
            highlightthickness=1,
            highlightbackground=self.renkler["kenarlik"],
        )
        if accent:
            tk.Frame(kart, bg=accent, height=3).pack(fill="x")
        govde = tk.Frame(kart, bg=self.renkler["kart_arkaplan"], padx=padx, pady=pady)
        govde.pack(fill="both", expand=True)
        if baslik:
            tk.Label(
                govde,
                text=baslik,
                bg=self.renkler["kart_arkaplan"],
                fg=self.renkler["yazi_rengi"],
                font=("Segoe UI", 13, "bold"),
            ).pack(anchor="w", pady=(0, 10))
        return kart, govde

    def profil_bilgi_satiri(self, parent, etiket, deger):
        satir = tk.Frame(parent, bg=self.renkler["kart_arkaplan"])
        satir.pack(fill="x", pady=3)
        tk.Label(
            satir,
            text=etiket,
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 9, "bold"),
            width=18,
            anchor="w",
        ).pack(side="left")
        tk.Label(
            satir,
            text=str(deger or "-"),
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["yazi_rengi"],
            font=("Segoe UI", 10),
            anchor="w",
            justify="left",
            wraplength=420,
        ).pack(side="left", fill="x", expand=True)

    def profil_metrik_karti(self, parent, baslik, deger, alt="", renk=None):
        renk = renk or self.renkler["button_primary_bg"]
        kart = tk.Frame(
            parent,
            bg=self.renkler["kart_ikincil"],
            highlightthickness=1,
            highlightbackground=self.renkler["kenarlik"],
            padx=14,
            pady=12,
        )
        tk.Label(
            kart,
            text=baslik.upper(),
            bg=self.renkler["kart_ikincil"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w")
        tk.Label(
            kart,
            text=str(deger),
            bg=self.renkler["kart_ikincil"],
            fg=renk,
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w", pady=(3, 0))
        if alt:
            tk.Label(
                kart,
                text=alt,
                bg=self.renkler["kart_ikincil"],
                fg=self.renkler["muted"],
                font=("Segoe UI", 8),
            ).pack(anchor="w", pady=(2, 0))
        return kart

    def profil_tablo_olustur(self, parent, kolonlar, genislikler=None, height=6):
        genislikler = genislikler or {}
        tablo_frame = tk.Frame(parent, bg=self.renkler["kart_arkaplan"])
        tablo_frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(tablo_frame, columns=kolonlar, show="headings", height=height, style="Modern.Treeview")
        for col in kolonlar:
            tree.heading(col, text=col)
            tree.column(col, width=genislikler.get(col, 120), minwidth=70, anchor="center", stretch=False)
        scroll_y = ttk.Scrollbar(tablo_frame, orient="vertical", command=tree.yview)
        scroll_x = ttk.Scrollbar(tablo_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        tablo_frame.grid_rowconfigure(0, weight=1)
        tablo_frame.grid_columnconfigure(0, weight=1)
        return tree

    def profil_durum_metni(self, hayvan):
        if hayvan.get("arsivli"):
            return "Arşivli"
        if hayvan.get("olu"):
            return "Ölü"
        if hayvan.get("kesildi"):
            return "Kesildi"
        if hayvan.get("satildi"):
            return "Satıldı"
        if hayvan.get("gebe_mi"):
            return "Gebe"
        return hayvan.get("durum") or "Hayatta"

    def profil_laktasyon_ozeti(self, hayvan):
        dogumlar = hayvan.get("dogumlar") or []
        toplam_sagim = 0
        aktif_sagim = "-"
        son_dogum = "-"
        for index, dogum in enumerate(dogumlar):
            tarih = dogum.get("tarih")
            if not tarih or tarih == "Bilinmiyor":
                continue
            try:
                baslangic = datetime.strptime(tarih, "%d/%m/%Y")
            except (ValueError, TypeError):
                continue
            son_dogum = tarih
            bitis = None
            if dogum.get("laktasyon_bitis_tarihi") and dogum.get("laktasyon_bitis_tarihi") != "Bilinmiyor":
                try:
                    bitis = datetime.strptime(dogum["laktasyon_bitis_tarihi"], "%d/%m/%Y")
                except (ValueError, TypeError):
                    bitis = None
            elif index == len(dogumlar) - 1 and hayvan.get("durum") == "Sağmal İnek":
                bitis = datetime.now()
                aktif_sagim = f"{max((bitis - baslangic).days, 0)} gün"
            if bitis:
                toplam_sagim += max((bitis - baslangic).days, 0)
        return {
            "laktasyon_sayisi": len(dogumlar),
            "toplam_sagim": toplam_sagim,
            "aktif_sagim": aktif_sagim,
            "son_dogum": son_dogum,
        }

    def profil_dogum_tahmini(self, hayvan):
        if not hayvan.get("gebe_mi") or not hayvan.get("gebelik_tarihi"):
            return "-", None
        try:
            gebelik = datetime.strptime(hayvan["gebelik_tarihi"], "%d/%m/%Y")
            dogum = gebelik + timedelta(days=283)
            return dogum.strftime("%d/%m/%Y"), (dogum - datetime.now()).days
        except (ValueError, TypeError):
            return "Tarih hatası", None

    def profil_uyarilari_hesapla(self, kupe_no, hayvan):
        uyarilar = []
        if hayvan.get("arsivli") or hayvan.get("olu") or hayvan.get("kesildi") or hayvan.get("satildi"):
            return uyarilar

        gorunen = self.hayvan_gorunen_kupe(kupe_no, hayvan)
        if self.sagmal_laktasyon_eksik_mi(hayvan):
            uyarilar.append(("Eksik veri", "Laktasyon numarası ve son doğum tarihi tamamlanmalı.", 0))

        son_tohumlama = (hayvan.get("tohumlamalar") or [None])[-1]
        if son_tohumlama and son_tohumlama.get("gebe_mi") is None:
            try:
                tarih = datetime.strptime(son_tohumlama.get("tarih", ""), "%d/%m/%Y")
                kontrol = tarih + timedelta(days=21)
                kalan = (kontrol - datetime.now()).days
                if kalan <= 7:
                    uyarilar.append(("Gebelik kontrol", f"{gorunen} için kontrol tarihi yaklaştı.", kalan))
            except (ValueError, TypeError):
                pass

        dogum_tahmini, kalan_dogum = self.profil_dogum_tahmini(hayvan)
        if kalan_dogum is not None:
            if kalan_dogum <= 60:
                uyarilar.append(("Doğum", f"Tahmini doğum: {dogum_tahmini}", kalan_dogum))
            if hayvan.get("durum") == "Sağmal İnek" and kalan_dogum <= 60:
                uyarilar.append(("Kuruya alma", "Kuruya alma zamanı kontrol edilmeli.", kalan_dogum))

        for prosedur in hayvan.get("asi_prosedurler") or []:
            sonraki = prosedur.get("sonraki_tarih")
            if not sonraki:
                continue
            try:
                tarih = datetime.strptime(sonraki, "%d/%m/%Y")
                kalan = (tarih - datetime.now()).days
                if kalan <= 30:
                    uyarilar.append((prosedur.get("ad") or "Aşı/Prosedür", f"Sonraki tarih: {sonraki}", kalan))
            except (ValueError, TypeError):
                pass
        return sorted(uyarilar, key=lambda item: item[2])

    def hayvan_detay_penceresi(self, kupe_no):
        hayvan_id = self.hayvan_id_bul(kupe_no) or kupe_no
        if hayvan_id not in self.hayvanlar:
            return
        mevcut = self.hayvanlar.get(hayvan_id, {})
        if (
            getattr(self, "api_modu", False)
            and mevcut.get("foto_paths")
            and not mevcut.get("foto_urls")
            and not mevcut.get("foto_datas")
            and not mevcut.get("foto_data")
        ):
            hayvan_id = self.api_hayvan_detayini_yukle(hayvan_id)
            if hayvan_id not in self.hayvanlar:
                return
        hayvan = self.hayvanlar[hayvan_id]
        cins = hayvan.get("cins", "")
        is_male = cins in ["Erkek Buzağı", "Dana"]
        gorunen_kupe = self.hayvan_gorunen_kupe(hayvan_id, hayvan)
        durum = self.profil_durum_metni(hayvan)
        yas_gun = max(int(hayvan.get("yas_gun", 0) or 0), 0)
        yas_metin = f"{yas_gun // 365} yıl {(yas_gun % 365) // 30} ay"
        laktasyon = self.profil_laktasyon_ozeti(hayvan)
        dogum_tahmini, kalan_dogum = self.profil_dogum_tahmini(hayvan)
        uyarilar = self.profil_uyarilari_hesapla(hayvan_id, hayvan)

        detay_window = tk.Toplevel(self.root)
        detay_window.title(f"Hayvan Profili - {gorunen_kupe}")
        detay_window.geometry("1360x820")
        detay_window.minsize(980, 680)
        detay_window.configure(bg=self.renkler["arkaplan"])
        detay_window.transient(self.root)
        detay_window.grab_set()

        def kapat():
            try:
                detay_window.grab_release()
            except tk.TclError:
                pass
            try:
                detay_window.destroy()
            except tk.TclError:
                pass

        detay_window.protocol("WM_DELETE_WINDOW", kapat)

        fotograflar = self.hayvan_fotograflari(hayvan)

        header = tk.Frame(detay_window, bg=self.renkler["siyah"], padx=22, pady=14)
        header.pack(fill="x")

        # ── header_top: grid ile başlık sol / butonlar sağ ──────────────────
        header_top = tk.Frame(header, bg=self.renkler["siyah"])
        header_top.pack(fill="x")
        header_top.grid_columnconfigure(0, weight=1)  # başlık esner
        header_top.grid_columnconfigure(1, weight=0)  # butonlar sabit

        sol_header = tk.Frame(header_top, bg=self.renkler["siyah"])
        sol_header.grid(row=0, column=0, sticky="w")
        tk.Label(
            sol_header,
            text=f"{gorunen_kupe} Hayvan Profili",
            bg=self.renkler["siyah"],
            fg=self.renkler["beyaz"],
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor="w")
        tk.Label(
            sol_header,
            text=f"{hayvan.get('cins') or '-'}  |  {durum}  |  Son güncelleme: {hayvan.get('son_guncelleme') or '-'}",
            bg=self.renkler["siyah"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(3, 0))

        # Aksiyon butonları — sağ sütunda, ortalanmış dikey
        aksiyon_frame = tk.Frame(header_top, bg=self.renkler["siyah"])
        aksiyon_frame.grid(row=0, column=1, sticky="se", padx=(14, 0), pady=(20, 0))

        aksiyonlar = [
            ("Düzenle", lambda: self.hayvan_duzenle_penceresi(hayvan_id, detay_window), "default"),
            ("Aşı/Prosedür", lambda: self.asi_prosedur_penceresi(hayvan_id, detay_window), "success"),
        ]
        aktif_hayvan = not hayvan.get("olu") and not hayvan.get("kesildi") and not hayvan.get("arsivli") and not hayvan.get("satildi")
        if self.hayvan_tohumlama_sonuclanabilir_mi(hayvan):
            aksiyonlar.append(("Tohumlamayı Sonuçla", lambda: self.tohumlama_sonuc_penceresi(hayvan_id, detay_window), "warning"))
        elif self.hayvan_tohumlanabilir_mi(hayvan):
            aksiyonlar.append(("Tohumla", lambda: self.tohumlama_ekranina_hayvanla_git(hayvan_id, detay_window), "primary"))
        if aktif_hayvan:
            if not is_male and hayvan.get("gebe_mi"):
                aksiyonlar.append(("Doğum Kaydet", lambda: self.dogum_kayit_olustur(hayvan_id, detay_window), "success"))
            if not is_male and hayvan.get("durum") == "Sağmal İnek":
                aksiyonlar.append(("Kuruya Ayır", lambda: self.kuruda_yap(hayvan_id, detay_window), "warning"))
            aksiyonlar.extend([
                ("Satıldı", lambda: self.hayvan_satildi(hayvan_id, detay_window), "warning"),
                ("Kesildi", lambda: self.hayvan_kesildi(hayvan_id, detay_window), "warning"),
                ("Öldü", lambda: self.hayvan_oldu(hayvan_id, detay_window), "danger"),
            ])
        if hayvan.get("arsivli"):
            if not hayvan.get("olu") and not hayvan.get("kesildi") and not hayvan.get("satildi"):
                aksiyonlar.append(("Arşivden Çıkar", lambda: self.hayvan_arsivden_cikar(hayvan_id, detay_window), "success"))
            aksiyonlar.append(("Kalıcı Sil", lambda: self.hayvan_kalici_sil(hayvan_id, detay_window), "danger"))
        elif aktif_hayvan:
            aksiyonlar.append(("Arşivle", lambda: self.hayvan_sil_detay(hayvan_id, detay_window), "danger"))
        aksiyonlar.append(("Kapat", kapat, "default"))

        # Butonları aksiyon_frame'e pack ile yerleştir (wrap için responsive)
        profil_butonlar = []
        for btn_metin, btn_komut, btn_amac in aksiyonlar:
            btn = self.modern_buton(aksiyon_frame, btn_metin, btn_komut, purpose=btn_amac, small=True)
            btn.pack(side="left", padx=(0, 6), pady=2)
            profil_butonlar.append(btn)

        # Ekran daraldığında butonlar 2. satıra (sol_header altına) taşınır
        ESIK = 900

        def profil_header_duzen(event=None):
            try:
                genislik = header_top.winfo_width()
                if genislik < 10:
                    return
                if genislik < ESIK:
                    # Dar: buton frame'i başlığın altına al
                    sol_header.grid(row=0, column=0, columnspan=2, sticky="w")
                    aksiyon_frame.grid(row=1, column=0, columnspan=2, sticky="w", pady=(12, 0))
                else:
                    # Geniş: yan yana
                    sol_header.grid(row=0, column=0, sticky="w")
                    aksiyon_frame.grid(row=0, column=1, sticky="se", padx=(14, 0), pady=(20, 0))
            except tk.TclError:
                pass

        header_top.bind("<Configure>", profil_header_duzen)

        # --- Rozetler: Yaş / Durum / Fotoğraf ─────────────────────────────
        rozetler = tk.Frame(header, bg=self.renkler["siyah"])
        rozetler.pack(anchor="w", pady=(10, 0))

        def header_rozet(baslik, deger, renk=None):
            renk = renk or self.renkler["button_primary_bg"]
            pill = tk.Frame(rozetler, bg=self.renkler["kart_ikincil"], padx=12, pady=7,
                            highlightthickness=1, highlightbackground=self.renkler["kenarlik"])
            pill.pack(side="left", padx=(0, 8))
            tk.Label(pill, text=baslik.upper(), bg=self.renkler["kart_ikincil"],
                     fg=self.renkler["muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
            tk.Label(pill, text=str(deger), bg=self.renkler["kart_ikincil"],
                     fg=renk, font=("Segoe UI", 12, "bold")).pack(anchor="w")

        header_rozet("Yaş", yas_metin)
        header_rozet("Durum", durum,
                     self.renkler["button_success_bg"] if durum not in {"Arşivli", "Ölü", "Kesildi", "Satıldı"}
                     else self.renkler["uyari"])
        header_rozet("Fotoğraf", f"{len(fotograflar)}/3")


        sayfa = self.kaydirilabilir_sayfa(detay_window, padx=22, pady=18)

        ust = tk.Frame(sayfa, bg=self.renkler["arkaplan"])
        ust.pack(fill="x")
        ust.grid_columnconfigure(0, weight=0)
        ust.grid_columnconfigure(1, weight=2)
        ust.grid_columnconfigure(2, weight=2)

        foto_kart, foto_body = self.profil_kart_olustur(ust, "Fotoğraflar", accent=self.renkler["button_primary_bg"])
        foto_kart.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        foto_grid = tk.Frame(foto_body, bg=self.renkler["kart_arkaplan"])
        foto_grid.pack(fill="both", expand=True)
        for col in range(3):
            foto_grid.grid_columnconfigure(col, weight=1)
        for idx in range(3):
            slot = tk.Frame(
                foto_grid,
                bg=self.renkler["kart_ikincil"],
                padx=6,
                pady=6,
                highlightthickness=1,
                highlightbackground=self.renkler["kenarlik"],
            )
            slot.grid(row=0, column=idx, sticky="nsew", padx=(0 if idx == 0 else 7, 0), pady=(0, 8))
            foto_canvas = tk.Canvas(
                slot,
                width=150,
                height=92,
                bg=self.renkler["input_bg"],
                highlightthickness=1,
                highlightbackground=self.renkler["kenarlik"],
                bd=0,
            )
            foto_canvas.pack(fill="both", expand=True)
            if idx < len(fotograflar):
                self.foto_slot_canvas_ciz(
                    foto_canvas,
                    fotograflar[idx],
                    idx + 1,
                    max_size=(150, 92),
                    open_callback=lambda f=fotograflar[idx], i=idx: self.fotograf_buyut_penceresi(
                        f,
                        f"{gorunen_kupe} - {i + 1}. Fotoğraf",
                        detay_window,
                    ),
                )
                alt_satir = tk.Frame(slot, bg=self.renkler["kart_ikincil"])
                alt_satir.pack(fill="x", pady=(6, 0))
                tk.Label(alt_satir, text=f"{idx + 1}. fotoğraf", bg=self.renkler["kart_ikincil"], fg=self.renkler["muted"], font=("Segoe UI", 8, "bold")).pack(side="left")
                self.modern_buton(alt_satir, "Sil", lambda i=idx: self.hayvan_fotograf_sil(hayvan_id, i, detay_window), purpose='danger', width=5, small=True).pack(side="right")
            else:
                self.foto_slot_canvas_ciz(foto_canvas, None, idx + 1, max_size=(150, 92))

        foto_alt = tk.Frame(foto_body, bg=self.renkler["kart_arkaplan"])
        foto_alt.pack(fill="x")
        tk.Label(
            foto_alt,
            text=f"{len(fotograflar)}/3 fotoğraf",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")
        if len(fotograflar) < 3:
            self.modern_buton(foto_alt, "Fotoğraf Ekle", lambda: self.hayvan_fotograf_sec(hayvan_id, detay_window), purpose='primary', small=True).pack(side="right")

        kimlik_kart, kimlik_body = self.profil_kart_olustur(ust, "Kimlik ve Durum", accent=self.renkler["button_success_bg"])
        kimlik_kart.grid(row=0, column=1, sticky="nsew", padx=(0, 14))
        self.profil_bilgi_satiri(kimlik_body, "Resmi Küpe", hayvan.get("resmi_kupe_no") or "-")
        self.profil_bilgi_satiri(kimlik_body, "Çiftlik Küpesi", hayvan.get("ciftlik_kupe_no") or "-")
        self.profil_bilgi_satiri(kimlik_body, "Doğum Tarihi", hayvan.get("dogum_tarihi") or "-")
        self.profil_bilgi_satiri(kimlik_body, "Yaş", yas_metin)
        self.profil_bilgi_satiri(kimlik_body, "Cinsi", hayvan.get("cins") or "-")
        self.profil_bilgi_satiri(kimlik_body, "Irk", hayvan.get("irk") or "-")
        self.profil_bilgi_satiri(kimlik_body, "Anne Resmi Küpe", hayvan.get("anne_kupe") or "Bilinmiyor")
        self.profil_bilgi_satiri(kimlik_body, "Durum", durum)

        metrik_kart, metrik_body = self.profil_kart_olustur(ust, "Özet", accent=self.renkler["uyari"])
        metrik_kart.grid(row=0, column=2, sticky="nsew")
        metrik_grid = tk.Frame(metrik_body, bg=self.renkler["kart_arkaplan"])
        metrik_grid.pack(fill="both", expand=True)
        for col in range(2):
            metrik_grid.grid_columnconfigure(col, weight=1)
        metrikler = [
            ("Durum", durum, hayvan.get("cins") or "-", self.renkler["button_success_bg"] if durum not in {"Arşivli", "Ölü", "Kesildi", "Satıldı"} else self.renkler["button_warning_bg"]),
            ("Doğum Tahmini", dogum_tahmini, f"{kalan_dogum} gün" if kalan_dogum is not None else "Gebe değil", self.renkler["uyari"]),
            ("Laktasyon", laktasyon["laktasyon_sayisi"], f"Son doğum: {laktasyon['son_dogum']}", self.renkler["button_primary_bg"]),
            ("Aktif Sağım", laktasyon["aktif_sagim"], f"Toplam: {laktasyon['toplam_sagim']} gün", self.renkler["button_success_bg"]),
        ]
        for idx, (baslik, deger, alt, renk) in enumerate(metrikler):
            kart = self.profil_metrik_karti(metrik_grid, baslik, deger, alt, renk)
            kart.grid(row=idx // 2, column=idx % 2, sticky="nsew", padx=5, pady=5)

        def profil_ust_yerlesim(event=None):
            try:
                genislik = min(max(ust.winfo_width(), 1), max(detay_window.winfo_width() - 60, 1))
                for kart in (foto_kart, kimlik_kart, metrik_kart):
                    kart.grid_forget()
                for col in range(3):
                    ust.grid_columnconfigure(col, weight=0, uniform="")

                if genislik < 1050:
                    ust.grid_columnconfigure(0, weight=1)
                    foto_kart.grid(row=0, column=0, sticky="nsew", pady=(0, 14))
                    kimlik_kart.grid(row=1, column=0, sticky="nsew", pady=(0, 14))
                    metrik_kart.grid(row=2, column=0, sticky="nsew")
                elif genislik < 1350:
                    ust.grid_columnconfigure(0, weight=1)
                    ust.grid_columnconfigure(1, weight=2)
                    foto_kart.grid(row=0, column=0, sticky="nsew", padx=(0, 14), pady=(0, 14))
                    kimlik_kart.grid(row=0, column=1, sticky="nsew", pady=(0, 14))
                    metrik_kart.grid(row=1, column=0, columnspan=2, sticky="nsew")
                else:
                    ust.grid_columnconfigure(0, weight=0)
                    ust.grid_columnconfigure(1, weight=2)
                    ust.grid_columnconfigure(2, weight=2)
                    foto_kart.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
                    kimlik_kart.grid(row=0, column=1, sticky="nsew", padx=(0, 14))
                    metrik_kart.grid(row=0, column=2, sticky="nsew")
            except tk.TclError:
                pass

        ust.bind("<Configure>", profil_ust_yerlesim)
        ust.after_idle(profil_ust_yerlesim)

        alt = tk.Frame(sayfa, bg=self.renkler["arkaplan"])
        alt.pack(fill="both", expand=True, pady=(16, 0))
        alt.grid_columnconfigure(0, weight=1)
        alt.grid_columnconfigure(1, weight=1)

        ureme_kart, ureme_body = self.profil_kart_olustur(alt, "Üreme ve Laktasyon", accent=self.renkler["button_primary_bg"])
        ureme_kart.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 16))
        if is_male:
            tk.Label(ureme_body, text="Bu hayvan için üreme kaydı tutulmuyor.", bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 10, "italic")).pack(anchor="w")
        else:
            self.profil_bilgi_satiri(ureme_body, "Gebelik", "Gebe" if hayvan.get("gebe_mi") else "Gebe değil")
            self.profil_bilgi_satiri(ureme_body, "Gebelik Tarihi", hayvan.get("gebelik_tarihi") or "-")
            self.profil_bilgi_satiri(ureme_body, "Tahmini Doğum", dogum_tahmini)
            self.profil_bilgi_satiri(ureme_body, "Aktif Sağım", laktasyon["aktif_sagim"])
            self.profil_bilgi_satiri(ureme_body, "Toplam Sağım", f"{laktasyon['toplam_sagim']} gün")

        uyari_kart, uyari_body = self.profil_kart_olustur(alt, "Aktif Uyarılar", accent=self.renkler["button_warning_bg"])
        uyari_kart.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 16))
        if uyarilar:
            for tip, mesaj, kalan in uyarilar[:6]:
                renk = self.renkler["button_danger_bg"] if kalan <= 0 else self.renkler["uyari"]
                satir = tk.Frame(uyari_body, bg=self.renkler["kart_ikincil"], padx=10, pady=8, highlightthickness=1, highlightbackground=self.renkler["kenarlik"])
                satir.pack(fill="x", pady=4)
                tk.Label(satir, text=tip, bg=self.renkler["kart_ikincil"], fg=renk, font=("Segoe UI", 10, "bold")).pack(anchor="w")
                kalan_metin = "Bugün/geçmiş" if kalan <= 0 else f"{kalan} gün kaldı"
                tk.Label(satir, text=f"{mesaj}  |  {kalan_metin}", bg=self.renkler["kart_ikincil"], fg=self.renkler["yazi_rengi"], font=("Segoe UI", 9), wraplength=520, justify="left").pack(anchor="w", pady=(2, 0))
        else:
            tk.Label(uyari_body, text="Bu hayvan için aktif uyarı yok.", bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 10, "italic")).pack(anchor="w")

        tohum_kart, tohum_body = self.profil_kart_olustur(alt, "Tohumlama Geçmişi", accent=self.renkler["button_primary_bg"])
        tohum_kart.grid(row=1, column=0, sticky="nsew", padx=(0, 8), pady=(0, 16))
        toh_tree = self.profil_tablo_olustur(tohum_body, ("#", "Tarih", "Şekil", "Suni İsim", "Sonuç"), {"#": 45, "Tarih": 110, "Şekil": 90, "Suni İsim": 150, "Sonuç": 110}, height=6)
        tohumlamalar = hayvan.get("tohumlamalar") or []
        if tohumlamalar:
            for i, tohumlama in enumerate(reversed(tohumlamalar), 1):
                sonuc = "Beklemede"
                if tohumlama.get("gebe_mi") is True:
                    sonuc = "Başarılı"
                elif tohumlama.get("gebe_mi") is False:
                    sonuc = "Başarısız"
                toh_tree.insert("", "end", values=(len(tohumlamalar) - i + 1, tohumlama.get("tarih", "-"), tohumlama.get("sekil", "-"), tohumlama.get("suni_isim", "-"), sonuc))
        else:
            toh_tree.insert("", "end", values=("-", "-", "-", "-", "Kayıt yok"))

        dogum_kart, dogum_body = self.profil_kart_olustur(alt, "Doğum ve Yavru Geçmişi", accent=self.renkler["button_success_bg"])
        dogum_kart.grid(row=1, column=1, sticky="nsew", padx=(8, 0), pady=(0, 16))
        dog_tree = self.profil_tablo_olustur(dogum_body, ("#", "Tarih", "Yavrular", "Not"), {"#": 45, "Tarih": 120, "Yavrular": 320, "Not": 520}, height=6)
        dogumlar = hayvan.get("dogumlar") or []
        dogum_yavrular_by_row = {}
        if dogumlar:
            for i, dogum in enumerate(dogumlar, 1):
                if not self.dogum_gecmisi_gosterilmeli_mi(dogum):
                    continue
                yavrular = self.dogum_gorunur_yavrular(dogum)
                yavru_metin = ", ".join([f"{y.get('cins', '-')}: {self.yavru_gorunen_kupe(y)}" for y in yavrular]) or "Yavru bilgisi yok"
                row_id = dog_tree.insert("", "end", values=(i, dogum.get("tarih", "-"), yavru_metin, dogum.get("not", "")))
                dogum_yavrular_by_row[row_id] = yavrular
            if not dogum_yavrular_by_row:
                dog_tree.insert("", "end", values=("-", "-", "Kayıt yok", ""))
        else:
            dog_tree.insert("", "end", values=("-", "-", "Kayıt yok", ""))

        def dogum_yavru_profili_ac(event=None):
            row_id = dog_tree.identify_row(event.y) if event is not None else ""
            if not row_id:
                secim = dog_tree.selection()
                row_id = secim[0] if secim else ""
            yavrular = dogum_yavrular_by_row.get(row_id) or []
            adaylar = []
            for yavru in yavrular:
                yavru_id = self.yavru_hayvan_id_bul(yavru)
                if not yavru_id or any(mevcut_id == yavru_id for mevcut_id, _ in adaylar):
                    continue
                etiket = f"{yavru.get('cins', '-')}: {self.yavru_gorunen_kupe(yavru)}"
                adaylar.append((yavru_id, etiket))

            if not adaylar:
                messagebox.showinfo(
                    "Yavru",
                    "Bu dogum kaydinda acilabilecek yavru hayvan kaydi bulunamadi.",
                    parent=detay_window,
                )
                return

            def yavruyu_ac(yavru_id):
                try:
                    detay_window.grab_release()
                except tk.TclError:
                    pass
                try:
                    detay_window.destroy()
                except tk.TclError:
                    pass
                self._track_after(self.root, 80, lambda h_id=yavru_id: self.hayvan_detay_penceresi(h_id))

            if len(adaylar) == 1:
                yavruyu_ac(adaylar[0][0])
                return

            menu = tk.Menu(
                detay_window,
                tearoff=0,
                bg=self.renkler["kart_ikincil"],
                fg=self.renkler["yazi_rengi"],
                activebackground=self.renkler["button_primary_bg"],
                activeforeground=self.renkler["button_primary_fg"],
            )
            for yavru_id, etiket in adaylar:
                menu.add_command(label=etiket, command=lambda h_id=yavru_id: yavruyu_ac(h_id))
            try:
                if event is not None:
                    menu.tk_popup(event.x_root, event.y_root)
                else:
                    menu.tk_popup(detay_window.winfo_pointerx(), detay_window.winfo_pointery())
            finally:
                menu.grab_release()

        dog_tree.bind("<Double-Button-1>", dogum_yavru_profili_ac)

        asi_kart, asi_body = self.profil_kart_olustur(alt, "Aşı ve Prosedürler", accent=self.renkler["uyari"])
        asi_kart.grid(row=2, column=0, sticky="nsew", padx=(0, 8))
        asi_tree = self.profil_tablo_olustur(asi_body, ("#", "Ad", "Tarih", "Sonraki", "Not"), {"#": 45, "Ad": 160, "Tarih": 110, "Sonraki": 110, "Not": 220}, height=6)
        prosedurler = hayvan.get("asi_prosedurler") or []
        if prosedurler:
            for i, prosedur in enumerate(prosedurler, 1):
                asi_tree.insert("", "end", values=(i, prosedur.get("ad", "-"), prosedur.get("tarih", "-"), prosedur.get("sonraki_tarih") or "-", prosedur.get("not", "")))
        else:
            asi_tree.insert("", "end", values=("-", "Kayıt yok", "-", "-", ""))

        not_kart, not_body = self.profil_kart_olustur(alt, "Notlar ve Son İşlemler", accent=self.renkler["button_default_bg"])
        not_kart.grid(row=2, column=1, sticky="nsew", padx=(8, 0))
        if hayvan.get("ek_notlar"):
            tk.Label(not_body, text=hayvan.get("ek_notlar"), bg=self.renkler["kart_ikincil"], fg=self.renkler["yazi_rengi"], justify="left", wraplength=560, padx=10, pady=8).pack(fill="x", pady=(0, 10))
        kimlikler = {str(hayvan_id), str(gorunen_kupe), str(hayvan.get("resmi_kupe_no") or ""), str(hayvan.get("ciftlik_kupe_no") or "")}
        ilgili_gecmis = []
        for kayit in self.islem_gecmisi[:200]:
            aciklama = str(kayit.get("aciklama") or kayit.get("detay") or "")
            if any(k and k in aciklama for k in kimlikler):
                ilgili_gecmis.append(kayit)
            if len(ilgili_gecmis) >= 8:
                break
        if ilgili_gecmis:
            for kayit in ilgili_gecmis:
                tk.Label(not_body, text=f"{kayit.get('zaman', '-')}: {kayit.get('aciklama') or kayit.get('detay')}", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], anchor="w", justify="left", wraplength=560, font=("Segoe UI", 9)).pack(fill="x", pady=2)
        else:
            tk.Label(not_body, text="Bu hayvan için yakın işlem kaydı yok.", bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 10, "italic")).pack(anchor="w")

        def profil_alt_yerlesim(event=None):
            try:
                genislik = min(max(alt.winfo_width(), 1), max(detay_window.winfo_width() - 60, 1))
                kartlar = (ureme_kart, uyari_kart, tohum_kart, dogum_kart, asi_kart, not_kart)
                for kart in kartlar:
                    kart.grid_forget()
                for col in range(2):
                    alt.grid_columnconfigure(col, weight=0, uniform="")

                if genislik < 1050:
                    alt.grid_columnconfigure(0, weight=1)
                    for row, kart in enumerate(kartlar):
                        kart.grid(row=row, column=0, sticky="nsew", pady=(0, 16))
                else:
                    alt.grid_columnconfigure(0, weight=1, uniform="profil_alt")
                    alt.grid_columnconfigure(1, weight=1, uniform="profil_alt")
                    ureme_kart.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 16))
                    uyari_kart.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 16))
                    tohum_kart.grid(row=1, column=0, sticky="nsew", padx=(0, 8), pady=(0, 16))
                    dogum_kart.grid(row=1, column=1, sticky="nsew", padx=(8, 0), pady=(0, 16))
                    asi_kart.grid(row=2, column=0, sticky="nsew", padx=(0, 8))
                    not_kart.grid(row=2, column=1, sticky="nsew", padx=(8, 0))
            except tk.TclError:
                pass

        alt.bind("<Configure>", profil_alt_yerlesim)
        alt.after_idle(profil_alt_yerlesim)

        detay_window.lift(self.root)
        detay_window.focus_force()

    # --- Kalan Fonksiyonlar ---
    def hayvan_listesini_guncelle(self):
        self.header_ozet_guncelle()
        for item in self.hayvan_tree.get_children(): self.hayvan_tree.delete(item)
        filtre = self.filtre_combo.get(); arama = self.arama_entry.get().strip()
        self.tum_hayvanlari_guncelle()
        sorted_hayvanlar = sorted(self.hayvanlar.items(), key=lambda item: item[0])
        row_idx = 0
        mevcut_idler = set()
        for kupe_no, hayvan in sorted_hayvanlar:
            if arama and not self.hayvan_arama_eslesir(kupe_no, hayvan, arama): continue
            arsivli = hayvan.get('arsivli', False)
            satildi = hayvan.get('satildi', False)
            aktif_degil = arsivli or hayvan.get('olu', False) or hayvan.get('kesildi', False) or satildi
            
            if filtre == "Aktif" and aktif_degil:
                continue
            elif filtre == "Arşivli" and not arsivli:
                continue
            elif filtre == "Satıldı" and not satildi:
                continue
            elif filtre not in ["Aktif", "Tümü", "Arşivli", "Satıldı"]:
                if arsivli or satildi:
                    continue
                filtre_durum_check = (filtre == "Gebe" and hayvan.get('gebe_mi', False)) or \
                                     (filtre == "Ölü" and hayvan.get('olu', False)) or \
                                     (filtre == "Kesildi" and hayvan.get('kesildi', False))
                filtre_gec = (filtre_durum_check or (hayvan.get('cins') == filtre))
                if not filtre_gec: continue

            yas_gun = hayvan.get('yas_gun', 0); yas_str = f"{yas_gun // 365} yıl {(yas_gun % 365) // 30} ay"
            
            if arsivli:
                mevcut_durum = "Arşivli"
            elif hayvan.get('olu', False):
                mevcut_durum = " Ölü"
            elif hayvan.get('kesildi', False):
                mevcut_durum = "Kesildi"
            elif satildi:
                mevcut_durum = "Satıldı"
            elif hayvan.get('gebe_mi', False):
                mevcut_durum = "Gebe"
            else:
                mevcut_durum = "Hayatta"

            son_tohumlama, dogum_tahmini, uyarilar, sagim_gun_str = "Yok", "-", "", "-"
            
            if hayvan.get('tohumlamalar'): son_tohumlama = hayvan['tohumlamalar'][-1]['tarih']
            if hayvan.get('gebe_mi', False) and hayvan.get('gebelik_tarihi'):
                try:
                    g_tarihi = datetime.strptime(hayvan['gebelik_tarihi'], "%d/%m/%Y")
                    d_tarihi = g_tarihi + timedelta(days=283); kalan_gun = (d_tarihi - datetime.now()).days
                    dogum_tahmini = d_tarihi.strftime("%d/%m/%Y")
                    if kalan_gun <= 60: uyarilar += f"Doğuma {kalan_gun} gün! " if kalan_gun > 0 else "DOĞUM VAKTİ!"
                except: dogum_tahmini = "Hata"
            
            if hayvan.get('durum') == 'Sağmal İnek':
                try:
                    dogumlar = hayvan.get('dogumlar', [])
                    if self.sagmal_laktasyon_eksik_mi(hayvan):
                        uyarilar += "Eksik veri: laktasyon/son doğum! "
                        sagim_gun_str = "Eksik"
                    elif dogumlar:
                        son_dogum = dogumlar[-1]
                        if son_dogum.get('laktasyon_bitis_tarihi') is None and son_dogum.get('tarih') != 'Bilinmiyor':
                            s_tarihi = datetime.strptime(son_dogum['tarih'], "%d/%m/%Y")
                            sagim_gun = (datetime.now() - s_tarihi).days
                            sagim_gun_str = f"{sagim_gun} gün"
                            if sagim_gun > 305: uyarilar += "Uzun sağım! "
                except Exception as e: 
                    sagim_gun_str = f"Hata: {e}"
            
            tag = "normal"
            if arsivli:
                tag = "archived"
            elif hayvan.get('olu', False): 
                tag = "dead"
            elif hayvan.get('kesildi', False):
                tag = "slaughtered"
            elif satildi:
                tag = "sold"
            elif self.sagmal_laktasyon_eksik_mi(hayvan):
                tag = "warning"
            elif hayvan.get('gebe_mi', False) and dogum_tahmini != "-":
                try:
                    kalan_gun = (datetime.strptime(dogum_tahmini, "%d/%m/%Y") - datetime.now()).days
                    if kalan_gun <= 7: tag = "critical"
                    elif kalan_gun <= 30: tag = "urgent"
                    elif kalan_gun <= 60: tag = "warning"
                    else: tag = "pregnant"
                except: tag = "pregnant"

            # Zebra stripe: normal satırlara çift/tek renk
            final_tags = [tag]
            if tag == 'normal':
                final_tags = ['odd' if row_idx % 2 == 0 else 'even']
            resmi = hayvan.get('resmi_kupe_no', '-') or '-'
            ciftlik = hayvan.get('ciftlik_kupe_no', '-') or '-'
            irk = hayvan.get('irk', '-') or '-'
            mevcut_idler.add(str(kupe_no))
            secim = "☑" if str(kupe_no) in getattr(self, "hayvan_secimleri", set()) else "☐"
            self.hayvan_tree.insert('', 'end', values=(kupe_no, secim, resmi, ciftlik, irk, yas_str, hayvan['cins'], mevcut_durum, son_tohumlama, dogum_tahmini, sagim_gun_str, uyarilar), tags=tuple(final_tags))
            row_idx += 1
        self.hayvan_secimleri = set(getattr(self, "hayvan_secimleri", set())) & mevcut_idler

        #  TAG RENKLERI 
        # Zebra stripes için temel renkler
        zebra_odd  = self.renkler["kart_arkaplan"]
        zebra_even = self._lighten_color(self.renkler["kart_arkaplan"], 8) if self.theme_mode == 'dark' else self.koyu_renk(self.renkler["kart_arkaplan"])

        light_green = "#34D399" if self.theme_mode == "dark" else "#059669"
        amber       = "#FBBF24" if self.theme_mode == "dark" else "#D97706"
        light_red   = "#F87171" if self.theme_mode == "dark" else "#DC2626"

        self.hayvan_tree.tag_configure('odd',        background=zebra_odd,  foreground=self.renkler["yazi_rengi"])
        self.hayvan_tree.tag_configure('even',       background=zebra_even, foreground=self.renkler["yazi_rengi"])
        self.hayvan_tree.tag_configure('pregnant',   foreground=light_green)
        self.hayvan_tree.tag_configure('warning',    foreground=amber)
        self.hayvan_tree.tag_configure('urgent',     foreground=light_red)
        
        # Dark mode uyumlu yumuşak kritik renkler
        bg_critical = '#4C0519' if self.theme_mode == "dark" else '#FEE2E2'
        fg_critical = '#FECDD3' if self.theme_mode == "dark" else '#991B1B'
        self.hayvan_tree.tag_configure('critical',   background=bg_critical, foreground=fg_critical)
        
        self.hayvan_tree.tag_configure('dead',       background=self.renkler["gri"],         foreground=self.renkler["muted"])
        self.hayvan_tree.tag_configure('slaughtered',background=self.renkler["kesildi_bg"],  foreground=self.renkler["kesildi_fg"])
        self.hayvan_tree.tag_configure('sold',       background=self.renkler["kart_ikincil"], foreground=self.renkler["uyari"])
        self.hayvan_tree.tag_configure('archived',   background=self.renkler["siyah"],       foreground=self.renkler["muted"])
        self.hayvan_tree.tag_configure('normal',     foreground=self.renkler["yazi_rengi"])
        self.tohumlama_hayvanlarini_guncelle()


    def tum_hayvanlari_guncelle(self):
        is_changed = False
        degisen_idler = set()
        for kupe_no, hayvan in list(self.hayvanlar.items()):
            if hayvan.get('olu', False) or hayvan.get('kesildi', False) or hayvan.get('arsivli', False) or hayvan.get('satildi', False): continue
            
            try:
                dogum_tarihi = datetime.strptime(hayvan['dogum_tarihi'], "%d/%m/%Y")
                yeni_yas_gun = (datetime.now() - dogum_tarihi).days
                if hayvan.get('yas_gun') != yeni_yas_gun:
                    hayvan['yas_gun'] = yeni_yas_gun; is_changed = True; degisen_idler.add(str(kupe_no))
                
                if not hayvan.get('gebe_mi', False) and hayvan.get('durum') not in ['Sağmal İnek', 'Kuru İnek']:
                    yeni_cins = self.otomatik_cins_guncelle(hayvan['cins'], yeni_yas_gun)
                    if yeni_cins != hayvan['cins']:
                        hayvan['cins'] = yeni_cins
                        hayvan['durum'] = self.durum_hesapla(yeni_cins, yeni_yas_gun)
                        is_changed = True
                        degisen_idler.add(str(kupe_no))
            
            except Exception as e:
                print(f"Hayvan güncellenirken hata ({kupe_no}): {e}")
                continue
        if is_changed:
            self.json_dosyasi_kaydet(self.data_file, self.hayvanlar, "hayvan_verileri", "Veri Kayit Hatası")

    def uyarilari_guncelle(self):
        uyarilar, uyari_metni = [], ""
        for kupe_no, hayvan in self.hayvanlar.items():
            if hayvan.get('arsivli', False) or hayvan.get('olu', False) or hayvan.get('kesildi', False) or hayvan.get('satildi', False):
                continue
            aktif_tohumlama_id = hayvan.get('aktif_tohumlama_id')

            if hayvan.get('tohumlamalar'):
                son_tohumlama = hayvan['tohumlamalar'][-1]
                if son_tohumlama.get('gebe_mi') is None:
                    try:
                        t_tarihi = datetime.strptime(son_tohumlama['tarih'], "%d/%m/%Y")
                        kontrol_tarihi = t_tarihi + timedelta(days=21)
                        kalan_kontrol = (kontrol_tarihi - datetime.now()).days
                        if kalan_kontrol <= 7:
                            tohumlama_id = son_tohumlama.get('id') or "bekleyen"
                            uyari_key = self.uyari_key_olustur(kupe_no, "gebelik_kontrol", tohumlama_id, kalan_kontrol)
                            okundu_mu = uyari_key in self.okunan_uyarilar if uyari_key else False
                            if kalan_kontrol <= 0:
                                durum, tip = "ACİL", "GEBELİK KONTROLÜ"
                            else:
                                durum, tip = "ÖNEMLİ", "GEBELİK KONTROLÜ YAKIN"
                            gorunen_kupe = hayvan.get('ciftlik_kupe_no') or hayvan.get('resmi_kupe_no') or kupe_no
                            if not okundu_mu:
                                uyari_metni += f" {gorunen_kupe}: Gebelik kontrolü! "
                            uyarilar.append({
                                'kupe_no': gorunen_kupe,
                                'tip': tip,
                                'mesaj': f"Kontrol tarihi: {kontrol_tarihi.strftime('%d/%m/%Y')}",
                                'kalan_gun': kalan_kontrol,
                                'durum': durum,
                                'uyari_durumu': "OKUNDU" if okundu_mu else "YENİ",
                                'okundu': okundu_mu
                            })
                    except: pass

            if aktif_tohumlama_id and hayvan.get('durum') == 'Sağmal İnek' and hayvan.get('gebe_mi', False):
                try:
                    g_tarihi = datetime.strptime(hayvan['gebelik_tarihi'], "%d/%m/%Y")
                    kalan_gun_doguma = (g_tarihi + timedelta(days=283) - datetime.now()).days
                    uyari_key = (
                        self.uyari_key_olustur(kupe_no, "kuruya_al", aktif_tohumlama_id, kalan_gun_doguma)
                        if kalan_gun_doguma <= 60
                        else None
                    )
                    if uyari_key:
                        okundu_mu = uyari_key in self.okunan_uyarilar
                        
                        gorunen_kupe = hayvan.get('ciftlik_kupe_no') or hayvan.get('resmi_kupe_no') or kupe_no
                        if not okundu_mu:
                            uyari_metni += f"{gorunen_kupe}: Kuruya Al! "
                        uyarilar.append({
                            'kupe_no': gorunen_kupe, 'tip': "KURUYA ALINMALI", 
                            'mesaj': f"Doğuma {kalan_gun_doguma} gün kaldı. Kuruya ayrılmalı!", 
                            'kalan_gun': kalan_gun_doguma, 'durum': "ACİL", 
                            'uyari_durumu': "OKUNDU" if okundu_mu else "YENİ", 'okundu': okundu_mu})
                except: pass

            if aktif_tohumlama_id and hayvan.get('gebe_mi', False):
                try:
                    g_tarihi = datetime.strptime(hayvan['gebelik_tarihi'], "%d/%m/%Y")
                    kalan_gun = (g_tarihi + timedelta(days=283) - datetime.now()).days
                    uyari_key = self.uyari_key_olustur(kupe_no, "gebelik", aktif_tohumlama_id, kalan_gun)
                    if uyari_key:
                        okundu_mu = uyari_key in self.okunan_uyarilar

                        if kalan_gun <= 0: durum, tip = "ACİL", "DOĞUM VAKTİ"
                        elif kalan_gun <= 7: durum, tip = "ACİL", "DOĞUM ÇOK YAKIN"
                        elif kalan_gun <= 30: durum, tip = "ÖNEMLİ", "DOĞUM YAKIN"
                        else: durum, tip = "DİKKAT", "DOĞUM HAZIRLIĞI"
                        
                        gorunen_kupe = hayvan.get('ciftlik_kupe_no') or hayvan.get('resmi_kupe_no') or kupe_no
                        if not okundu_mu and 'ACİL' in durum: 
                            uyari_metni += f" {gorunen_kupe}: {kalan_gun} gün! "
                            
                        uyarilar.append({'kupe_no': gorunen_kupe, 'tip': tip, 'mesaj': f"Doğuma {kalan_gun} gün" if kalan_gun > 0 else "DOĞUM VAKTİ!", 'kalan_gun': kalan_gun, 'durum': durum, 'uyari_durumu': "OKUNDU" if okundu_mu else "YENİ", 'okundu': okundu_mu})
                except: pass

            for prosedur in hayvan.get('asi_prosedurler', []):
                sonraki_tarih = prosedur.get('sonraki_tarih')
                if not sonraki_tarih:
                    continue
                try:
                    p_tarihi = datetime.strptime(sonraki_tarih, "%d/%m/%Y")
                    kalan_prosedur = (p_tarihi - datetime.now()).days
                    if kalan_prosedur <= 7:
                        prosedur_id = prosedur.get('id') or prosedur.get('ad', 'prosedur')
                        uyari_key = self.uyari_key_olustur(kupe_no, "asi_prosedur", prosedur_id, kalan_prosedur)
                        okundu_mu = uyari_key in self.okunan_uyarilar if uyari_key else False
                        if kalan_prosedur <= 0:
                            durum, tip = "ACİL", "AŞI/PROSEDÜR GECİKTİ"
                        else:
                            durum, tip = "DİKKAT", "AŞI/PROSEDÜR YAKIN"
                        if not okundu_mu:
                            gorunen_kupe = hayvan.get('ciftlik_kupe_no') or hayvan.get('resmi_kupe_no') or kupe_no
                            uyari_metni += f" {gorunen_kupe}: {prosedur.get('ad', 'Prosedür')}! "
                        else:
                            gorunen_kupe = hayvan.get('ciftlik_kupe_no') or hayvan.get('resmi_kupe_no') or kupe_no
                        uyarilar.append({
                            'kupe_no': gorunen_kupe,
                            'tip': tip,
                            'mesaj': f"{prosedur.get('ad', 'Prosedür')} - tarih: {sonraki_tarih}",
                            'kalan_gun': kalan_prosedur,
                            'durum': durum,
                            'uyari_durumu': "OKUNDU" if okundu_mu else "YENİ",
                            'okundu': okundu_mu
                        })
                except: pass
        
        okunmamis_uyarilar = [u for u in uyarilar if not u['okundu']]
        okunmamis_kritik = [u for u in okunmamis_uyarilar if 'ACİL' in u['durum']]

        def _set_band(bg, fg, ikon, ind_renk, metin, puls=False):
            self.uyari_frame.config(bg=bg)
            self.uyari_label.config(text=metin, bg=bg, fg=fg)
            if hasattr(self, 'uyari_indicator'):
                self.uyari_indicator.config(bg=ind_renk)
            if hasattr(self, '_saat_label'):
                self._saat_label.config(bg=bg, fg=fg)
            if hasattr(self, '_uyari_ikon_lbl'):
                self._uyari_ikon_lbl.config(text=ikon, bg=bg)
            # Pulse animasyonu
            onceki_puls = getattr(self, '_puls_aktif', False)
            self._puls_aktif = puls
            if puls:
                if not onceki_puls or not getattr(self, "_puls_after_id", None):
                    self._puls_animasyon()
            else:
                self._puls_zamanlayici_iptal_et()

        if okunmamis_kritik:
            _set_band(
                bg=self.renkler["band_critical_bg"], fg=self.renkler["band_critical_fg"],
                ikon='', ind_renk=self.renkler["button_danger_bg"],
                metin=f"KRİTİK: {len(okunmamis_kritik)} uyarı aktif  —  {uyari_metni.strip()}",
                puls=True
            )
        elif okunmamis_uyarilar:
            _set_band(
                bg=self.renkler["band_warning_bg"], fg=self.renkler["band_warning_fg"],
                ikon='', ind_renk='#F59E0B',
                metin=f"{len(okunmamis_uyarilar)} okunmamış uyarı var  —  Uyarılar sekmesini kontrol edin",
                puls=False
            )
        else:
            _set_band(
                bg=self.renkler["band_normal_bg"], fg=self.renkler["band_normal_fg"],
                ikon='', ind_renk=self.renkler["yesil"],
                metin="Tüm sistemler normal  —  Kritik uyarı bulunmuyor",
                puls=False
            )

    
        if hasattr(self, 'uyari_tree'):
            for item in self.uyari_tree.get_children(): self.uyari_tree.delete(item)
            uyarilar_sirali = sorted(uyarilar, key=lambda x: (x['okundu'], x['kalan_gun']))
            
            koyu_kirmizi = self.renkler.get("koyu_kirmizi", "#B71C1C")
            turuncu = "#FFA726" if self.theme_mode == "dark" else "#FFB74D"
            sari = "#FFEE58" if self.theme_mode == "dark" else "#FFF176"

            kuruya_al_bg = self.renkler["button_primary_bg"]
            kuruya_al_fg = "#FFFFFF"
            self.uyari_tree.tag_configure('dryoff_new', background=kuruya_al_bg, foreground=kuruya_al_fg)

            bg_critical = koyu_kirmizi  # koyu_kirmizi artık tag_configure'da kullanılıyor
            fg_critical = '#FECDD3' if self.theme_mode == "dark" else '#991B1B'
            self.uyari_tree.tag_configure('critical_new', background=bg_critical, foreground=fg_critical)
            self.uyari_tree.tag_configure('important_new', background=turuncu, foreground=self.renkler["uyari_yazi"])
            self.uyari_tree.tag_configure('warning_new', background=sari, foreground=self.renkler["uyari_yazi"])
            self.uyari_tree.tag_configure('read', background=self.renkler["gri"], foreground=self.renkler["yazi_rengi"])
            
            for uyari in uyarilar_sirali:
                tag = "read"
                if not uyari['okundu']:
                    if 'KURUYA ALINMALI' in uyari['tip']: tag = "dryoff_new"
                    elif 'ACİL' in uyari['durum']: tag = "critical_new"
                    elif 'ÖNEMLİ' in uyari['durum']: tag = "important_new"
                    else: tag = "warning_new"
                self.uyari_tree.insert('', 'end', values=(uyari['kupe_no'], uyari['tip'], uyari['mesaj'], uyari['kalan_gun'], uyari['durum'], uyari['uyari_durumu']), tags=(tag,))

    def uyari_sistemi_baslat(self):
        self.uyari_dongusu()

    def uyari_dongusu(self):
        if not self.uyari_thread_running or getattr(self, "_kapanis_istegi", False):
            return
        try:
            self.uyarilari_guncelle()
            self._uyari_after_id = self.root.after(1800 * 1000, self.uyari_dongusu)
        except tk.TclError:
            self.uyari_thread_running = False

    def uygulamayi_kapat(self):
        self._kapanis_istegi = True
        self.uyari_thread_running = False
        self._cancel_tracked_afters()
        for after_attr in ("_uyari_after_id", "_saat_after_id", "_baslangic_after_id", "_puls_after_id", "_otomatik_baglanti_after_id"):
            after_id = getattr(self, after_attr, None)
            if after_id:
                try:
                    self.root.after_cancel(after_id)
                except tk.TclError:
                    pass
                setattr(self, after_attr, None)
        try:
            for pencere in list(self.root.winfo_children()):
                if isinstance(pencere, tk.Toplevel) and pencere.winfo_exists():
                    pencere.destroy()
        except tk.TclError:
            pass
        try:
            self.root.quit()
            self.root.destroy()
        except tk.TclError:
            pass

    def calistir(self):
        if not getattr(self, "_baslatma_tamam", False):
            return
        try:
            if not self.root.winfo_exists():
                return
        except tk.TclError:
            return

        self.root.protocol("WM_DELETE_WINDOW", self.uygulamayi_kapat)
        self.root.mainloop()

# --- Uygulamayı Başlat ---
if __name__ == "__main__":
    try:
        # PIL (Pillow) kontrolü - Dosya başında import edildi, burada sadece kontrol ediyoruz
        if Image is None:
            messagebox.showerror("Eksik Kütüphane", "Lütfen 'Pillow' kütüphanesini yükleyin.\nKomut: pip install Pillow")
            exit()
        app = HayvanTakipSistemi()
        app.calistir()
    except Exception as e:
        messagebox.showerror("Kritik Hata", f"Uygulama başlatılamadı:\n{str(e)}")
