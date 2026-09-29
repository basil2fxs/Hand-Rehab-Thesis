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
rem Wait until the simulator is listening (up to 20 s by the clock), so
rem the game finds it on the first try instead of opening its port
rem picker. Each try gives up after half a second: on Windows a refused
rem connect can take about two seconds by itself.
powershell -NoProfile -Command "$w=[Diagnostics.Stopwatch]::StartNew();while($w.Elapsed.TotalSeconds -lt 20){$c=New-Object Net.Sockets.TcpClient;try{if($c.ConnectAsync('127.0.0.1',50410).Wait(500)){$c.Close();exit 0}}catch{};$c.Close();Start-Sleep -Milliseconds 250};exit 1"
if errorlevel 1 (
  echo The simulator did not start. Close any other copy and run this again.
  pause
  exit /b 1
)
start "Finger Rehab" "Finger Rehab.exe" --windowed --eeg-port socket://127.0.0.1:50410
