@echo off
cd /d "%~dp0"

echo 正在停止定时任务...
schtasks /Delete /F /TN "homework-check" >nul 2>nul
schtasks /Delete /F /TN "homework-summary" >nul 2>nul
schtasks /Delete /F /TN "homework-refresh-cookie" >nul 2>nul
echo √ 已停止

echo.
echo 本程序已停止运行。如需彻底移除，请直接删除本文件夹。
pause
