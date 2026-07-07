$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
$env:HF_HOME = Join-Path $ProjectRoot ".cache\huggingface"
$env:HUGGINGFACE_HUB_CACHE = Join-Path $env:HF_HOME "hub"
New-Item -ItemType Directory -Force -Path $env:HUGGINGFACE_HUB_CACHE | Out-Null

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e . --no-build-isolation

# Pre-download the default faster-whisper model so the first VRChat run is smoother.
.\.venv\Scripts\python.exe -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8'); print('faster-whisper base model is ready')"

Write-Host "Setup complete. Copy .env.example to .env and fill OPENAI_API_KEY."
