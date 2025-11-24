@echo off
REM AI Newsletter - Run Immediately Script
REM This script activates the environment and runs the application right now

echo.
echo ================================================================================
echo                    AI Newsletter - Run Now
echo ================================================================================
echo.
echo This will run the newsletter application immediately (not wait until Monday)
echo.
echo IMPORTANT: Make sure you've updated .env file with:
echo   - TELEGRAM_BOT_TOKEN=your_real_token
echo   - TELEGRAM_CHAT_ID=your_real_chat_id
echo.
echo If you haven't updated .env, press Ctrl+C now to cancel
echo.
pause

REM Navigate to project directory
cd /d "%~dp0"

REM Check if venv exists
if not exist venv\Scripts\activate.bat (
    echo.
    echo ERROR: Virtual environment not found!
    echo Please run: python -m venv venv
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Verify .env file exists
if not exist .env (
    echo.
    echo ERROR: .env file not found!
    echo Please copy .env.example to .env and update with your credentials
    echo.
    pause
    exit /b 1
)

REM Run the application
echo.
echo ================================================================================
echo Running AI Newsletter Application NOW
echo ================================================================================
echo.
echo Watch the logs below for progress...
echo.

python -m src.main --log-level INFO

REM Check result
if %errorlevel% equ 0 (
    echo.
    echo ================================================================================
    echo SUCCESS! Newsletter application completed
    echo ================================================================================
    echo.
    echo Check your Telegram chat for the newsletter message
    echo See logs/newsletter.log for detailed information
    echo.
) else (
    echo.
    echo ================================================================================
    echo ERROR: Application failed
    echo ================================================================================
    echo.
    echo Check logs/newsletter.log for error details
    echo.
)

pause
