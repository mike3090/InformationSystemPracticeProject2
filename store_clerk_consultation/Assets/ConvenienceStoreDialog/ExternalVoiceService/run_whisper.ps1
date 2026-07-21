$ErrorActionPreference = "Stop"

$serviceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Resolve-Path (Join-Path $serviceDir "..\..\..")).Path
$python = Join-Path $projectRoot ".voice-venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Whisper environment is missing. Run setup_whisper.ps1 first."
}

$env:HF_HOME = Join-Path $projectRoot ".cache\huggingface"
if (-not $env:STORE_CLERK_CAPTURE_MICROPHONE -and -not $env:VRCHAT_AI_CAPTURE_MICROPHONE) {
    $env:STORE_CLERK_CAPTURE_MICROPHONE = "MIXLINE Record"
}
& $python (Join-Path $serviceDir "voice_choice_server.py") @args
