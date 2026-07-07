# Run AI chat + proximity auto-facing together.
param(
    [switch]$NoFacing,
    [switch]$FacingOnce,
    [switch]$SaveDebug,
    [switch]$InvertLook,
    [string]$TargetingArgs = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$argsList = @("run_all.py")
if ($NoFacing) { $argsList += "--no-facing" }
if ($FacingOnce) { $argsList += "--facing-once" }
if ($SaveDebug) { $argsList += "--save-debug" }
if ($InvertLook) { $argsList += "--invert-look" }
if ($TargetingArgs) { $argsList += @("--targeting-args", $TargetingArgs) }

.\.venv\Scripts\python.exe @argsList
