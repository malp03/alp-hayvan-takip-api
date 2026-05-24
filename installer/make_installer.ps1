$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root "dist"
$packageDir = Join-Path $dist "installer_package"
$zipPath = Join-Path $dist "ALP_Ziraat_Hayvan_Takip_Kurulum.zip"
$exePath = Join-Path $dist "ALP_Ziraat_Hayvan_Takip_Setup.exe"
$appExe = Join-Path $dist "ALP_Ziraat_Hayvan_Takip.exe"
$appIcon = Join-Path $root "alp_ziraat_logo_led.ico"

if (!(Test-Path $appExe)) {
    throw "Once EXE uretin: python -m PyInstaller alp_ziraat_hayvan_takip.spec --noconfirm"
}
if (!(Test-Path $appIcon)) {
    throw "Kisayol ikonu bulunamadi: $appIcon"
}

if (Test-Path $packageDir) {
    Remove-Item -LiteralPath $packageDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $packageDir | Out-Null
Copy-Item -Path $appExe -Destination $packageDir -Force
Copy-Item -Path $appIcon -Destination $packageDir -Force
Copy-Item -Path (Join-Path $PSScriptRoot "install.ps1") -Destination $packageDir -Force
Copy-Item -Path (Join-Path $PSScriptRoot "uninstall.ps1") -Destination $packageDir -Force
Copy-Item -Path (Join-Path $PSScriptRoot "Kur.bat") -Destination $packageDir -Force
Copy-Item -Path (Join-Path $PSScriptRoot "Kaldir.bat") -Destination $packageDir -Force

if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $packageDir "*") -DestinationPath $zipPath -Force

$pyinstallerBuilt = $false
$python = Get-Command python.exe -ErrorAction SilentlyContinue
if ($python) {
    if (Test-Path $exePath) {
        Remove-Item -LiteralPath $exePath -Force
    }
    $setupScript = Join-Path $PSScriptRoot "setup_installer.py"
    $setupWork = Join-Path $root "build\setup_installer"
    $setupSpec = Join-Path $root "build\setup_spec"
    $uninstallScript = Join-Path $PSScriptRoot "uninstall.ps1"
    $uninstallBat = Join-Path $PSScriptRoot "Kaldir.bat"
    $installerIcon = $appIcon

    & $python.Source -m PyInstaller $setupScript `
        --onefile `
        --noconsole `
        --name "ALP_Ziraat_Hayvan_Takip_Setup" `
        --icon "$installerIcon" `
        --distpath $dist `
        --workpath $setupWork `
        --specpath $setupSpec `
        --add-data "$appExe;." `
        --add-data "$appIcon;." `
        --add-data "$uninstallScript;." `
        --add-data "$uninstallBat;." `
        --noconfirm
    if ($LASTEXITCODE -eq 0 -and (Test-Path $exePath)) {
        $pyinstallerBuilt = $true
    } else {
        Write-Warning "Kurulum EXE PyInstaller ile uretilemedi. ZIP paketi yine de hazir."
    }
}

Write-Host "Kurulum ZIP: $zipPath"
if (Test-Path $exePath) {
    Write-Host "Kurulum EXE: $exePath"
}
