@echo off
REM Build the standalone Windows .exe. Result lands in bin\dist\.
REM Build intermediates go to bin\build\ so the project root stays clean.
setlocal

cd /d "%~dp0"

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

echo.
echo Build complete.
echo Exe: bin\dist\Finger Rehab\Finger Rehab.exe
echo Double-click the exe or run from the command line.
