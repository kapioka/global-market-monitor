@echo off
setlocal

set "PROJECT_DIR=%~dp0project"
set "HISTORY_DASHBOARD=%PROJECT_DIR%\reports\dashboard.html"

echo.
echo Global Market Monitor
echo.
echo   [1] Fetch data, generate report, and open it
echo   [2] Open saved history
echo   [3] Exit
echo.
choice /c 123 /n /m "Select an option [1-3]: "

if errorlevel 3 goto :exit
if errorlevel 2 goto :open_history
if errorlevel 1 goto :generate_report
goto :exit

:generate_report
cd /d "%PROJECT_DIR%"

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
  echo Report generation completed.
)

goto :finish

:open_history
if not exist "%HISTORY_DASHBOARD%" (
  echo.
  echo No saved history dashboard was found.
  echo Select [1] first to generate a report.
  goto :finish
)

echo.
echo Opening saved history in the default browser.
start "" "%HISTORY_DASHBOARD%"
if errorlevel 1 (
  echo Failed to open: %HISTORY_DASHBOARD%
)

:finish
echo.
pause

:exit
endlocal
