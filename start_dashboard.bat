@echo off
chcp 65001 >nul 2>&1
echo ========================================
echo Quant-AI-Dashboard 启动脚本
echo ========================================
echo.
cd /d "%~dp0"
echo 当前目录: %CD%
echo.

REM 激活虚拟环境
set VENV_PATH=%~dp0..\.venv\Scripts\activate.bat
if exist "%VENV_PATH%" (
    echo 正在激活虚拟环境...
    call "%VENV_PATH%"
) else (
    echo 警告: 未找到虚拟环境，将使用系统 Python
)
echo.

REM 设置环境变量
set STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
set STREAMLIT_SERVER_HEADLESS=true

REM 检查是否已设置密码
if not "%APP_LOGIN_PASSWORD%"=="" goto :HAS_PASSWORD
if not "%APP_LOGIN_PASSWORD_HASH%"=="" goto :HAS_HASH

REM 未设置密码，显示配置菜单
echo.
echo ========================================
echo 登录配置
echo ========================================
echo.
echo 当前未设置登录保护，系统将以开发模式运行
echo.
echo 请选择：
echo.
echo     [1] 配置登录保护
echo.
echo     [2] 跳过，直接启动
echo.
set /p PASSWORD_CHOICE="请输入选项 1 或 2: "

if "%PASSWORD_CHOICE%"=="1" goto :SET_PASSWORD
goto :DEV_MODE

:SET_PASSWORD
set /p APP_LOGIN_PASSWORD="请输入访问口令: "
if "%APP_LOGIN_PASSWORD%"=="" goto :DEV_MODE
echo.
echo 口令已配置，系统将启用登录保护
echo.
goto :START_APP

:DEV_MODE
echo.
echo 使用开发模式启动
echo.
goto :START_APP

:HAS_PASSWORD
echo [提示] 登录保护已启用
echo.
goto :START_APP

:HAS_HASH
echo [提示] 登录保护已启用
echo.
goto :START_APP

:START_APP
echo 正在启动 Streamlit 应用...
echo 启动后请在浏览器中访问: http://localhost:8501
echo.
echo 按 Ctrl+C 停止服务
echo.
python -m streamlit run app.py --server.port=8501
pause
