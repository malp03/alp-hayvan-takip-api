import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime, timedelta
import json
import copy
import hashlib
import hmac
import os
import shutil
import secrets
import uuid
import urllib.error
import urllib.parse
import urllib.request
try:
    from PIL import Image, ImageTk
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

# --- Grafik çizimi için matplotlib kütüphanesini ekliyoruz ---
try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


class ApiHatasi(Exception):
    def __init__(self, mesaj, status=None):
        super().__init__(mesaj)
        self.status = status


VARSAYILAN_API_URL = "https://alp-hayvan-takip-api.onrender.com"
# --------------------------------------------------------------------

# --- Exe'de dosya yolunu doğru bulmak için fonksiyon ---
def resource_path(relative_path):
    """ Hem script hem de donmuş exe için varlıklara mutlak yol oluşturur. """
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
                "ana_kirmizi": "#D92D20", "koyu_kirmizi": "#B42318",
                "siyah": "#101510",
                "arkaplan": "#121611",
                "kart_arkaplan": "#1B211A",
                "kart_ikincil": "#232B21",
                "gri": "#2E372B",
                "kenarlik": "#3D4938",
                "input_bg": "#20281F",
                "muted": "#A7B0A4",
                "yazi_rengi": "#F4F7F2",
                "beyaz": "#FFFFFF",
                "yesil": "#16A34A", "koyu_yesil": "#15803D",
                "uyari": "#F59E0B", "uyari_yazi": "#18140A",
                "kesildi_bg": "#40473E", "kesildi_fg": "#FFFFFF",
                "button_default_bg": "#31402F", "button_default_fg": "#F4F7F2",
                "button_success_bg": "#168A43", "button_success_fg": "#FFFFFF",
                "button_danger_bg": "#D92D20", "button_danger_fg": "#FFFFFF",
                "button_warning_bg": "#F59E0B", "button_warning_fg": "#18140A",
                "button_theme_bg": "#232B21", "button_theme_fg": "#F4F7F2",
                "button_primary_bg": "#2563EB", "button_primary_fg": "#FFFFFF",
                "band_normal_bg": "#123C2A", "band_normal_fg": "#D9FBE8",
                "band_warning_bg": "#563B12", "band_warning_fg": "#FEF3C7",
                "band_critical_bg": "#7F1D1D", "band_critical_fg": "#FFF1F2",
            }

            self.light_theme = {
                "ana_kirmizi": "#D92D20", "koyu_kirmizi": "#B42318",
                "siyah": "#172016",
                "arkaplan": "#F5F7F2",
                "kart_arkaplan": "#FFFFFF",
                "kart_ikincil": "#EEF3E9",
                "gri": "#E6ECE1",
                "kenarlik": "#D4DDCF",
                "input_bg": "#F8FAF6",
                "muted": "#66735F",
                "yazi_rengi": "#1F2A1D",
                "beyaz": "#FFFFFF",
                "yesil": "#15803D", "koyu_yesil": "#166534",
                "uyari": "#F59E0B", "uyari_yazi": "#1F2A1D",
                "kesildi_bg": "#9AA79A", "kesildi_fg": "#FFFFFF",
                "button_default_bg": "#E0E7DA", "button_default_fg": "#1F2A1D",
                "button_success_bg": "#15803D", "button_success_fg": "#FFFFFF",
                "button_danger_bg": "#D92D20", "button_danger_fg": "#FFFFFF",
                "button_warning_bg": "#F59E0B", "button_warning_fg": "#1F2A1D",
                "button_theme_bg": "#EEF3E9", "button_theme_fg": "#1F2A1D",
                "button_primary_bg": "#2563EB", "button_primary_fg": "#FFFFFF",
                "band_normal_bg": "#DDF7E8", "band_normal_fg": "#14532D",
                "band_warning_bg": "#FEF3C7", "band_warning_fg": "#78350F",
                "band_critical_bg": "#FEE2E2", "band_critical_fg": "#991B1B",
            }
            
            self.theme_mode = "dark"
            self.renkler = self.dark_theme
            self.themed_widgets = []
            self.themed_buttons = []

            self.logo_path = resource_path("alp_ziraat_logo.png")
            
            self.root.title("ALP ZİRAAT - Sürü Takip Sistemi")
            self.root.geometry("1600x1000")
            self.root.configure(bg=self.renkler["arkaplan"])

            try:
                self.logo_ikon = ImageTk.PhotoImage(file=self.logo_path)
                self.root.iconphoto(False, self.logo_ikon)
            except Exception as e:
                print(f"Logo ikonu yüklenemedi: {e}")

            self.stil_ayarla()
            self.veri_klasoru_hazirla()
            self.api_token = None
            self.api_kullanici = None
            self.admin_aktif_ciftlik_id = None
            self.admin_aktif_ciftlik_ad = None
            self._otomatik_baglanti_after_id = None
            self._otomatik_baglanti_kontrol_ediliyor = False
            self.otomatik_baglanti_araligi_ms = 60 * 1000
            self.otomatik_baglanti_ilk_gecikme_ms = 30 * 1000
            if self.api_modu:
                if not self.api_giris_penceresi():
                    self.root.destroy()
                    return
                if self.admin_mi():
                    if not self.admin_yonetim_merkezi():
                        self.root.destroy()
                        return
                    self.themed_widgets = []
                    self.themed_buttons = []
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
            self._baslatma_tamam = True

        except Exception as e:
            messagebox.showerror("Başlatma Hatası", f"Uygulama başlatılamadı: {e}")

    # --- Tema Yönetimi ve Diğer Yardımcı Fonksiyonlar ---
    def toggle_theme(self):
        if self.theme_mode == "dark":
            self.theme_mode = "light"
            self.renkler = self.light_theme
            self.theme_toggle_button.itemconfig(self.theme_toggle_button.text_item, text="🌙 Koyu Mod")
        else:
            self.theme_mode = "dark"
            self.renkler = self.dark_theme
            self.theme_toggle_button.itemconfig(self.theme_toggle_button.text_item, text="☀️ Açık Mod")
        self.apply_theme_to_widgets()

    def apply_theme_to_widgets(self):
        self.root.config(bg=self.renkler["arkaplan"])
        self.stil_ayarla()
        for widget, widget_type in self.themed_widgets:
            try:
                if not widget.winfo_exists():
                    continue
                if widget_type == 'frame':
                    widget.config(bg=self.renkler["arkaplan"])
                elif widget_type == 'arkaplan':
                    widget.config(bg=self.renkler["arkaplan"])
                elif widget_type == 'kart':
                    widget.config(
                        bg=self.renkler["kart_arkaplan"],
                        highlightbackground=self.renkler.get("kenarlik", self.renkler["gri"])
                    )
                elif widget_type == 'soft_panel':
                    widget.config(
                        bg=self.renkler["kart_ikincil"],
                        highlightbackground=self.renkler.get("kenarlik", self.renkler["gri"])
                    )
                elif widget_type == 'label':
                    try:
                        parent_bg = widget.master.cget('bg')
                    except Exception:
                        parent_bg = self.renkler["kart_arkaplan"]
                    widget.config(bg=parent_bg, fg=self.renkler["yazi_rengi"])
                elif widget_type == 'muted_label':
                    try:
                        parent_bg = widget.master.cget('bg')
                    except Exception:
                        parent_bg = self.renkler["kart_arkaplan"]
                    widget.config(bg=parent_bg, fg=self.renkler["muted"])
                elif widget_type == 'divider':
                    widget.config(bg=self.renkler.get("kenarlik", self.renkler["gri"]))
                elif widget_type == 'baslik_frame':
                    widget.config(bg=self.renkler["siyah"])
                elif widget_type == 'baslik_label':
                    widget.config(bg=self.renkler["siyah"], fg='#F8FAFC')
                elif widget_type == 'baslik_muted_label':
                    widget.config(bg=self.renkler["siyah"], fg=self.renkler["muted"])
                elif widget_type == 'kirmizi_baslik_frame':
                    widget.config(bg=self.renkler["ana_kirmizi"])
                elif widget_type == 'kirmizi_baslik_label':
                    widget.config(bg=self.renkler["ana_kirmizi"], fg='#FFFFFF')
                elif widget_type == 'kontrol_frame':
                    widget.config(bg=self.renkler["kart_arkaplan"])
                elif widget_type == 'kontrol_label':
                    widget.config(bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"])
                elif widget_type in ['uyari_baslik', 'uyari_baslik_btn']:
                    widget.config(bg=self.renkler["uyari"])
                elif widget_type == 'uyari_baslik_label':
                    widget.config(bg=self.renkler["uyari"], fg=self.renkler["uyari_yazi"])
            except tk.TclError:
                pass  # Widget yok edilmiş olabilir
        for button, purpose in self.themed_buttons:
            try:
                if button.winfo_exists():
                    bg_color = self.renkler.get(f"button_{purpose}_bg", self.renkler["button_default_bg"])
                    fg_color = self.renkler.get(f"button_{purpose}_fg", self.renkler["button_default_fg"])
                    if isinstance(button, tk.Canvas):
                        parent_bg = button.master.cget('bg')
                        button.config(bg=parent_bg)
                        for p in getattr(button, 'border_parts', []):
                            button.itemconfig(p, fill=self.renkler.get("kenarlik", self.renkler["gri"]))
                        for p in getattr(button, 'button_parts', []):
                            button.itemconfig(p, fill=bg_color)
                        if hasattr(button, 'text_item'):
                            button.itemconfig(button.text_item, fill=fg_color)
                    else:
                        hover_color = self._lighten_color(bg_color, 25) if self.theme_mode == 'dark' else self.koyu_renk(bg_color)
                        button.config(bg=bg_color, fg=fg_color, activebackground=hover_color, activeforeground=fg_color)
            except tk.TclError:
                pass
        self.uyarilari_guncelle()
        self.hayvan_listesini_guncelle()
        if hasattr(self, '_update_custom_tabs'):
            self._update_custom_tabs()
        if hasattr(self, 'api_durum_guncelle'):
            self.api_durum_guncelle()
        if MATPLOTLIB_AVAILABLE and hasattr(self, 'rapor_frame'):
            self.raporlari_guncelle()



    def stil_ayarla(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background=self.renkler["arkaplan"])
        style.configure('TLabel', background=self.renkler["arkaplan"], foreground=self.renkler["yazi_rengi"], font=('Segoe UI', 11))
        style.configure('TNotebook', background=self.renkler["arkaplan"], borderwidth=0, tabmargins=[0, 0, 0, 0])
        style.configure('Modern.TNotebook', background=self.renkler["arkaplan"], borderwidth=0)
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
            background=self.renkler["siyah"],
            foreground=self.renkler["muted"],
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
            padding=[10, 8], borderwidth=1, relief='flat')
        style.map('TCombobox',
            fieldbackground=[('readonly', self.renkler["input_bg"]), ('focus', self.renkler["input_bg"])],
            selectbackground=[('readonly', self.renkler["input_bg"])])
        style.configure('TEntry',
            fieldbackground=self.renkler["input_bg"],
            foreground=self.renkler["yazi_rengi"],
            insertcolor=self.renkler["yazi_rengi"],
            padding=[10, 8], borderwidth=1, relief='flat')
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

    def _animate_bg_color(self, widget, current_rgb, target_rgb, step=0, total_steps=8):
        if not widget.winfo_exists(): return
        if step > total_steps:
            widget.config(bg=self._rgb_to_hex(target_rgb))
            return
        r = int(current_rgb[0] + (target_rgb[0] - current_rgb[0]) * (step / total_steps))
        g = int(current_rgb[1] + (target_rgb[1] - current_rgb[1]) * (step / total_steps))
        b = int(current_rgb[2] + (target_rgb[2] - current_rgb[2]) * (step / total_steps))
        
        widget.config(bg=self._rgb_to_hex((r, g, b)))
        widget.after(15, lambda: self._animate_bg_color(widget, current_rgb, target_rgb, step + 1, total_steps))

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
            
        canvas.after(15, lambda: self._animate_canvas_bg(canvas, parts, current_rgb, target_rgb, step + 1, total_steps))

    def modern_buton(self, parent, text, command, purpose='default', width=None, small=False):
        bg_color = self.renkler.get(f"button_{purpose}_bg", self.renkler["button_default_bg"])
        fg_color = self.renkler.get(f"button_{purpose}_fg", self.renkler["button_default_fg"])
        hover_color = self._lighten_color(bg_color, 25) if self.theme_mode == 'dark' else self.koyu_renk(bg_color)
        _ = hover_color  # hover_color kullanımı canvas içindeki get_colors()'da dinamik olarak yapılıyor
        
        pad_x = 18 if small else 26
        pad_y = 6 if small else 9
        font_size = 10 if small else 11
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
        
        radius = 8
        border_color = self.renkler.get("kenarlik", self.renkler["gri"])
        border_parts = self._create_rounded_rect(canvas, 0, 0, req_w, req_h, radius=radius, fill=border_color)
        parts = self._create_rounded_rect(canvas, 1, 1, req_w - 1, req_h - 1, radius=max(6, radius - 1), fill=bg_color)
        
        text_id = canvas.create_text(req_w/2, req_h/2, text=text, fill=fg_color, font=font_spec, justify='center')
        
        canvas.border_parts = border_parts
        canvas.button_parts = parts
        canvas.text_item = text_id
        canvas.purpose = purpose
        
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
            if command:
                bg_rgb, hover_rgb, hover_hex = get_colors()
                click_color = self._lighten_color(hover_hex, 30) if self.theme_mode == 'dark' else self.koyu_renk(hover_hex)
                for p in parts: canvas.itemconfig(p, fill=click_color)
                canvas.update_idletasks()
                canvas.after(50, lambda: self._animate_canvas_bg(canvas, parts, self._hex_to_rgb(click_color), hover_rgb))
                canvas.after(100, command)
                
        # Bindings only on the canvas widget to prevent event bubbling/double-firing
        canvas.bind("<Enter>", on_enter)
        canvas.bind("<Leave>", on_leave)
        canvas.bind("<Button-1>", on_click)
        
        self.themed_buttons.append((canvas, purpose))
        return canvas

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
        """Modern kart — düz, temiz frame. accent rengi verilirse sol kenar çizgisi eklenir."""
        if accent:
            outer = tk.Frame(parent, bg=self.renkler["kart_arkaplan"])
            accent_bar = tk.Frame(outer, bg=accent, width=4)
            accent_bar.pack(side='left', fill='y')
            inner = tk.Frame(outer, bg=self.renkler["kart_arkaplan"])
            inner.pack(side='left', fill='both', expand=True)
            self.themed_widgets.append((outer, 'kart'))
            self.themed_widgets.append((inner, 'kart'))
            return inner   # İÇ frame dönüyor — children doğru yere giriyor
        else:
            kart = tk.Frame(
                parent,
                bg=self.renkler["kart_arkaplan"],
                highlightthickness=1,
                highlightbackground=self.renkler.get("kenarlik", self.renkler["gri"]),
                bd=0
            )
            self.themed_widgets.append((kart, 'kart'))
            return kart

    def modern_section_baslik(self, parent, text, icon='', color=None):
        """Sekme içi bölüm başlığı — ince sol accent çizgisi ile."""
        renk = color or self.renkler["ana_kirmizi"]
        frame = tk.Frame(parent, bg=self.renkler["kart_arkaplan"])
        accent = tk.Frame(frame, bg=renk, width=4, height=32)
        accent.pack(side='left', fill='y', padx=(0, 12))
        lbl = tk.Label(frame, text=f"{icon} {text}".strip(), font=('Segoe UI', 14, 'bold'),
                       bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"])
        lbl.pack(side='left', anchor='w')
        self.themed_widgets.append((frame, 'kart'))
        self.themed_widgets.append((lbl, 'label'))
        return frame

    # ── ANİMASYON METODLARı ──────────────────────────────────────────────────
    def _bildirim_puls_baslat(self):
        """Kritik uyarı varsa gösterge çubuğunu pulse animasyonuyla yanıp söndürür."""
        self._puls_durum = True
        self._puls_animasyon()

    def _puls_animasyon(self):
        """Indicator bar rengini A→B→A→... şeklinde animasyonla değiştirir."""
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

    def _hover_animasyon(self, widget, enter_bg, leave_bg, steps=8, delay=12):
        """Widget arka plan rengini smooth geçişle değiştirir."""
        def _interpolate(c1, c2, t):
            r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
            r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
            r = int(r1 + (r2 - r1) * t)
            g = int(g1 + (g2 - g1) * t)
            b = int(b1 + (b2 - b1) * t)
            return f'#{r:02x}{g:02x}{b:02x}'

        def _animate(step, direction):
            if not widget.winfo_exists():
                return
            t = (step / steps) if direction == 'in' else ((steps - step) / steps)
            c = _interpolate(leave_bg, enter_bg, t)
            try:
                widget.config(bg=c)
                if step < steps:
                    widget.after(delay, lambda: _animate(step + 1, direction))
            except tk.TclError:
                pass

        widget.bind('<Enter>', lambda e: _animate(0, 'in'))
        widget.bind('<Leave>', lambda e: _animate(0, 'out'))

    def modern_form_satir(self, parent, label_text, widget_class, row, col=0, **kwargs):
        """Form satırı: küçük üst-etiket + widget — modern input görünümü."""
        container = tk.Frame(parent, bg=self.renkler["kart_arkaplan"])
        lbl = tk.Label(container, text=label_text.upper(),
                       font=('Segoe UI', 8, 'bold'),
                       bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"])
        lbl.pack(anchor='w', padx=2, pady=(0, 2))
        widget = widget_class(container, **kwargs)
        widget.pack(fill='x', pady=(0, 0))
        container.grid(row=row, column=col, sticky='ew', padx=8, pady=8)
        self.themed_widgets.append((container, 'kart'))
        self.themed_widgets.append((lbl, 'muted_label'))
        return widget



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
        self.pending_sync_file = os.path.join(self.data_dir, "bekleyen_senkron.json")
        self.admin_cache_file = os.path.join(self.data_dir, "admin_onbellek.json")
        os.makedirs(self.islem_yedek_dir, exist_ok=True)

        self.eski_veriyi_tasi("hayvan_verileri.json", self.data_file)
        self.eski_veriyi_tasi("okunan_uyarilar.json", self.uyari_file)
        self.api_url = self.api_url_yukle()
        self.api_modu = bool(self.api_url)
        self.api_cevrimdisi = False
        self.api_offline_oturum = False
        self._api_son_idler = set()
        self._api_son_hata = None
        self._offline_kullanici_adi = None
        self._offline_sifre = None
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
            with open(dosya_yolu, 'r', encoding='utf-8') as f:
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
        if cache.get("api_url") and cache.get("api_url") != getattr(self, "api_url", ""):
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
        kayit = copy.deepcopy(self.hayvan_kayit_tamamla(h_id, veri))
        kayit["id"] = h_id
        self.bekleyen_senkron.setdefault("upserts", {})[h_id] = kayit

    def bekleyen_senkron_delete(self, h_id):
        h_id = str(h_id)
        self.bekleyen_senkron.setdefault("upserts", {}).pop(h_id, None)
        self.bekleyen_senkron.setdefault("deletes", {})[h_id] = {
            "id": h_id,
            "zaman": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        }

    def bekleyen_senkron_snapshot_guncelle(self):
        onceki_idler = set(getattr(self, "_api_son_idler", set()))
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
        request = urllib.request.Request(
            f"{self.api_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
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
        except TimeoutError as e:
            raise ApiHatasi("API isteği zaman aşımına uğradı.") from e

    def api_giris_yap(self, kullanici_adi, sifre):
        try:
            yanit = self.api_istek(
                "POST",
                "/api/auth/login",
                {"kullanici_adi": kullanici_adi, "sifre": sifre},
                timeout=20,
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
        return True

    def api_online_oturum_ac(self):
        if getattr(self, "api_token", None) and not getattr(self, "api_offline_oturum", False):
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
            timeout=20,
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
        if self.admin_mi() and getattr(self, "admin_aktif_ciftlik_id", None):
            payload["ciftlik_id"] = payload.get("ciftlik_id") or self.admin_aktif_ciftlik_id
            payload["ciftlik_ad"] = payload.get("ciftlik_ad") or self.admin_aktif_ciftlik_ad

        if h_id in onceki_idler:
            try:
                kayit = self.api_istek("PATCH", f"/api/hayvanlar/{self.api_ref(h_id)}", payload)
            except ApiHatasi as e:
                if e.status != 404:
                    raise
                kayit = self.api_istek("POST", "/api/hayvanlar", payload)
        else:
            try:
                kayit = self.api_istek("POST", "/api/hayvanlar", payload)
            except ApiHatasi as e:
                if e.status == 409 and "eski offline" in str(e).lower():
                    return h_id, None
                if e.status not in (400, 404, 409):
                    raise
                kayit = self.api_istek("PATCH", f"/api/hayvanlar/{self.api_ref(h_id)}", payload)

        kayit_id = str((kayit or {}).get("id") or h_id)
        return kayit_id, self.hayvan_kayit_tamamla(kayit_id, kayit or payload)

    def bekleyen_senkron_gonder(self, sessiz=False):
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
                silme_zamani = (deletes.get(h_id) or {}).get("zaman")
                delete_path = f"/api/hayvanlar/{self.api_ref(h_id)}?kalici=true"
                if silme_zamani:
                    delete_path += f"&degisiklik_zamani={self.api_ref(silme_zamani)}"
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
            return False
        self.hayvanlar = self.api_hayvanlari_yukle()
        self.json_dosyasi_kaydet(self.data_file, self.hayvanlar, "hayvan_verileri", "API Onbellek Kayit Hatasi")
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

    def _api_giris_penceresi_popup_eski(self):
        sonuc = {"ok": False}
        pencere = tk.Toplevel(self.root)
        pencere.title("ALP Ziraat Giriş")
        pencere.geometry("420x360")
        pencere.resizable(False, False)
        pencere.configure(bg=self.renkler["arkaplan"])
        pencere.transient(self.root)
        pencere.grab_set()
        pencere.update_idletasks()
        x = self.root.winfo_x() + max((self.root.winfo_width() - pencere.winfo_width()) // 2, 80)
        y = self.root.winfo_y() + max((self.root.winfo_height() - pencere.winfo_height()) // 2, 80)
        pencere.geometry(f"+{x}+{y}")
        pencere.lift()
        pencere.attributes("-topmost", True)
        pencere.after(250, lambda: pencere.attributes("-topmost", False) if pencere.winfo_exists() else None)
        pencere.focus_force()

        kutu = tk.Frame(
            pencere,
            bg=self.renkler["kart_arkaplan"],
            padx=26,
            pady=24,
            highlightthickness=1,
            highlightbackground=self.renkler["kenarlik"],
        )
        kutu.pack(fill="both", expand=True, padx=22, pady=22)

        tk.Label(
            kutu,
            text="ALP Ziraat",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["yazi_rengi"],
            font=("Segoe UI", 19, "bold"),
        ).pack(anchor="w")
        tk.Label(
            kutu,
            text="Çiftlik hesabınızla giriş yapın",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(0, 18))

        tk.Label(kutu, text="Kullanıcı adı", bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
        kullanici_entry = ttk.Entry(kutu, font=("Segoe UI", 11), style="TEntry")
        kullanici_entry.pack(fill="x", pady=(4, 12), ipady=5)

        tk.Label(kutu, text="Şifre", bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
        sifre_entry = ttk.Entry(kutu, font=("Segoe UI", 11), style="TEntry", show="*")
        sifre_entry.pack(fill="x", pady=(4, 12), ipady=5)

        durum_label = tk.Label(kutu, text="", bg=self.renkler["kart_arkaplan"], fg=self.renkler["ana_kirmizi"], font=("Segoe UI", 9))
        durum_label.pack(anchor="w", pady=(0, 10))

        def giris():
            kullanici_adi = kullanici_entry.get().strip()
            sifre = sifre_entry.get()
            if not kullanici_adi or not sifre:
                durum_label.config(text="Kullanıcı adı ve şifre zorunludur.")
                return
            try:
                self.api_giris_yap(kullanici_adi, sifre)
                sonuc["ok"] = True
                pencere.destroy()
            except ApiHatasi as e:
                durum_label.config(text=str(e))

        def iptal():
            sonuc["ok"] = False
            pencere.destroy()

        btn_frame = tk.Frame(kutu, bg=self.renkler["kart_arkaplan"])
        btn_frame.pack(fill="x", pady=(4, 0))
        tk.Button(
            btn_frame,
            text="Giriş",
            command=giris,
            bg=self.renkler["button_primary_bg"],
            fg=self.renkler["button_primary_fg"],
            activebackground=self.renkler["button_primary_bg"],
            activeforeground=self.renkler["button_primary_fg"],
            relief="flat",
            padx=16,
            pady=8,
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")
        tk.Button(
            btn_frame,
            text="İptal",
            command=iptal,
            bg=self.renkler["button_default_bg"],
            fg=self.renkler["button_default_fg"],
            relief="flat",
            padx=16,
            pady=8,
            font=("Segoe UI", 10),
        ).pack(side="left", padx=(8, 0))

        sifre_entry.bind("<Return>", lambda event: giris())
        kullanici_entry.focus_set()
        pencere.protocol("WM_DELETE_WINDOW", iptal)
        self.root.wait_window(pencere)
        return sonuc["ok"]

    def api_giris_penceresi(self):
        sonuc = {"ok": False}
        tamam = tk.BooleanVar(value=False)

        for child in self.root.winfo_children():
            child.destroy()

        self.root.title("ALP Ziraat - Giris")
        self.root.geometry("460x430")
        self.root.minsize(460, 430)
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

        tk.Label(
            kutu,
            text="ALP Ziraat",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["yazi_rengi"],
            font=("Segoe UI", 21, "bold"),
        ).pack(anchor="w")
        tk.Label(
            kutu,
            text="Ciftlik hesabiniza giris yapin",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(0, 22))

        tk.Label(
            kutu,
            text="Kullanici adi",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")
        kullanici_entry = ttk.Entry(kutu, font=("Segoe UI", 11), style="TEntry")
        kullanici_entry.pack(fill="x", pady=(5, 14), ipady=6)

        tk.Label(
            kutu,
            text="Sifre",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["muted"],
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")
        sifre_entry = ttk.Entry(kutu, font=("Segoe UI", 11), style="TEntry", show="*")
        sifre_entry.pack(fill="x", pady=(5, 14), ipady=6)

        durum_label = tk.Label(
            kutu,
            text="",
            bg=self.renkler["kart_arkaplan"],
            fg=self.renkler["ana_kirmizi"],
            font=("Segoe UI", 9),
            wraplength=350,
            justify="left",
        )
        durum_label.pack(anchor="w", fill="x", pady=(0, 12))

        def bitir(ok):
            sonuc["ok"] = ok
            try:
                tamam.set(True)
            except tk.TclError:
                pass

        def giris():
            kullanici_adi = kullanici_entry.get().strip()
            sifre = sifre_entry.get()
            if not kullanici_adi or not sifre:
                durum_label.config(text="Kullanici adi ve sifre zorunludur.")
                return
            durum_label.config(text="Giris yapiliyor...")
            self.root.update_idletasks()
            try:
                self.api_giris_yap(kullanici_adi, sifre)
                bitir(True)
            except ApiHatasi as e:
                durum_label.config(text=str(e))

        def iptal():
            bitir(False)

        btn_frame = tk.Frame(kutu, bg=self.renkler["kart_arkaplan"])
        btn_frame.pack(fill="x", pady=(2, 0))
        tk.Button(
            btn_frame,
            text="Giris",
            command=giris,
            bg=self.renkler["button_primary_bg"],
            fg=self.renkler["button_primary_fg"],
            activebackground=self.renkler["button_primary_bg"],
            activeforeground=self.renkler["button_primary_fg"],
            relief="flat",
            padx=18,
            pady=9,
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")
        tk.Button(
            btn_frame,
            text="Iptal",
            command=iptal,
            bg=self.renkler["button_default_bg"],
            fg=self.renkler["button_default_fg"],
            relief="flat",
            padx=18,
            pady=9,
            font=("Segoe UI", 10),
        ).pack(side="left", padx=(8, 0))

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
        self.root.after(100, kullanici_entry.focus_force)

        try:
            self.root.wait_variable(tamam)
        except tk.TclError:
            return False

        for child in self.root.winfo_children():
            child.destroy()
        self.root.unbind("<Escape>")

        if not sonuc["ok"]:
            return False

        self.root.title("ALP ZIRAAT - Suru Takip Sistemi")
        self.root.geometry("1600x1000")
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
        if not self.admin_mi():
            return messagebox.showerror("Yedek", "Bu islem icin admin yetkisi gerekir.", parent=parent or self.root)
        if not self.online_islem_gerekli("Online yedek alma", parent or self.root):
            return
        try:
            yedek = self.api_istek("GET", "/api/yedek", timeout=45)
        except ApiHatasi as e:
            return messagebox.showerror("Yedek", f"Online yedek alinamadi:\n{e}", parent=parent or self.root)
        zaman = datetime.now().strftime("%Y%m%d_%H%M%S")
        varsayilan_ad = f"alp_online_yedek_{zaman}.json"
        dosya = filedialog.asksaveasfilename(
            parent=parent or self.root,
            title="Online Yedek Kaydet",
            defaultextension=".json",
            initialfile=varsayilan_ad,
            filetypes=[("JSON", "*.json"), ("Tum dosyalar", "*.*")],
        )
        if not dosya:
            return
        try:
            with open(dosya, "w", encoding="utf-8") as f:
                json.dump(yedek, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Yedek", f"Online yedek kaydedildi:\n{dosya}", parent=parent or self.root)
        except Exception as e:
            messagebox.showerror("Yedek", f"Yedek dosyasi yazilamadi:\n{e}", parent=parent or self.root)

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
            columns=("zaman", "kullanici", "tip", "ciftlik", "detay"),
            show="headings",
            style="Modern.Treeview",
        )
        for col, baslik, genislik in [
            ("zaman", "Zaman", 150),
            ("kullanici", "Kullanici", 130),
            ("tip", "Islem", 130),
            ("ciftlik", "Ciftlik", 140),
            ("detay", "Detay", 390),
        ]:
            tree.heading(col, text=baslik)
            tree.column(col, width=genislik, anchor="w")
        tree.pack(fill="both", expand=True)

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
                        kayit.get("detay") or "",
                    ),
                )

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
                            f"API baglantisi kurulamadi; son kayitli yonetim listesi gosteriliyor.\n\n{e}",
                            parent=self.root,
                        )
                    else:
                        messagebox.showerror("Admin Merkezi", f"Yonetim verileri alinamadi:\n{e}", parent=self.root)
                return False

        verileri_yenile(sessiz=True)

        for child in self.root.winfo_children():
            child.destroy()

        self.root.title("ALP Ziraat - Admin Merkezi")
        self.root.geometry("860x640")
        self.root.minsize(780, 560)
        self.root.resizable(True, True)
        self.root.configure(bg=self.renkler["arkaplan"])
        self.root.deiconify()
        self.root.lift()

        sayfa = tk.Frame(self.root, bg=self.renkler["arkaplan"], padx=28, pady=24)
        sayfa.pack(fill="both", expand=True)

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
            text="Ciftlikleri, kullanicilari ve suru verilerini tek yerden yonetin.",
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

        sol = tk.Frame(govde, bg=self.renkler["kart_arkaplan"], padx=18, pady=18, highlightthickness=1, highlightbackground=self.renkler["kenarlik"])
        sag = tk.Frame(govde, bg=self.renkler["kart_arkaplan"], padx=18, pady=18, highlightthickness=1, highlightbackground=self.renkler["kenarlik"])
        sol.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        sag.grid(row=0, column=1, sticky="nsew", padx=(9, 0))

        tk.Label(sol, text="Suruye Giris", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=("Segoe UI", 15, "bold")).pack(anchor="w")
        tk.Label(sol, text="Tum kayitlari gorebilir veya belirli bir ciftlige odaklanabilirsiniz.", bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 9), wraplength=320, justify="left").pack(anchor="w", pady=(4, 14))

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

        def bitir(ok):
            sonuc["ok"] = ok
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
                    "Offline modda tum suru verisi guvenli sekilde yenilenemez. Internet gelince Senkronize Et ile tekrar deneyin.",
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
                    "Offline modda ciftlik degistirmek yerine sadece son kayitli ciftlik listesi gosterilir. Internet gelince Senkronize Et ile suruye girin.",
                    parent=self.root,
                )
                return
            ciftlik = secili_ciftlik()
            if not ciftlik:
                messagebox.showwarning("Admin Merkezi", "Once bir ciftlik secin.", parent=self.root)
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

        ciftlik_liste.bind("<<ListboxSelect>>", listeden_ciftlik_sec)

        admin_buton(sol, "Tum ciftliklerin suru takibine gir", tum_suruye_gir, self.renkler["button_primary_bg"]).pack(fill="x", pady=5)
        admin_buton(sol, "Secili ciftligin surusune gir", secili_suruye_gir, self.renkler["button_success_bg"]).pack(fill="x", pady=5)

        tk.Label(sag, text="Yonetim", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=("Segoe UI", 15, "bold")).pack(anchor="w")
        tk.Label(sag, text="Yeni ciftlik acin, kullanici atayin veya mevcut yetkileri duzenleyin.", bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 9), wraplength=320, justify="left").pack(anchor="w", pady=(4, 14))

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
                text=f"{len(state['ciftlikler'])} ciftlik  |  {len(state['kullanicilar'])} kullanici  |  Admin: {(self.api_kullanici or {}).get('kullanici_adi', '-')}"
            )
            if state.get("offline_cache"):
                zaman = state.get("cache_time") or "bilinmiyor"
                admin_durum_label.config(
                    text=f"Offline: son kayitli liste gosteriliyor. Son guncelleme: {zaman}",
                    fg=self.renkler["uyari"],
                )
            else:
                admin_durum_label.config(text="API bagli: yonetim listesi guncel.", fg=self.renkler["yesil"])

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
                messagebox.showinfo("Admin Merkezi", "API baglantisi yenilendi ve yonetim listesi guncellendi.", parent=self.root)

        admin_buton(sag, "Ciftlikleri yonet", ciftlikleri_yonet).pack(fill="x", pady=5)
        admin_buton(sag, "Kullanicilari yonet", lambda: kullanicilari_yonet(False)).pack(fill="x", pady=5)
        admin_buton(sag, "Yeni kullanici olustur", lambda: kullanicilari_yonet(True), self.renkler["button_success_bg"]).pack(fill="x", pady=5)
        admin_buton(sag, "Son islemleri gor", self.admin_islem_gecmisi_penceresi).pack(fill="x", pady=5)
        admin_buton(sag, "Online yedek indir", lambda: self.admin_online_yedek_indir(self.root), self.renkler["button_primary_bg"]).pack(fill="x", pady=5)
        admin_buton(sag, "Sifremi degistir", lambda: self.sifre_degistir_penceresi(self.root)).pack(fill="x", pady=5)
        admin_buton(sag, "Senkronize Et", admin_senkronize_et, self.renkler["button_primary_bg"]).pack(fill="x", pady=5)
        admin_buton(sag, "Listeyi yenile", lambda: (verileri_yenile(), ekrani_yenile())).pack(fill="x", pady=5)

        alt = tk.Frame(sayfa, bg=self.renkler["arkaplan"])
        alt.pack(fill="x", pady=(18, 0))
        admin_buton(alt, "Cikis", lambda: bitir(False), self.renkler["button_danger_bg"]).pack(side="right")

        self.root.protocol("WM_DELETE_WINDOW", lambda: bitir(False))
        self.root.bind("<Escape>", lambda event: bitir(False))
        ekrani_yenile()

        try:
            self.root.wait_variable(tamam)
        except tk.TclError:
            return False

        self.root.unbind("<Escape>")
        for child in self.root.winfo_children():
            child.destroy()
        return sonuc["ok"]

    def admin_ciftlik_yonetim_penceresi(self):
        if not self.online_islem_gerekli("Ciftlik yonetimi", self.root):
            return
        pencere = tk.Toplevel(self.root)
        pencere.title("Ciftlik Yonetimi")
        pencere.geometry("860x520")
        pencere.configure(bg=self.renkler["arkaplan"])
        pencere.transient(self.root)
        pencere.grab_set()

        ciftlikler = []
        secili = {"id": None}

        ana = tk.Frame(pencere, bg=self.renkler["arkaplan"], padx=16, pady=16)
        ana.pack(fill="both", expand=True)
        ana.columnconfigure(0, weight=3)
        ana.columnconfigure(1, weight=2)

        tree = ttk.Treeview(ana, columns=("id", "ad", "aktif", "aciklama"), show="headings", style="Modern.Treeview")
        for col, baslik, genislik in [
            ("id", "ID", 170),
            ("ad", "Ciftlik", 180),
            ("aktif", "Durum", 80),
            ("aciklama", "Aciklama", 260),
        ]:
            tree.heading(col, text=baslik)
            tree.column(col, width=genislik, anchor="center")
        tree.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        ana.rowconfigure(0, weight=1)

        form = tk.Frame(ana, bg=self.renkler["kart_arkaplan"], padx=16, pady=16, highlightthickness=1, highlightbackground=self.renkler["kenarlik"])
        form.grid(row=0, column=1, sticky="nsew")

        tk.Label(form, text="Ciftlik Bilgisi", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 12))
        tk.Label(form, text="ID (yeni kayitta istege bagli)", bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
        id_entry = ttk.Entry(form, font=("Segoe UI", 10), style="TEntry")
        id_entry.pack(fill="x", pady=(4, 10), ipady=4)
        tk.Label(form, text="Ciftlik adi", bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
        ad_entry = ttk.Entry(form, font=("Segoe UI", 10), style="TEntry")
        ad_entry.pack(fill="x", pady=(4, 10), ipady=4)
        tk.Label(form, text="Aciklama", bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
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
                return messagebox.showerror("Ciftlik", "Ciftlik adi zorunludur.", parent=pencere)
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
                messagebox.showerror("Ciftlik", str(e), parent=pencere)

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
                return messagebox.showwarning("Ciftlik Sil", "Silmek icin listeden bir ciftlik secin.", parent=pencere)
            ciftlik = next((c for c in ciftlikler if c.get("id") == secili["id"]), None)
            if not ciftlik:
                return messagebox.showerror("Ciftlik Sil", "Secili ciftlik bulunamadi.", parent=pencere)
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
                detaylar.append(f"{kullanici_sayisi} kullanici")
            detay_metni = "\nSilinecek kayitlar: " + ", ".join(detaylar) if detaylar else ""
            onay = messagebox.askyesno(
                "Ciftlik Sil",
                (
                    f"{ciftlik.get('ad') or secili['id']} ciftligi kalici olarak silinecek."
                    f"{detay_metni}\n\nBu islem geri alinamaz. Emin misiniz?"
                ),
                parent=pencere,
                icon="warning",
            )
            if not onay:
                return
            yazili_onay = simpledialog.askstring(
                "Kalici Silme Onayi",
                "Devam etmek icin SIL yazin:",
                parent=pencere,
            )
            if (yazili_onay or "").strip().upper() != "SIL":
                return messagebox.showinfo("Ciftlik Sil", "Silme islemi iptal edildi.", parent=pencere)
            try:
                sonuc = self.api_istek("DELETE", f"/api/ciftlikler/{self.api_ref(secili['id'])}", timeout=30)
                if getattr(self, "admin_aktif_ciftlik_id", None) == secili["id"]:
                    self.admin_aktif_ciftlik_id = None
                    self.admin_aktif_ciftlik_ad = None
                    self.hayvanlar = {}
                messagebox.showinfo("Ciftlik Sil", sonuc.get("message", "Ciftlik silindi."), parent=pencere)
                liste_yenile()
                form_temizle()
            except ApiHatasi as e:
                messagebox.showerror("Ciftlik Sil", str(e), parent=pencere)

        tree.bind("<<TreeviewSelect>>", secimi_yukle)
        btnler = tk.Frame(form, bg=self.renkler["kart_arkaplan"])
        btnler.pack(fill="x", pady=(8, 0))
        tk.Button(btnler, text="Yeni", command=form_temizle, bg=self.renkler["button_default_bg"], fg=self.renkler["button_default_fg"], relief="flat", padx=12, pady=8).pack(side="left")
        tk.Button(btnler, text="Kaydet", command=kaydet, bg=self.renkler["button_success_bg"], fg="#FFFFFF", relief="flat", padx=12, pady=8).pack(side="left", padx=8)
        tk.Button(btnler, text="Sil", command=sil, bg=self.renkler["button_danger_bg"], fg="#FFFFFF", relief="flat", padx=12, pady=8).pack(side="left")
        tk.Button(btnler, text="Kapat", command=pencere.destroy, bg=self.renkler["button_default_bg"], fg=self.renkler["button_default_fg"], relief="flat", padx=12, pady=8).pack(side="left", padx=8)

        try:
            liste_yenile()
        except ApiHatasi as e:
            messagebox.showerror("Ciftlik", str(e), parent=pencere)
        pencere.wait_window()

    def admin_kullanici_yonetim_penceresi(self, yeni_kullanici=False):
        if not self.online_islem_gerekli("Kullanici yonetimi", self.root):
            return
        pencere = tk.Toplevel(self.root)
        pencere.title("Kullanici Yonetimi")
        pencere.geometry("960x580")
        pencere.configure(bg=self.renkler["arkaplan"])
        pencere.transient(self.root)
        pencere.grab_set()

        kullanicilar = []
        ciftlikler = self.api_ciftlikleri_yukle()
        secili = {"id": None}

        ana = tk.Frame(pencere, bg=self.renkler["arkaplan"], padx=16, pady=16)
        ana.pack(fill="both", expand=True)
        ana.columnconfigure(0, weight=3)
        ana.columnconfigure(1, weight=2)

        tree = ttk.Treeview(ana, columns=("id", "kullanici", "rol", "ciftlik", "aktif"), show="headings", style="Modern.Treeview")
        for col, baslik, genislik in [
            ("id", "ID", 130),
            ("kullanici", "Kullanici", 150),
            ("rol", "Rol", 90),
            ("ciftlik", "Ciftlik", 170),
            ("aktif", "Durum", 80),
        ]:
            tree.heading(col, text=baslik)
            tree.column(col, width=genislik, anchor="center")
        tree.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        ana.rowconfigure(0, weight=1)

        form = tk.Frame(ana, bg=self.renkler["kart_arkaplan"], padx=16, pady=16, highlightthickness=1, highlightbackground=self.renkler["kenarlik"])
        form.grid(row=0, column=1, sticky="nsew")
        tk.Label(form, text="Kullanici Bilgisi", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 12))

        tk.Label(form, text="Kullanici adi", bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
        ad_entry = ttk.Entry(form, font=("Segoe UI", 10), style="TEntry")
        ad_entry.pack(fill="x", pady=(4, 10), ipady=4)
        tk.Label(form, text="Sifre (guncellemede bos kalabilir)", bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
        sifre_entry = ttk.Entry(form, font=("Segoe UI", 10), style="TEntry", show="*")
        sifre_entry.pack(fill="x", pady=(4, 10), ipady=4)
        tk.Label(form, text="Rol", bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
        rol_combo = ttk.Combobox(form, values=["ciftlik", "admin"], state="readonly", font=("Segoe UI", 10), style="TCombobox")
        rol_combo.pack(fill="x", pady=(4, 10), ipady=4)
        rol_combo.set("ciftlik")
        tk.Label(form, text="Ciftlik", bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
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
                ciftlik_ad = (k.get("ciftlik") or {}).get("ad") or ("Tum ciftlikler" if k.get("rol") == "admin" else "-")
                tree.insert("", "end", iid=k.get("id"), values=(k.get("id"), k.get("kullanici_adi"), k.get("rol"), ciftlik_ad, "Aktif" if k.get("aktif", True) else "Pasif"))

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
                return messagebox.showerror("Kullanici", "Kullanici adi zorunludur.", parent=pencere)
            if not secili["id"] and not sifre:
                return messagebox.showerror("Kullanici", "Yeni kullanici icin sifre zorunludur.", parent=pencere)
            if rol != "admin" and not ciftlik_id:
                return messagebox.showerror("Kullanici", "Ciftlik kullanicisi icin ciftlik secilmelidir.", parent=pencere)
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
                messagebox.showerror("Kullanici", str(e), parent=pencere)

        def sil():
            if not secili["id"]:
                return messagebox.showwarning("Kullanici Sil", "Silmek icin listeden bir kullanici secin.", parent=pencere)
            kullanici = next((k for k in kullanicilar if k.get("id") == secili["id"]), None)
            if not kullanici:
                return messagebox.showerror("Kullanici Sil", "Secili kullanici bulunamadi.", parent=pencere)
            aktif_id = (self.api_kullanici or {}).get("id")
            if aktif_id and aktif_id == secili["id"]:
                return messagebox.showerror("Kullanici Sil", "Kendi admin kullanicinizi silemezsiniz.", parent=pencere)
            onay = messagebox.askyesno(
                "Kullanici Sil",
                (
                    f"{kullanici.get('kullanici_adi') or secili['id']} kullanicisi kalici olarak silinecek.\n\n"
                    "Bu islem geri alinamaz. Emin misiniz?"
                ),
                parent=pencere,
                icon="warning",
            )
            if not onay:
                return
            try:
                sonuc = self.api_istek("DELETE", f"/api/kullanicilar/{self.api_ref(secili['id'])}", timeout=20)
                messagebox.showinfo("Kullanici Sil", sonuc.get("message", "Kullanici silindi."), parent=pencere)
                liste_yenile()
                form_temizle()
            except ApiHatasi as e:
                messagebox.showerror("Kullanici Sil", str(e), parent=pencere)

        def sifre_sifirla():
            if not secili["id"]:
                return messagebox.showwarning("Sifre Sifirla", "Sifresini degistirmek icin listeden bir kullanici secin.", parent=pencere)
            kullanici = next((k for k in kullanicilar if k.get("id") == secili["id"]), None)
            if not kullanici:
                return messagebox.showerror("Sifre Sifirla", "Secili kullanici bulunamadi.", parent=pencere)
            yeni = simpledialog.askstring("Sifre Sifirla", "Yeni sifre (en az 8 karakter):", show="*", parent=pencere)
            if yeni is None:
                return
            tekrar = simpledialog.askstring("Sifre Sifirla", "Yeni sifre tekrar:", show="*", parent=pencere)
            if tekrar is None:
                return
            if yeni != tekrar:
                return messagebox.showerror("Sifre Sifirla", "Yeni sifreler ayni degil.", parent=pencere)
            try:
                sonuc = self.api_istek(
                    "POST",
                    f"/api/kullanicilar/{self.api_ref(secili['id'])}/sifre-sifirla",
                    {"yeni_sifre": yeni},
                    timeout=20,
                )
                messagebox.showinfo("Sifre Sifirla", sonuc.get("message", "Sifre sifirlandi."), parent=pencere)
                sifre_entry.delete(0, tk.END)
            except ApiHatasi as e:
                messagebox.showerror("Sifre Sifirla", str(e), parent=pencere)

        tree.bind("<<TreeviewSelect>>", secimi_yukle)
        btnler = tk.Frame(form, bg=self.renkler["kart_arkaplan"])
        btnler.pack(fill="x", pady=(8, 0))
        tk.Button(btnler, text="Yeni", command=form_temizle, bg=self.renkler["button_default_bg"], fg=self.renkler["button_default_fg"], relief="flat", padx=12, pady=8).pack(side="left")
        tk.Button(btnler, text="Kaydet", command=kaydet, bg=self.renkler["button_success_bg"], fg="#FFFFFF", relief="flat", padx=12, pady=8).pack(side="left", padx=8)
        tk.Button(btnler, text="Sil", command=sil, bg=self.renkler["button_danger_bg"], fg="#FFFFFF", relief="flat", padx=12, pady=8).pack(side="left")
        tk.Button(btnler, text="Sifre", command=sifre_sifirla, bg=self.renkler["button_warning_bg"], fg=self.renkler["button_warning_fg"], relief="flat", padx=12, pady=8).pack(side="left", padx=8)
        tk.Button(btnler, text="Kapat", command=pencere.destroy, bg=self.renkler["button_default_bg"], fg=self.renkler["button_default_fg"], relief="flat", padx=12, pady=8).pack(side="left")

        try:
            liste_yenile()
            if yeni_kullanici:
                form_temizle()
        except ApiHatasi as e:
            messagebox.showerror("Kullanici", str(e), parent=pencere)
        pencere.wait_window()

    def admin_merkeze_don(self):
        if not self.admin_mi():
            return
        eski_ciftlik_id = getattr(self, "admin_aktif_ciftlik_id", None)
        eski_ciftlik_ad = getattr(self, "admin_aktif_ciftlik_ad", None)
        self.uyari_thread_running = False
        if getattr(self, "_uyari_after_id", None):
            try:
                self.root.after_cancel(self._uyari_after_id)
            except tk.TclError:
                pass
            self._uyari_after_id = None
        for child in self.root.winfo_children():
            child.destroy()
        self.themed_widgets = []
        self.themed_buttons = []
        if not self.admin_yonetim_merkezi():
            self.admin_aktif_ciftlik_id = eski_ciftlik_id
            self.admin_aktif_ciftlik_ad = eski_ciftlik_ad
        try:
            self.hayvanlar = self.veri_yukle()
        except Exception as e:
            messagebox.showerror("Admin Merkezi", f"Suru verisi yuklenemedi:\n{e}", parent=self.root)
        self.uyari_thread_running = True
        self.ana_interface_olustur()
        self.uyari_sistemi_baslat()

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
        self.api_cevrimdisi = False
        self.api_offline_oturum = False
        self._api_son_hata = None
        return hayvanlar_dict

    def api_hayvanlari_kaydet(self):
        if self.offline_modda_mi():
            raise ApiHatasi("API offline modda; kayitlar yerel senkron kuyruguna alinacak.")
        if self.bekleyen_senkron_var() and not self.bekleyen_senkron_gonder(sessiz=True):
            raise ApiHatasi("Bekleyen offline degisiklikler senkronlanamadi.")

        onceki_idler = set(getattr(self, "_api_son_idler", set()))
        mevcut_idler = {str(h_id) for h_id in self.hayvanlar.keys()}

        for silinen_id in sorted(onceki_idler - mevcut_idler):
            self.api_istek("DELETE", f"/api/hayvanlar/{self.api_ref(silinen_id)}?kalici=true")

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
        veri['cins'] = veri.get('cins') or "Bilinmiyor"
        veri['yas_gun'] = self.hayvan_yas_gun_hesapla(veri)
        veri['durum'] = veri.get('durum') or self.durum_hesapla(veri.get('cins'), veri.get('yas_gun', 0))
        veri['tohumlamalar'] = list(veri.get('tohumlamalar') or [])
        veri['dogumlar'] = list(veri.get('dogumlar') or [])
        veri['asi_prosedurler'] = list(veri.get('asi_prosedurler') or [])
        veri['gebe_mi'] = bool(veri.get('gebe_mi', False))
        veri['olu'] = bool(veri.get('olu', False))
        veri['kesildi'] = bool(veri.get('kesildi', False))
        veri['arsivli'] = bool(veri.get('arsivli', False))
        veri.setdefault('anne_kupe', "")
        veri.setdefault('ciftlik_id', None)
        veri.setdefault('ciftlik_ad', None)
        veri.setdefault('kayit_tarihi', "")
        veri.setdefault('gebelik_tarihi', None)
        veri.setdefault('aktif_tohumlama_id', None)
        veri.setdefault('olum_tarihi', None)
        veri.setdefault('kesim_bilgisi', None)
        veri.setdefault('arsiv_tarihi', None)
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

    def hayvan_id_bul(self, kupe_girdi, aktif_olsun=False, haric_id=None):
        aranan = str(kupe_girdi or "").strip().upper()
        if not aranan:
            return None
        haric_id = str(haric_id) if haric_id is not None else None
        for h_id, hayvan in self.hayvanlar.items():
            if haric_id is not None and str(h_id) == haric_id:
                continue
            if aktif_olsun and (hayvan.get('arsivli') or hayvan.get('olu') or hayvan.get('kesildi')):
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

    def veri_kaydet(self, kupe_no=None):
        if getattr(self, "api_modu", False):
            if self.offline_modda_mi():
                self.bekleyen_senkron_snapshot_guncelle()
                self.api_durum_guncelle()
                return self.json_dosyasi_kaydet(self.data_file, self.hayvanlar, "hayvan_verileri", "Veri Kayit Hatasi")
            try:
                return self.api_hayvanlari_kaydet()
            except ApiHatasi as e:
                self.api_cevrimdisi = True
                self._api_son_hata = str(e)
                self.bekleyen_senkron_snapshot_guncelle()
                self.api_durum_guncelle()
                print(f"API kaydetme hatası: {e}")
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

    def islem_kaydi_baslat(self, aciklama):
        if hasattr(self, "hayvanlar"):
            try:
                self.geri_al_yigini.append({
                    "zaman": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    "aciklama": aciklama,
                    "hayvanlar": copy.deepcopy(self.hayvanlar),
                })
                if len(self.geri_al_yigini) > 30:
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

    def islem_gecmisi_kaydet(self):
        pass

    def son_islemi_geri_al(self):
        if not getattr(self, "geri_al_yigini", None):
            messagebox.showinfo("Geri Al", "Geri alınabilecek işlem yok.", parent=self.root)
            return
        son = self.geri_al_yigini.pop()
        if not messagebox.askyesno(
            "Geri Al",
            f"Son işlem geri alınacak:\n\n{son.get('aciklama', '-')}\n\nDevam edilsin mi?",
            parent=self.root,
        ):
            self.geri_al_yigini.append(son)
            return
        self.hayvanlar = copy.deepcopy(son.get("hayvanlar", {}))
        if self.veri_kaydet():
            self.ekranlari_guncelle()
            self.header_ozet_guncelle()
            messagebox.showinfo("Geri Al", "Son işlem geri alındı.", parent=self.root)
        else:
            messagebox.showerror("Geri Al", "Geri alma kaydedilemedi.", parent=self.root)

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

        self.modern_buton(pencere, "SON İŞLEMİ GERİ AL", self.son_islemi_geri_al, purpose='warning').pack(pady=(0, 15))

    def gorunen_hayvan_satirlari(self):
        columns = list(self.hayvan_tree["columns"])
        rows = [self.hayvan_tree.item(item, "values") for item in self.hayvan_tree.get_children()]
        return columns, rows

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
            export_rows_to_excel(dosya_yolu, "ALP Ziraat Hayvan Listesi", columns, rows)
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
            export_rows_to_pdf(dosya_yolu, "ALP Ziraat Hayvan Listesi", columns, rows)
            messagebox.showinfo("Başarılı", f"PDF dosyası oluşturuldu:\n{dosya_yolu}")
        except Exception as e:
            messagebox.showerror("Dışa Aktar", f"PDF çıktısı oluşturulamadı:\n{e}")

    def yedekleri_listele(self):
        if not os.path.exists(self.backup_dir):
            return []
        yedekler = []
        for ad in os.listdir(self.backup_dir):
            if not ad.endswith(".json") or "_bozuk_" in ad:
                continue
            tam_yol = os.path.join(self.backup_dir, ad)
            if ad.startswith("hayvan_verileri_"):
                tur = "Hayvan Verileri"
            elif ad.startswith("okunan_uyarilar_"):
                tur = "Okunan Uyarılar"
            else:
                continue
            yedekler.append({
                'ad': ad,
                'tur': tur,
                'yol': tam_yol,
                'zaman': datetime.fromtimestamp(os.path.getmtime(tam_yol)).strftime("%d/%m/%Y %H:%M:%S")
            })
        return sorted(yedekler, key=lambda x: os.path.getmtime(x['yol']), reverse=True)

    def yedekten_yukle_penceresi(self):
        yedekler = self.yedekleri_listele()
        if not yedekler:
            return messagebox.showinfo("Yedekten Yükle", "Kullanılabilir yedek bulunamadı.")

        pencere = tk.Toplevel(self.root)
        pencere.title("Yedekten Yükle")
        pencere.geometry("900x520")
        pencere.configure(bg=self.renkler["arkaplan"])
        pencere.transient(self.root)

        columns = ("Tür", "Tarih", "Dosya")
        tree = ttk.Treeview(pencere, columns=columns, show="headings", style='Modern.Treeview')
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=180 if col != "Dosya" else 500, anchor='center')
        tree.pack(fill='both', expand=True, padx=15, pady=15)
        for i, yedek in enumerate(yedekler):
            tree.insert('', 'end', iid=str(i), values=(yedek['tur'], yedek['zaman'], yedek['ad']))

        def yukle():
            secim = tree.selection()
            if not secim:
                return messagebox.showwarning("Yedekten Yükle", "Önce bir yedek seçin.", parent=pencere)
            yedek = yedekler[int(secim[0])]
            if not messagebox.askyesno("Yedekten Yükle", f"Seçilen yedek geri yüklenecek:\n\n{yedek['ad']}\n\nMevcut veri önce yedeklenir. Devam edilsin mi?", parent=pencere):
                return
            try:
                if yedek['tur'] == "Hayvan Verileri":
                    self.islem_kaydi_baslat(f"Yedekten yükleme öncesi: {yedek['ad']}")
                    yeni_veri = self.json_dosyasi_yukle(yedek['yol'], None, "hayvan_verileri")
                    if yeni_veri is None:
                        return
                    self.hayvanlar = yeni_veri
                    self.veri_kaydet()
                else:
                    yeni_veri = self.json_dosyasi_yukle(yedek['yol'], None, "okunan_uyarilar")
                    if yeni_veri is None:
                        return
                    self.okunan_uyarilar = yeni_veri
                    self.okunan_uyarilar_kaydet()
                self.hayvan_listesini_guncelle()
                self.uyarilari_guncelle()
                self.raporlari_guncelle()
                if hasattr(self, 'asi_tree'):
                    self.asi_prosedur_listesini_guncelle()
                messagebox.showinfo("Başarılı", "Yedek geri yüklendi.", parent=pencere)
                pencere.destroy()
            except Exception as e:
                messagebox.showerror("Yedekten Yükle", f"Yedek geri yüklenemedi:\n{e}", parent=pencere)

        self.modern_buton(pencere, "SEÇİLİ YEDEĞİ YÜKLE", yukle, purpose='warning').pack(pady=(0, 15))

    def ekranlari_guncelle(self):
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
        # ─── ÜST BAŞLIK (HEADER) ────────────────────────────────────────────
        # Header: net, düşük gürültülü operasyon barı
        header_accentstrip = tk.Frame(self.root, bg=self.renkler["ana_kirmizi"], height=4)
        header_accentstrip.pack(fill='x')

        self.baslik_frame = tk.Frame(self.root, bg=self.renkler["siyah"], height=88)
        self.baslik_frame.pack(fill='x')
        self.baslik_frame.pack_propagate(False)
        self.themed_widgets.append((self.baslik_frame, 'baslik_frame'))

        # ── Sol: Logo paneli (beyaz arka plan — görünürlük için) ──
        sol_grup = tk.Frame(self.baslik_frame, bg=self.renkler["siyah"])
        sol_grup.pack(side='left', fill='y', padx=(16, 0))

        # Logo beyaz pill — logo PNG'nin karanlık elemanları görünsün diye
        logo_pill = tk.Frame(
            sol_grup,
            bg='#FFFFFF',
            padx=8,
            pady=5,
            highlightthickness=1,
            highlightbackground=self.renkler.get("kenarlik", self.renkler["gri"]),
            bd=0
        )
        logo_pill.pack(side='left', fill='y', pady=12, padx=(0, 14))
        try:
            logo_image = Image.open(self.logo_path).resize((120, 48), Image.Resampling.LANCZOS)
            self.logo_gorsel = ImageTk.PhotoImage(logo_image)
            tk.Label(logo_pill, image=self.logo_gorsel, bg='#FFFFFF').pack()
        except Exception as e:
            print(f"Logo yüklenemedi: {e}")
            tk.Label(logo_pill, text="ALP\nZİRAAT", font=('Segoe UI', 11, 'bold'),
                     bg='#FFFFFF', fg=self.renkler["siyah"]).pack(padx=6)

        # Başlık + tagline grubu
        baslik_metin_grup = tk.Frame(sol_grup, bg=self.renkler["siyah"])
        baslik_metin_grup.pack(side='left', fill='y')

        baslik_label = tk.Label(baslik_metin_grup, text="SÜRÜ TAKİP SİSTEMİ",
                                bg=self.renkler["siyah"], fg='#F1F5F9',
                                font=('Segoe UI', 18, 'bold'), anchor='w')
        baslik_label.pack(anchor='w', pady=(18, 0))
        self.themed_widgets.append((baslik_label, 'baslik_label'))

        alt_baslik = tk.Label(baslik_metin_grup, text="Alp Ziraat  ·  Hayvan Yönetim Platformu",
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
            pady=7,
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
        self.api_durum_guncelle()

        # Dikey ayırıcı
        header_ayirici = tk.Frame(self.baslik_frame, bg=self.renkler["kenarlik"], width=1)
        header_ayirici.pack(
            side='left', fill='y', padx=18, pady=12)
        self.themed_widgets.append((header_ayirici, 'divider'))

        # ── Sağ: İşlem Butonları ──
        sag_grup = tk.Frame(self.baslik_frame, bg=self.renkler["siyah"])
        sag_grup.pack(side='right', fill='y', padx=(0, 14))

        self.theme_toggle_button = self.modern_buton(
            sag_grup, "☀️ Açık Mod", self.toggle_theme, purpose='theme', small=True)
        self.theme_toggle_button.pack(side='right', padx=(4, 0), pady=18)
        if self.admin_mi():
            self.modern_buton(sag_grup, "Admin", self.admin_merkeze_don,
                              purpose='primary', small=True).pack(side='right', padx=4, pady=18)
        if getattr(self, "api_modu", False):
            self.modern_buton(sag_grup, "Sifre", self.sifre_degistir_penceresi,
                              purpose='default', small=True).pack(side='right', padx=4, pady=18)
            self.modern_buton(sag_grup, "Senkronize Et", self.api_senkronize_et_ui,
                              purpose='primary', small=True).pack(side='right', padx=4, pady=18)

        for metin, komut, amac in [
            ("🔗 API",          self.api_ayar_penceresi,          'primary'),
            ("↩ Geri Al",        self.son_islemi_geri_al,         'warning'),
            ("📜 Geçmiş",        self.islem_gecmisi_penceresi,    'default'),
            ("📤 Dışa Aktar",    self.disa_aktar_penceresi,       'success'),
            ("🧯 Yedekten Yükle",self.yedekten_yukle_penceresi,   'danger'),
        ]:
            if "API" in metin and not self.admin_mi():
                continue
            self.modern_buton(sag_grup, metin, komut,
                              purpose=amac, small=True).pack(side='right', padx=4, pady=18)

        # ─── BİLDİRİM BANDI ─────────────────────────────────────────────────
        self.uyari_frame = tk.Frame(self.root, bg=self.renkler["band_normal_bg"], height=38)
        self.uyari_frame.pack(fill='x')
        self.uyari_frame.pack_propagate(False)

        self.uyari_indicator = tk.Frame(self.uyari_frame, bg=self.renkler["yesil"], width=5)
        self.uyari_indicator.pack(side='left', fill='y')

        # İkon
        self._uyari_ikon_lbl = tk.Label(self.uyari_frame, text="✅",
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

        # ─── NOTEBOOK ────────────────────────────────────────────────────────
        self.notebook = ttk.Notebook(self.root, style='Modern.TNotebook')
        self.notebook.pack(fill='both', expand=True, padx=12, pady=(10, 12))

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
        self.custom_tab_bar.pack(fill='x', padx=12, pady=(10, 0), before=self.notebook)
        self.themed_widgets.append((self.custom_tab_bar, 'arkaplan'))

        self.tab_buttons = []
        for i, tab_id in enumerate(self.notebook.tabs()):
            text = self.notebook.tab(tab_id, "text")
            btn = self.modern_buton(self.custom_tab_bar, text, command=lambda idx=i: self._select_tab(idx), purpose='theme')
            btn.pack(side='left', padx=(0, 6))
            self.tab_buttons.append(btn)
            
        self.notebook.bind('<<NotebookTabChanged>>', self._update_custom_tabs)
        self._update_custom_tabs() # Başlangıçta ilk sekmeyi renklendir

        self._baslangic_after_id = self.root.after(500, self.baslangic_guncellemesi)
        self.otomatik_baglanti_kontrol_baslat()

    def header_ozet_guncelle(self):
        if not hasattr(self, 'header_stats_label'):
            return
        aktif = 0
        gebe = 0
        arsivli = 0
        for hayvan in self.hayvanlar.values():
            if hayvan.get('arsivli'):
                arsivli += 1
            if not hayvan.get('arsivli') and not hayvan.get('olu') and not hayvan.get('kesildi'):
                aktif += 1
            if hayvan.get('gebe_mi') and not hayvan.get('arsivli') and not hayvan.get('olu') and not hayvan.get('kesildi'):
                gebe += 1
        self.header_stats_label.config(text=f"{aktif} aktif  ·  {gebe} gebe  ·  {arsivli} arşiv")

    def api_durum_guncelle(self):
        if not hasattr(self, 'api_status_label'):
            return
        if getattr(self, "api_modu", False):
            kisa_url = self.api_url.replace("https://", "").replace("http://", "")
            if len(kisa_url) > 26:
                kisa_url = kisa_url[:23] + "..."
            kullanici = getattr(self, "api_kullanici", None) or {}
            kullanici_adi = kullanici.get("kullanici_adi")
            rol = kullanici.get("rol")
            if rol == "admin":
                ciftlik = getattr(self, "admin_aktif_ciftlik_ad", None) or "Tum ciftlikler"
            else:
                ciftlik = (kullanici.get("ciftlik") or {}).get("ad") or ""
            kimlik = f" · {kullanici_adi}" if kullanici_adi else ""
            if ciftlik:
                kimlik += f" · {ciftlik}"
            bekleyen = self.bekleyen_senkron_sayisi()
            bekleyen_metin = f" Â· {bekleyen} bekliyor" if bekleyen else ""
            if getattr(self, "api_cevrimdisi", False):
                metin = f"API çevrimdışı · {kisa_url}{kimlik}"
                renk = self.renkler["uyari"]
            else:
                metin = f"API bağlı · {kisa_url}{kimlik}"
                renk = self.renkler["yesil"]
            if bekleyen_metin:
                metin += bekleyen_metin
        else:
            metin = "Yerel veri"
            renk = self.renkler["muted"]
        self.api_status_label.config(text=metin, fg=renk, bg=self.api_status_pill.cget("bg"))

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

        yerel_kopya = dict(self.hayvanlar)
        if not self.api_ayarlarini_kaydet(yeni_url):
            return

        if not self.api_modu:
            self.hayvanlar = self.veri_yukle()
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
        self.header_ozet_guncelle()
        self.api_durum_guncelle()
        self.hayvan_listesini_guncelle()
        self.uyarilari_guncelle()
        self.asi_prosedur_listesini_guncelle()
        if MATPLOTLIB_AVAILABLE: 
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
                self.api_istek("GET", "/api/health", timeout=4, auth=False)
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
    
    # #################################################################
    # ### GÜNCELLENMİŞ FONKSİYON: hayvan_kayit_sekmesi
    # #################################################################
    def hayvan_kayit_sekmesi(self):
        kayit_frame = ttk.Frame(self.notebook, style='TFrame')
        self.notebook.add(kayit_frame, text="📋 Hayvan Kaydı")

        main_card = self.modern_kart(kayit_frame)
        main_card.pack(fill='both', expand=True, padx=16, pady=16)

        # ─── Bölüm Başlığı ───────────────────────────────────────────────────
        header = tk.Frame(main_card, bg=self.renkler["kart_arkaplan"], pady=20)
        header.pack(fill='x', padx=24)
        self.themed_widgets.append((header, 'kart'))

        baslik_lbl = tk.Label(header, text="Yeni Hayvan Kaydı",
                               font=('Segoe UI', 18, 'bold'),
                               bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"])
        baslik_lbl.pack(side='left')
        self.themed_widgets.append((baslik_lbl, 'label'))

        alt_lbl = tk.Label(header, text="  —  Tüm alanları doldurun ve kaydedin.",
                            font=('Segoe UI', 11),
                            bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"])
        alt_lbl.pack(side='left')
        self.themed_widgets.append((alt_lbl, 'muted_label'))

        # Yatay ayırıcı
        sep = tk.Frame(main_card, bg=self.renkler["kenarlik"], height=1)
        sep.pack(fill='x', padx=24)
        self.themed_widgets.append((sep, 'divider'))

        # Form Container
        form_frame = tk.Frame(main_card, bg=self.renkler["kart_arkaplan"], padx=32, pady=28)
        form_frame.pack(fill='both', expand=True)
        form_frame.columnconfigure((0, 1), weight=1)
        self.themed_widgets.append((form_frame, 'kart'))

        # --- Row 0 ---
        self.resmi_kupe_no_entry = self.modern_form_satir(form_frame, "🇹🇷 Resmi Küpe No", ttk.Entry, row=0, col=0, font=('Segoe UI', 11), style='TEntry')
        self.ciftlik_kupe_no_entry = self.modern_form_satir(form_frame, "🏷️ Çiftlik Küpe No", ttk.Entry, row=0, col=1, font=('Segoe UI', 11), style='TEntry')

        # --- Row 1 ---
        self.dogum_tarihi_entry = self.modern_form_satir(form_frame, "📅 Doğum Tarihi (GG/AA/YYYY)", ttk.Entry, row=1, col=0, font=('Segoe UI', 11), style='TEntry')
        self.dogum_tarihi_entry.bind('<KeyRelease>', self.tarih_formatlama)
        self.cins_combo = self.modern_form_satir(form_frame, "🐄 Cinsi", ttk.Combobox, row=1, col=1, values=["Dişi Buzağı", "Erkek Buzağı", "Dana", "Düve", "Sağmal İnek", "Kuru İnek"], font=('Segoe UI', 11), style='TCombobox')

        # --- Row 2 ---
        self.anne_kupe_entry = self.modern_form_satir(form_frame, "👩 Anne Çiftlik Küpe No", ttk.Entry, row=2, col=0, font=('Segoe UI', 11), style='TEntry')

        # --- Row 3 (Dinamik Gizli Alanlar) ---
        self.laktasyon_container = tk.Frame(form_frame, bg=self.renkler["kart_arkaplan"])
        self.laktasyon_container.grid(row=3, column=0, columnspan=2, sticky='ew')
        self.laktasyon_container.columnconfigure((0, 1), weight=1)
        self.themed_widgets.append((self.laktasyon_container, 'kart'))

        self.laktasyon_no_entry = self.modern_form_satir(self.laktasyon_container, "🔢 Laktasyon Numarası", ttk.Entry, row=0, col=0, font=('Segoe UI', 11), style='TEntry')
        self.son_dogum_tarihi_entry = self.modern_form_satir(self.laktasyon_container, "📅 Son Doğum Tarihi", ttk.Entry, row=0, col=1, font=('Segoe UI', 11), style='TEntry')
        self.son_dogum_tarihi_entry.bind('<KeyRelease>', self.tarih_formatlama)

        self.laktasyon_container.grid_remove() # Başlangıçta gizli

        self.cins_combo.bind('<<ComboboxSelected>>', self._on_cins_change)

        # Buton Container
        btn_frame = tk.Frame(form_frame, bg=self.renkler["kart_arkaplan"])
        btn_frame.grid(row=4, column=0, columnspan=2, pady=(40, 10))
        self.themed_widgets.append((btn_frame, 'kart'))

        kaydet_btn = self.modern_buton(btn_frame, "💾 HAYVANI KAYDET", self.hayvan_kaydet, purpose='success', width=25)
        kaydet_btn.pack()

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
        self.notebook.add(tohumlama_frame, text="💉 Tohumlama")

        main_card = self.modern_kart(tohumlama_frame)
        main_card.pack(fill='both', expand=True, padx=16, pady=16)

        # ─── Bölüm Başlığı ───────────────────────────────────────────────────
        header = tk.Frame(main_card, bg=self.renkler["kart_arkaplan"], pady=20)
        header.pack(fill='x', padx=24)
        self.themed_widgets.append((header, 'kart'))

        baslik_lbl = tk.Label(header, text="💉 Tohumlama İşlemleri",
                               font=('Segoe UI', 18, 'bold'),
                               bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"])
        baslik_lbl.pack(side='left')
        self.themed_widgets.append((baslik_lbl, 'label'))

        sep = tk.Frame(main_card, bg=self.renkler["kenarlik"], height=1)
        sep.pack(fill='x', padx=24)
        self.themed_widgets.append((sep, 'divider'))

        # Form Container
        form_frame = tk.Frame(main_card, bg=self.renkler["kart_arkaplan"], padx=32, pady=28)
        form_frame.pack(fill='both', expand=True)
        form_frame.columnconfigure((0, 1), weight=1)
        self.themed_widgets.append((form_frame, 'kart'))

        # --- Row 0 ---
        self.tohumlama_hayvan_combo = self.modern_form_satir(form_frame, "🐄 Hayvan Küpe No", ttk.Combobox, row=0, col=0, font=('Segoe UI', 11), style='TCombobox')
        self.tohumlama_hayvan_combo.bind('<KeyRelease>', self.hayvan_ara)
        self.tohumlama_hayvan_combo.bind('<<ComboboxSelected>>', self.combo_secimi)
        self.tohumlama_hayvanlarini_guncelle()
        
        self.tohumlama_sekli_combo = self.modern_form_satir(form_frame, "⚡ Tohumlama Şekli", ttk.Combobox, row=0, col=1, values=["Suni", "Boğa"], font=('Segoe UI', 11), style='TCombobox')
        self.tohumlama_sekli_combo.bind('<<ComboboxSelected>>', self.tohumlama_sekli_degisti)

        # --- Row 1 ---
        self.suni_container = tk.Frame(form_frame, bg=self.renkler["kart_arkaplan"])
        self.suni_container.grid(row=1, column=0, sticky='ew', padx=0, pady=0)
        self.suni_container.columnconfigure(0, weight=1)
        self.themed_widgets.append((self.suni_container, 'kart'))
        self.suni_entry = self.modern_form_satir(self.suni_container, "🧬 Suni Tohumlama İsmi", ttk.Entry, row=0, col=0, font=('Segoe UI', 11), style='TEntry')
        
        self.tohumlama_tarih_entry = self.modern_form_satir(form_frame, "📅 Tohumlama Tarihi (GG/AA/YYYY)", ttk.Entry, row=1, col=1, font=('Segoe UI', 11), style='TEntry')
        self.tohumlama_tarih_entry.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.tohumlama_tarih_entry.bind('<KeyRelease>', self.tarih_formatlama)

        # Buton Container
        btn_frame = tk.Frame(form_frame, bg=self.renkler["kart_arkaplan"])
        btn_frame.grid(row=2, column=0, columnspan=2, pady=(40, 10))
        self.themed_widgets.append((btn_frame, 'kart'))

        self.modern_buton(btn_frame, "💉 TOHUMLAMA KAYDET", self.tohumlama_kaydet, purpose='default', width=20).pack(side='left', padx=10)
        self.modern_buton(btn_frame, "✅ GEBELİK POZİTİF", self.gebelik_pozitif, purpose='success', width=20).pack(side='left', padx=10)
        self.modern_buton(btn_frame, "❌ GEBELİK NEGATİF", self.gebelik_negatif, purpose='danger', width=20).pack(side='left', padx=10)


    def hayvan_listesi_sekmesi(self):
        liste_frame = ttk.Frame(self.notebook, style='TFrame')
        self.notebook.add(liste_frame, text="📊 Hayvan Listesi")

        # ─── TOOLBAR ─────────────────────────────────────────────────────────
        toolbar = tk.Frame(
            liste_frame,
            bg=self.renkler["kart_arkaplan"],
            height=76,
            highlightthickness=1,
            highlightbackground=self.renkler["kenarlik"],
            bd=0
        )
        toolbar.pack(fill='x', padx=12, pady=(12, 0))
        toolbar.pack_propagate(False)
        self.themed_widgets.append((toolbar, 'kart'))

        # Sol — filtre ve arama
        sol = tk.Frame(toolbar, bg=self.renkler["kart_arkaplan"])
        sol.pack(side='left', fill='y', padx=16)
        self.themed_widgets.append((sol, 'kart'))

        # Filtre etiketi
        filtre_lbl = tk.Label(sol, text="FİLTRE", font=('Segoe UI', 8, 'bold'),
                              bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"])
        filtre_lbl.pack(anchor='w', pady=(10, 0))
        self.filtre_combo = ttk.Combobox(sol,
            values=["Aktif", "Tümü", "Dişi Buzağı", "Erkek Buzağı", "Dana",
                    "Düve", "Sağmal İnek", "Kuru İnek", "Gebe", "Ölü", "Kesildi", "Arşivli"],
            width=16, font=('Segoe UI', 11), state="readonly", style='TCombobox')
        self.filtre_combo.set("Aktif")
        self.filtre_combo.pack(anchor='w')
        self.filtre_combo.bind('<<ComboboxSelected>>', self.filtre_degisti)
        self.themed_widgets.append((filtre_lbl, 'muted_label'))

        # Ayırıcı
        toolbar_divider = tk.Frame(toolbar, bg=self.renkler["kenarlik"], width=1)
        toolbar_divider.pack(side='left', fill='y', padx=16, pady=12)
        self.themed_widgets.append((toolbar_divider, 'divider'))

        # Arama
        ara_grup = tk.Frame(toolbar, bg=self.renkler["kart_arkaplan"])
        ara_grup.pack(side='left', fill='y')
        self.themed_widgets.append((ara_grup, 'kart'))
        ara_lbl = tk.Label(ara_grup, text="ARA", font=('Segoe UI', 8, 'bold'),
                           bg=self.renkler["kart_arkaplan"], fg=self.renkler["muted"])
        ara_lbl.pack(anchor='w', pady=(10, 0))
        self.arama_entry = ttk.Entry(ara_grup, width=22, font=('Segoe UI', 11), style='TEntry')
        self.arama_entry.pack(anchor='w')
        self.arama_entry.bind('<KeyRelease>', self.arama_degisti)
        self.themed_widgets.append((ara_lbl, 'muted_label'))

        # Sağ — butonlar
        sag = tk.Frame(toolbar, bg=self.renkler["kart_arkaplan"])
        sag.pack(side='right', fill='y', padx=16)
        self.themed_widgets.append((sag, 'kart'))
        self.modern_buton(sag, "🔄 Yenile", self.api_verilerini_yenile,
                          purpose='success', small=True).pack(side='right', padx=(6, 0), pady=18)
        self.modern_buton(sag, "✖ Temizle", self.filtreleri_temizle,
                          purpose='danger', small=True).pack(side='right', padx=6, pady=18)

        # ─── TABLO ───────────────────────────────────────────────────────────
        liste_kart = self.modern_kart(liste_frame)
        liste_kart.pack(fill='both', expand=True, padx=12, pady=12)

        tree_frame = tk.Frame(liste_kart, bg=self.renkler["kart_arkaplan"])
        tree_frame.pack(fill='both', expand=True)
        self.themed_widgets.append((tree_frame, 'kart'))

        columns = ('ID', 'Çiftlik', 'Resmi Küpe', 'Çiftlik Küpesi', 'Yaş', 'Cinsi', 'Durum', 'Son Tohumlama', 'Doğum Tahmini', 'Sağım Günü', 'Uyarılar')
        self.hayvan_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', style='Modern.Treeview')
        col_widths = {
            'ID': 0, 'Çiftlik': 160, 'Resmi Küpe': 130, 'Çiftlik Küpesi': 110, 'Yaş': 90, 'Cinsi': 150, 'Durum': 140,
            'Son Tohumlama': 145, 'Doğum Tahmini': 145, 'Sağım Günü': 120, 'Uyarılar': 240
        }
        
        self.hayvan_tree.heading('ID', text='ID')
        self.hayvan_tree.column('ID', width=0, stretch=tk.NO) # Hide ID column
        for col in columns[1:]:
            self.hayvan_tree.heading(col, text=col)
            self.hayvan_tree.column(col, width=col_widths.get(col, 120), anchor='center', minwidth=80)

        sb_v = ttk.Scrollbar(tree_frame, orient='vertical', command=self.hayvan_tree.yview)
        sb_h = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.hayvan_tree.xview)
        self.hayvan_tree.configure(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)
        self.hayvan_tree.grid(row=0, column=0, sticky='nsew')
        sb_v.grid(row=0, column=1, sticky='ns')
        sb_h.grid(row=1, column=0, sticky='ew')
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.hayvan_tree.bind('<Double-Button-1>', self.hayvan_detay_ac)
        self.hayvan_tree.bind('<Button-3>', self.sag_tik_menu)


    def raporlama_sekmesi(self):
        rapor_sekme_frame = ttk.Frame(self.notebook, style='TFrame')
        self.notebook.add(rapor_sekme_frame, text="📈 Raporlama")

        main_card = self.modern_kart(rapor_sekme_frame)
        main_card.pack(fill='both', expand=True, padx=16, pady=16)

        header = tk.Frame(main_card, bg=self.renkler["kart_arkaplan"], pady=20)
        header.pack(fill='x', padx=24)
        self.themed_widgets.append((header, 'kart'))

        rapor_baslik_label = tk.Label(header, text="📊 Sürü Genel Durum Raporu", font=('Segoe UI', 18, 'bold'), bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"])
        rapor_baslik_label.pack(side='left')
        self.themed_widgets.append((rapor_baslik_label, 'label'))

        self.modern_buton(header, "🔄 Raporları Yenile", self.raporlari_guncelle, purpose='success', small=True).pack(side='right')

        cizgi = tk.Frame(main_card, bg=self.renkler["kenarlik"], height=1)
        cizgi.pack(fill='x', padx=24, pady=(0, 10))
        self.themed_widgets.append((cizgi, 'divider'))

        self.rapor_frame = tk.Frame(main_card, bg=self.renkler["kart_arkaplan"])
        self.rapor_frame.pack(fill='both', expand=True, padx=15, pady=15)
        self.themed_widgets.append((self.rapor_frame, 'kart'))

        if not MATPLOTLIB_AVAILABLE:
            uyari_label = tk.Label(self.rapor_frame, 
                                     text="Grafikleri görüntülemek için 'matplotlib' kütüphanesi gereklidir.\nLütfen terminal veya komut istemine 'pip install matplotlib' yazarak yükleyin.",
                                     font=('Segoe UI', 14, 'bold'), bg=self.renkler["kart_arkaplan"], fg=self.renkler["ana_kirmizi"], justify='center', wraplength=800)
            uyari_label.pack(expand=True)
            self.themed_widgets.append((uyari_label, 'label'))
    
    def raporlari_guncelle(self):
        if not MATPLOTLIB_AVAILABLE:
            return 

        if hasattr(self, 'chart_canvases'):
            for canvas in self.chart_canvases:
                try:
                    plt.close(canvas.figure)
                except Exception:
                    pass
            self.chart_canvases = []

        for widget in self.rapor_frame.winfo_children():
            widget.destroy()

        aktif_hayvanlar = {kupe: h for kupe, h in self.hayvanlar.items() if not h.get('arsivli', False)}

        if not aktif_hayvanlar:
            tk.Label(self.rapor_frame, text="Gösterilecek veri yok.", font=('Segoe UI', 16), bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"]).pack(expand=True)
            return

        cinsiyet_dagilimi = {'Dişi': 0, 'Erkek': 0}
        cins_dagilimi = {} 
        ozel_durum_dagilimi = {'Gebe': 0, 'Ölü': 0, 'Kesildi': 0}
        erkek_cinsler = ["Erkek Buzağı", "Dana"]
        
        for hayvan in aktif_hayvanlar.values():
            cins = hayvan.get('cins', 'Bilinmiyor')

            if cins in erkek_cinsler:
                cinsiyet_dagilimi['Erkek'] += 1
            else:
                cinsiyet_dagilimi['Dişi'] += 1
            
            if hayvan.get('olu', False):
                ozel_durum_dagilimi['Ölü'] += 1
            elif hayvan.get('kesildi', False):
                ozel_durum_dagilimi['Kesildi'] += 1
            else:
                cins_dagilimi[cins] = cins_dagilimi.get(cins, 0) + 1
                if hayvan.get('gebe_mi', False):
                    ozel_durum_dagilimi['Gebe'] += 1

        charts_frame = tk.Frame(self.rapor_frame, bg=self.renkler["kart_arkaplan"])
        charts_frame.pack(fill="both", expand=True, padx=10, pady=10)
        charts_frame.grid_columnconfigure((0, 1, 2), weight=1)
        charts_frame.grid_rowconfigure(1, weight=1)

        arsivli_sayi = len(self.hayvanlar) - len(aktif_hayvanlar)
        toplam_hayvan_label = tk.Label(charts_frame, text=f"Aktif Hayvan Sayısı: {len(aktif_hayvanlar)} | Arşivli: {arsivli_sayi}", font=('Segoe UI', 16, 'bold'), bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"])
        toplam_hayvan_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        self.themed_widgets.append((toplam_hayvan_label, 'label'))
        
        self.create_pie_chart(charts_frame, cinsiyet_dagilimi, "Cinsiyet Dağılımı", 0)
        self.create_pie_chart(charts_frame, cins_dagilimi, "Sürüdeki Hayvan Tipleri", 1)
        self.create_pie_chart(charts_frame, ozel_durum_dagilimi, "Özel Durumlar", 2)


    def create_pie_chart(self, parent, data, title, column):
        filtered_data = {label: value for label, value in data.items() if value > 0}
        
        labels = list(filtered_data.keys())
        sizes = list(filtered_data.values())

        if not any(sizes):
            tk.Label(parent, text=f"{title}\n(Veri Yok)", font=('Segoe UI', 12), bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"]).grid(row=1, column=column, sticky="nsew", padx=15)
            return

        fig, ax = plt.subplots(figsize=(5, 4), dpi=100)
        fig.patch.set_facecolor(self.renkler["kart_arkaplan"]) 
        
        wedges, texts, autotexts = ax.pie(sizes, autopct=lambda p: '{:.0f}'.format(p * sum(sizes) / 100),
                                            startangle=90, textprops={'color': self.renkler["yazi_rengi"]},
                                            pctdistance=0.85, wedgeprops=dict(width=0.4))
        
        plt.setp(autotexts, size=10, weight="bold", color=self.renkler["beyaz"])
        ax.set_title(title, color=self.renkler["yazi_rengi"], size=14, weight='bold', pad=20)
        
        ax.axis('equal')

        legend_labels = [f'{l} ({s})' for l, s in zip(labels, sizes)]
        ax.legend(wedges, legend_labels,
                  loc="lower center",
                  bbox_to_anchor=(0.5, -0.15),
                  prop={'size': 10},
                  labelcolor=self.renkler["yazi_rengi"],
                  frameon=False
                  )
        
        plt.tight_layout(pad=1.5)

        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().grid(row=1, column=column, sticky="nsew", padx=10)
        if not hasattr(self, 'chart_canvases'):
            self.chart_canvases = []
        self.chart_canvases.append(canvas)

    def asi_prosedur_sekmesi(self):
        asi_frame = ttk.Frame(self.notebook, style='TFrame')
        self.notebook.add(asi_frame, text="💉 Aşı/Prosedür")

        self.asi_main_card = self.modern_kart(asi_frame)
        self.asi_main_card.pack(fill='both', expand=True, padx=16, pady=16)

        header = tk.Frame(self.asi_main_card, bg=self.renkler["kart_arkaplan"], pady=20)
        header.pack(fill='x', padx=24)
        self.themed_widgets.append((header, 'kart'))

        baslik = tk.Label(header, text="💉 Aşı ve Prosedür Takibi", font=('Segoe UI', 18, 'bold'), bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"])
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
                if not v.get('arsivli') and not v.get('olu') and not v.get('kesildi'):
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

        self.modern_buton(header, "💉 YENİ AŞI EKLE", yeni_asi_dialog, purpose='primary', small=True).pack(side='right', padx=(6, 0))
        self.modern_buton(header, "🔄 YENİLE", self.asi_prosedur_listesini_guncelle, purpose='success', small=True).pack(side='right', padx=6)

        cizgi = tk.Frame(self.asi_main_card, bg=self.renkler["kenarlik"], height=1)
        cizgi.pack(fill='x', padx=24, pady=(0, 10))
        self.themed_widgets.append((cizgi, 'divider'))

        tree_frame = tk.Frame(self.asi_main_card, bg=self.renkler["kart_arkaplan"])
        tree_frame.pack(fill='both', expand=True, padx=15, pady=15)
        self.themed_widgets.append((tree_frame, 'kart'))

        columns = ("ID", "Küpe No", "Prosedür", "Uygulama Tarihi", "Sonraki Tarih", "Kalan Gün", "Not")
        self.asi_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', style='Modern.Treeview')
        
        self.asi_tree.heading("ID", text="ID")
        self.asi_tree.column("ID", width=0, stretch=tk.NO) # Hide ID column
        
        col_widths = {"Küpe No": 140, "Prosedür": 200, "Uygulama Tarihi": 130, "Sonraki Tarih": 130, "Kalan Gün": 100, "Not": 260}
        for col in columns[1:]:
            self.asi_tree.heading(col, text=col)
            self.asi_tree.column(col, width=col_widths.get(col, 150), anchor='center')
        self.asi_tree.pack(fill='both', expand=True, padx=1, pady=1)
        self.asi_tree.bind('<Double-Button-1>', self.asi_prosedur_detay_ac)

    def asi_prosedur_listesini_guncelle(self):
        if not hasattr(self, 'asi_tree'):
            return
        for item in self.asi_tree.get_children():
            self.asi_tree.delete(item)

        bugun = datetime.now().date()
        satirlar = []
        for kupe_no, hayvan in self.hayvanlar.items():
            if hayvan.get('arsivli') or hayvan.get('olu') or hayvan.get('kesildi'):
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

    def asi_prosedur_penceresi(self, kupe_no):
        if kupe_no not in self.hayvanlar:
            return
        hayvan = self.hayvanlar[kupe_no]
        hayvan.setdefault('asi_prosedurler', [])
        
        gorunen_kupe = hayvan.get('ciftlik_kupe_no') or hayvan.get('resmi_kupe_no') or kupe_no

        pencere = tk.Toplevel(self.root)
        pencere.title(f"Aşı/Prosedür - {gorunen_kupe}")
        pencere.geometry("900x620")
        pencere.configure(bg=self.renkler["arkaplan"])
        pencere.transient(self.root)

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
            self.veri_kaydet()
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
            self.veri_kaydet()
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
            self.veri_kaydet()
            temizle()
            yenile()
            self.ekranlari_guncelle()

        tree.bind('<<TreeviewSelect>>', seciliyi_forma_al)
        
        import uuid
        
        self.modern_buton(btn_inner, "YENİ KAYDET", yeni_kaydet, purpose='success').pack(side='left', padx=8)
        self.modern_buton(btn_inner, "SEÇİLİYİ GÜNCELLE", secili_guncelle, purpose='default').pack(side='left', padx=8)
        self.modern_buton(btn_inner, "SEÇİLİYİ SİL", secili_sil, purpose='danger').pack(side='left', padx=8)
        self.modern_buton(btn_inner, "TEMİZLE", temizle, purpose='warning').pack(side='left', padx=8)
        yenile()
    
    def uyari_sekmesi(self):
        uyari_frame = ttk.Frame(self.notebook, style='TFrame')
        self.notebook.add(uyari_frame, text="⚠️ Uyarılar")
        
        main_card = self.modern_kart(uyari_frame)
        main_card.pack(fill='both', expand=True, padx=16, pady=16)

        header = tk.Frame(main_card, bg=self.renkler["kart_arkaplan"], pady=20)
        header.pack(fill='x', padx=24)
        self.themed_widgets.append((header, 'kart'))

        uyari_baslik_label = tk.Label(header, text="⚠️ Aktif Uyarılar ve Bildirimler", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 18, 'bold'))
        uyari_baslik_label.pack(side='left')
        self.themed_widgets.append((uyari_baslik_label, 'label'))
        
        self.modern_buton(header, "👁️ TÜMÜNÜ OKUNDU İŞARETLE", self.uyarilari_okundu_isaretle, purpose='success', small=True).pack(side='right')
        
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
            if hayvan.get('arsivli', False) or hayvan.get('olu', False) or hayvan.get('kesildi', False):
                continue
            ciftlik = (hayvan.get('ciftlik_kupe_no') or '').upper()
            resmi = (hayvan.get('resmi_kupe_no') or '').upper()
            gorunen = ciftlik or resmi
            if gorunen.startswith(text):
                eslesenler.append(ciftlik or resmi)
        current_text = self.tohumlama_hayvan_combo.get()
        self.tohumlama_hayvan_combo['values'] = sorted(eslesenler)
        self.tohumlama_hayvan_combo.set(current_text)

    def aktif_hayvan_secim_degerleri(self):
        degerler = []
        for h_id, hayvan in self.hayvanlar.items():
            if hayvan.get('arsivli', False) or hayvan.get('olu', False) or hayvan.get('kesildi', False):
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

    def combo_secimi(self, event): pass
    def tohumlama_sekli_degisti(self, event):
        if self.tohumlama_sekli_combo.get() == "Suni":
            self.suni_container.grid()
        else:
            self.suni_container.grid_remove()

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
            popup = tk.Menu(self.root, tearoff=0, bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"])
            popup.add_command(label="📋 Detayları Göster", command=lambda: self.hayvan_detay_ac(None))
            popup.add_command(label="💉 Tohumlama Yap", command=self.hizli_tohumlama)
            popup.add_separator()
            popup.add_command(label="❌ İptal")
            popup.tk_popup(event.x_root, event.y_root)

    def hizli_tohumlama(self):
        try:
            selection = self.hayvan_tree.selection()
            if not selection: return messagebox.showwarning("Uyarı", "Önce bir hayvan seçin!")
            item = self.hayvan_tree.item(selection[0])
            kupe_no = str(item['values'][0]).strip()
            
            gorunen = kupe_no
            if kupe_no in self.hayvanlar:
                gorunen = self.hayvanlar[kupe_no].get('ciftlik_kupe_no') or self.hayvanlar[kupe_no].get('resmi_kupe_no') or kupe_no
                
            self.notebook.select(1)
            self.tohumlama_hayvan_combo.set(gorunen)
        except Exception as e:
            messagebox.showerror("Hata", f"Hızlı tohumlama hatası: {str(e)}")

    def uyarilari_okundu_isaretle(self):
        if not messagebox.askyesno("Onay", "Tüm aktif uyarıları okundu olarak işaretlemek istediğinizden emin misiniz?"):
            return

        aktif_uyari_keyleri = []
        for kupe_no, hayvan in self.hayvanlar.items():
            if hayvan.get('arsivli', False) or hayvan.get('olu', False) or hayvan.get('kesildi', False):
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
        messagebox.showinfo("Başarılı", "✅ Tüm aktif uyarılar okundu olarak işaretlendi.")

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

    # --- Ana Veri İşleme Fonksiyonları ---
    # #################################################################
    # ### GÜNCELLENMİŞ FONKSİYON: hayvan_kaydet
    # #################################################################
    def hayvan_kaydet(self):
        import uuid
        resmi_kupe = self.resmi_kupe_no_entry.get().strip().upper()
        ciftlik_kupe = self.ciftlik_kupe_no_entry.get().strip().upper()
        dogum_tarihi = self.dogum_tarihi_entry.get().strip()
        cins = self.cins_combo.get()
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

        # --- YENİ LAKTASYON MANTIĞI ---
        if cins in ["Sağmal İnek", "Kuru İnek"]:
            laktasyon_no_str = self.laktasyon_no_entry.get().strip()
            son_dogum_tarihi = self.son_dogum_tarihi_entry.get().strip()

            if not laktasyon_no_str or not son_dogum_tarihi:
                return messagebox.showerror("Hata", "Sağmal/Kuru inekler için Laktasyon Numarası ve Son Doğum Tarihi zorunludur!")

            try:
                laktasyon_no = int(laktasyon_no_str)
                if laktasyon_no <= 0: raise ValueError
            except ValueError:
                return messagebox.showerror("Hata", "Geçersiz laktasyon numarası. Lütfen pozitif bir sayı girin.")

            son_dogum_dt = self.tarih_coz(son_dogum_tarihi, "Son doğum tarihi")
            if son_dogum_dt is None:
                return
            if son_dogum_dt < dogum_dt:
                return messagebox.showerror("Hata", "Son doğum tarihi, hayvanın doğum tarihinden önce olamaz.")

            if laktasyon_no > 1:
                for _ in range(laktasyon_no - 1):
                    gecmis_dogum = {'tarih': 'Bilinmiyor', 'yavrular': [], 'laktasyon_bitis_tarihi': 'Bilinmiyor', 'not': 'Geçmiş kayıt, süre bilinmiyor'}
                    dogumlar_listesi.append(gecmis_dogum)
            
            aktif_dogum = {'tarih': son_dogum_tarihi, 'yavrular': [], 'laktasyon_bitis_tarihi': None, 'not': 'Sisteme giriş yapılan laktasyon'}
            if cins == "Kuru İnek":
                aktif_dogum['laktasyon_bitis_tarihi'] = datetime.now().strftime("%d/%m/%Y")
            dogumlar_listesi.append(aktif_dogum)
        
        yeni_id = uuid.uuid4().hex
        gorunen_kupe = ciftlik_kupe if ciftlik_kupe else resmi_kupe
        self.islem_kaydi_baslat(f"Hayvan eklendi: {gorunen_kupe}")
        
        self.hayvanlar[yeni_id] = {
            'kupe_no': gorunen_kupe, # Geriye dönük uyumluluk
            'ciftlik_id': hedef_ciftlik_id,
            'ciftlik_ad': hedef_ciftlik_ad,
            'resmi_kupe_no': resmi_kupe,
            'ciftlik_kupe_no': ciftlik_kupe,
            'dogum_tarihi': dogum_tarihi, 
            'cins': gercek_cins, 
            'anne_kupe': anne_kupe, 
            'kayit_tarihi': datetime.now().strftime("%d/%m/%Y %H:%M:%S"), 
            'yas_gun': yas_gun, 
            'tohumlamalar': [], 
            'dogumlar': dogumlar_listesi, 
            'durum': self.durum_hesapla(gercek_cins, yas_gun), 
            'gebe_mi': False, 'gebelik_tarihi': None, 'aktif_tohumlama_id': None,
            'olu': False, 'olum_tarihi': None,
            'kesildi': False, 'kesim_bilgisi': None,
            'asi_prosedurler': [],
            'arsivli': False, 'arsiv_tarihi': None,
            'son_guncelleme': datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        }
        self.veri_kaydet()
        messagebox.showinfo("Başarılı", f"🎉 Hayvan {gorunen_kupe} başarıyla kaydedildi!")
        
        for entry in [self.resmi_kupe_no_entry, self.ciftlik_kupe_no_entry, self.dogum_tarihi_entry, self.anne_kupe_entry, self.laktasyon_no_entry, self.son_dogum_tarihi_entry]:
            entry.delete(0, tk.END)
        self.cins_combo.set('')
        self._on_cins_change() 
        
        self.hayvan_listesini_guncelle()
        self.raporlari_guncelle()

    def otomatik_cins_guncelle(self, mevcut_cins, yas_gun):
        return is_otomatik_cins_guncelle(mevcut_cins, yas_gun)

    def durum_hesapla(self, cins, yas_gun):
        return is_durum_hesapla(cins, yas_gun)

    def tohumlama_kaydet(self):
        kupe_girdi = self.tohumlama_hayvan_combo.get().strip().upper()
        sekil = self.tohumlama_sekli_combo.get()
        tarih = self.tohumlama_tarih_entry.get().strip()
        if not all([kupe_girdi, sekil, tarih]): return messagebox.showerror("Hata", "Lütfen tüm alanları doldurun!")
        
        kupe_no = self.hayvan_id_bul(kupe_girdi)
                
        if not kupe_no: return messagebox.showerror("Hata", f"'{kupe_girdi}' küpeli hayvan bulunamadı!")
        
        hayvan = self.hayvanlar[kupe_no]
        
        if hayvan.get('olu', False) or hayvan.get('kesildi', False) or hayvan.get('arsivli', False):
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
        self.veri_kaydet()
        messagebox.showinfo("Başarılı", f"💉 Tohumlama kaydı başarılı!\nTohumlama ID: {tohumlama_id}")
        self.tohumlama_hayvan_combo.set('')
        self.suni_entry.delete(0, tk.END)
        self.tohumlama_sekli_combo.set('')
        self.hayvan_listesini_guncelle()

    def gebelik_pozitif(self):
        kupe_girdi = self.tohumlama_hayvan_combo.get().strip().upper()
        if not kupe_girdi:
            return messagebox.showerror("Hata", "Geçerli bir hayvan seçin veya tohumlama kaydı oluşturun!")
        
        kupe_no = self.hayvan_id_bul(kupe_girdi)
        
        if not kupe_no or not self.hayvanlar[kupe_no].get('tohumlamalar'):
            return messagebox.showerror("Hata", "Geçerli bir hayvan seçin veya tohumlama kaydı oluşturun!")
        
        hayvan = self.hayvanlar[kupe_no]
        son_tohumlama = hayvan['tohumlamalar'][-1]
        gorunen = hayvan.get('ciftlik_kupe_no') or hayvan.get('resmi_kupe_no') or kupe_no
        
        if son_tohumlama.get('gebe_mi') is not None:
            messagebox.showerror("Hata", "Bu hayvan için bekleyen yeni bir tohumlama kaydı bulunmamaktadır.\nLütfen önce 'Tohumlama Kaydet' ile yeni bir tohumlama işlemi girin.")
            return

        self.islem_kaydi_baslat(f"Gebelik pozitif işlendi: {gorunen}")
        son_tohumlama.update({'gebe_mi': True, 'kontrol_tarihi': datetime.now().strftime("%d/%m/%Y")})
        
        hayvan.update({
            'gebe_mi': True, 
            'gebelik_tarihi': son_tohumlama['tarih'],
            'aktif_tohumlama_id': son_tohumlama.get('id')
        })
        if hayvan.get('durum') not in ['Sağmal İnek', 'Kuru İnek']:
            hayvan['durum'] = 'Gebe'

        self.veri_kaydet()
        messagebox.showinfo("Başarılı", f"🎉 {gorunen} numaralı hayvan gebe olarak işaretlendi!")
        self.hayvan_listesini_guncelle()
        self.uyarilari_guncelle()
        self.raporlari_guncelle()

    def gebelik_negatif(self):
        kupe_girdi = self.tohumlama_hayvan_combo.get().strip().upper()
        if not kupe_girdi:
            return messagebox.showerror("Hata", "Geçerli bir hayvan seçin veya tohumlama kaydı oluşturun!")
        
        kupe_no = self.hayvan_id_bul(kupe_girdi)
        
        if not kupe_no or not self.hayvanlar[kupe_no].get('tohumlamalar'):
            return messagebox.showerror("Hata", "Geçerli bir hayvan seçin veya tohumlama kaydı oluşturun!")
        
        hayvan = self.hayvanlar[kupe_no]
        son_tohumlama = hayvan['tohumlamalar'][-1]
        gorunen = hayvan.get('ciftlik_kupe_no') or hayvan.get('resmi_kupe_no') or kupe_no
        
        if son_tohumlama.get('gebe_mi') is not None:
            messagebox.showerror("Hata", "Bu hayvan için bekleyen yeni bir tohumlama kaydı bulunmamaktadır.\nLütfen önce 'Tohumlama Kaydet' ile yeni bir tohumlama işlemi girin.")
            return

        self.islem_kaydi_baslat(f"Gebelik negatif işlendi: {gorunen}")
        son_tohumlama.update({'gebe_mi': False, 'kontrol_tarihi': datetime.now().strftime("%d/%m/%Y")})
        
        yeni_durum = self.durum_hesapla(hayvan.get('cins'), hayvan.get('yas_gun'))
        hayvan.update({'gebe_mi': False, 'gebelik_tarihi': None, 'aktif_tohumlama_id': None, 'durum': yeni_durum})
        
        self.veri_kaydet()
        messagebox.showinfo("Başarılı", f"📋 {gorunen} numaralı hayvan boş olarak işaretlendi!")
        self.hayvan_listesini_guncelle()
        self.raporlari_guncelle()

    def _ask_calf_details(self, parent, calf_number):
        dialog = tk.Toplevel(parent)
        dialog.transient(parent)
        dialog.grab_set()
        dialog.title(f"{calf_number}. Yavru Bilgileri")
        dialog.geometry("450x300")
        dialog.configure(bg=self.renkler["arkaplan"])
        
        result = {}

        main_frame = tk.Frame(dialog, bg=self.renkler["arkaplan"], padx=20, pady=20)
        main_frame.pack(fill="both", expand=True)

        tk.Label(main_frame, text=f"Lütfen {calf_number}. Yavrunun Bilgilerini Girin", font=('Segoe UI', 14, 'bold'), bg=self.renkler["arkaplan"], fg=self.renkler["yazi_rengi"]).pack(pady=(0, 20))

        tk.Label(main_frame, text="Yavru Cinsi:", font=('Segoe UI', 12), bg=self.renkler["arkaplan"], fg=self.renkler["yazi_rengi"]).pack(pady=5)
        cins_combo = ttk.Combobox(main_frame, values=["Dişi Buzağı", "Erkek Buzağı"], width=20, font=('Segoe UI', 11), style='TCombobox')
        cins_combo.pack(pady=5)

        tk.Label(main_frame, text="Yavru Küpe No (isteğe bağlı):", font=('Segoe UI', 12), bg=self.renkler["arkaplan"], fg=self.renkler["yazi_rengi"]).pack(pady=5)
        kupe_entry = ttk.Entry(main_frame, width=22, font=('Segoe UI', 11), style='TEntry')
        kupe_entry.pack(pady=5)
        kupe_entry.focus_set()
        
        def on_ok():
            cins = cins_combo.get()
            if not cins:
                messagebox.showerror("Hata", "Lütfen yavrunun cinsini seçin.", parent=dialog)
                return
            result['cins'] = cins
            result['kupe'] = kupe_entry.get().strip().upper()
            dialog.destroy()
        
        def on_cancel():
            result['cins'] = None 
            dialog.destroy()

        btn_frame = tk.Frame(main_frame, bg=self.renkler["arkaplan"])
        btn_frame.pack(pady=20)
        self.modern_buton(btn_frame, "Tamam", on_ok, purpose='success').pack(side='left', padx=10)
        self.modern_buton(btn_frame, "İptal", on_cancel, purpose='danger').pack(side='left', padx=10)
        
        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        parent.wait_window(dialog)
        return result if result.get('cins') is not None else None

    def dogum_kayit_olustur(self, anne_kupe, detay_pencere):
        if detay_pencere:
            detay_pencere.destroy()
            
        hayvan = self.hayvanlar.get(anne_kupe, {})
        gorunen_kupe = hayvan.get('ciftlik_kupe_no') or hayvan.get('resmi_kupe_no') or anne_kupe
        
        dogum_window = tk.Toplevel(self.root)
        dogum_window.title(f"🍼 Doğum Kaydı - {gorunen_kupe}")
        dogum_window.geometry("700x700")
        dogum_window.configure(bg=self.renkler["arkaplan"])
        dogum_window.transient(self.root)
        dogum_window.grab_set()

        title_frame = tk.Frame(dogum_window, bg=self.renkler["ana_kirmizi"], height=80)
        title_frame.pack(fill='x', expand=False)
        title_frame.pack_propagate(False)
        tk.Label(title_frame, text=f"🍼 {anne_kupe} - Yeni Doğum Kaydı", bg=self.renkler["ana_kirmizi"], fg=self.renkler["beyaz"], font=('Segoe UI', 18, 'bold')).pack(expand=True)
        
        form_kart = self.modern_kart(dogum_window)
        form_kart.pack(fill='both', expand=True, padx=25, pady=25)
        
        form_frame = tk.Frame(form_kart, bg=self.renkler["kart_arkaplan"], padx=40, pady=30)
        form_frame.pack(fill='both', expand=True)
        
        tk.Label(form_frame, text="DOĞUM BİLGİLERİ", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 16, 'bold')).pack(pady=10)
        
        tk.Label(form_frame, text="📅 Doğum Tarihi:", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 12, 'bold')).pack(pady=(15, 5))
        dogum_tarih_entry = ttk.Entry(form_frame, font=('Segoe UI', 11), width=25, justify='center', style='TEntry')
        dogum_tarih_entry.pack(pady=5)
        dogum_tarih_entry.insert(0, datetime.now().strftime("%d/%m/%Y"))

        tk.Label(form_frame, text="🔢 Yavru Sayısı:", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 12, 'bold')).pack(pady=(15, 5))
        yavru_sayi_entry = ttk.Entry(form_frame, font=('Segoe UI', 11), width=25, justify='center', style='TEntry')
        yavru_sayi_entry.pack(pady=5)
        yavru_sayi_entry.insert(0, "1")
        
        tk.Label(form_frame, text="🐄 1. Yavru Cinsi:", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 12, 'bold')).pack(pady=(15, 5))
        yavru_cins_combo = ttk.Combobox(form_frame, values=["Dişi Buzağı", "Erkek Buzağı"], width=22, font=('Segoe UI', 11), justify='center', style='TCombobox')
        yavru_cins_combo.pack(pady=5)
        
        tk.Label(form_frame, text="🏷️ 1. Yavru Küpe No (isteğe bağlı):", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 12, 'bold')).pack(pady=(15, 5))
        yavru_kupe_entry = ttk.Entry(form_frame, font=('Segoe UI', 11), width=25, justify='center', style='TEntry')
        yavru_kupe_entry.pack(pady=5)
        
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
                    'kupe': yavru_kupe_entry.get().strip().upper()
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
                
                temp_kupe_list = [y['kupe'] for y in yavrular_data if y['kupe']]
                if len(temp_kupe_list) != len(set(temp_kupe_list)):
                    return messagebox.showerror("Hata", "Yavrular için aynı küpe numarasını birden fazla kez girdiniz.", parent=dogum_window)

                for yavru in yavrular_data:
                    if yavru['kupe'] and self.hayvan_id_bul(yavru['kupe']):
                        return messagebox.showerror("Hata", f"Yavru küpe numarası '{yavru['kupe']}' zaten başka bir hayvana kayıtlı!", parent=dogum_window)

                self.islem_kaydi_baslat(f"Doğum kaydı oluşturuldu: {anne_kupe}")
                kaydedilen_yavrular_bilgi = []
                for i, yavru_data in enumerate(yavrular_data):
                    yeni_yavru_id = uuid.uuid4().hex
                    yavru_gorunen = yavru_data['kupe']
                    self.hayvanlar[yeni_yavru_id] = {
                        'kupe_no': yavru_gorunen or yeni_yavru_id,
                        'resmi_kupe_no': yavru_gorunen if yavru_gorunen else '',
                        'ciftlik_kupe_no': '',
                        'dogum_tarihi': dogum_tarihi, 'cins': yavru_data['cins'], 'anne_kupe': anne_kupe,
                        'kayit_tarihi': datetime.now().strftime("%d/%m/%Y %H:%M:%S"), 'yas_gun': (datetime.now() - dogum_dt).days, 'tohumlamalar': [], 'dogumlar': [],
                        'durum': 'Buzağı', 'gebe_mi': False, 'gebelik_tarihi': None, 'aktif_tohumlama_id': None, 'olu': False, 'olum_tarihi': None,
                        'kesildi': False, 'kesim_bilgisi': None, 'asi_prosedurler': [], 'arsivli': False, 'arsiv_tarihi': None, 'son_guncelleme': datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    }
                    kaydedilen_yavrular_bilgi.append({'kupe': yavru_gorunen or yeni_yavru_id, 'cins': yavru_data['cins']})
                
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
                
                self.veri_kaydet()
                kaydedilen_kupeler = [y['kupe'] for y in kaydedilen_yavrular_bilgi]
                messagebox.showinfo("Başarılı", f"🍼 Doğum kaydı başarılı!\nKaydedilen Yavrular: {', '.join(kaydedilen_kupeler)}")
                dogum_window.destroy()
                self.hayvan_listesini_guncelle()
                self.raporlari_guncelle()

            except Exception as e:
                messagebox.showerror("Hata", f"Doğum kaydı sırasında bir hata oluştu: {str(e)}", parent=dogum_window)

        self.modern_buton(btn_frame, "👶 DOĞUM KAYDET", dogum_kaydet, purpose='success').pack(side='left', padx=15)
        self.modern_buton(btn_frame, "❌ İPTAL", dogum_window.destroy, purpose='danger').pack(side='left', padx=15)

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
        
        self.veri_kaydet()
        messagebox.showinfo("Başarılı", f"🛑 {kupe_no} numaralı hayvan kuruya ayrıldı!")
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
            self.veri_kaydet()
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

            self.veri_kaydet()
            messagebox.showinfo("Başarılı", f"🔪 {kupe_no} küpeli hayvan kesildi olarak kaydedildi.")
            pencere.destroy()
            self.hayvan_listesini_guncelle()
            self.raporlari_guncelle()

    def hayvan_sil_detay(self, kupe_no, pencere):
        uyari = f"⚠️ DİKKAT!\n\n{kupe_no} küpeli hayvan aktif sürüden arşive alınacak.\n\nKayıt geçmişi korunur; hayvan listesinde sadece 'Arşivli' filtresinde görünür."
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
            self.veri_kaydet()
            messagebox.showinfo("Başarılı", f"🗄️ {kupe_no} numaralı hayvan arşive alındı.")
            pencere.destroy()
            self.hayvan_listesini_guncelle()
            self.raporlari_guncelle()

    def hayvan_kalici_sil(self, kupe_no, pencere):
        if kupe_no not in self.hayvanlar:
            return
        uyari = f"⚠️ DİKKAT!\n\n{kupe_no} küpeli arşivli hayvan kalıcı olarak silinecek.\n\nBu işlem geri alma geçmişine alınır ama aktif kayıttan tamamen kaldırılır."
        if not messagebox.askyesno("Kalıcı Silme Onayı", uyari, parent=pencere):
            return
        self.islem_kaydi_baslat(f"Arşivli hayvan kalıcı silindi: {kupe_no}")
        if getattr(self, "api_modu", False) and self.offline_modda_mi():
            self.bekleyen_senkron_delete(kupe_no)
        del self.hayvanlar[kupe_no]
        self.veri_kaydet()
        messagebox.showinfo("Başarılı", f"{kupe_no} kalıcı olarak silindi.", parent=pencere)
        pencere.destroy()
        self.ekranlari_guncelle()



    def hayvan_gebelik_durumunu_senkronla(self, kupe_no):
        hayvan = self.hayvanlar.get(kupe_no)
        if not hayvan:
            return
        tohumlamalar = hayvan.get('tohumlamalar', [])
        son_tohumlama = tohumlamalar[-1] if tohumlamalar else None
        is_male = hayvan.get('cins') in ["Erkek Buzağı", "Dana"]

        if son_tohumlama and son_tohumlama.get('gebe_mi') is True and not is_male and not hayvan.get('olu') and not hayvan.get('kesildi') and not hayvan.get('arsivli'):
            hayvan['gebe_mi'] = True
            hayvan['gebelik_tarihi'] = son_tohumlama.get('tarih')
            hayvan['aktif_tohumlama_id'] = son_tohumlama.get('id')
            if hayvan.get('durum') not in ['Sağmal İnek', 'Kuru İnek']:
                hayvan['durum'] = 'Gebe'
        else:
            hayvan['gebe_mi'] = False
            hayvan['gebelik_tarihi'] = None
            hayvan['aktif_tohumlama_id'] = None
            if not hayvan.get('olu') and not hayvan.get('kesildi') and not hayvan.get('arsivli'):
                hayvan['durum'] = self.durum_hesapla(hayvan.get('cins'), hayvan.get('yas_gun', 0))

    def hayvan_duzenle_penceresi(self, kupe_no, detay_pencere=None):
        if kupe_no not in self.hayvanlar:
            return
        hayvan = self.hayvanlar[kupe_no]
        
        gorunen_kupe = hayvan.get('ciftlik_kupe_no') or hayvan.get('resmi_kupe_no') or kupe_no

        pencere = tk.Toplevel(self.root)
        pencere.title(f"Kayıt Düzenle - {gorunen_kupe}")
        pencere.geometry("950x700")
        pencere.configure(bg=self.renkler["arkaplan"])
        pencere.transient(self.root)
        pencere.grab_set()

        notebook = ttk.Notebook(pencere, style='Modern.TNotebook')
        notebook.pack(fill='both', expand=True, padx=15, pady=15)

        genel_frame = ttk.Frame(notebook, style='TFrame')
        notebook.add(genel_frame, text="Genel Bilgiler")
        genel_kart = self.modern_kart(genel_frame)
        genel_kart.pack(fill='both', expand=True, padx=15, pady=15)

        form = tk.Frame(genel_kart, bg=self.renkler["kart_arkaplan"], padx=30, pady=30)
        form.pack(fill='both', expand=True)
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
        anne_entry = ttk.Entry(form, width=25, font=('Segoe UI', 11), style='TEntry')
        anne_entry.insert(0, hayvan.get('anne_kupe', ''))

        for row, (label_text, widget) in enumerate([
            ("Resmi Küpe No", resmi_kupe_entry),
            ("Çiftlik Küpe No", ciftlik_kupe_entry),
            ("Doğum Tarihi", dogum_entry),
            ("Cinsi", cins_combo),
            ("Anne Küpe No", anne_entry),
        ]):
            label = tk.Label(form, text=label_text, bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 12, 'bold'))
            label.grid(row=row, column=0, sticky='w', pady=12, padx=(0, 20))
            widget.grid(row=row, column=1, sticky='ew', pady=12)

        def genel_kaydet():
            yeni_resmi = resmi_kupe_entry.get().strip().upper()
            yeni_ciftlik = ciftlik_kupe_entry.get().strip().upper()
            dogum_tarihi = dogum_entry.get().strip()
            yeni_cins = cins_combo.get().strip()
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

            self.islem_kaydi_baslat(f"Genel bilgiler düzenlendi: {kupe_no}")
            hayvan['resmi_kupe_no'] = yeni_resmi
            hayvan['ciftlik_kupe_no'] = yeni_ciftlik
            hayvan['dogum_tarihi'] = dogum_tarihi
            hayvan['cins'] = yeni_cins
            hayvan['anne_kupe'] = anne_kupe
            hayvan['yas_gun'] = (datetime.now() - dogum_dt).days
            if yeni_cins in ["Erkek Buzağı", "Dana"]:
                hayvan['gebe_mi'] = False
                hayvan['gebelik_tarihi'] = None
                hayvan['aktif_tohumlama_id'] = None
            self.hayvan_gebelik_durumunu_senkronla(kupe_no)
            hayvan['son_guncelleme'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            self.veri_kaydet()
            self.ekranlari_guncelle()
            messagebox.showinfo("Başarılı", "Genel bilgiler güncellendi.", parent=pencere)

        self.modern_buton(form, "GENEL BİLGİLERİ KAYDET", genel_kaydet, purpose='success').grid(row=4, column=0, columnspan=2, pady=25)

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
                self.veri_kaydet()
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
            self.veri_kaydet()
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
                yavrular = ", ".join([y.get('kupe', '-') for y in dogum.get('yavrular', [])]) or "-"
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
                self.islem_kaydi_baslat(f"Doğum kaydı düzenlendi: {kupe_no}")
                kayit['tarih'] = tarih
                kayit['laktasyon_bitis_tarihi'] = bitis or None
                hayvan['son_guncelleme'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                self.veri_kaydet()
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
            self.veri_kaydet()
            dogum_tree_yenile()
            self.ekranlari_guncelle()

        dogum_btn = tk.Frame(dogum_kart, bg=self.renkler["kart_arkaplan"])
        dogum_btn.pack(pady=(0, 10))
        self.modern_buton(dogum_btn, "DÜZENLE", dogum_duzenle, purpose='default').pack(side='left', padx=8)
        self.modern_buton(dogum_btn, "SİL", dogum_sil, purpose='danger').pack(side='left', padx=8)
        dogum_tree_yenile()

    # #################################################################
    # ### GÜNCELLENMİŞ FONKSİYON: hayvan_detay_penceresi
    # #################################################################
    def hayvan_detay_penceresi(self, kupe_no):
        if kupe_no not in self.hayvanlar: return
        hayvan = self.hayvanlar[kupe_no]
        
        cins = hayvan.get('cins', '')
        is_male = cins in ["Erkek Buzağı", "Dana"]
        
        gorunen_kupe = hayvan.get('ciftlik_kupe_no') or hayvan.get('resmi_kupe_no') or "Bilinmiyor"

        detay_window = tk.Toplevel(self.root)
        detay_window.title(f"Hayvan Detayları - {gorunen_kupe}")
        detay_window.geometry("1400x800")
        detay_window.configure(bg=self.renkler["arkaplan"])
        detay_window.transient(self.root)
        detay_window.grab_set()
        detay_window.update_idletasks()

        baslik_frame = tk.Frame(detay_window, bg=self.renkler["siyah"], height=90)
        baslik_frame.pack(fill='x', expand=False)
        baslik_frame.pack_propagate(False)
        tk.Label(baslik_frame, text=f"🐄 {gorunen_kupe} Numaralı Hayvanın Profili", bg=self.renkler["siyah"], fg=self.renkler["beyaz"], font=('Segoe UI', 20, 'bold')).pack(side='left', padx=30)
        
        btn_frame = tk.Frame(baslik_frame, bg=self.renkler["siyah"])
        btn_frame.pack(side='right', padx=20, pady=15)
        
        self.modern_buton(btn_frame, "🛠️ DÜZENLE", lambda: self.hayvan_duzenle_penceresi(kupe_no, detay_window), purpose='default').pack(side='left', padx=5)
        self.modern_buton(btn_frame, "💉 AŞI/PROSEDÜR", lambda: self.asi_prosedur_penceresi(kupe_no), purpose='success').pack(side='left', padx=5)
        
        if not hayvan.get('olu', False) and not hayvan.get('kesildi', False) and not hayvan.get('arsivli', False):
            if not is_male:
                if hayvan.get('gebe_mi', False): self.modern_buton(btn_frame, "🍼 DOĞUM KAYDET", lambda: self.dogum_kayit_olustur(kupe_no, detay_window), purpose='success').pack(side='left', padx=5)
                if hayvan.get('durum') == 'Sağmal İnek': 
                    self.modern_buton(btn_frame, "🛑 KURUYA AYIR", lambda: self.kuruda_yap(kupe_no, detay_window), purpose='warning').pack(side='left', padx=5)
            
            self.modern_buton(btn_frame, "🔪 KESİLDİ", lambda: self.hayvan_kesildi(kupe_no, detay_window), purpose='warning').pack(side='left', padx=5)
            self.modern_buton(btn_frame, "💀 ÖLDÜ", lambda: self.hayvan_oldu(kupe_no, detay_window), purpose='danger').pack(side='left', padx=5)

        if not hayvan.get('arsivli', False):
            self.modern_buton(btn_frame, "🗄️ ARŞİVLE", lambda: self.hayvan_sil_detay(kupe_no, detay_window), purpose='danger').pack(side='left', padx=5)
        else:
            self.modern_buton(btn_frame, "🗑️ KALICI SİL", lambda: self.hayvan_kalici_sil(kupe_no, detay_window), purpose='danger').pack(side='left', padx=5)
        
        ana_frame = tk.Frame(detay_window, bg=self.renkler["arkaplan"])
        ana_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        sol_panel = tk.Frame(ana_frame, bg=self.renkler["kart_arkaplan"])
        sol_panel.pack(side='left', fill='both', expand=True, padx=(0, 10 if not is_male else 0))
        
        tk.Label(sol_panel, text="📋 GENEL BİLGİLER", bg=self.renkler["gri"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 14, 'bold'), pady=15).pack(fill='x')
        bilgi_frame = tk.Frame(sol_panel, bg=self.renkler["kart_arkaplan"], padx=20, pady=15)
        bilgi_frame.pack(fill='both', expand=True, anchor='n')
        
        dogumlar = hayvan.get('dogumlar', [])
        laktasyon_sayisi = len(dogumlar)
        yas_gun = hayvan.get('yas_gun', 0)
        
        if hayvan.get('arsivli', False):
            mevcut_durum_str = "🗄️ Arşivli"
        elif hayvan.get('olu', False):
            mevcut_durum_str = "💀 Ölü"
        elif hayvan.get('kesildi', False):
            mevcut_durum_str = "🔪 Kesildi"
        elif hayvan.get('gebe_mi', False):
            mevcut_durum_str = "🤰 Gebe"
        else:
            mevcut_durum_str = "✅ Hayatta"

        bilgi_text = (f"🇹🇷 Resmi Küpe No: {hayvan.get('resmi_kupe_no') or '-'}\n"
                      f"🏷️ Çiftlik Küpe No: {hayvan.get('ciftlik_kupe_no') or '-'}\n"
                      f"📅 Doğum Tarihi: {hayvan.get('dogum_tarihi', '-')}\n"
                      f"🎂 Yaş: {yas_gun // 365} yıl {(yas_gun % 365) // 30} ay\n"
                      f"🐄 Cinsi: {hayvan.get('cins', '-')}\n"
                      f"📊 Mevcut Durum: {mevcut_durum_str}\n"
                      f"👩 Anne Küpe: {hayvan.get('anne_kupe') or 'Bilinmiyor'}\n"
                      f"🍼 Laktasyon Sayısı: {laktasyon_sayisi}")

        laktasyon_gun_bilgisi = ""
        if laktasyon_sayisi > 0:
            toplam_sagim_gunu = 0
            laktasyon_gun_bilgisi += "\n\n🥛 LAKTASYON SÜRELERİ"
            for i, dogum in enumerate(dogumlar):
                # --- YENİ LAKTASYON SÜRESİ GÖSTERİMİ ---
                if dogum.get('not') == 'Geçmiş kayıt, süre bilinmiyor':
                    laktasyon_gun_bilgisi += f"\n  - {i+1}. Laktasyon: Süre bilinmiyor (geçmiş kayıt)"
                    continue
                # --- YENİLİK SONU ---
                
                try:
                    baslangic_tarihi = datetime.strptime(dogum['tarih'], "%d/%m/%Y")
                    bitis_tarihi = None
                    durum_str = ""

                    if dogum.get('laktasyon_bitis_tarihi'):
                        bitis_tarihi = datetime.strptime(dogum['laktasyon_bitis_tarihi'], "%d/%m/%Y")
                    elif i + 1 < laktasyon_sayisi:
                        # Sonraki doğumun 'bilinmiyor' olup olmadığını kontrol et
                        sonraki_dogum = dogumlar[i+1]
                        if sonraki_dogum.get('tarih') != 'Bilinmiyor':
                           bitis_tarihi = datetime.strptime(sonraki_dogum['tarih'], "%d/%m/%Y")
                        else: # Eğer sonraki doğum bilinmiyorsa, bu laktasyonun sonu belirsizdir
                           bitis_tarihi = None
                    elif hayvan.get('olu', False) and hayvan.get('olum_tarihi'):
                        bitis_tarihi = datetime.strptime(hayvan['olum_tarihi'], "%d/%m/%Y")
                    elif hayvan.get('kesildi', False) and hayvan.get('kesim_bilgisi', {}).get('tarih'):
                        bitis_tarihi = datetime.strptime(hayvan['kesim_bilgisi']['tarih'], "%d/%m/%Y")
                    else:
                        bitis_tarihi = datetime.now()
                        durum_str = " (devam ediyor)"

                    if bitis_tarihi:
                       laktasyon_suresi = (bitis_tarihi - baslangic_tarihi).days
                       if laktasyon_suresi < 0: laktasyon_suresi = 0
                       toplam_sagim_gunu += laktasyon_suresi
                       laktasyon_gun_bilgisi += f"\n  - {i+1}. Laktasyon: {laktasyon_suresi} gün sağıldı{durum_str}"
                    else:
                       laktasyon_gun_bilgisi += f"\n  - {i+1}. Laktasyon: Bitiş tarihi belirsiz."

                except (ValueError, TypeError) as e:
                    print(e)
                    laktasyon_gun_bilgisi += f"\n  - {i+1}. Laktasyon: Tarih hatası!"
            
            bilgi_text += f"\n\nToplam Sağım Günü: {toplam_sagim_gunu} gün"
            bilgi_text += laktasyon_gun_bilgisi

        if hayvan.get('kesildi', False) and hayvan.get('kesim_bilgisi'):
            kesim_bilgisi = hayvan['kesim_bilgisi']
            yas = kesim_bilgisi.get('yas_gun', 0)
            yas_str = f"{yas // 365} yıl {(yas % 365) // 30} ay"
            bilgi_text += (f"\n\n➖➖➖➖ KESİM BİLGİSİ ➖➖➖➖\n"
                           f"🔪 Durumu: KESİLDİ\n"
                           f"📅 Kesim Tarihi: {kesim_bilgisi.get('tarih', '-')}\n"
                           f"⚖️ Kesim Ağırlığı: {kesim_bilgisi.get('kilo', '-')} kg\n"
                           f"🗓️ Kesim Yaşı: {yas_str}")
        elif not is_male and hayvan.get('gebe_mi', False) and hayvan.get('gebelik_tarihi'):
            try:
                g_tarihi = datetime.strptime(hayvan['gebelik_tarihi'], "%d/%m/%Y"); d_tarihi = g_tarihi + timedelta(days=283); kalan_gun = (d_tarihi - datetime.now()).days
                bilgi_text += f"\n\n🤰 Gebelik Durumu: GEBE ✅\n  - Tahmini Doğum: {d_tarihi.strftime('%d/%m/%Y')} ({kalan_gun} gün kaldı)"
            except: bilgi_text += "\n\n🤰 Gebelik Durumu: GEBE ✅"
            
        elif hayvan.get('olu', False):
            bilgi_text += f"\n\n💀 Hayat Durumu: ÖLÜ ({hayvan.get('olum_tarihi', '-')})"
        
        tk.Label(bilgi_frame, text=bilgi_text, font=('Segoe UI', 12), bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], justify='left', anchor='nw').pack(fill='x', pady=5, anchor='n')

        if not is_male:
            tk.Label(sol_panel, text="🍼 DOĞUM GEÇMİŞİ", bg=self.renkler["gri"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 14, 'bold'), pady=15).pack(fill='x')
            dogum_frame = tk.Frame(sol_panel, bg=self.renkler["kart_arkaplan"], padx=20, pady=10)
            dogum_frame.pack(fill='both', expand=True)
            if dogumlar:
                for i, dogum in enumerate(dogumlar, 1):
                    # --- YENİ DOĞUM GEÇMİŞİ GÖSTERİMİ ---
                    if dogum.get('not') == 'Geçmiş kayıt, süre bilinmiyor':
                         dogum_txt = f"{i}. Doğum: {dogum.get('not')}"
                    else:
                        yavrular_str_list = [f"{y.get('cins', 'Bilinmiyor')} (Küpe: {y.get('kupe', 'Bilinmiyor')})" for y in dogum.get('yavrular', [])]
                        yavrular_str = ", ".join(yavrular_str_list) if yavrular_str_list else "Yavru bilgisi yok"
                        dogum_txt = f"{i}. Doğum ({dogum.get('tarih','-')}): {yavrular_str}"
                    # --- YENİLİK SONU ---
                    tk.Label(dogum_frame, text=dogum_txt, bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 11), wraplength=sol_panel.winfo_width()-50).pack(anchor='w')
            else: tk.Label(dogum_frame, text="Kayıtlı doğum yok.", bg=self.renkler["kart_arkaplan"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 11, 'italic')).pack(anchor='w')

        if not is_male:
            sag_panel = tk.Frame(ana_frame, bg=self.renkler["kart_arkaplan"])
            sag_panel.pack(side='right', fill='both', expand=True, padx=(10, 0))
            tk.Label(sag_panel, text="💉 TOHUMLAMA GEÇMİŞİ", bg=self.renkler["gri"], fg=self.renkler["yazi_rengi"], font=('Segoe UI', 14, 'bold'), pady=15).pack(fill='x')
            tohumlama_tree_frame = tk.Frame(sag_panel, bg=self.renkler["kart_arkaplan"])
            tohumlama_tree_frame.pack(fill='both', expand=True, padx=1, pady=1)
            toh_cols = ('#', 'Tarih', 'Şekil', 'Suni İsim', 'Sonuç')
            toh_tree = ttk.Treeview(tohumlama_tree_frame, columns=toh_cols, show='headings', style='Modern.Treeview')
            for col in toh_cols:
                toh_tree.heading(col, text=col); toh_tree.column(col, width=120 if col != '#' else 40, anchor='center')
            if hayvan.get('tohumlamalar'):
                for i, tohumlama in enumerate(reversed(hayvan['tohumlamalar']), 1):
                    sonuc = "Beklemede";
                    if tohumlama.get('gebe_mi') is True: sonuc = "✅ Başarılı"
                    elif tohumlama.get('gebe_mi') is False: sonuc = "❌ Başarısız"
                    toh_tree.insert('', 'end', values=(len(hayvan['tohumlamalar']) - i + 1, tohumlama.get('tarih', '-'), tohumlama.get('sekil', '-'), tohumlama.get('suni_isim', '-'), sonuc))
            toh_tree.pack(fill='both', expand=True)

    # --- Kalan Fonksiyonlar ---
    def hayvan_listesini_guncelle(self):
        self.header_ozet_guncelle()
        for item in self.hayvan_tree.get_children(): self.hayvan_tree.delete(item)
        filtre = self.filtre_combo.get(); arama = self.arama_entry.get().strip().upper()
        self.tum_hayvanlari_guncelle()
        sorted_hayvanlar = sorted(self.hayvanlar.items(), key=lambda item: item[0])
        row_idx = 0
        for kupe_no, hayvan in sorted_hayvanlar:
            gorunen_kupe_arama = ((hayvan.get('ciftlik_kupe_no') or '') + ' ' + (hayvan.get('resmi_kupe_no') or '')).upper()
            if arama and arama not in gorunen_kupe_arama: continue
            arsivli = hayvan.get('arsivli', False)
            aktif_degil = arsivli or hayvan.get('olu', False) or hayvan.get('kesildi', False)
            
            if filtre == "Aktif" and aktif_degil:
                continue
            elif filtre == "Arşivli" and not arsivli:
                continue
            elif filtre not in ["Aktif", "Tümü", "Arşivli"]:
                if arsivli:
                    continue
                filtre_durum_check = (filtre == "Gebe" and hayvan.get('gebe_mi', False)) or \
                                     (filtre == "Ölü" and hayvan.get('olu', False)) or \
                                     (filtre == "Kesildi" and hayvan.get('kesildi', False))
                filtre_gec = (filtre_durum_check or (hayvan.get('cins') == filtre))
                if not filtre_gec: continue

            yas_gun = hayvan.get('yas_gun', 0); yas_str = f"{yas_gun // 365} yıl {(yas_gun % 365) // 30} ay"
            
            if arsivli:
                mevcut_durum = "🗄️ Arşivli"
            elif hayvan.get('olu', False):
                mevcut_durum = "💀 Ölü"
            elif hayvan.get('kesildi', False):
                mevcut_durum = "🔪 Kesildi"
            elif hayvan.get('gebe_mi', False):
                mevcut_durum = "🤰 Gebe"
            else:
                mevcut_durum = "✅ Hayatta"

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
                    if dogumlar:
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
            ciftlik_ad = hayvan.get('ciftlik_ad') or hayvan.get('ciftlik_id') or '-'
            self.hayvan_tree.insert('', 'end', values=(kupe_no, ciftlik_ad, resmi, ciftlik, yas_str, hayvan['cins'], mevcut_durum, son_tohumlama, dogum_tahmini, sagim_gun_str, uyarilar), tags=tuple(final_tags))
            row_idx += 1

        # ─── TAG RENKLERI ──────────────────────────────────────────────────
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
        self.hayvan_tree.tag_configure('archived',   background=self.renkler["siyah"],       foreground=self.renkler["muted"])
        self.hayvan_tree.tag_configure('normal',     foreground=self.renkler["yazi_rengi"])
        self.tohumlama_hayvanlarini_guncelle()


    def tum_hayvanlari_guncelle(self):
        is_changed = False
        for kupe_no, hayvan in list(self.hayvanlar.items()):
            if hayvan.get('olu', False) or hayvan.get('kesildi', False) or hayvan.get('arsivli', False): continue
            
            try:
                dogum_tarihi = datetime.strptime(hayvan['dogum_tarihi'], "%d/%m/%Y")
                yeni_yas_gun = (datetime.now() - dogum_tarihi).days
                if hayvan.get('yas_gun') != yeni_yas_gun:
                    hayvan['yas_gun'] = yeni_yas_gun; is_changed = True
                
                if not hayvan.get('gebe_mi', False) and hayvan.get('durum') not in ['Sağmal İnek', 'Kuru İnek']:
                    yeni_cins = self.otomatik_cins_guncelle(hayvan['cins'], yeni_yas_gun)
                    if yeni_cins != hayvan['cins']:
                        hayvan['cins'] = yeni_cins
                        hayvan['durum'] = self.durum_hesapla(yeni_cins, yeni_yas_gun)
                        is_changed = True
            
            except Exception as e:
                print(f"Hayvan güncellenirken hata ({kupe_no}): {e}")
                continue
        if is_changed: self.veri_kaydet()

    def uyarilari_guncelle(self):
        uyarilar, uyari_metni = [], ""
        for kupe_no, hayvan in self.hayvanlar.items():
            if hayvan.get('arsivli', False) or hayvan.get('olu', False) or hayvan.get('kesildi', False):
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
                                durum, tip = "🔴 ACİL", "🚨 GEBELİK KONTROLÜ"
                            else:
                                durum, tip = "🟠 ÖNEMLİ", "📋 GEBELİK KONTROLÜ YAKIN"
                            gorunen_kupe = hayvan.get('ciftlik_kupe_no') or hayvan.get('resmi_kupe_no') or kupe_no
                            if not okundu_mu:
                                uyari_metni += f"📋 {gorunen_kupe}: Gebelik kontrolü! "
                            uyarilar.append({
                                'kupe_no': gorunen_kupe,
                                'tip': tip,
                                'mesaj': f"Kontrol tarihi: {kontrol_tarihi.strftime('%d/%m/%Y')}",
                                'kalan_gun': kalan_kontrol,
                                'durum': durum,
                                'uyari_durumu': "👁️ OKUNDU" if okundu_mu else "🔔 YENİ",
                                'okundu': okundu_mu
                            })
                    except: pass

            if aktif_tohumlama_id and hayvan.get('durum') == 'Sağmal İnek' and hayvan.get('gebe_mi', False):
                try:
                    g_tarihi = datetime.strptime(hayvan['gebelik_tarihi'], "%d/%m/%Y")
                    kalan_gun_doguma = (g_tarihi + timedelta(days=283) - datetime.now()).days
                    uyari_key = self.uyari_key_olustur(kupe_no, "kuruya_al", aktif_tohumlama_id, kalan_gun_doguma)
                    if uyari_key:
                        okundu_mu = uyari_key in self.okunan_uyarilar
                        
                        gorunen_kupe = hayvan.get('ciftlik_kupe_no') or hayvan.get('resmi_kupe_no') or kupe_no
                        if not okundu_mu:
                            uyari_metni += f"🐮 {gorunen_kupe}: Kuruya Al! "
                        uyarilar.append({
                            'kupe_no': gorunen_kupe, 'tip': "🚨 KURUYA ALINMALI", 
                            'mesaj': f"Doğuma {kalan_gun_doguma} gün kaldı. Kuruya ayrılmalı!", 
                            'kalan_gun': kalan_gun_doguma, 'durum': "🔴 ACİL", 
                            'uyari_durumu': "👁️ OKUNDU" if okundu_mu else "🔔 YENİ", 'okundu': okundu_mu})
                except: pass

            if aktif_tohumlama_id and hayvan.get('gebe_mi', False):
                try:
                    g_tarihi = datetime.strptime(hayvan['gebelik_tarihi'], "%d/%m/%Y")
                    kalan_gun = (g_tarihi + timedelta(days=283) - datetime.now()).days
                    uyari_key = self.uyari_key_olustur(kupe_no, "gebelik", aktif_tohumlama_id, kalan_gun)
                    if uyari_key:
                        okundu_mu = uyari_key in self.okunan_uyarilar

                        if kalan_gun <= 0: durum, tip = "🔴 ACİL", "🚨 DOĞUM VAKTİ"
                        elif kalan_gun <= 7: durum, tip = "🔴 ACİL", "🚨 DOĞUM ÇOK YAKIN"
                        elif kalan_gun <= 30: durum, tip = "🟠 ÖNEMLİ", "⚠️ DOĞUM YAKIN"
                        else: durum, tip = "🟡 DİKKAT", "📢 DOĞUM HAZIRLIĞI"
                        
                        gorunen_kupe = hayvan.get('ciftlik_kupe_no') or hayvan.get('resmi_kupe_no') or kupe_no
                        if not okundu_mu and 'ACİL' in durum: 
                            uyari_metni += f"🚨 {gorunen_kupe}: {kalan_gun} gün! "
                            
                        uyarilar.append({'kupe_no': gorunen_kupe, 'tip': tip, 'mesaj': f"Doğuma {kalan_gun} gün" if kalan_gun > 0 else "DOĞUM VAKTİ!", 'kalan_gun': kalan_gun, 'durum': durum, 'uyari_durumu': "👁️ OKUNDU" if okundu_mu else "🔔 YENİ", 'okundu': okundu_mu})
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
                            durum, tip = "🔴 ACİL", "🚨 AŞI/PROSEDÜR GECİKTİ"
                        else:
                            durum, tip = "🟡 DİKKAT", "💉 AŞI/PROSEDÜR YAKIN"
                        if not okundu_mu:
                            gorunen_kupe = hayvan.get('ciftlik_kupe_no') or hayvan.get('resmi_kupe_no') or kupe_no
                            uyari_metni += f"💉 {gorunen_kupe}: {prosedur.get('ad', 'Prosedür')}! "
                        else:
                            gorunen_kupe = hayvan.get('ciftlik_kupe_no') or hayvan.get('resmi_kupe_no') or kupe_no
                        uyarilar.append({
                            'kupe_no': gorunen_kupe,
                            'tip': tip,
                            'mesaj': f"{prosedur.get('ad', 'Prosedür')} - tarih: {sonraki_tarih}",
                            'kalan_gun': kalan_prosedur,
                            'durum': durum,
                            'uyari_durumu': "👁️ OKUNDU" if okundu_mu else "🔔 YENİ",
                            'okundu': okundu_mu
                        })
                except: pass
        
        okunmamis_uyarilar = [u for u in uyarilar if not u['okundu']]
        okunmamis_kritik = [u for u in okunmamis_uyarilar if '🔴' in u['durum']]

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
            self._puls_aktif = puls
            if puls:
                self._puls_animasyon()

        if okunmamis_kritik:
            _set_band(
                bg=self.renkler["band_critical_bg"], fg=self.renkler["band_critical_fg"],
                ikon='🚨', ind_renk=self.renkler["koyu_kirmizi"],
                metin=f"KRİTİK: {len(okunmamis_kritik)} uyarı aktif  —  {uyari_metni.strip()}",
                puls=True
            )
        elif okunmamis_uyarilar:
            _set_band(
                bg=self.renkler["band_warning_bg"], fg=self.renkler["band_warning_fg"],
                ikon='⚠️', ind_renk='#F59E0B',
                metin=f"{len(okunmamis_uyarilar)} okunmamış uyarı var  —  Uyarılar sekmesini kontrol edin",
                puls=False
            )
        else:
            _set_band(
                bg=self.renkler["band_normal_bg"], fg=self.renkler["band_normal_fg"],
                ikon='✅', ind_renk=self.renkler["yesil"],
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
                    elif '🔴' in uyari['durum']: tag = "critical_new"
                    elif '🟠' in uyari['durum']: tag = "important_new"
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
        
        if not MATPLOTLIB_AVAILABLE:
            messagebox.showwarning("Eksik Kütüphane", "Raporlama özelliği için 'matplotlib' kütüphanesi önerilir.\nKomut: pip install matplotlib")

        app = HayvanTakipSistemi()
        app.calistir()
    except Exception as e:
        messagebox.showerror("Kritik Hata", f"Uygulama başlatılamadı:\n{str(e)}")
