param(
    [string]$InstallDir = "$env:LOCALAPPDATA\Programs\ALP Ziraat Hayvan Takip"
)

$ErrorActionPreference = "Stop"
$appName = "ALP Ziraat Hayvan Takip"
$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "$appName.lnk"
$startDir = Join-Path ([Environment]::GetFolderPath("Programs")) "ALP Ziraat"

Remove-Item -LiteralPath $desktopShortcut -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $startDir "$appName.lnk") -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $startDir "ALP Ziraat Kaldir.lnk") -Force -ErrorAction SilentlyContinue

if (Test-Path $startDir) {
    $remaining = Get-ChildItem -LiteralPath $startDir -Force -ErrorAction SilentlyContinue
    if (!$remaining) {
        Remove-Item -LiteralPath $startDir -Force -ErrorAction SilentlyContinue
    }
}

Remove-Item -LiteralPath $InstallDir -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "$appName kaldirildi."
