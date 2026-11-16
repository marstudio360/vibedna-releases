@echo off
REM Double click and your vault opens. It looks for the Python of the package's own environment
REM and, if it is not there, the system one: a buyer does not need to know which is which.
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" "vault_ui.py"
) else (
  start "" pythonw "vault_ui.py"
)
