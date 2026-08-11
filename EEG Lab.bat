@echo off
rem Double-click launcher for EEG lab sessions on the lab's Windows
rem desktop. Runs the SAME main.py as the normal game with the lab
rem overlay: markers on, trigger box required (COM10 by default).
cd /d "%~dp0"

echo Starting Finger Rehab (EEG lab mode)...
echo.

python main.py --config config/eeg_lab.yaml
if errorlevel 1 (
    echo.
    echo EEG lab mode exited with an error.
    echo If it says the trigger port could not be opened, plug the
    echo trigger box in and check eeg.port in config\eeg_lab.yaml
    echo against Device Manager's Ports list.
    echo.
    pause
)
