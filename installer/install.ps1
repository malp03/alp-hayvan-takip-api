param(
    [string]$InstallDir = "$env:LOCALAPPDATA\Programs\ALP Ziraat Hayvan Takip"
)

$ErrorActionPreference = "Stop"
$appName = "ALP Ziraat Hayvan Takip"
$exeName = "ALP_Ziraat_Hayvan_Takip.exe"
$sourceExe = Join-Path $PSScriptRoot $exeName

if (!(Test-Path $sourceExe)) {
    throw "Kurulum dosyasi bulunamadi: $sourceExe"
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item -Path $sourceExe -Destination (Join-Path $InstallDir $exeName) -Force

$uninstallSource = Join-Path $PSScriptRoot "uninstall.ps1"
if (Test-Path $uninstallSource) {
    Copy-Item -Path $uninstallSource -Destination (Join-Path $InstallDir "uninstall.ps1") -Force
}

$shell = New-Object -ComObject WScript.Shell
$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "$appName.lnk"
$shortcut = $shell.CreateShortcut($desktopShortcut)
$shortcut.TargetPath = Join-Path $InstallDir $exeName
$shortcut.WorkingDirectory = $InstallDir
$shortcut.IconLocation = Join-Path $InstallDir $exeName
$shortcut.Save()

$startDir = Join-Path ([Environment]::GetFolderPath("Programs")) "ALP Ziraat"
New-Item -ItemType Directory -Force -Path $startDir | Out-Null
$startShortcut = Join-Path $startDir "$appName.lnk"
$shortcut = $shell.CreateShortcut($startShortcut)
$shortcut.TargetPath = Join-Path $InstallDir $exeName
$shortcut.WorkingDirectory = $InstallDir
$shortcut.IconLocation = Join-Path $InstallDir $exeName
$shortcut.Save()

$uninstallShortcut = Join-Path $startDir "ALP Ziraat Kaldir.lnk"
$shortcut = $shell.CreateShortcut($uninstallShortcut)
$shortcut.TargetPath = "powershell.exe"
$shortcut.Arguments = "-ExecutionPolicy Bypass -File `"$InstallDir\uninstall.ps1`""
$shortcut.WorkingDirectory = $InstallDir
$shortcut.Save()

Write-Host "$appName kuruldu: $InstallDir"
