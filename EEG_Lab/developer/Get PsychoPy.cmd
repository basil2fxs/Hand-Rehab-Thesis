@echo off
rem Downloads the Standalone PsychoPy installer for Windows (2026.2.4,
rem Python 3.10, about 530 MB) from PsychoPy's GitHub releases into
rem downloads\, checks it against the SHA-256 GitHub lists for it, then
rem starts it. Run it once on a new PC.
setlocal
set VERSION=2026.2.4
set FILE=StandalonePsychoPy-%VERSION%-win64-3.10.exe
set URL=https://github.com/psychopy/psychopy/releases/download/%VERSION%/%FILE%
set SHA256=4d2ca8bae2d8795f8cb0b561496cd4615b744a4a2e88b2c90cb7b3b00101fe5c
cd /d "%~dp0"
if not exist downloads mkdir downloads
if not exist "downloads\%FILE%" (
  echo Downloading %FILE%, about 530 MB...
  curl -L --fail -o "downloads\%FILE%.part" "%URL%"
  if errorlevel 1 (
    echo The download failed. Get it by hand: https://github.com/psychopy/psychopy/releases
    del "downloads\%FILE%.part" 2>nul
    pause
    exit /b 1
  )
  move /y "downloads\%FILE%.part" "downloads\%FILE%" >nul
)
echo Checking the file...
certutil -hashfile "downloads\%FILE%" SHA256 | findstr /i /c:"%SHA256%" >nul
if errorlevel 1 (
  echo The installer does not match the one PsychoPy published, so it was deleted.
  echo Run this again to download it fresh.
  del "downloads\%FILE%"
  pause
  exit /b 1
)
echo Starting the PsychoPy installer...
start "" "downloads\%FILE%"
