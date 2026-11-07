param(
    [Parameter(Position = 0)]
    [ValidateSet("install", "start", "status", "stop", "update")]
    [string]$Action = "install",
    [switch]$NoOpen
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$cli = Join-Path $repoRoot "bin\cli.js"

if (-not (Test-Path -LiteralPath $cli)) {
    throw "CLI topilmadi: $cli"
}

$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCommand) {
    throw "Node.js 20+ topilmadi. O‘rnating: https://nodejs.org/"
}

$nodeVersion = (& $nodeCommand.Source --version 2>&1 | Out-String).Trim()
if ($nodeVersion -match '^v?(\d+)\.') {
    $nodeMajor = [int]$Matches[1]
} else {
    throw "Node.js versiyasini aniqlab bo‘lmadi: $nodeVersion"
}
if ($nodeMajor -lt 20) {
    throw "Node.js 20+ kerak. Topilgan versiya: $nodeVersion"
}

$cliArgs = @($cli, $Action)
if ($NoOpen) {
    $cliArgs += "--no-open"
}

Write-Host "OSH Agriculture AI local mode: $Action" -ForegroundColor Cyan
& $nodeCommand.Source @cliArgs
if ($LASTEXITCODE -ne 0) {
    throw "Local CLI muvaffaqiyatsiz tugadi (exit $LASTEXITCODE)."
}
