@echo off
rem Convenience launcher for the self-contained build. Double-clicking
rem the exe itself does the same thing (it finds the eeg_lab.yaml
rem beside it); this bat only adds a window that stays open with a
rem hint when the launch fails, instead of flashing and vanishing.
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
