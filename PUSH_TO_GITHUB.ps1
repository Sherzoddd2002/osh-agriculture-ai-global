param(
    [Parameter(Mandatory=$true)]
    [string]$RepositoryUrl
)
$ErrorActionPreference = 'Stop'
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "Git topilmadi. Git for Windows o'rnating." }
if (-not (Test-Path ".git")) { git init }
git add .
git commit -m "Initial OSH Agriculture AI Global foundation"
git branch -M main
$remote = git remote get-url origin 2>$null
if ($LASTEXITCODE -eq 0) { git remote set-url origin $RepositoryUrl } else { git remote add origin $RepositoryUrl }
git push -u origin main
