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
rem Wait until the simulator is listening (up to 20 s), so the game
rem finds it on the first try instead of opening its port picker.
powershell -NoProfile -Command "for($i=0;$i -lt 40;$i++){try{$c=New-Object Net.Sockets.TcpClient('127.0.0.1',50410);$c.Close();exit 0}catch{Start-Sleep -Milliseconds 500}};exit 1"
if errorlevel 1 (
  echo The simulator did not start. Close any other copy and run this again.
  pause
  exit /b 1
)
start "Finger Rehab" "Finger Rehab.exe" --windowed --eeg-port socket://127.0.0.1:50410
