$ErrorActionPreference = "Stop"

$serviceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Resolve-Path (Join-Path $serviceDir "..\..\..")).Path
$venvDir = Join-Path $projectRoot ".voice-venv"
$requirements = Join-Path $serviceDir "requirements.txt"

if (-not (Test-Path (Join-Path $venvDir "Scripts\python.exe"))) {
    py -3.11 -m venv $venvDir
}

$python = Join-Path $venvDir "Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install -r $requirements

$env:HF_HOME = Join-Path $projectRoot ".cache\huggingface"
& $python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8'); print('faster-whisper base model is ready')"

Write-Host "Setup complete. Start with:"
Write-Host "  & '$python' '$serviceDir\voice_choice_server.py'"
