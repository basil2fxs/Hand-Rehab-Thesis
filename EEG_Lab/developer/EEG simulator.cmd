@echo off
rem Rehearse the EEG session without the lab. The simulator window stands
rem in for the trigger box and the amplifier, and the game sends its
rem markers to it instead of COM10.
cd /d "%~dp0.."
if not exist "Finger Rehab.exe" (
  echo Put Finger Rehab.exe in the EEG_Lab folder first, from the latest release.
  pause
  exit /b 1
)
start "EEG simulator" "Finger Rehab.exe" --eeg-simulator
timeout /t 4 /nobreak >nul
start "Finger Rehab" "Finger Rehab.exe" --eeg-port socket://127.0.0.1:50410
