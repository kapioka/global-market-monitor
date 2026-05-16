@echo off
setlocal

cd /d "%~dp0project"

where py >nul 2>nul
if %ERRORLEVEL%==0 (
  set "PYTHON_CMD=py -3"
) else (
  set "PYTHON_CMD=python"
)

echo Starting market monitor...
%PYTHON_CMD% main.py
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo main.py failed. Exit code: %EXIT_CODE%
)

if "%EXIT_CODE%"=="0" (
  echo.
  echo main.py finished successfully.
)

pause
endlocal
