import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PYTHON_FILES = [
    "alp_ziraat_hayvan_takip.py",
    "api.py",
    "api_deploy/api.py",
    "schemas.py",
    "api_deploy/schemas.py",
    "models.py",
    "api_deploy/models.py",
    "database.py",
    "api_deploy/database.py",
    "init_db.py",
    "api_deploy/init_db.py",
    "alp_ziraat_export.py",
    "alp_ziraat_is_kurallari.py",
    "tools/server_backup.py",
    "tools/smoke_api.py",
    "tools/smoke_admin_popups.py",
    "tools/smoke_exports.py",
    "tools/smoke_update.py",
    "tools/smoke_login.py",
    "tools/smoke_offline_login.py",
    "tools/smoke_remember_logout.py",
    "tools/smoke_admin_panel_logout.py",
    "tools/smoke_login_responsive.py",
    "tools/smoke_ui.py",
    "installer/setup_installer.py",
]


def run_step(name, command):
    print(f"\n== {name} ==", flush=True)
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main():
    files = [str(ROOT / path) for path in PYTHON_FILES]
    run_step("Python syntax check", [sys.executable, "-m", "py_compile", *files])

    if importlib.util.find_spec("pyflakes"):
        run_step("Pyflakes static check", [sys.executable, "-m", "pyflakes", *files])
    else:
        print("\n== Pyflakes static check ==\npyflakes not installed, skipped.", flush=True)

    run_step("Desktop UI smoke", [sys.executable, str(ROOT / "tools" / "smoke_ui.py")])
    run_step("Admin popup UI smoke", [sys.executable, str(ROOT / "tools" / "smoke_admin_popups.py")])
    run_step("Export smoke", [sys.executable, str(ROOT / "tools" / "smoke_exports.py")])
    run_step("Update smoke", [sys.executable, str(ROOT / "tools" / "smoke_update.py")])
    run_step("Login UI smoke", [sys.executable, str(ROOT / "tools" / "smoke_login.py")])
    run_step("Offline login smoke", [sys.executable, str(ROOT / "tools" / "smoke_offline_login.py")])
    run_step("Remembered logout smoke", [sys.executable, str(ROOT / "tools" / "smoke_remember_logout.py")])
    run_step("Admin panel logout smoke", [sys.executable, str(ROOT / "tools" / "smoke_admin_panel_logout.py")])
    run_step("Login responsiveness smoke", [sys.executable, str(ROOT / "tools" / "smoke_login_responsive.py")])
    run_step("API HTTP smoke", [sys.executable, str(ROOT / "tools" / "smoke_api.py")])

    print("\nAll smoke tests passed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
