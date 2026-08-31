@echo off
:: ============================================================
::  V.I.R.U.S.  --  One-Time Autostart Registration
::  Run this ONCE as your regular user (no admin needed).
::  Registers virus_supervisor.py to start silently at login.
:: ============================================================

setlocal

set "BACKEND=C:\Users\aakas\OneDrive\Desktop\V.I.R.U.S\backend"
set "SCRIPT=%BACKEND%\virus_supervisor.py"
set "TASK_NAME=VIRUS_Supervisor"

:: Find pythonw.exe (runs Python with no console window)
for /f "delims=" %%p in ('where pythonw 2^>nul') do set "PYTHONW=%%p"
if not defined PYTHONW (
    :: Fallback: look next to python.exe
    for /f "delims=" %%p in ('where python 2^>nul') do (
        set "PY_DIR=%%~dpp"
        if exist "!PY_DIR!pythonw.exe" set "PYTHONW=!PY_DIR!pythonw.exe"
    )
)
if not defined PYTHONW (
    echo [ERROR] pythonw.exe not found. Using python.exe instead (a terminal window may flash briefly on login).
    for /f "delims=" %%p in ('where python 2^>nul') do set "PYTHONW=%%p"
)

echo.
echo  ================================================
echo    V.I.R.U.S.  --  Autostart Registration
echo  ================================================
echo.
echo  Python  : %PYTHONW%
echo  Script  : %SCRIPT%
echo  Task    : %TASK_NAME%
echo.

:: Delete existing task if present (clean slate)
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: Register: runs at logon of current user, hidden, with 3 auto-restart retries
schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "\"%PYTHONW%\" \"%SCRIPT%\"" ^
  /sc onlogon ^
  /ru "%USERNAME%" ^
  /f ^
  /rl HIGHEST ^
  /delay 0000:10 ^
  >nul

if %errorlevel% neq 0 (
    echo [ERROR] Task registration failed. Try running as Administrator.
    pause
    exit /b 1
)

echo [OK] Task "%TASK_NAME%" registered successfully.
echo.
echo  What happens next:
echo   • Log out and back in  ^(or restart^)
echo   • V.I.R.U.S. Supervisor will start silently in the background
echo   • A small coloured dot will appear in your system tray ^(bottom-right^)
echo   • Clap once, then say "hey virus" to launch V.I.R.U.S.
echo.
echo  To remove autostart at any time, run:
echo    schtasks /delete /tn "%TASK_NAME%" /f
echo.

pause
endlocal
