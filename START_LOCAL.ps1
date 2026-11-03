$ErrorActionPreference = 'Stop'
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker topilmadi. Docker Desktop o'rnatib ishga tushiring."
}
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ".env yaratildi. JWT_SECRET ni almashtirib, skriptni qayta ishga tushiring." -ForegroundColor Yellow
    notepad .env
    exit 0
}
Write-Host "OSH Agriculture AI Global ishga tushmoqda..." -ForegroundColor Green
docker compose up --build
