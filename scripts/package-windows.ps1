param(
    [switch]$Smoke
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$TauriDir = Join-Path $Root "frontend\src-tauri"
$BinaryDir = Join-Path $TauriDir "binaries"
$BuildDir = Join-Path $Root ".build\windows-x64"
$VenvDir = Join-Path $BuildDir "venv"
$Python = Join-Path $VenvDir "Scripts\python.exe"
$Target = "x86_64-pc-windows-msvc"
$FfmpegArchive = "ffmpeg-N-126122-gca821e458a-win64-gpl.zip"
$FfmpegUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-08-13-17-03/$FfmpegArchive"
$FfmpegSha256 = "94136beb3ddec448ae2c56e3176897dc28f5e81c0c93ae529fa5db9ac75ba7fb"

function Begin-NativeCommand {
    $script:ErrorActionPreference = "Continue"
}

function Assert-NativeSuccess([string]$Step) {
    $ExitCode = $LASTEXITCODE
    $script:ErrorActionPreference = "Stop"
    if ($ExitCode -ne 0) { throw "$Step failed with exit code $ExitCode." }
}

function Get-Sha256([string]$Path) {
    $Stream = [IO.File]::OpenRead($Path)
    try {
        $Sha256 = [Security.Cryptography.SHA256]::Create()
        try { return -join ($Sha256.ComputeHash($Stream) | ForEach-Object { $_.ToString("x2") }) }
        finally { $Sha256.Dispose() }
    } finally { $Stream.Dispose() }
}

if (-not [Environment]::Is64BitOperatingSystem -or $env:OS -ne "Windows_NT") {
    throw "Run this script natively on Windows 11 x64."
}
if (-not $env:TAURI_SIGNING_PRIVATE_KEY) {
    throw "TAURI_SIGNING_PRIVATE_KEY is required to build the signed Windows updater artifact."
}

New-Item -ItemType Directory -Force -Path $BuildDir, $BinaryDir | Out-Null
Copy-Item (Join-Path $Root "configs\default.yaml") (Join-Path $TauriDir "resources\configs\default.yaml") -Force

if (-not (Test-Path $Python)) {
    Begin-NativeCommand
    & py -3.11 -m venv $VenvDir
    Assert-NativeSuccess "Python venv creation"
}
Begin-NativeCommand
& $Python -m pip install --upgrade pip wheel
Assert-NativeSuccess "pip bootstrap"
Begin-NativeCommand
& $Python -m pip install $Root "pyinstaller==6.16.0" "setuptools==70.3.0"
Assert-NativeSuccess "runtime dependency install"
Begin-NativeCommand
& $Python -m pip uninstall -y typing
Assert-NativeSuccess "obsolete typing backport removal"

$BackendDist = Join-Path $BuildDir "backend-dist"
Begin-NativeCommand
& $Python -m PyInstaller --clean --noconfirm --onefile --noupx `
    --name mnema-backend `
    --distpath $BackendDist `
    --workpath (Join-Path $BuildDir "pyinstaller") `
    --specpath $BuildDir `
    --collect-all whisper `
    --collect-all onnx_asr `
    --collect-all librosa `
    --collect-all resemblyzer `
    --collect-all sklearn `
    (Join-Path $Root "src\mnema\cli\main.py")
Assert-NativeSuccess "PyInstaller backend build"

$ArchivePath = Join-Path $BuildDir $FfmpegArchive
if (-not (Test-Path $ArchivePath) -or (Get-Sha256 $ArchivePath) -ne $FfmpegSha256) {
    Invoke-WebRequest -Uri $FfmpegUrl -OutFile $ArchivePath
}
$ActualHash = Get-Sha256 $ArchivePath
if ($ActualHash -ne $FfmpegSha256) {
    throw "FFmpeg archive checksum mismatch: $ActualHash"
}

$FfmpegDir = Join-Path $BuildDir "ffmpeg"
Remove-Item $FfmpegDir -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive $ArchivePath $FfmpegDir

$Artifacts = @{
    "mnema-backend" = Join-Path $BackendDist "mnema-backend.exe"
    "ffmpeg" = (Get-ChildItem $FfmpegDir -Filter "ffmpeg.exe" -Recurse | Select-Object -First 1).FullName
    "ffprobe" = (Get-ChildItem $FfmpegDir -Filter "ffprobe.exe" -Recurse | Select-Object -First 1).FullName
}
foreach ($Name in $Artifacts.Keys) {
    $Destination = Join-Path $BinaryDir "$Name-$Target.exe"
    Copy-Item $Artifacts[$Name] $Destination -Force
    if (-not (Test-Path $Destination)) { throw "Missing generated sidecar: $Destination" }
}

Begin-NativeCommand
& (Join-Path $BinaryDir "mnema-backend-$Target.exe") --help | Out-Null
Assert-NativeSuccess "backend self-check"
Begin-NativeCommand
& (Join-Path $BinaryDir "ffmpeg-$Target.exe") -version | Out-Null
Assert-NativeSuccess "FFmpeg self-check"
Begin-NativeCommand
& (Join-Path $BinaryDir "ffprobe-$Target.exe") -version | Out-Null
Assert-NativeSuccess "FFprobe self-check"

Push-Location (Join-Path $Root "frontend")
try {
    Begin-NativeCommand
    npm ci --include=dev
    Assert-NativeSuccess "npm install"
    Begin-NativeCommand
    npm run build
    Assert-NativeSuccess "frontend build"
    Begin-NativeCommand
    npm exec tauri build -- --bundles nsis --target $Target
    Assert-NativeSuccess "Tauri NSIS build"
} finally {
    Pop-Location
}

$ReleaseDir = Join-Path $TauriDir "target\$Target\release"
$AppExe = Join-Path $ReleaseDir "mnema.exe"
$BundleDir = Join-Path $ReleaseDir "bundle\nsis"
$Installer = @(Get-ChildItem $BundleDir -Filter "*-setup.exe")
if ($Installer.Count -ne 1) { throw "Expected one NSIS installer, found $($Installer.Count)." }
$Installer = $Installer[0].FullName
$InstallerSignature = "$Installer.sig"
foreach ($Path in @($AppExe, (Join-Path $ReleaseDir "mnema-backend.exe"), (Join-Path $ReleaseDir "ffmpeg.exe"), (Join-Path $ReleaseDir "ffprobe.exe"))) {
    if (-not (Test-Path $Path)) { throw "Tauri output is missing: $Path" }
}
if (-not (Test-Path $InstallerSignature)) { throw "Missing signed updater artifact: $InstallerSignature" }

$Manifest = [ordered]@{
    target = $Target
    python = (& $Python --version 2>&1 | Out-String).Trim()
    ffmpeg_source = $FfmpegUrl
    ffmpeg_archive_sha256 = $FfmpegSha256
    python_packages = @(& $Python -m pip freeze)
    artifacts = @{}
}
foreach ($ArtifactPath in @(
    (Join-Path $ReleaseDir "mnema-backend.exe"),
    (Join-Path $ReleaseDir "ffmpeg.exe"),
    (Join-Path $ReleaseDir "ffprobe.exe"),
    $AppExe,
    $Installer,
    $InstallerSignature
)) {
    $Manifest.artifacts[(Split-Path $ArtifactPath -Leaf)] = [ordered]@{
        size = (Get-Item $ArtifactPath).Length
        sha256 = Get-Sha256 $ArtifactPath
    }
}
$ManifestPath = Join-Path $BuildDir "runtime-manifest.json"
$Manifest | ConvertTo-Json -Depth 6 | Set-Content $ManifestPath -Encoding UTF8

if ($Smoke) {
    $InstallDir = Join-Path $env:LOCALAPPDATA "Mnema"
    $InstalledApp = Join-Path $InstallDir "mnema.exe"
    $Uninstaller = Join-Path $InstallDir "uninstall.exe"
    if (Test-Path $InstallDir) { throw "Clean install smoke requires Mnema to be absent: $InstallDir" }
    $Install = Start-Process $Installer -ArgumentList "/S" -Wait -PassThru
    if ($Install.ExitCode -ne 0 -or -not (Test-Path $InstalledApp)) {
        throw "Silent clean install failed with exit code $($Install.ExitCode)."
    }
    $SmokeRoot = Join-Path $env:TEMP "Mnema smoke Юникод"
    $FinalDir = Join-Path $SmokeRoot "Markdown с пробелом"
    New-Item -ItemType Directory -Force -Path $FinalDir | Out-Null
    Add-Type -AssemblyName System.Speech
    $MediaPath = Join-Path $SmokeRoot "речь с пробелом.wav"
    $Voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $Voice.SetOutputToWaveFile($MediaPath)
    $Voice.Speak("Mnema Windows transcription smoke test")
    $Voice.Dispose()

    $App = Start-Process $InstalledApp -PassThru
    try {
        $Backend = $null
        for ($Attempt = 0; $Attempt -lt 120 -and -not $Backend; $Attempt++) {
            Start-Sleep -Milliseconds 500
            $Backend = Get-CimInstance Win32_Process -Filter "Name = 'mnema-backend.exe'" |
                Where-Object { $_.ParentProcessId -eq $App.Id } | Select-Object -First 1
        }
        if (-not $Backend -or $Backend.CommandLine -notmatch '--port\s+(\d+)') {
            throw "Bundled backend did not start."
        }
        $BaseUrl = "http://127.0.0.1:$($Matches[1])"
        if ($Backend.CommandLine -notmatch '--app-data-dir\s+(?:"([^"]+)"|(\S+))') {
            throw "Bundled backend did not receive an app data directory."
        }
        $AppDataDir = if ($Matches[1]) { $Matches[1] } else { $Matches[2] }
        $Health = $null
        for ($Attempt = 0; $Attempt -lt 60 -and -not $Health; $Attempt++) {
            try { $Health = Invoke-RestMethod "$BaseUrl/health" }
            catch { Start-Sleep -Milliseconds 500 }
        }
        if ($Health.status -ne "ok" -or -not $Health.media_tools.ffmpeg.available -or -not $Health.media_tools.ffprobe.available) {
            throw "Backend health did not report bundled media tools."
        }

        Invoke-RestMethod "$BaseUrl/models/download" -Method Post -ContentType "application/json" -Body '{"model_name":"tiny"}' | Out-Null
        for ($Attempt = 0; $Attempt -lt 600; $Attempt++) {
            $Model = (Invoke-RestMethod "$BaseUrl/models").models | Where-Object { $_.name -eq "tiny" }
            if ($Model.status -eq "ready") { break }
            if ($Model.status -eq "corrupt") { throw "Tiny model download failed." }
            Start-Sleep -Seconds 1
        }
        if ($Model.status -ne "ready") { throw "Tiny model download timed out." }

        $JobBody = [Text.Encoding]::UTF8.GetBytes((@{
            input_path = $MediaPath
            display_title = "Windows smoke Юникод"
            asr_model_name = "tiny"
            final_markdown_dir = $FinalDir
        } | ConvertTo-Json))
        $JobId = (Invoke-RestMethod "$BaseUrl/jobs" -Method Post -ContentType "application/json" -Body $JobBody).job.job_id
        for ($Attempt = 0; $Attempt -lt 600; $Attempt++) {
            $Job = (Invoke-RestMethod "$BaseUrl/jobs/$JobId").job
            if ($Job.status -in @("completed", "failed")) { break }
            Start-Sleep -Seconds 1
        }
        if ($Job.status -ne "completed") { throw "Transcription failed: $($Job.error)" }
        Invoke-RestMethod "$BaseUrl/jobs/$JobId/speaker-review" -Method Post -ContentType "application/json" -Body '{"assignments":{},"skipped":true}' | Out-Null
        if (-not (Test-Path (Join-Path $FinalDir "Windows smoke Юникод.md"))) {
            throw "Canonical Markdown was not saved."
        }
        if (-not (Test-Path (Join-Path $AppDataDir "output\$JobId\job.json"))) {
            throw "Canonical job was not saved in app data."
        }
        if (@(Get-ChildItem (Join-Path $AppDataDir "models") -File -Recurse).Count -eq 0) {
            throw "Downloaded model was not saved in app data."
        }
        $SettingsJson = @{ default_model_name = "tiny"; autosave_markdown_dir = $FinalDir } |
            ConvertTo-Json
        [IO.File]::WriteAllText(
            (Join-Path $AppDataDir "settings.json"),
            $SettingsJson,
            [Text.UTF8Encoding]::new($false)
        )
    } finally {
        Stop-Process -Id $App.Id -Force -ErrorAction SilentlyContinue
    }

    $Reinstall = Start-Process $Installer -ArgumentList "/S" -Wait -PassThru
    if ($Reinstall.ExitCode -ne 0) { throw "Silent reinstall failed with exit code $($Reinstall.ExitCode)." }
    $ReinstalledApp = Start-Process $InstalledApp -PassThru
    try {
        $ReinstalledBackend = $null
        for ($Attempt = 0; $Attempt -lt 120 -and -not $ReinstalledBackend; $Attempt++) {
            Start-Sleep -Milliseconds 500
            $ReinstalledBackend = Get-CimInstance Win32_Process -Filter "Name = 'mnema-backend.exe'" |
                Where-Object { $_.ParentProcessId -eq $ReinstalledApp.Id } | Select-Object -First 1
        }
        if (-not $ReinstalledBackend) { throw "Reinstalled app did not launch bundled backend." }
        foreach ($Path in @(
            (Join-Path $AppDataDir "output\$JobId\job.json"),
            (Join-Path $AppDataDir "settings.json"),
            (Join-Path $FinalDir "Windows smoke Юникод.md")
        )) {
            if (-not (Test-Path $Path)) { throw "Reinstall did not preserve user data: $Path" }
        }
    } finally {
        Stop-Process -Id $ReinstalledApp.Id -Force -ErrorAction SilentlyContinue
    }
    $Uninstall = Start-Process $Uninstaller -ArgumentList "/S" -Wait -PassThru
    if ($Uninstall.ExitCode -ne 0 -or (Test-Path $InstalledApp)) {
        throw "Silent uninstall failed with exit code $($Uninstall.ExitCode)."
    }
    foreach ($Path in @(
        (Join-Path $AppDataDir "output\$JobId\job.json"),
        (Join-Path $AppDataDir "settings.json"),
        (Join-Path $FinalDir "Windows smoke Юникод.md")
    )) {
        if (-not (Test-Path $Path)) { throw "Uninstall removed user data: $Path" }
    }
}

Write-Host "Windows x64 runtime ready. Manifest: $ManifestPath"
