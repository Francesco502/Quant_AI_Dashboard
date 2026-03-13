# Quant-AI-Dashboard Startup Script (PowerShell)
$ErrorActionPreference = "Stop"

# Set Encoding
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Quant-AI-Dashboard Startup Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Switch to script directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath
Write-Host "Current Directory: $scriptPath" -ForegroundColor Green
Write-Host ""

# Activate Virtual Environment
$localVenv = Join-Path $scriptPath ".venv\Scripts\Activate.ps1"
$parentVenv = Join-Path $scriptPath "..\.venv\Scripts\Activate.ps1"

if (Test-Path $localVenv) {
    Write-Host "Activating local venv (.venv)..." -ForegroundColor Yellow
    & $localVenv
    Write-Host "Local venv activated" -ForegroundColor Green
} elseif (Test-Path $parentVenv) {
    Write-Host "Activating parent venv (..\.venv)..." -ForegroundColor Yellow
    & $parentVenv
    Write-Host "Parent venv activated" -ForegroundColor Green
} else {
    Write-Host "WARNING: No virtual environment found. Using system Python." -ForegroundColor Yellow
}
Write-Host ""

# Check Password
if (-not $env:APP_LOGIN_PASSWORD -and -not $env:APP_LOGIN_PASSWORD_HASH) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Login Configuration" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "No login protection configured. System will run in DEV mode." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Please choose:" -ForegroundColor White
    Write-Host "  1. Configure Password" -ForegroundColor White
    Write-Host "  2. Skip (Start Directly)" -ForegroundColor White
    Write-Host ""
    $passwordChoice = Read-Host "Enter 1 or 2 (default 2)"
    
    if ($passwordChoice -eq "1") {
        $securePassword = Read-Host "Enter Password" -AsSecureString
        $passwordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
        )
        if ($passwordPlain) {
            $env:APP_LOGIN_PASSWORD = $passwordPlain
            Write-Host ""
            Write-Host "Password set. Login protection enabled." -ForegroundColor Green
            Write-Host ""
        } else {
            Write-Host ""
            Write-Host "No password entered. Using DEV mode." -ForegroundColor Yellow
            Write-Host ""
        }
    } else {
        Write-Host ""
        Write-Host "Using DEV mode." -ForegroundColor Yellow
        Write-Host ""
    }
}

# Show Password Status
if ($env:APP_LOGIN_PASSWORD) {
    Write-Host "[INFO] Login protection enabled." -ForegroundColor Green
    Write-Host ""
} elseif ($env:APP_LOGIN_PASSWORD_HASH) {
    Write-Host "[INFO] Login protection enabled (Hash)." -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "[INFO] DEV Mode: No login protection." -ForegroundColor Yellow
    Write-Host ""
}

# Start API Server
Write-Host "Starting API Server (Port 8685)..." -ForegroundColor Yellow
try {
    Start-Process -FilePath "python" -ArgumentList "-m uvicorn api.main:app --host 0.0.0.0 --port 8685 --reload"
    Write-Host "API Server started in background" -ForegroundColor Green
} catch {
    Write-Host "Failed to start API Server: $_" -ForegroundColor Red
}

# Start Next.js Frontend
Write-Host "Starting Next.js Frontend (Port 8686)..." -ForegroundColor Yellow
try {
    $webPath = Join-Path $scriptPath "web"
    if (-not (Test-Path $webPath)) {
        throw "Web directory not found: $webPath"
    }
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "cd /d `"$webPath`" && npm run dev"
    Write-Host "Next.js Frontend started in background" -ForegroundColor Green
} catch {
    Write-Host "Failed to start Next.js Frontend: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "Services Started!" -ForegroundColor Green
Write-Host "Please access: http://localhost:8686" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press any key to close this launcher (services will keep running)..." -ForegroundColor Gray
Read-Host
