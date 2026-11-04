$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$state = Join-Path $root ".osh-central"
$logs = Join-Path $state "logs"
$envFile = Join-Path $root ".env.central"
$python = if ($env:OSH_AGRI_PYTHON) { $env:OSH_AGRI_PYTHON } else { (Get-Command python -ErrorAction Stop).Source }
$psql = "E:\Claude\postgresql-17.11-5-windows-x64-binaries\pgsql\bin\psql.exe"

New-Item -ItemType Directory -Force -Path $state, $logs | Out-Null

if (-not (Test-Path -LiteralPath $envFile)) {
    $bytes = New-Object byte[] 48
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $rng.Dispose()
    $jwt = [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+","-").Replace("/","_")
    $lines = @(
        "APP_ENV=production"
        "APP_NAME=OSH Agriculture AI Global"
        "DATABASE_URL=postgresql+psycopg://osh_global_app@127.0.0.1:5433/osh_agriculture_global"
        "ENABLE_POSTGIS=false"
        "JWT_SECRET=$jwt"
        "JWT_EXPIRE_MINUTES=10080"
        "CORS_ORIGINS=*"
        "MAX_UPLOAD_MB=25"
        "WORKER_POLL_SECONDS=3"
    )
    [System.IO.File]::WriteAllLines($envFile, $lines, [System.Text.UTF8Encoding]::new($false))
    Write-Host "Created .env.central with a new JWT secret."
}

# Load only this server's private environment file. Do not print values.
Get-Content -LiteralPath $envFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $parts = $line.Split("=", 2)
        [Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1], "Process")
    }
}

if ($env:APP_ENV -ne "production") { throw "APP_ENV must be production." }
if (-not $env:DATABASE_URL.StartsWith("postgresql+psycopg://")) { throw "Central server requires PostgreSQL + psycopg." }
if ($env:DATABASE_URL -match "://[^/@:]+:[^@]+@") { throw "Do not store PostgreSQL passwords in .env.central. Use pgpass.conf." }
if ([string]::IsNullOrWhiteSpace($env:JWT_SECRET) -or $env:JWT_SECRET.Length -lt 32) { throw "JWT_SECRET must be at least 32 characters." }

if (-not (Test-Path -LiteralPath $python)) { throw "Python not found: $python" }
if (-not (Test-Path -LiteralPath $psql)) { throw "PostgreSQL 17 psql.exe not found: $psql" }

$env:PYTHONPATH = Join-Path $root "backend"
$env:PYTHONUNBUFFERED = "1"

Write-Host "Checking central PostgreSQL connection..."
& $psql -X -h 127.0.0.1 -p 5433 -U osh_global_app -d osh_agriculture_global -w -v ON_ERROR_STOP=1 -c "SELECT current_database(), current_user, inet_server_port();"
if ($LASTEXITCODE -ne 0) { throw "PostgreSQL connection failed. Check the osh_global_app entry in pgpass.conf." }

function Test-ProcessPidFile($path, $needle) {
    if (-not (Test-Path -LiteralPath $path)) { return $false }
    try {
        $data = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $($data.pid)" -ErrorAction Stop
        return ($null -ne $proc -and $proc.CommandLine -like "*$needle*")
    } catch { return $false }
}

$webPidFile = Join-Path $state "web.pid"
$workerPidFile = Join-Path $state "worker.pid"
if (Test-ProcessPidFile $webPidFile "uvicorn app.main:app") {
    Write-Host "Web server is already running."
    if (-not (Test-ProcessPidFile $workerPidFile "app.worker")) {
        $worker = Start-Process -FilePath $python -ArgumentList @("-m","app.worker") -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logs "worker.out.log") -RedirectStandardError (Join-Path $logs "worker.err.log")
        @{ pid = $worker.Id; command = "app.worker" } | ConvertTo-Json | Set-Content -LiteralPath $workerPidFile -Encoding ascii
        Write-Host "Worker started. PID $($worker.Id)"
    }
    exit 0
}

# Stop only stale state files. Never kill an unverified PID.
if (Test-Path $webPidFile) { Remove-Item -LiteralPath $webPidFile -Force }
if (Test-Path $workerPidFile) {
    if (Test-ProcessPidFile $workerPidFile "app.worker") { throw "Worker is already running; use stop-central.ps1 first." }
    Remove-Item -LiteralPath $workerPidFile -Force
}

Write-Host "Installing/updating Python requirements..."
& $python -m pip install -r (Join-Path $root "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "pip install failed." }

Write-Host "Initializing central PostgreSQL schema..."
& $python -m app.init_db
if ($LASTEXITCODE -ne 0) { throw "Database initialization failed." }

$worker = Start-Process -FilePath $python -ArgumentList @("-m","app.worker") -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logs "worker.out.log") -RedirectStandardError (Join-Path $logs "worker.err.log")
@{ pid = $worker.Id; command = "app.worker" } | ConvertTo-Json | Set-Content -LiteralPath $workerPidFile -Encoding ascii

$web = Start-Process -FilePath $python -ArgumentList @("-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8080") -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logs "web.out.log") -RedirectStandardError (Join-Path $logs "web.err.log")
@{ pid = $web.Id; command = "uvicorn app.main:app" } | ConvertTo-Json | Set-Content -LiteralPath $webPidFile -Encoding ascii

$healthy = $false
for ($i = 0; $i -lt 45; $i++) {
    try {
        $h = Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/v1/health" -TimeoutSec 2
        if ($h.ok -and $h.database -eq "connected") { $healthy = $true; break }
    } catch {}
    Start-Sleep -Seconds 2
}
if (-not $healthy) {
    Write-Host "Web did not become healthy. Logs:"
    Get-Content (Join-Path $logs "web.err.log") -Tail 60 -ErrorAction SilentlyContinue
    throw "Central web server did not start. See .osh-central\logs."
}

Write-Host ""
Write-Host "OSH Agriculture AI Global CENTRAL SERVER is running."
Write-Host "Local health: http://127.0.0.1:8080/api/v1/health"
Write-Host "Web PID: $($web.Id) | Worker PID: $($worker.Id)"
Write-Host "PostgreSQL database: osh_agriculture_global (port 5433)"
Write-Host "PostgreSQL is not exposed publicly."
Write-Host "Logs: $logs"
