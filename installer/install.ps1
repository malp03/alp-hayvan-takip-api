param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA ("Programs\Alp Ziraat S{0}r{0} Takip" -f [char]0x00FC))
)

$ErrorActionPreference = "Stop"
$u = [char]0x00FC
$appName = "Alp Ziraat S${u}r${u} Takip"
$legacyAppNames = @("ALP Ziraat Hayvan Takip")
$legacyInstallDirs = @("$env:LOCALAPPDATA\Programs\ALP Ziraat Hayvan Takip")
$exeName = "ALP_Ziraat_Suru_Takip.exe"
$iconName = "alp_ziraat_pdf_dark.ico"
$sourceExe = Join-Path $PSScriptRoot $exeName
$sourceIcon = Join-Path $PSScriptRoot $iconName

if (!(Test-Path $sourceExe)) {
    throw "Kurulum dosyasi bulunamadi: $sourceExe"
}

$startDir = Join-Path ([Environment]::GetFolderPath("Programs")) "ALP Ziraat"
foreach ($oldName in $legacyAppNames) {
    Remove-Item -LiteralPath (Join-Path ([Environment]::GetFolderPath("Desktop")) "$oldName.lnk") -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $startDir "$oldName.lnk") -Force -ErrorAction SilentlyContinue
}
foreach ($oldDir in $legacyInstallDirs) {
    if ($oldDir -and (Test-Path $oldDir) -and ($oldDir -ne $InstallDir)) {
        Remove-Item -LiteralPath $oldDir -Recurse -Force -ErrorAction SilentlyContinue
    }
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
$shortcut.Description = "Alp Ziraat S${u}r${u} Takip Sistemi"
$shortcut.Save()

New-Item -ItemType Directory -Force -Path $startDir | Out-Null
$startShortcut = Join-Path $startDir "$appName.lnk"
$shortcut = $shell.CreateShortcut($startShortcut)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = $InstallDir
$shortcut.IconLocation = $shortcutIcon
$shortcut.Description = "Alp Ziraat S${u}r${u} Takip Sistemi"
$shortcut.Save()

$uninstallShortcut = Join-Path $startDir "ALP Ziraat Kaldir.lnk"
$shortcut = $shell.CreateShortcut($uninstallShortcut)
$shortcut.TargetPath = "powershell.exe"
$shortcut.Arguments = "-ExecutionPolicy Bypass -File `"$InstallDir\uninstall.ps1`""
$shortcut.WorkingDirectory = $InstallDir
$shortcut.Save()

Write-Host "$appName kuruldu: $InstallDir"
