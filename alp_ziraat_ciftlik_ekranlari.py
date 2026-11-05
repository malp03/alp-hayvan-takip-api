import threading
import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, simpledialog, ttk


class CiftlikEkEkranlari:
    def ek_kayit_ciftlik_id(self):
        kullanici = getattr(self, "api_kullanici", None) or {}
        return self.admin_aktif_ciftlik_id if self.admin_mi() else kullanici.get("ciftlik_id")

    def ek_kayit_istegi(self, parent, method, path, tamamla, *, veri=None, hata=None):
        kapsam = (getattr(self, "api_url", None), self.api_son_islemler_kapsami())

        def worker():
            sonuc = None
            sorun = None
            try:
                sonuc = self.api_istek(method, path, payload=veri, timeout=12)
            except Exception as exc:
                sorun = str(exc)

            def goster():
                if not parent.winfo_exists() or kapsam != (getattr(self, "api_url", None), self.api_son_islemler_kapsami()):
                    return
                if sorun is None:
                    tamamla(sonuc)
                elif hata:
                    hata(sorun)
                else:
                    messagebox.showerror("İşlem tamamlanamadı", sorun, parent=parent)

            self.ui_threadinde_calistir(goster)

        threading.Thread(target=worker, daemon=True, name="alp-ek-kayit").start()

    def tohumlama_secenek_yolu(self, ciftlik_id=None):
        kimlik = ciftlik_id or self.ek_kayit_ciftlik_id()
        return f"/api/ciftlikler/{self.api_ref(kimlik)}/tohumlama-secenekleri" if kimlik else None

    def tohumlama_secenekleri_yukle(self, suni, veteriner, *, ciftlik_id=None):
        yol = self.tohumlama_secenek_yolu(ciftlik_id)
        if not yol or not getattr(self, "api_token", None) or self.offline_modda_mi():
            return
        if getattr(suni, "_secenek_yukleniyor", False):
            return
        suni._secenek_yukleniyor = True

        def tamamla(veri):
            suni._secenek_yukleniyor = False
            suni.configure(values=veri.get("suni") or ())
            veteriner.configure(values=veri.get("veteriner") or ())

        def hata(_):
            suni._secenek_yukleniyor = False

        self.ek_kayit_istegi(suni, "GET", yol, tamamla, hata=hata)

    def tohumlama_secenegi_ekle(self, tur):
        yol = self.tohumlama_secenek_yolu()
        if not yol:
            return messagebox.showwarning("Tohumlama", "Önce bir çiftlik seçin.", parent=self.root)
        if not self.online_islem_gerekli("Tohumlama seçeneği ekleme", self.root):
            return
        baslik = "Suni tohumlama çeşidi" if tur == "suni" else "Veteriner"
        ad = simpledialog.askstring(baslik + " ekle", baslik + " adı:", parent=self.root)
        if not ad or not ad.strip():
            return
        combo = self.suni_entry if tur == "suni" else self.tohumlama_veteriner_combo

        def tamamla(veri):
            secilen = veri["ad"]
            combo.configure(values=tuple(dict.fromkeys([*combo["values"], secilen])))
            combo.set(secilen)

        self.ek_kayit_istegi(combo, "POST", yol, tamamla, veri={"tur": tur, "ad": ad.strip()})

    def hayvan_kolonlarini_uygula(self):
        kullanici = (getattr(self, "api_kullanici", None) or {}).get("id") or "yerel"
        self._hayvan_kolon_dosyasi = self.data_dir + "/hayvan_kolonlari.json"
        tercihler = self.json_dosyasi_yukle(self._hayvan_kolon_dosyasi, {}, "hayvan_kolonlari")
        kayit = tercihler.get(kullanici) if isinstance(tercihler, dict) else None
        kolonlar = self.hayvan_tree["columns"][2:]
        varsayilan = kolonlar[:kolonlar.index("Gebelik Günü")]
        secili = [kolon for kolon in kolonlar if kolon in kayit] if isinstance(kayit, list) else varsayilan
        self.hayvan_tree.configure(displaycolumns=("Seç", *(secili or kolonlar)))

    def hayvan_kolonlarini_duzenle(self):
        pencere, kart = self.modern_popup("Liste Görünümü", 450, 350)
        secenekler = ttk.Frame(kart)
        secenekler.pack(fill="both", expand=True, padx=8, pady=8)
        mevcut = set(self.hayvan_tree["displaycolumns"])
        alanlar = {}
        for index, kolon in enumerate(self.hayvan_tree["columns"][2:]):
            var = tk.BooleanVar(pencere, kolon in mevcut)
            alanlar[kolon] = var
            ttk.Checkbutton(secenekler, text=kolon, variable=var).grid(
                row=index // 2, column=index % 2, sticky="w", padx=14, pady=6,
            )

        def uygula():
            secili = [kolon for kolon, var in alanlar.items() if var.get()]
            if not secili:
                messagebox.showwarning("Liste Görünümü", "En az bir bilgi seçin.", parent=pencere)
                return
            kullanici = (getattr(self, "api_kullanici", None) or {}).get("id") or "yerel"
            tercihler = self.json_dosyasi_yukle(self._hayvan_kolon_dosyasi, {}, "hayvan_kolonlari")
            tercihler = tercihler if isinstance(tercihler, dict) else {}
            tercihler[kullanici] = secili
            if self.json_dosyasi_kaydet(self._hayvan_kolon_dosyasi, tercihler, "hayvan_kolonlari", "Görünüm Kaydedilemedi"):
                self.hayvan_tree.configure(displaycolumns=("Seç", *secili))
                pencere.destroy()

        self.modern_buton(secenekler, "Kaydet", uygula, purpose="primary", small=True).grid(
            row=(len(alanlar) + 1) // 2, columnspan=2, pady=10,
        )
        self.pencere_ortala(pencere, self.root)
        pencere.grab_set()

    @staticmethod
    def _ek_tarih(deger):
        try:
            return date.fromisoformat(deger).strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            return "-"

    @staticmethod
    def gebelik_gunu(hayvan):
        if not hayvan.get("gebe_mi") or any(hayvan.get(k) for k in ("arsivli", "olu", "kesildi", "satildi")):
            return None
        try:
            baslangic = datetime.strptime(hayvan.get("gebelik_tarihi") or "", "%d/%m/%Y").date()
        except ValueError:
            return None
        gun = (date.today() - baslangic).days
        return gun if gun >= 0 else None

    @staticmethod
    def _ek_sayi(deger):
        return "-" if deger is None else f"{deger:.2f}".replace(".", ",")

    def _ek_kayit_formu(self, parent, baslik, alanlar, gonder):
        pencere, kart = self.modern_popup(baslik, 520, 380, parent)
        girisler = {}
        for key, etiket, deger in alanlar:
            if key == "aciklama":
                ttk.Label(kart, text=etiket).pack(anchor="w", padx=12, pady=(8, 0))
                widget = tk.Text(kart, height=4, wrap="word", bg=self.renkler["input_bg"], fg=self.renkler["yazi_rengi"])
                widget.pack(fill="x", padx=12, pady=4)
                widget.insert("1.0", deger)
                girisler[key] = lambda w=widget: w.get("1.0", "end-1c")
            else:
                ttk.Label(kart, text=etiket).pack(anchor="w", padx=12, pady=(8, 0))
                widget = ttk.Entry(kart)
                widget.pack(fill="x", padx=12, pady=4)
                widget.insert(0, deger)
                girisler[key] = widget.get
        bar = self.popup_buton_bar(kart)
        busy = False

        def hata(mesaj):
            nonlocal busy
            busy = False
            messagebox.showerror("Kayıt tamamlanamadı", mesaj, parent=pencere)

        def kaydet():
            nonlocal busy
            if busy:
                return
            busy = True
            gonder(pencere, {k: f().strip() for k, f in girisler.items()}, hata)

        self.modern_buton(bar, "Kaydet", kaydet, purpose="primary", small=True).pack(side="right")
        self.modern_buton(bar, "Vazgeç", pencere.destroy, small=True).pack(side="right", padx=8)
        self.pencere_ortala(pencere, parent)
        pencere.grab_set()
        pencere.wait_window()
        if parent is not self.root and parent.winfo_exists():
            parent.grab_set()

    def _ek_kayit_sil(self, pencere, yol, kayit, yenile):
        if messagebox.askyesno("Kaydı Sil", "Seçili kayıt silinsin mi?", parent=pencere):
            hedef = f"{yol}/{self.api_ref(kayit['id'])}?surum={self.api_ref(kayit['surum'])}"
            self.ek_kayit_istegi(pencere, "DELETE", hedef, lambda _: yenile())

    def _ek_kayit_kaydet(self, pencere, yol, kayit, veri, hata, yenile):
        hedef = f"{yol}/{self.api_ref(kayit['id'])}?surum={self.api_ref(kayit['surum'])}" if kayit else yol

        def tamamla(sonuc):
            pencere.destroy()
            yenile(sonuc)

        self.ek_kayit_istegi(pencere, "PATCH" if kayit else "POST", hedef, tamamla, veri=veri, hata=hata)

    def hayvan_olaylari_penceresi(self, h_id, parent):
        if not self.online_islem_gerekli("Hayvan olayları", parent):
            return
        yol = f"/api/hayvanlar/{self.api_ref(h_id)}/olaylar"
        pencere, kart = self.modern_popup("Hayvan Olayları", 750, 500, parent)
        tablo = self.profil_tablo_olustur(kart, ("Tarih", "Olay"), {"Tarih": 115, "Olay": 560})
        detay = ttk.Label(kart, text="", wraplength=630, justify="left")
        detay.pack(fill="x", padx=12, pady=8)
        kayitlar = {}

        def secili():
            secim = tablo.selection()
            return kayitlar.get(secim[0]) if secim else None

        def doldur(veri):
            tablo.delete(*tablo.get_children())
            kayitlar.clear()
            detay.configure(text="" if veri else "Henüz olay kaydı yok.")
            for k in veri:
                kayitlar[k["id"]] = k
                tablo.insert("", "end", iid=k["id"], values=(self._ek_tarih(k["tarih"]), k["baslik"]))

        def yenile():
            self.ek_kayit_istegi(pencere, "GET", yol, doldur)

        def form(kayit=None):
            k = kayit or {}

            def gonder(dialog, veri, hata):
                try:
                    veri["tarih"] = datetime.strptime(veri["tarih"], "%d/%m/%Y").date().isoformat()
                except ValueError:
                    return hata("Tarih GG/AA/YYYY biçiminde olmalı.")
                self._ek_kayit_kaydet(dialog, yol, kayit, veri, hata, lambda _: yenile())

            self._ek_kayit_formu(pencere, "Hayvan Olayı", [
                ("tarih", "Tarih (GG/AA/YYYY)", self._ek_tarih(k.get("tarih") or date.today().isoformat())),
                ("baslik", "Olay başlığı", k.get("baslik", "")),
                ("aciklama", "Açıklama", k.get("aciklama", "")),
            ], gonder)

        tablo.bind("<<TreeviewSelect>>", lambda _: detay.configure(text=(secili() or {}).get("aciklama", "")))
        tablo.bind("<Double-Button-1>", lambda _: secili() and form(secili()))
        bar = self.popup_buton_bar(kart)
        for ad, komut, stil in [
            ("Olay Ekle", form, "primary"), ("Düzenle", lambda: secili() and form(secili()), "default"),
            ("Sil", lambda: secili() and self._ek_kayit_sil(pencere, yol, secili(), yenile), "danger"),
            ("Yenile", yenile, "default"),
        ]:
            self.modern_buton(bar, ad, komut, purpose=stil, small=True).pack(side="left", padx=4)
        self.pencere_ortala(pencere, parent)
        pencere.grab_set()
        yenile()
        pencere.wait_window()
        if parent.winfo_exists():
            parent.grab_set()

    def sut_kaydi_sekmesi(self):
        sayfa = ttk.Frame(self.notebook)
        self.notebook.add(sayfa, text="Süt Kayıtları")
        kart = self.modern_kart(sayfa)
        kart.pack(fill="both", expand=True, padx=18, pady=16)
        bar = ttk.Frame(kart)
        bar.pack(fill="x", padx=12, pady=10)
        ozet = ttk.Label(kart, text="")
        ozet.pack(anchor="w", padx=14, pady=6)
        tablo = self.profil_tablo_olustur(kart, ("Tarih", "Toplam (L)", "Sağmal", "L/inek", "Sapma", "Uyarı"),
                                        {"Uyarı": 330}, height=11)
        tablo.tag_configure("sapma", foreground=self.renkler["uyari"])
        ay = date.today().replace(day=1)
        kayitlar = {}
        durum = {}
        istek_no = 0
        ay_label = ttk.Label(bar)
        yol = None

        def doldur(veri):
            durum.clear()
            durum.update(veri)
            tablo.delete(*tablo.get_children())
            kayitlar.clear()
            ozet.configure(text=f"Bugünkü sağmal: {veri['guncel_sagmal_sayisi']}   |   "
                                f"Aylık toplam: {self._ek_sayi(veri['toplam_litre'])} L   |   "
                                f"Aylık verim: {self._ek_sayi(veri['ortalama_verim'])} L/inek")
            for k in veri["kayitlar"]:
                kayitlar[k["id"]] = k
                tablo.insert("", "end", iid=k["id"], tags=("sapma",) if k["uyari"] else (), values=(
                    self._ek_tarih(k["tarih"]), self._ek_sayi(k["litre"]), k["sagmal_sayisi"],
                    self._ek_sayi(k["verim"]), self._ek_sayi(k["sapma_yuzde"]) + "%" if k["sapma_yuzde"] is not None else "-",
                    "Sürü sağlık ve sağım kontrollerini yapın" if k["uyari"] else "-",
                ))

        def yenile():
            nonlocal istek_no, yol
            istek_no += 1
            no = istek_no
            ay_label.configure(text=ay.strftime("%m/%Y"))
            ciftlik = self.ek_kayit_ciftlik_id()
            yol = None
            kayitlar.clear()
            tablo.delete(*tablo.get_children())
            durum.clear()
            if not ciftlik or not getattr(self, "api_token", None):
                ozet.configure(text="Süt kayıtları için çevrimiçi giriş yapın ve bir çiftlik seçin.")
                return
            yol = f"/api/ciftlikler/{self.api_ref(ciftlik)}/sut-kayitlari"
            ozet.configure(text="Süt kayıtları yükleniyor…")
            self.ek_kayit_istegi(kart, "GET", f"{yol}?ay={ay:%Y-%m}",
                                 lambda veri: no == istek_no and doldur(veri),
                                 hata=lambda mesaj: no == istek_no and ozet.configure(text=mesaj))

        def ay_degistir(adim):
            nonlocal ay
            yil, ay_no = divmod(ay.year * 12 + ay.month - 1 + adim, 12)
            if 1 <= yil <= 9998:
                ay = date(yil, ay_no + 1, 1)
                yenile()

        def secili():
            secim = tablo.selection()
            return kayitlar.get(secim[0]) if secim else None

        def form(kayit=None):
            if not yol or not durum:
                return
            k = kayit or {}
            bugun = date.fromisoformat(durum["bugun"])
            tarih = k.get("tarih") or (bugun if (bugun.year, bugun.month) == (ay.year, ay.month) else ay).isoformat()
            alanlar = [
                ("litre", "Günlük toplam süt (litre)", str(k.get("litre", ""))),
                ("sagmal_sayisi", f"Sağmal sayısı (bugün boşsa otomatik: {durum['guncel_sagmal_sayisi']})",
                 str(k.get("sagmal_sayisi", ""))),
            ]
            if not kayit:
                alanlar.insert(0, ("tarih", "Tarih (GG/AA/YYYY)", self._ek_tarih(tarih)))

            def gonder(dialog, veri, hata):
                try:
                    veri["litre"] = veri["litre"].replace(",", ".")
                    veri["sagmal_sayisi"] = int(veri["sagmal_sayisi"]) if veri["sagmal_sayisi"] else None
                    if not kayit:
                        veri["tarih"] = datetime.strptime(veri["tarih"], "%d/%m/%Y").date().isoformat()
                except ValueError:
                    return hata("Tarihi ve sağmal sayısını kontrol edin.")
                def kaydedildi(sonuc):
                    nonlocal ay
                    ay = date.fromisoformat(sonuc["tarih"]).replace(day=1)
                    yenile()

                self._ek_kayit_kaydet(dialog, yol, kayit, veri, hata, kaydedildi)

            self._ek_kayit_formu(self.root, f"Süt Kaydı{(' - ' + self._ek_tarih(tarih)) if kayit else ''}", alanlar, gonder)

        self.modern_buton(bar, "‹", lambda: ay_degistir(-1), small=True).pack(side="left")
        ay_label.pack(side="left", padx=10)
        self.modern_buton(bar, "›", lambda: ay_degistir(1), small=True).pack(side="left")
        for ad, komut, stil in [
            ("Süt Kaydı Ekle", form, "primary"), ("Düzenle", lambda: secili() and form(secili()), "default"),
            ("Sil", lambda: yol and secili() and self._ek_kayit_sil(kart, yol, secili(), yenile), "danger"),
            ("Yenile", yenile, "default"),
        ]:
            self.modern_buton(bar, ad, komut, purpose=stil, small=True).pack(side="left", padx=(8, 0))
        self.notebook.bind("<<NotebookTabChanged>>",
                           lambda _: self.notebook.select() == str(sayfa) and yenile(), add="+")
