import ctypes
import os
import shutil
import subprocess
import sys
from pathlib import Path


APP_NAME = "ALP Ziraat Hayvan Takip"
APP_EXE = "ALP_Ziraat_Hayvan_Takip.exe"
INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs" / APP_NAME


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def ps_quote(value: Path | str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def show_message(title: str, message: str, error: bool = False) -> None:
    flags = 0x10 if error else 0x40
    ctypes.windll.user32.MessageBoxW(None, message, title, flags)


def create_shortcuts() -> None:
    exe_path = INSTALL_DIR / APP_EXE
    uninstall_path = INSTALL_DIR / "uninstall.ps1"
    script = f"""
$appName = {ps_quote(APP_NAME)}
$installDir = {ps_quote(INSTALL_DIR)}
$exePath = {ps_quote(exe_path)}
$uninstallPath = {ps_quote(uninstall_path)}
$shell = New-Object -ComObject WScript.Shell
$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "$appName.lnk"
$shortcut = $shell.CreateShortcut($desktopShortcut)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = $installDir
$shortcut.IconLocation = $exePath
$shortcut.Save()
$startDir = Join-Path ([Environment]::GetFolderPath("Programs")) "ALP Ziraat"
New-Item -ItemType Directory -Force -Path $startDir | Out-Null
$startShortcut = Join-Path $startDir "$appName.lnk"
$shortcut = $shell.CreateShortcut($startShortcut)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = $installDir
$shortcut.IconLocation = $exePath
$shortcut.Save()
$uninstallShortcut = Join-Path $startDir "ALP Ziraat Kaldir.lnk"
$shortcut = $shell.CreateShortcut($uninstallShortcut)
$shortcut.TargetPath = "powershell.exe"
$shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$uninstallPath`""
$shortcut.WorkingDirectory = $installDir
$shortcut.Save()
"""
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def install() -> None:
    source_exe = resource_path(APP_EXE)
    uninstall_script = resource_path("uninstall.ps1")
    uninstall_bat = resource_path("Kaldir.bat")

    if not source_exe.exists():
        raise FileNotFoundError(f"Kurulum paketi eksik: {source_exe}")

    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_exe, INSTALL_DIR / APP_EXE)

    if uninstall_script.exists():
        shutil.copy2(uninstall_script, INSTALL_DIR / "uninstall.ps1")
    if uninstall_bat.exists():
        shutil.copy2(uninstall_bat, INSTALL_DIR / "Kaldir.bat")

    create_shortcuts()


def main() -> int:
    try:
        install()
    except Exception as exc:
        show_message(APP_NAME, f"Kurulum tamamlanamadi:\n{exc}", error=True)
        return 1

    show_message(APP_NAME, f"Kurulum tamamlandi:\n{INSTALL_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
