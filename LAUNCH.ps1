$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$Py = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $Py)) {
    Write-Host ''
    Write-Host 'First launch: setting up FaceStudio AI...' -ForegroundColor Cyan
    & (Join-Path $PSScriptRoot 'INSTALL.ps1')
    if (-not (Test-Path $Py)) {
        throw 'Setup did not finish. Install Python 3.12 then re-run LAUNCH.ps1.'
    }
}
Write-Host 'Opening FaceStudio AI. Close this window to stop the local server.' -ForegroundColor Green
& (Join-Path $PSScriptRoot 'START.ps1')
