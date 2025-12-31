# Quant-AI-Dashboard 启动脚本 (PowerShell)
$ErrorActionPreference = "Stop"

# 设置编码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Quant-AI-Dashboard 启动脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 切换到脚本目录
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath
Write-Host "当前目录: $scriptPath" -ForegroundColor Green
Write-Host ""

# 激活虚拟环境（位于上级目录）
$venvActivate = Join-Path $scriptPath "..\\.venv\\Scripts\\Activate.ps1"
if (Test-Path $venvActivate) {
    Write-Host "正在激活虚拟环境..." -ForegroundColor Yellow
    & $venvActivate
    Write-Host "虚拟环境已激活" -ForegroundColor Green
} else {
    Write-Host "警告: 未找到虚拟环境，将使用系统 Python" -ForegroundColor Yellow
}
Write-Host ""

# 设置环境变量
$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = "false"
$env:STREAMLIT_SERVER_HEADLESS = "true"

# ========== 登录密码配置 ==========
if (-not $env:APP_LOGIN_PASSWORD -and -not $env:APP_LOGIN_PASSWORD_HASH) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "登录密码配置" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "当前未设置登录密码，系统将以开发模式运行（无需登录）" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "如需启用密码保护，请选择：" -ForegroundColor White
    Write-Host "  1. 设置明文密码（简单，适合测试）" -ForegroundColor White
    Write-Host "  2. 跳过，使用开发模式（无需密码）" -ForegroundColor White
    Write-Host ""
    $passwordChoice = Read-Host "请选择 (1/2，直接回车默认选择2)"
    
    if ($passwordChoice -eq "1") {
        $securePassword = Read-Host "请输入密码" -AsSecureString
        $passwordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
        )
        if ($passwordPlain) {
            $env:APP_LOGIN_PASSWORD = $passwordPlain
            Write-Host ""
            Write-Host "密码已设置，系统将启用登录保护" -ForegroundColor Green
            Write-Host ""
        } else {
            Write-Host ""
            Write-Host "未输入密码，将使用开发模式" -ForegroundColor Yellow
            Write-Host ""
        }
    } else {
        Write-Host ""
        Write-Host "使用开发模式（无需密码）" -ForegroundColor Yellow
        Write-Host ""
    }
}

# 显示密码状态
if ($env:APP_LOGIN_PASSWORD) {
    Write-Host "[提示] 登录密码已启用，访问时需要输入密码" -ForegroundColor Green
    Write-Host ""
} elseif ($env:APP_LOGIN_PASSWORD_HASH) {
    Write-Host "[提示] 登录密码已启用（使用哈希），访问时需要输入密码" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "[提示] 开发模式：未启用登录保护" -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "正在启动 Streamlit 应用..." -ForegroundColor Yellow
Write-Host "启动后请在浏览器中访问: http://localhost:8501" -ForegroundColor Green
Write-Host ""
Write-Host "按 Ctrl+C 停止服务" -ForegroundColor Yellow
Write-Host ""
Write-Host "----------------------------------------" -ForegroundColor Gray
Write-Host ""

# 启动 Streamlit
try {
    python -m streamlit run app.py --server.port=8501
} catch {
    Write-Host "启动失败: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "请检查:" -ForegroundColor Yellow
    Write-Host "1. Python 是否正确安装" -ForegroundColor White
    Write-Host "2. 依赖是否已安装 (pip install -r requirements.txt)" -ForegroundColor White
    Write-Host "3. 端口 8501 是否被占用" -ForegroundColor White
    Write-Host ""
    Read-Host "按 Enter 键退出"
}

