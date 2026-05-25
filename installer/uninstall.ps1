param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA ("Programs\Alp Ziraat S{0}r{0} Takip" -f [char]0x00FC))
)

$ErrorActionPreference = "Stop"
$u = [char]0x00FC
$appName = "Alp Ziraat S${u}r${u} Takip"
$legacyAppNames = @("ALP Ziraat Hayvan Takip")
$legacyInstallDirs = @("$env:LOCALAPPDATA\Programs\ALP Ziraat Hayvan Takip")
$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "$appName.lnk"
$startDir = Join-Path ([Environment]::GetFolderPath("Programs")) "ALP Ziraat"

Remove-Item -LiteralPath $desktopShortcut -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $startDir "$appName.lnk") -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $startDir "ALP Ziraat Kaldir.lnk") -Force -ErrorAction SilentlyContinue
foreach ($oldName in $legacyAppNames) {
    Remove-Item -LiteralPath (Join-Path ([Environment]::GetFolderPath("Desktop")) "$oldName.lnk") -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $startDir "$oldName.lnk") -Force -ErrorAction SilentlyContinue
}

if (Test-Path $startDir) {
    $remaining = Get-ChildItem -LiteralPath $startDir -Force -ErrorAction SilentlyContinue
    if (!$remaining) {
        Remove-Item -LiteralPath $startDir -Force -ErrorAction SilentlyContinue
    }
}

Remove-Item -LiteralPath $InstallDir -Recurse -Force -ErrorAction SilentlyContinue
foreach ($oldDir in $legacyInstallDirs) {
    Remove-Item -LiteralPath $oldDir -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Host "$appName kaldirildi."
