@echo off
rem EEG lab launcher for the self-contained build. No Python install
rem needed: Finger Rehab.exe carries everything, and this just starts
rem it with the lab config (markers on, trigger box required).
cd /d "%~dp0"

echo Starting Finger Rehab (EEG lab mode)...
echo.

"Finger Rehab.exe" --config eeg_lab.yaml
if errorlevel 1 (
    echo.
    echo EEG lab mode exited with an error.
    echo If it says the trigger port could not be opened, plug the
    echo trigger box in and check eeg.port in eeg_lab.yaml against
    echo Device Manager's Ports list.
    echo.
    pause
)
