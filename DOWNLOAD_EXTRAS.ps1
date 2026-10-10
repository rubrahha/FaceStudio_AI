$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
$Py=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (!(Test-Path $Py)) { Write-Host 'Install FaceStudio once using LAUNCH.bat first.' -ForegroundColor Yellow; exit 1 }
Write-Host 'Optional AI models: about 90 MB total; resume is supported.' -ForegroundColor Cyan
Write-Host 'Press Ctrl+C at any time; cached partial files will be reused next time.' -ForegroundColor DarkGray
& $Py scripts\download_models.py --extras
if ($LASTEXITCODE -ne 0) { Write-Host 'One or more extras did not download; you can retry later.' -ForegroundColor Yellow }
Write-Host 'When finished, click Reload models in FaceStudio settings. No reinstall necessary.' -ForegroundColor Green
