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

function Stop-RunningApp {
    try {
        & taskkill /IM $exeName /T /F 2>$null | Out-Null
        Start-Sleep -Milliseconds 800
    } catch {
    }
}

function Copy-WithRetry {
    param(
        [string]$Source,
        [string]$Destination,
        [int]$TimeoutSeconds = 90
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $tempDestination = "$Destination.new.$PID"
    $stoppedProcess = $false

    while ($true) {
        try {
            Copy-Item -LiteralPath $Source -Destination $tempDestination -Force
            Move-Item -LiteralPath $tempDestination -Destination $Destination -Force
            return
        } catch {
            Remove-Item -LiteralPath $tempDestination -Force -ErrorAction SilentlyContinue
            if ((Get-Date) -lt $deadline) {
                if (-not $stoppedProcess) {
                    Stop-RunningApp
                    $stoppedProcess = $true
                }
                Start-Sleep -Seconds 1
                continue
            }
            throw
        }
    }
}

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
Stop-RunningApp
Copy-WithRetry -Source $sourceExe -Destination (Join-Path $InstallDir $exeName)
if (Test-Path $sourceIcon) {
    Copy-WithRetry -Source $sourceIcon -Destination (Join-Path $InstallDir $iconName)
}

$uninstallSource = Join-Path $PSScriptRoot "uninstall.ps1"
if (Test-Path $uninstallSource) {
    Copy-WithRetry -Source $uninstallSource -Destination (Join-Path $InstallDir "uninstall.ps1")
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
