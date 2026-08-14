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
    npm exec tauri build -- --no-bundle --target $Target
    Assert-NativeSuccess "Tauri build"
} finally {
    Pop-Location
}

$ReleaseDir = Join-Path $TauriDir "target\$Target\release"
$AppExe = Join-Path $ReleaseDir "mnema.exe"
foreach ($Path in @($AppExe, (Join-Path $ReleaseDir "mnema-backend.exe"), (Join-Path $ReleaseDir "ffmpeg.exe"), (Join-Path $ReleaseDir "ffprobe.exe"))) {
    if (-not (Test-Path $Path)) { throw "Tauri output is missing: $Path" }
}

$Manifest = [ordered]@{
    target = $Target
    python = (& $Python --version 2>&1 | Out-String).Trim()
    ffmpeg_source = $FfmpegUrl
    ffmpeg_archive_sha256 = $FfmpegSha256
    python_packages = @(& $Python -m pip freeze)
    artifacts = @{}
}
foreach ($Path in @("mnema-backend.exe", "ffmpeg.exe", "ffprobe.exe", "mnema.exe")) {
    $ArtifactPath = Join-Path $ReleaseDir $Path
    $Manifest.artifacts[$Path] = [ordered]@{
        size = (Get-Item $ArtifactPath).Length
        sha256 = Get-Sha256 $ArtifactPath
    }
}
$ManifestPath = Join-Path $BuildDir "runtime-manifest.json"
$Manifest | ConvertTo-Json -Depth 6 | Set-Content $ManifestPath -Encoding UTF8

if ($Smoke) {
    $SmokeRoot = Join-Path $env:TEMP "Mnema smoke Юникод"
    $FinalDir = Join-Path $SmokeRoot "Markdown с пробелом"
    New-Item -ItemType Directory -Force -Path $FinalDir | Out-Null
    Add-Type -AssemblyName System.Speech
    $MediaPath = Join-Path $SmokeRoot "речь с пробелом.wav"
    $Voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $Voice.SetOutputToWaveFile($MediaPath)
    $Voice.Speak("Mnema Windows transcription smoke test")
    $Voice.Dispose()

    $App = Start-Process $AppExe -PassThru
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
        $Health = Invoke-RestMethod "$BaseUrl/health"
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

        $JobBody = @{
            input_path = $MediaPath
            display_title = "Windows smoke Юникод"
            asr_model_name = "tiny"
            final_markdown_dir = $FinalDir
        } | ConvertTo-Json
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
    } finally {
        Stop-Process -Id $App.Id -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "Windows x64 runtime ready. Manifest: $ManifestPath"
