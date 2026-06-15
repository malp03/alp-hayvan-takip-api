import queue
import sys
import threading
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import alp_ziraat_hayvan_takip as appmod


class FakeRoot:
    def __init__(self):
        self.events = []
        self.next_id = 0
        self.main_thread = threading.current_thread()

    def after(self, delay, callback):
        assert threading.current_thread() is self.main_thread, "Tk çağrısı worker thread içinden yapıldı."
        self.next_id += 1
        self.events.append((time.monotonic() + delay / 1000, self.next_id, callback))
        return self.next_id

    def after_cancel(self, event_id):
        self.events = [event for event in self.events if event[1] != event_id]

    def update(self):
        now = time.monotonic()
        due = [event for event in self.events if event[0] <= now]
        self.events = [event for event in self.events if event[0] > now]
        for _, _, callback in due:
            callback()


def app_hazirla():
    root = FakeRoot()
    app = appmod.HayvanTakipSistemi.__new__(appmod.HayvanTakipSistemi)
    app.root = root
    app.api_modu = True
    app.api_token = "smoke"
    app.api_offline_oturum = False
    app.api_cevrimdisi = False
    app.api_baglanti_durumu = "online"
    app._api_son_hata = None
    app._api_ag_lock = threading.Lock()
    app._ui_callback_kuyrugu = queue.Queue()
    app._kapanis_istegi = False
    app._ui_callback_after_id = root.after(10, app._ui_callback_kuyrugunu_isle)
    app.api_durum_guncelle = lambda: None
    app.hata_gunlugu_yaz = lambda *args, **kwargs: None
    app.data_file = str(ROOT / "_smoke_hayvan_verileri.json")
    app.pending_sync_file = str(ROOT / "_smoke_bekleyen_senkron.json")
    return app, root


def tamamlanana_kadar(root, tamamlandi, timeout=2):
    pulse = 0
    baslangic = time.monotonic()
    while not tamamlandi() and time.monotonic() - baslangic < timeout:
        root.update()
        pulse += 1
        time.sleep(0.005)
    assert tamamlandi(), "Arka plan bağlantı işlemi tamamlanmadı."
    assert pulse > 20, "Ağ beklenirken ana arayüz döngüsü çalışmadı."


def manuel_senkron_testi():
    app, root = app_hazirla()
    app._api_senkronizasyon_devam_ediyor = False
    app.bekleyen_senkron_sayisi = lambda: 0
    app.api_uyandir = lambda maksimum_bekleme=95: time.sleep(0.35) or True
    app.api_baglantiyi_yenile_sessiz = lambda ui_guncelle=False: True
    tamamlandi = threading.Event()
    appmod.messagebox.showinfo = lambda *args, **kwargs: tamamlandi.set()
    appmod.messagebox.showwarning = lambda *args, **kwargs: tamamlandi.set()

    app.api_senkronize_et_ui()
    assert app._api_senkronizasyon_devam_ediyor
    tamamlanana_kadar(root, tamamlandi.is_set)
    assert not app._api_senkronizasyon_devam_ediyor


def otomatik_keepalive_testi():
    app, root = app_hazirla()
    durum = {"bekleyen": False, "senkron": 0}
    app._otomatik_baglanti_after_id = None
    app._otomatik_baglanti_kontrol_ediliyor = False
    app.otomatik_baglanti_araligi_ms = 8 * 60 * 1000
    app.otomatik_baglanti_hata_araligi_ms = 60 * 1000
    app.bekleyen_senkron_sayisi = lambda: 0
    app.bekleyen_senkron_var = lambda: durum["bekleyen"]
    app.offline_modda_mi = lambda: False

    def api_uyandir(maksimum_bekleme=95):
        time.sleep(0.35)
        durum["bekleyen"] = True
        return True

    def senkronize_et(ui_guncelle=False):
        durum["senkron"] += 1
        durum["bekleyen"] = False
        return True

    app.api_uyandir = api_uyandir
    app.api_baglantiyi_yenile_sessiz = senkronize_et

    app.otomatik_baglanti_kontrol()
    assert app._otomatik_baglanti_kontrol_ediliyor
    tamamlanana_kadar(root, lambda: not app._otomatik_baglanti_kontrol_ediliyor)
    assert app.api_baglanti_durumu == "online"
    assert app._otomatik_baglanti_after_id is not None
    assert durum["senkron"] == 1, "Health kontrolü sırasında oluşan kuyruk gönderilmedi."


def render_uyandirma_testi():
    app, _ = app_hazirla()
    istek_sayisi = 0

    def api_istek(*args, **kwargs):
        nonlocal istek_sayisi
        istek_sayisi += 1
        if istek_sayisi == 1:
            raise appmod.ApiHatasi("Render servisi uyanıyor.", status=503)
        return {"status": "ok"}

    class FakeTime:
        now = 0

        @classmethod
        def monotonic(cls):
            return cls.now

        @classmethod
        def sleep(cls, seconds):
            cls.now += seconds

    app.api_istek = api_istek
    gercek_time = appmod.time
    appmod.time = FakeTime
    try:
        assert app.api_uyandir(maksimum_bekleme=10, ilk_timeout=3)
    finally:
        appmod.time = gercek_time
    assert istek_sayisi == 2
    assert app.api_baglanti_durumu == "online"


def timeout_retry_testi():
    app, _ = app_hazirla()
    istek_sayisi = 0

    def api_istek(*args, **kwargs):
        nonlocal istek_sayisi
        istek_sayisi += 1
        if istek_sayisi == 1:
            raise appmod.ApiHatasi("API bağlantısı kurulamadı: timed out")
        return {"status": "ok"}

    class FakeTime:
        now = 0

        @classmethod
        def monotonic(cls):
            return cls.now

        @classmethod
        def sleep(cls, seconds):
            cls.now += seconds

    app.api_istek = api_istek
    gercek_time = appmod.time
    appmod.time = FakeTime
    try:
        assert app.api_uyandir(maksimum_bekleme=10, ilk_timeout=3)
    finally:
        appmod.time = gercek_time
    assert istek_sayisi == 2


def oturum_401_yenileme_testi():
    app, _ = app_hazirla()
    app.api_token = "eski-token"
    cagrilar = {"ham": 0, "yenile": 0}

    def ham_istek(method, path, payload=None, timeout=12, auth=True):
        cagrilar["ham"] += 1
        if cagrilar["ham"] == 1:
            raise appmod.ApiHatasi("API 401: Oturum süresi doldu", status=401)
        assert app.api_token == "yeni-token"
        return {"ok": True}

    def yenile():
        cagrilar["yenile"] += 1
        app.api_token = "yeni-token"
        return True

    app._api_istek_ham = ham_istek
    app.api_oturumu_yenile = yenile
    assert app.api_istek("GET", "/api/hayvanlar") == {"ok": True}
    assert cagrilar == {"ham": 2, "yenile": 1}


def stale_update_kuyruk_testi():
    app, _ = app_hazirla()
    app.hayvanlar = {
        "A": {
            "id": "A",
            "resmi_kupe_no": "A",
            "cins": "Sağmal İnek",
            "son_guncelleme": "01/01/2026 10:00:00",
        }
    }
    app.bekleyen_senkron = {
        "upserts": {
            "A": {
                "id": "A",
                "resmi_kupe_no": "A",
                "cins": "Sağmal İnek",
                "son_guncelleme": "01/01/2026 10:00:00",
                "base_son_guncelleme": "01/01/2026 10:00:00",
            }
        },
        "deletes": {},
        "updated_at": None,
    }
    app._api_son_idler = {"A"}
    app._api_base_versions = {"A": "01/01/2026 10:00:00"}
    app.api_online_oturum_ac = lambda: True
    app.admin_mi = lambda: False
    app.bekleyen_senkron_kaydet = lambda: True
    app.json_dosyasi_kaydet = lambda *args, **kwargs: True

    def api_istek(method, path, payload=None, timeout=12, auth=True, oturum_yenile=True):
        if method == "PATCH":
            raise appmod.ApiHatasi(
                "API 409: {'code': 'stale_update', 'message': 'Merkezdeki kayıt daha yeni.'}",
                status=409,
            )
        if method == "GET":
            return {
                "id": "A",
                "resmi_kupe_no": "A",
                "cins": "Kuru İnek",
                "son_guncelleme": "15/06/2026 15:57:30",
            }
        raise AssertionError(f"Beklenmeyen istek: {method} {path}")

    app.api_istek = api_istek
    assert app.bekleyen_senkron_gonder(sessiz=True)
    assert not app.bekleyen_senkron_var()
    assert app.hayvanlar["A"]["cins"] == "Kuru İnek"
    assert app._api_base_versions["A"] == "15/06/2026 15:57:30"


def main():
    render_uyandirma_testi()
    timeout_retry_testi()
    oturum_401_yenileme_testi()
    stale_update_kuyruk_testi()
    manuel_senkron_testi()
    otomatik_keepalive_testi()
    print("Render sleep resilience smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
