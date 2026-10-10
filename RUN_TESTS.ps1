$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$Py = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (!(Test-Path $Py)) { Write-Error 'Run INSTALL.ps1 first'; exit 1 }
& $Py -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { exit 1 }
