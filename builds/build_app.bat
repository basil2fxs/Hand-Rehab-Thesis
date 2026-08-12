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

rem Refresh the EEG lab package: the one folder that gets copied to
rem the lab desktop. The exe, the lab config and the setup notes all
rem come from this build, so the folder can never carry a stale
rem pairing. The exe and the two copies are gitignored; the sources
rem of truth stay in config\ and docs\.
if not exist docs\lab_package mkdir docs\lab_package
copy /y "bin\dist\Finger Rehab.exe" "docs\lab_package\Finger Rehab.exe" >nul
copy /y "config\eeg_lab.yaml" "docs\lab_package\eeg_lab.yaml" >nul
copy /y "docs\eeg_lab_setup.txt" "docs\lab_package\eeg_lab_setup.txt" >nul

echo.
echo Build complete.
echo Ready to run: builds\Windows\Finger Rehab.exe
echo Copy that one file to any Windows PC and double-click it.
echo Lab install: copy the whole docs\lab_package folder to the lab PC.
