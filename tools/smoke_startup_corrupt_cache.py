import os
import sys
import tempfile
import threading
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIVE_ENV_KEYS = ("ALP_API_URL", "DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "ALP_PHOTO_BUCKET")


def prepare_appdata():
    tmp = tempfile.mkdtemp(prefix="alp_corrupt_startup_")
    for key in LIVE_ENV_KEYS:
        os.environ.pop(key, None)
    os.environ["APPDATA"] = tmp
    os.environ["ALP_SKIP_UPDATE_CHECK"] = "1"
    cfg_dir = Path(tmp) / "ALP Ziraat" / "HayvanTakip"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "api_ayarlar.json").write_text('{"api_url":""}', encoding="utf-8")
    (cfg_dir / "hayvan_verileri.json").write_text("{ bozuk json", encoding="utf-8")


def main():
    prepare_appdata()
    sys.path.insert(0, str(ROOT))

    import alp_ziraat_hayvan_takip as appmod

    warning_threads = []
    appmod.messagebox.showwarning = lambda *args, **kwargs: warning_threads.append(threading.current_thread().name)
    appmod.messagebox.showerror = lambda *args, **kwargs: None

    app = appmod.HayvanTakipSistemi()
    try:
        start = time.time()
        while time.time() - start < 8:
            app.root.update()
            if warning_threads and getattr(app, "_baslangic_hazirligi_tamam", False):
                break
            time.sleep(0.02)
        assert warning_threads == ["MainThread"], warning_threads
        print("Startup corrupt cache smoke OK")
        return 0
    finally:
        app.uygulamayi_kapat()


if __name__ == "__main__":
    raise SystemExit(main())
