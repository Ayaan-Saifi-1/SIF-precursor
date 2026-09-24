$ErrorActionPreference='Stop'
$ascRoot=Split-Path -Parent $PSScriptRoot
$ascPython=Join-Path $ascRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $ascPython)) {
  $ascPython='python.exe'
}
$env:ASCENSION_DEVELOPMENT_MODEL='1'
$env:DEMO_MODE='1'
$env:DJANGO_SECRET_KEY='local-demo-only-not-for-deployment'
$ascLogs=Join-Path $ascRoot '.logs'
New-Item -ItemType Directory -Path $ascLogs -Force | Out-Null
$ascApi=Get-NetTCPConnection -LocalPort 9000 -State Listen -ErrorAction SilentlyContinue
if (-not $ascApi) {
  $ascBackend=Start-Process -FilePath $ascPython -ArgumentList @('backend/manage.py','runserver','127.0.0.1:9000','--noreload') -WorkingDirectory $ascRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $ascLogs 'api.log') -RedirectStandardError (Join-Path $ascLogs 'api.error.log')
  Write-Output "Started local API (process $($ascBackend.Id))."
}
$ascWeb=Get-NetTCPConnection -LocalPort 5785 -State Listen -ErrorAction SilentlyContinue
if (-not $ascWeb) {
  $ascFrontend=Start-Process -FilePath 'cmd.exe' -ArgumentList @('/c','npm run dev') -WorkingDirectory (Join-Path $ascRoot 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $ascLogs 'web.log') -RedirectStandardError (Join-Path $ascLogs 'web.error.log')
  Write-Output "Started local frontend (process $($ascFrontend.Id))."
}
Write-Output 'ASCENSION local preview: http://localhost:5785'
