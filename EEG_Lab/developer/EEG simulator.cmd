@echo off
rem The trigger box and the EEG, simulated. Run this first, then start
rem the game as at the lab (Run in PsychoPy, or Finger Rehab.exe). The
rem game finds no box on COM10, finds this simulator instead and runs
rem as if the box were plugged in; every marker shows up here as it
rem would on the recording. A game already open finds it on Scan again.
cd /d "%~dp0.."
if not exist "Finger Rehab.exe" (
  echo Put Finger Rehab.exe in the EEG_Lab folder first, from the latest release.
  pause
  exit /b 1
)
start "EEG simulator" "Finger Rehab.exe" --eeg-simulator
