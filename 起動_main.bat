@echo off
setlocal

cd /d "%~dp0project"

echo Starting market monitor...
call "C:\Python313\python.exe" main.py
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
