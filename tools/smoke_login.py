import os
import subprocess
import sys
import tempfile
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from smoke_api import free_port, request, wait_for_health


ROOT = Path(__file__).resolve().parents[1]
LIVE_ENV_KEYS = ("ALP_API_URL", "DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "ALP_PHOTO_BUCKET")


def clear_live_env(env):
    for key in LIVE_ENV_KEYS:
        env.pop(key, None)


def walk_widgets(widget):
    widgets = [widget]
    try:
        children = widget.winfo_children()
    except tk.TclError:
        children = []
    for child in children:
        widgets.extend(walk_widgets(child))
    return widgets


def start_api():
    tmp = tempfile.mkdtemp(prefix="alp_login_api_")
    db_path = Path(tmp) / "login_smoke.db"
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    clear_live_env(env)
    env["APPDATA"] = tmp
    env["DATABASE_URL"] = "sqlite:///" + str(db_path).replace("\\", "/")
    env["ALP_BOOTSTRAP_ADMIN_USERNAME"] = "admin"
    env["ALP_BOOTSTRAP_ADMIN_PASSWORD"] = "admin1234"

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "api:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=creationflags,
    )
    wait_for_health(proc, base_url)
    return proc, base_url


def prepare_appdata(base_url):
    tmp = tempfile.mkdtemp(prefix="alp_login_ui_")
    clear_live_env(os.environ)
    os.environ["APPDATA"] = tmp
    cfg_dir = Path(tmp) / "ALP Ziraat" / "HayvanTakip"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "api_ayarlar.json").write_text(
        json_text({"api_url": base_url}),
        encoding="utf-8",
    )
    return tmp


def json_text(data):
    import json

    return json.dumps(data, ensure_ascii=False)


def assert_main_layout(app):
    app.root.geometry("1280x820")
    app.root.update_idletasks()
    app.root.update()
    assert "Sürü Takip Sistemi" in app.root.title(), app.root.title()
    assert hasattr(app, "custom_tab_bar"), "custom tab bar missing after login"
    assert hasattr(app, "notebook"), "notebook missing after login"
    assert len(getattr(app, "tab_buttons", [])) >= 7, "main tabs missing after login"
    tab_y = app.custom_tab_bar.winfo_rooty()
    notebook_y = app.notebook.winfo_rooty()
    assert tab_y < notebook_y, f"tab bar is below content after login: tab_y={tab_y}, notebook_y={notebook_y}"


def main():
    proc, base_url = start_api()
    prepare_appdata(base_url)

    try:
        _, health = request(base_url, "GET", "/api/health", expected=200)
        assert health["status"] == "ok"

        sys.path.insert(0, str(ROOT))
        import alp_ziraat_hayvan_takip as appmod

        original_login = appmod.HayvanTakipSistemi.api_giris_penceresi
        original_admin = appmod.HayvanTakipSistemi.admin_yonetim_merkezi

        def auto_login(self):
            attempts = {"count": 0}

            def fill_and_submit():
                attempts["count"] += 1
                entries = [w for w in walk_widgets(self.root) if isinstance(w, ttk.Entry)]
                if len(entries) < 2:
                    if attempts["count"] < 20:
                        self._track_after(self.root, 150, fill_and_submit)
                    return
                entries[0].delete(0, tk.END)
                entries[0].insert(0, "admin")
                entries[1].delete(0, tk.END)
                entries[1].insert(0, "admin1234")
                entries[1].focus_force()
                entries[1].event_generate("<Return>")
                for widget in walk_widgets(self.root):
                    if isinstance(widget, tk.Canvas) and hasattr(widget, "text_item"):
                        try:
                            text = widget.itemcget(widget.text_item, "text")
                        except tk.TclError:
                            continue
                        if text == "Giriş":
                            getattr(widget, "command", lambda: widget.event_generate("<Button-1>", x=8, y=8))()
                            return

            self._track_after(self.root, 300, fill_and_submit)
            return original_login(self)

        def auto_admin(self):
            attempts = {"count": 0}

            def enter_all_farms():
                attempts["count"] += 1
                for widget in walk_widgets(self.root):
                    if isinstance(widget, tk.Button):
                        try:
                            text = widget.cget("text")
                        except tk.TclError:
                            continue
                        if text.startswith("Tüm çiftliklerin") or text.startswith("Tum ciftliklerin"):
                            widget.invoke()
                            return
                if attempts["count"] < 30:
                    self._track_after(self.root, 200, enter_all_farms)

            self._track_after(self.root, 500, enter_all_farms)
            return original_admin(self)

        appmod.HayvanTakipSistemi.api_giris_penceresi = auto_login
        appmod.HayvanTakipSistemi.admin_yonetim_merkezi = auto_admin

        app = appmod.HayvanTakipSistemi()
        try:
            assert app._baslatma_tamam is True
            assert app.api_kullanici and app.api_kullanici.get("rol") == "admin"
            assert hasattr(app, "hayvan_tree")
            assert_main_layout(app)
            print(f"Login smoke OK: {base_url}")
        finally:
            app.uygulamayi_kapat()
        return 0
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
