@echo off
REM Build the standalone Windows exe (one file, everything inside).
REM PyInstaller output goes to bin\dist\, then the exe is copied into
REM builds\Windows\ so the ready-to-run deliverables always live in one
REM obvious place at the project root.
setlocal

rem The script lives in builds\; the build runs from the project root.
cd /d "%~dp0.."

py -m pip install --quiet --upgrade pyinstaller
if errorlevel 1 (
    echo Failed to install pyinstaller
    exit /b 1
)

rmdir /s /q bin\build 2>nul
rmdir /s /q bin\dist 2>nul
if not exist bin mkdir bin

py -m PyInstaller --noconfirm ^
    --workpath bin\build ^
    --distpath bin\dist ^
    finger_rehab.spec
if errorlevel 1 (
    echo Build failed
    exit /b 1
)

if not exist builds\Windows mkdir builds\Windows
copy /y "bin\dist\Finger Rehab.exe" "builds\Windows\Finger Rehab.exe" >nul

echo.
echo Build complete.
echo Ready to run: builds\Windows\Finger Rehab.exe
echo Copy that one file to any Windows PC and double-click it.
