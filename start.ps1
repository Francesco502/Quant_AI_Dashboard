param(
    [switch]$SkipDaemon
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

function Write-Step {
    param(
        [string]$Message
    )

    Write-Host "[START] $Message" -ForegroundColor Cyan
}

function Activate-LocalVenv {
    $localVenv = Join-Path $repoRoot ".venv\Scripts\Activate.ps1"
    $parentVenv = Join-Path $repoRoot "..\.venv\Scripts\Activate.ps1"

    if (Test-Path $localVenv) {
        & $localVenv
        Write-Host "[INFO] Activated .venv" -ForegroundColor Green
        return
    }

    if (Test-Path $parentVenv) {
        & $parentVenv
        Write-Host "[INFO] Activated ..\\.venv" -ForegroundColor Green
        return
    }

    Write-Host "[WARN] No virtual environment found. Using system Python." -ForegroundColor Yellow
}

function Start-CommandWindow {
    param(
        [string]$Title,
        [string]$WorkingDirectory,
        [string]$Command
    )

    $commandLine = "cd /d `"$WorkingDirectory`" && $Command"
    Start-Process -FilePath "cmd.exe" -ArgumentList "/k", $commandLine -WindowStyle Normal | Out-Null
    Write-Host "[OK] $Title" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Quant-AI Dashboard Local Launcher" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "[INFO] Repository root: $repoRoot" -ForegroundColor Green
Write-Host ""

Activate-LocalVenv

if (Test-Path ".env") {
    Write-Host "[INFO] Found .env" -ForegroundColor Green
} else {
    Write-Host "[WARN] .env not found. Defaults will be used where supported." -ForegroundColor Yellow
}

Write-Step "Backend API on 8685"
Start-CommandWindow -Title "Backend started on port 8685" -WorkingDirectory $repoRoot -Command "python -m uvicorn api.main:app --host 0.0.0.0 --port 8685 --reload"

if (-not $SkipDaemon) {
    Start-Sleep -Seconds 1
    Write-Step "Daemon worker"
    Start-CommandWindow -Title "Daemon started" -WorkingDirectory $repoRoot -Command "python -m core.daemon"
} else {
    Write-Host "[INFO] Daemon start skipped." -ForegroundColor Yellow
}

$webPath = Join-Path $repoRoot "web"
if (-not (Test-Path $webPath)) {
    throw "Web directory not found: $webPath"
}

Start-Sleep -Seconds 1
Write-Step "Frontend on 8686"
Start-CommandWindow -Title "Frontend started on port 8686" -WorkingDirectory $webPath -Command "npm run dev"

Write-Host ""
Write-Host "Services launched." -ForegroundColor Green
Write-Host "Frontend : http://localhost:8686" -ForegroundColor Cyan
Write-Host "Backend  : http://localhost:8685" -ForegroundColor Cyan
Write-Host "API Docs : http://localhost:8685/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Admin initialization requires APP_LOGIN_PASSWORD or APP_LOGIN_PASSWORD_HASH." -ForegroundColor Yellow
Write-Host "Close this launcher window at any time; child service windows stay open." -ForegroundColor Gray
