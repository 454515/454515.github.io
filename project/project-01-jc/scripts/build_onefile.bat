@echo off
chcp 65001 >nul
cd /d %~dp0..
rem Put the bundled UPX compressor on PATH so PyInstaller's upx=True takes effect.
set PATH=%cd%\tools\upx;%PATH%
if exist tools\upx\upx.exe (
    echo [UPX] found - exe will be compressed
) else (
    echo [UPX] NOT found ^(tools\upx\upx.exe^) - exe will NOT be compressed
)
echo === jc onefile build (single exe) ===
rem Clear the PyInstaller work dir + stale exe, but keep the dist dir itself:
rem z keeps a git repo inside dist, which rmdir /s /q would wipe out.
rmdir /s /q build 2>nul
if exist dist\jc.exe del /f /q dist\jc.exe 2>nul
call .venv\Scripts\python.exe -m PyInstaller jc.spec --noconfirm
echo === build exit: %errorlevel% ===
if exist dist\jc.exe (
    for %%f in (dist\jc.exe) do echo exe size: %%~zf bytes
    echo done: dist\jc.exe
) else (
    echo ERROR: build failed, no exe found
)
pause
