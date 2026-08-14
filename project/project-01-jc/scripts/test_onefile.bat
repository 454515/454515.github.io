@echo off
chcp 65001 >nul
cd /d %~dp0..
echo === testing onefile build ===
set EXE=dist\jc.exe
if not exist "%EXE%" (
    echo ERROR: %EXE% not found. Run scripts\build_onefile.bat first.
    pause
    exit /b 1
)
echo running %EXE% ...
start "" "%EXE%"
timeout /t 8 /nobreak >nul
echo test complete
pause
