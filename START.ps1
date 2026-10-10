$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$Py = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (!(Test-Path $Py)) {
    Write-Host 'Run INSTALL.ps1 first.' -ForegroundColor Red
    exit 1
}
& $Py -m faceflow.app

if ($LASTEXITCODE -ne 0) { throw "FaceStudio server exited with error code $LASTEXITCODE" }
