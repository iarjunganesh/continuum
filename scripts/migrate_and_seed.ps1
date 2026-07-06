# Continuum DB setup (Windows) — equivalent of `make migrate` + `make seed-data`.
# Applies infra/schema.sql, then generates and loads synthetic incidents
# (with Bedrock embeddings) into $env:COCKROACH_DATABASE_URL.
#
# Usage:
#   .\scripts\migrate_and_seed.ps1                # migrate + seed (40 incidents, Bedrock)
#   .\scripts\migrate_and_seed.ps1 -SkipSeed       # migrate only (no AWS creds needed)
#   .\scripts\migrate_and_seed.ps1 -Offline        # migrate + seed with deterministic
#                                                  #   vectors — no Bedrock/AWS creds needed
#   .\scripts\migrate_and_seed.ps1 -Count 100      # migrate + seed with 100 incidents
param(
    [switch]$SkipSeed,
    [switch]$Offline,
    [int]$Count = 40
)
$ErrorActionPreference = "Stop"

# $ErrorActionPreference only governs PowerShell cmdlets/terminating errors —
# it does NOT stop the script when an external command (python.exe) exits
# non-zero, so every python call below is followed by an explicit
# $LASTEXITCODE check. Without this, a failed step (e.g. a bad DB URL) would
# print a traceback and the script would carry on regardless.
function Assert-LastExitCode([string]$step) {
    if ($LASTEXITCODE -ne 0) {
        Write-Host "$step failed (exit code $LASTEXITCODE) — stopping." -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

if (-not $env:COCKROACH_DATABASE_URL) {
    Write-Host "COCKROACH_DATABASE_URL is not set in this session." -ForegroundColor Red
    Write-Host 'Set it first: $env:COCKROACH_DATABASE_URL = "postgresql://..."' -ForegroundColor Yellow
    exit 1
}

Write-Host "[1/3] Applying infra/schema.sql..." -ForegroundColor Cyan
python -c "import psycopg, os; conn = psycopg.connect(os.environ['COCKROACH_DATABASE_URL']); cur = conn.cursor(); cur.execute(open('infra/schema.sql').read()); conn.commit(); print('schema applied')"
Assert-LastExitCode "Schema migration"

if ($SkipSeed) {
    Write-Host "Skipping seed step (-SkipSeed). Schema is applied; tables exist but are empty." -ForegroundColor Yellow
    exit 0
}

if (-not $Offline -and (-not $env:AWS_ACCESS_KEY_ID -or -not $env:AWS_SECRET_ACCESS_KEY)) {
    Write-Host "AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY not set — seeding needs Bedrock for embeddings." -ForegroundColor Red
    Write-Host "Set both, re-run with -Offline for deterministic vectors (no AWS), or -SkipSeed to leave tables empty." -ForegroundColor Yellow
    exit 1
}

Write-Host "[2/3] Generating $Count synthetic incidents..." -ForegroundColor Cyan
python scripts/generate_synthetic_incidents.py --out data/synthetic/incidents_seed.jsonl --count $Count
Assert-LastExitCode "Synthetic incident generation"

if ($Offline) {
    Write-Host "[3/3] Seeding CockroachDB (incidents + remediation_steps + deterministic vectors, no Bedrock)..." -ForegroundColor Cyan
    python scripts/seed_memory.py --file data/synthetic/incidents_seed.jsonl --no-embeddings
} else {
    Write-Host "[3/3] Seeding CockroachDB (incidents + remediation_steps + Bedrock embeddings)..." -ForegroundColor Cyan
    python scripts/seed_memory.py --file data/synthetic/incidents_seed.jsonl
}
Assert-LastExitCode "Seeding"

Write-Host "Done. Refresh the console / Space to see the seeded incidents." -ForegroundColor Green
