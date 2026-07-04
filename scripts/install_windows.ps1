# One-time setup on the Windows 11 mini PC. Run from an elevated PowerShell:
#   powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1 -Time "18:00"
param(
    [string]$Time = "18:00",
    [string]$TaskName = "NyxPromoter"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

# 1. Python virtual environment + dependencies
$python = Get-Command py -ErrorAction SilentlyContinue
if ($python) { py -3 -m venv .venv } else { python -m venv .venv }
& .\.venv\Scripts\pip.exe install --upgrade pip
& .\.venv\Scripts\pip.exe install -r requirements.txt

# 2. .env from template (never overwrites an existing one)
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host ""
    Write-Host ">>> Created .env — open it and fill in the API keys for your enabled platforms." -ForegroundColor Yellow
}

# 3. Daily scheduled task
$pythonExe = (Resolve-Path .\.venv\Scripts\python.exe).Path
$action = New-ScheduledTaskAction -Execute $pythonExe -Argument "src\main.py" -WorkingDirectory $repoRoot
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

Write-Host ""
Write-Host "Installed. '$TaskName' runs daily at $Time." -ForegroundColor Green
Write-Host "Test it now with:  .\.venv\Scripts\python.exe src\main.py --dry-run"
