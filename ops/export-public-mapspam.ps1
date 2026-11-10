param(
    [string]$Countries = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$centralHome = if ($env:OSH_AGRI_CENTRAL_HOME) {
    $env:OSH_AGRI_CENTRAL_HOME
} else {
    Join-Path $env:LOCALAPPDATA "OSH\AgricultureAI-Central"
}

# Reuse the already-installed central environment when available.
$pythonCandidates = @(
    (Join-Path $centralHome ".venv\Scripts\python.exe"),
    (Join-Path $repoRoot ".venv\Scripts\python.exe")
)
$python = $null
foreach ($candidate in $pythonCandidates) {
    if (Test-Path -LiteralPath $candidate) {
        $python = $candidate
        break
    }
}
if (-not $python) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) { $python = $pythonCommand.Source }
}
if (-not $python) {
    throw "Python topilmadi. Avval ops/start-central.ps1 orqali Python muhitini tayyorlang."
}

$env:PYTHONPATH = Join-Path $repoRoot "backend"
$env:PYTHONUTF8 = "1"
# The central server uses this local role and pgpass.conf. No password is stored here.
$env:DATABASE_URL = "postgresql+psycopg://osh_global_app@127.0.0.1:5433/osh_agriculture_global"

Write-Host "Global MAPSPAM export: local PostgreSQL dan faqat SELECT so‘rovlari."
Write-Host "Ma’lumotlar: ADM0 country + ADM1 province + ADM2 district."
Write-Host "Xom raster, FAOSTAT yozuvlari, foydalanuvchi CSV va credential eksport qilinmaydi."

$exporter = Join-Path $repoRoot "scripts\export_public_mapspam_global.py"
$verify = Join-Path $repoRoot "scripts\verify_public_mapspam_export.py"
$arguments = @($exporter)
if (-not [string]::IsNullOrWhiteSpace($Countries)) {
    $arguments += @("--countries", $Countries)
}
& $python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "MAPSPAM eksporti muvaffaqiyatsiz tugadi (exit $LASTEXITCODE). PostgreSQL, pgpass.conf va Python kutubxonalarini tekshiring."
}

& $python $verify
if ($LASTEXITCODE -ne 0) {
    throw "MAPSPAM public paket tekshiruvi muvaffaqiyatsiz tugadi. Tekshiruvdan o‘tmaguncha fayllarni commit qilmang."
}

Write-Host ""
Write-Host "EXPORT VA VALIDATSIYA MUVAFFAQIYATLI."
Write-Host "Chiqqan fayllar: $repoRoot\docs\data\mapspam\global"
Write-Host "Ushbu fayllarni ko‘rib chiqing; faqat shundan keyin GitHub'ga commit/push qiling."
