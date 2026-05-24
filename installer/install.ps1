param(
    [string]$InstallDir = "$env:LOCALAPPDATA\Programs\ALP Ziraat Hayvan Takip"
)

$ErrorActionPreference = "Stop"
$appName = "ALP Ziraat Hayvan Takip"
$exeName = "ALP_Ziraat_Hayvan_Takip.exe"
$iconName = "alp_ziraat_logo_led.ico"
$sourceExe = Join-Path $PSScriptRoot $exeName
$sourceIcon = Join-Path $PSScriptRoot $iconName

if (!(Test-Path $sourceExe)) {
    throw "Kurulum dosyasi bulunamadi: $sourceExe"
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item -Path $sourceExe -Destination (Join-Path $InstallDir $exeName) -Force
if (Test-Path $sourceIcon) {
    Copy-Item -Path $sourceIcon -Destination (Join-Path $InstallDir $iconName) -Force
}

$uninstallSource = Join-Path $PSScriptRoot "uninstall.ps1"
if (Test-Path $uninstallSource) {
    Copy-Item -Path $uninstallSource -Destination (Join-Path $InstallDir "uninstall.ps1") -Force
}

$shell = New-Object -ComObject WScript.Shell
$exePath = Join-Path $InstallDir $exeName
$iconPath = Join-Path $InstallDir $iconName
$shortcutIcon = if (Test-Path $iconPath) { "$iconPath,0" } else { "$exePath,0" }
$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "$appName.lnk"
$shortcut = $shell.CreateShortcut($desktopShortcut)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = $InstallDir
$shortcut.IconLocation = $shortcutIcon
$shortcut.Description = "ALP Ziraat Suru Takip Sistemi"
$shortcut.Save()

$startDir = Join-Path ([Environment]::GetFolderPath("Programs")) "ALP Ziraat"
New-Item -ItemType Directory -Force -Path $startDir | Out-Null
$startShortcut = Join-Path $startDir "$appName.lnk"
$shortcut = $shell.CreateShortcut($startShortcut)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = $InstallDir
$shortcut.IconLocation = $shortcutIcon
$shortcut.Description = "ALP Ziraat Suru Takip Sistemi"
$shortcut.Save()

$uninstallShortcut = Join-Path $startDir "ALP Ziraat Kaldir.lnk"
$shortcut = $shell.CreateShortcut($uninstallShortcut)
$shortcut.TargetPath = "powershell.exe"
$shortcut.Arguments = "-ExecutionPolicy Bypass -File `"$InstallDir\uninstall.ps1`""
$shortcut.WorkingDirectory = $InstallDir
$shortcut.Save()

Write-Host "$appName kuruldu: $InstallDir"
