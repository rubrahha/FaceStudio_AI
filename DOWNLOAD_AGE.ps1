$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $Python)) { throw 'Python environment not found. First run LAUNCH.bat in your existing project.' }
Push-Location $Root
try {
    & $Python scripts\download_models.py --age
    if ($LASTEXITCODE -ne 0) { throw 'Age model download failed or interrupted. Run this command again to retry / resume.' }
    Write-Host 'Age models downloaded. Open FaceStudio -> More options -> Reload models.' -ForegroundColor Green
} finally { Pop-Location }
