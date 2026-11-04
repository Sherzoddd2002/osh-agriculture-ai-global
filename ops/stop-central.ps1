$ErrorActionPreference = "Stop"
$centralHome = if ($env:OSH_AGRI_CENTRAL_HOME) { $env:OSH_AGRI_CENTRAL_HOME } else { Join-Path $env:LOCALAPPDATA "OSH\AgricultureAI-Central" }
$state = Join-Path $centralHome "state"

function Stop-VerifiedProcess($file, $needle, $label) {
    if (-not (Test-Path -LiteralPath $file)) {
        Write-Host "$label is not running (no PID file)."
        return
    }
    $data = Get-Content -LiteralPath $file -Raw | ConvertFrom-Json
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $($data.pid)" -ErrorAction SilentlyContinue
    if ($null -eq $proc) {
        Remove-Item -LiteralPath $file -Force
        Write-Host "$label was already stopped."
        return
    }
    if ($proc.CommandLine -notlike "*$needle*") {
        throw "$label PID $($data.pid) does not match expected command. Process was NOT stopped."
    }
    & taskkill.exe /PID $data.pid /T /F | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not stop $label PID $($data.pid)." }
    Remove-Item -LiteralPath $file -Force
    Write-Host "$label stopped."
}

Stop-VerifiedProcess (Join-Path $state "web.pid") "uvicorn app.main:app" "Web server"
Stop-VerifiedProcess (Join-Path $state "worker.pid") "app.worker" "Worker"
Write-Host "PostgreSQL service and databases were not touched."
