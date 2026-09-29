@echo off
rem Checks this PC can run the lab folder: the game's flashing tools,
rem and the USB driver of any Arduino plugged in (the hand device or the
rem trigger box).
cd /d "%~dp0.."
if not exist "Finger Rehab.exe" (
  echo Put Finger Rehab.exe in the EEG_Lab folder first, from the latest release.
  pause
  exit /b 1
)
set REPORT=%TEMP%\finger_rehab_check.json
start /wait "" "Finger Rehab.exe" --check-tools "%REPORT%"
type "%REPORT%"
echo.
pause
