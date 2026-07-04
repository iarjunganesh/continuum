# Continuum kill-and-recover demo (Windows).
# Same beat as `make chaos-demo`:
#   start API -> fire alert -> HARD-KILL the API mid-step-execution ->
#   restart API -> fire the same alert -> it resumes from CockroachDB.
$ErrorActionPreference = "Stop"

Write-Host "[1/6] Starting API..." -ForegroundColor Cyan
$api = Start-Process python -ArgumentList "-m","uvicorn","api.main:app","--port","8000" -PassThru -NoNewWindow
Start-Sleep 3

Write-Host "[2/6] Firing alert (step execution takes ~5s)..." -ForegroundColor Cyan
$tick = Start-Process python -ArgumentList "scripts/demo_run.py","--tick","--via-api" -PassThru -NoNewWindow
Start-Sleep 2

Write-Host "[3/6] CHAOS: killing the API mid-step (no graceful shutdown)..." -ForegroundColor Red
python scripts/chaos_kill.py --port 8000
try { $tick | Wait-Process -Timeout 5 } catch {}

Write-Host "[4/6] API is dead. The step it was executing is durably 'executing' in CockroachDB." -ForegroundColor Yellow
Start-Sleep 1

Write-Host "[5/6] Restarting API cold..." -ForegroundColor Cyan
$api2 = Start-Process python -ArgumentList "-m","uvicorn","api.main:app","--port","8000" -PassThru -NoNewWindow
Start-Sleep 3

Write-Host "[6/6] Firing the same alert -> watch it RESUME the interrupted step:" -ForegroundColor Green
python scripts/demo_run.py --tick --via-api --resume-check

python scripts/chaos_kill.py --port 8000
Write-Host "Done. Memory outlived the failure." -ForegroundColor Green
