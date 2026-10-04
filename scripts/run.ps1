# Manual run helper:  .\scripts\run.ps1 --dry-run
$repoRoot = Split-Path -Parent $PSScriptRoot
& "$repoRoot\.venv\Scripts\python.exe" "$repoRoot\src\main.py" @args
