@echo off
REM Setup Windows Task Scheduler for AI Newsletter
REM Usage: setup-task-scheduler.bat [monday|daily|12hourly]
REM
REM Examples:
REM   setup-task-scheduler.bat monday      : Every Monday 9 AM
REM   setup-task-scheduler.bat daily       : Every day 9 AM
REM   setup-task-scheduler.bat 12hourly    : Every 12 hours

setlocal enabledelayedexpansion

REM Get the project directory
set SCRIPT_DIR=%~dp0
for %%I in ("%SCRIPT_DIR%..") do set PROJECT_DIR=%%~fI

REM Find Python
where python >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found in PATH
    exit /b 1
)
for /f "tokens=*" %%i in ('where python') do set PYTHON=%%i

REM Get schedule parameter
set SCHEDULE=%1
if "%SCHEDULE%"=="" set SCHEDULE=monday

echo.
echo === AI Newsletter Task Scheduler Setup ===
echo Project directory: %PROJECT_DIR%
echo Python executable: %PYTHON%
echo Schedule: %SCHEDULE%
echo.

REM Determine schedule
if /i "%SCHEDULE%"=="monday" (
    set TRIGGER=/SC WEEKLY /D MON /ST 09:00:00
    set DESC=Every Monday at 9:00 AM
) else if /i "%SCHEDULE%"=="daily" (
    set TRIGGER=/SC DAILY /ST 09:00:00
    set DESC=Every day at 9:00 AM
) else if /i "%SCHEDULE%"=="12hourly" (
    set TRIGGER=/SC HOURLY /MO 12
    set DESC=Every 12 hours
) else (
    echo Error: Unknown schedule '%SCHEDULE%'
    echo Valid options: monday, daily, 12hourly
    exit /b 1
)

echo Schedule: %DESC%
echo.

REM Check for admin rights
net session >nul 2>&1
if errorlevel 1 (
    echo.
    echo Error: This script requires administrator privileges
    echo Please run as Administrator (right-click and select "Run as Administrator")
    exit /b 1
)

REM Delete existing task if it exists
echo Checking for existing task...
schtasks /query /tn "AI Newsletter" >nul 2>&1
if errorlevel 1 (
    echo No existing task found
) else (
    echo Existing task found
    setlocal
    schtasks /delete /tn "AI Newsletter" /f >nul 2>&1
    echo Removed old task
    endlocal
)

echo.
echo Creating new scheduled task...
echo.

REM Create the scheduled task
schtasks /create ^
    /tn "AI Newsletter" ^
    /tr "cmd /c cd /d %PROJECT_DIR% && %PYTHON% -m src.main --log-level INFO >> logs\task-scheduler.log 2>&1" ^
    /ru SYSTEM ^
    %TRIGGER% ^
    /f

if errorlevel 1 (
    echo.
    echo Error: Failed to create scheduled task
    exit /b 1
)

echo.
echo === Setup Complete ===
echo.
echo Task created successfully!
echo.
echo Next steps:
echo 1. Test the newsletter manually:
echo    python -m src.main --log-level INFO
echo.
echo 2. View the task in Task Scheduler:
echo    - Open Task Scheduler
echo    - Navigate to: Task Scheduler Library
echo    - Look for: AI Newsletter
echo.
echo 3. Monitor logs:
echo    - Check: %PROJECT_DIR%\logs\task-scheduler.log
echo.
echo 4. To modify the task:
echo    - Open Task Scheduler
echo    - Right-click "AI Newsletter" task
echo    - Select "Properties"
echo.
echo 5. To remove the task:
echo    schtasks /delete /tn "AI Newsletter" /f
echo.

REM Show the created task
echo Current task details:
schtasks /query /tn "AI Newsletter" /v
