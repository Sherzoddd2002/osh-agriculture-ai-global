$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$centralHome = if ($env:OSH_AGRI_CENTRAL_HOME) { $env:OSH_AGRI_CENTRAL_HOME } else { Join-Path $env:LOCALAPPDATA "OSH\AgricultureAI-Central" }
$state = Join-Path $centralHome "state"
$logs = Join-Path $centralHome "logs"
$envFile = Join-Path $centralHome ".env.central"
$venv = Join-Path $centralHome ".venv"
$python = Join-Path $venv "Scripts\python.exe"
$psql = "E:\Claude\postgresql-17.11-5-windows-x64-binaries\pgsql\bin\psql.exe"

New-Item -ItemType Directory -Force -Path $centralHome, $state, $logs | Out-Null

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
    Write-Host "Private central config created at $envFile"
}

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

if (-not (Test-Path -LiteralPath $python)) {
    $basePython = $null
    $baseArgs = @()

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $probe = & $pythonCommand.Source --version 2>&1
        if ($LASTEXITCODE -eq 0 -and "$probe" -match "Python 3\.(12|1[3-9])") {
            $basePython = $pythonCommand.Source
        }
    }

    if (-not $basePython) {
        $pyCommand = Get-Command py -ErrorAction SilentlyContinue
        if ($pyCommand) {
            $probe = & $pyCommand.Source -3.12 --version 2>&1
            if ($LASTEXITCODE -eq 0 -and "$probe" -match "Python 3\.(12|1[3-9])") {
                $basePython = $pyCommand.Source
                $baseArgs = @("-3.12")
            }
        }
    }

    if (-not $basePython) { throw "Python 3.12+ topilmadi. Python 3.12 o‘rnating yoki OSH_AGRI_PYTHON ni belgilang." }
    & $basePython @baseArgs -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw "Central Python virtual environment could not be created." }
}
if (-not (Test-Path -LiteralPath $psql)) { throw "PostgreSQL 17 psql.exe not found: $psql" }

$env:PYTHONPATH = Join-Path $root "backend"
$env:PYTHONUNBUFFERED = "1"

Write-Host "Checking central PostgreSQL connection..."
& $psql -X -h 127.0.0.1 -p 5433 -U osh_global_app -d osh_agriculture_global -w -v ON_ERROR_STOP=1 -c "SELECT current_database(), current_user, inet_server_port();"
if ($LASTEXITCODE -ne 0) { throw "PostgreSQL connection failed. Check pgpass.conf mapping for osh_global_app." }

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

if (Test-Path $webPidFile) { Remove-Item -LiteralPath $webPidFile -Force }
if (Test-Path $workerPidFile) {
    if (Test-ProcessPidFile $workerPidFile "app.worker") { throw "Worker is already running; run ops/stop-central.ps1 first." }
    Remove-Item -LiteralPath $workerPidFile -Force
}

Write-Host "Installing Python requirements in the central virtual environment..."
& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
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
    throw "Central web server did not start. See $logs."
}

Write-Host ""
Write-Host "OSH Agriculture AI Global CENTRAL SERVER is running."
Write-Host "Local health: http://127.0.0.1:8080/api/v1/health"
Write-Host "Web PID: $($web.Id) | Worker PID: $($worker.Id)"
Write-Host "Central PostgreSQL: osh_agriculture_global on 127.0.0.1:5433"
Write-Host "PostgreSQL is not exposed publicly."
Write-Host "Persistent data/config/logs: $centralHome"
