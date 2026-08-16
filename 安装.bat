@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"

echo ============================================
echo           作业提醒 · 安装程序
echo ============================================
echo.
echo 此程序会自动监控作业状态，有新发布、未交或临近截止日期未交的作业会通过微信及时通知你。
echo 安装过程预计需要 2-5 分钟，期间请勿关闭本窗口。
echo.
echo 正在检测系统环境...

where python >nul 2>nul
if %errorlevel% equ 0 goto :have_python

echo 未检测到 Python 运行环境（本程序依赖此环境）。
echo 正在下载 Python 3.12 安装包...
winget install -e --id Python.Python.3.12 --silent --accept-source-agreements --accept-package-agreements
if %errorlevel% neq 0 goto :python_fail
echo ✓ Python 安装完成
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%PATH%"

:have_python
echo 正在安装依赖组件...
python -m pip install -r requirements.txt playwright -q
if %errorlevel% neq 0 goto :deps_fail
echo ✓ 依赖安装完成

echo 正在启动配置向导...
python install.py
if %errorlevel% neq 0 goto :config_fail

echo.
echo 安装完成，可以关闭本窗口。
pause
exit /b 0

:python_fail
echo.
echo 自动安装 Python 失败。请访问 python.org 手动下载安装（勾选 Add to PATH），完成后重新运行「安装.bat」。
pause
exit /b 1

:deps_fail
echo.
echo 安装依赖失败，可能是网络连接异常。请检查网络后重新运行「安装.bat」。
pause
exit /b 1

:config_fail
echo.
echo 配置失败，请重新运行「安装.bat」。
pause
exit /b 1
