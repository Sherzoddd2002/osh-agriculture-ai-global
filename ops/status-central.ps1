$ErrorActionPreference = "Continue"
$centralHome = if ($env:OSH_AGRI_CENTRAL_HOME) { $env:OSH_AGRI_CENTRAL_HOME } else { Join-Path $env:LOCALAPPDATA "OSH\AgricultureAI-Central" }
$state = Join-Path $centralHome "state"
foreach ($item in @(@{file="web.pid";needle="uvicorn app.main:app";name="WEB"},@{file="worker.pid";needle="app.worker";name="WORKER"})) {
    $path = Join-Path $state $item.file
    $running = $false
    if (Test-Path -LiteralPath $path) {
        try {
            $data = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
            $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $($data.pid)"
            $running = ($null -ne $proc -and $proc.CommandLine -like "*$($item.needle)*")
        } catch {}
    }
    Write-Host "$($item.name): $(if($running){'RUNNING'}else{'STOPPED'})"
}
try {
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/v1/health" -TimeoutSec 3
    Write-Host "API: $($h.service) | Database: $($h.database)"
    if ($h.background_worker) {
        $worker = $h.background_worker
        Write-Host "Worker heartbeat: $($worker.status) | State: $($worker.worker_status) | Last seen: $($worker.last_seen)"
        if ($worker.current_job_id) {
            Write-Host "Current job: #$($worker.current_job_id) | Type: $($worker.current_job_type)"
        }
    }
} catch {
    Write-Host "API: NOT RESPONDING"
}
