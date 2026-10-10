param([switch]$Extras)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
Write-Host 'FaceStudio AI - quick setup (optional extras are skipped)' -ForegroundColor Cyan
$Py = $null
foreach ($v in @('3.12','3.11','3.13','3.14')) {
    try { & py "-$v" -c 'import sys; print(sys.version_info[:2])' *> $null; if ($LASTEXITCODE -eq 0) { $Py = $v; break } } catch {}
}
if (-not $Py) { Write-Host 'Install Python 3.12 x64 from python.org then retry.' -ForegroundColor Red; exit 1 }
if (!(Test-Path '.venv\Scripts\python.exe')) { & py "-$Py" -m venv .venv; if ($LASTEXITCODE -ne 0) { exit 1 } }
$VenvPy = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $VenvPy -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
Write-Host 'Checking core models (existing downloads will be reused)...' -ForegroundColor Cyan
& $VenvPy scripts\download_models.py --core
if ($LASTEXITCODE -ne 0) { Write-Host 'Core model download incomplete; local basic detection still works.' -ForegroundColor Yellow }
if ($Extras) {
    & $VenvPy scripts\download_models.py --extras
    if ($LASTEXITCODE -ne 0) { Write-Host 'Extras incomplete; retry later with DOWNLOAD_EXTRAS.ps1.' -ForegroundColor Yellow }
}
Write-Host 'Setup finished. Extras do NOT block startup. Launch with LAUNCH.bat.' -ForegroundColor Green
