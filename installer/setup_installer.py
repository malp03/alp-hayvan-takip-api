import ctypes
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


APP_NAME = "ALP Ziraat Hayvan Takip"
APP_EXE = "ALP_Ziraat_Hayvan_Takip.exe"
APP_ICON = "alp_ziraat_logo_led.ico"
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
    icon_path = INSTALL_DIR / APP_ICON
    uninstall_path = INSTALL_DIR / "uninstall.ps1"
    script = f"""
$appName = {ps_quote(APP_NAME)}
$installDir = {ps_quote(INSTALL_DIR)}
$exePath = {ps_quote(exe_path)}
$iconPath = {ps_quote(icon_path)}
$uninstallPath = {ps_quote(uninstall_path)}
$shortcutIcon = if (Test-Path $iconPath) {{ "$iconPath,0" }} else {{ "$exePath,0" }}
$shell = New-Object -ComObject WScript.Shell
$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "$appName.lnk"
$shortcut = $shell.CreateShortcut($desktopShortcut)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = $installDir
$shortcut.IconLocation = $shortcutIcon
$shortcut.Description = "ALP Ziraat Suru Takip Sistemi"
$shortcut.Save()
$startDir = Join-Path ([Environment]::GetFolderPath("Programs")) "ALP Ziraat"
New-Item -ItemType Directory -Force -Path $startDir | Out-Null
$startShortcut = Join-Path $startDir "$appName.lnk"
$shortcut = $shell.CreateShortcut($startShortcut)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = $installDir
$shortcut.IconLocation = $shortcutIcon
$shortcut.Description = "ALP Ziraat Suru Takip Sistemi"
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


def wait_for_process(pid: int, timeout: int = 45) -> None:
    if not pid:
        return
    try:
        handle = ctypes.windll.kernel32.OpenProcess(0x00100000, False, int(pid))
        if handle:
            ctypes.windll.kernel32.WaitForSingleObject(handle, timeout * 1000)
            ctypes.windll.kernel32.CloseHandle(handle)
            time.sleep(0.6)
    except Exception:
        time.sleep(1.5)


def install() -> None:
    source_exe = resource_path(APP_EXE)
    source_icon = resource_path(APP_ICON)
    uninstall_script = resource_path("uninstall.ps1")
    uninstall_bat = resource_path("Kaldir.bat")

    if not source_exe.exists():
        raise FileNotFoundError(f"Kurulum paketi eksik: {source_exe}")

    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_exe, INSTALL_DIR / APP_EXE)
    if source_icon.exists():
        shutil.copy2(source_icon, INSTALL_DIR / APP_ICON)

    if uninstall_script.exists():
        shutil.copy2(uninstall_script, INSTALL_DIR / "uninstall.ps1")
    if uninstall_bat.exists():
        shutil.copy2(uninstall_bat, INSTALL_DIR / "Kaldir.bat")

    create_shortcuts()


def parse_args(argv: list[str]) -> dict:
    args = {"launch": False, "wait_pid": 0}
    index = 0
    while index < len(argv):
        value = argv[index]
        if value == "--launch":
            args["launch"] = True
        elif value == "--wait-pid" and index + 1 < len(argv):
            try:
                args["wait_pid"] = int(argv[index + 1])
            except ValueError:
                args["wait_pid"] = 0
            index += 1
        index += 1
    return args


def launch_app() -> None:
    exe_path = INSTALL_DIR / APP_EXE
    if exe_path.exists():
        subprocess.Popen([str(exe_path)], cwd=str(INSTALL_DIR), close_fds=True)


def main() -> int:
    args = parse_args(sys.argv[1:])
    try:
        wait_for_process(args["wait_pid"])
        install()
    except Exception as exc:
        show_message(APP_NAME, f"Kurulum tamamlanamadi:\n{exc}", error=True)
        return 1

    show_message(APP_NAME, f"Kurulum tamamlandi:\n{INSTALL_DIR}")
    if args["launch"]:
        launch_app()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
