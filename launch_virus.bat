@echo off
setlocal EnableDelayedExpansion

:: ============================================================
::  V.I.R.U.S.  Launch Script
::  Called by wake_listener.py after wake-word confirmation.
::  Also runnable manually (double-click) for quick launch.
:: ============================================================

set "ROOT=C:\Users\aakas\OneDrive\Desktop\V.I.R.U.S"
set "BACKEND=%ROOT%\backend"
set "FRONTEND=%ROOT%\frontend"
set "TAURI_EXE=%ROOT%\tauri-app\src-tauri\target\release\v-i-r-u-s.exe"

echo.
echo  ================================================
echo    V.I.R.U.S.  --  Launch Sequence
echo  ================================================
echo.

:: ── 1. Kill any stale process already on port 8000 ────────────────────────
set "STALE="
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    if not "%%a"=="" (
        echo [LAUNCH] Stopping stale process PID=%%a on port 8000...
        taskkill /f /pid %%a >nul 2>&1
        set "STALE=1"
    )
)
if defined STALE (timeout /t 1 /nobreak >nul)

:: ── 2. Start the V.I.R.U.S. backend (minimized so it doesn't clutter) ────
echo [LAUNCH] Starting backend (uvicorn port 8000)...
start /min "VIRUS_BACKEND" cmd /k "cd /d "%BACKEND%" && python -m uvicorn virus_server:app --host 0.0.0.0 --port 8000"

:: ── 3. Wait for backend to be ready (poll every second, up to 30 s) ───────
echo [LAUNCH] Waiting for backend to be ready...
set /a "TRIES=0"
:wait_loop
timeout /t 1 /nobreak >nul
set /a "TRIES+=1"
curl -s http://localhost:8000/ >nul 2>&1
if %errorlevel% neq 0 (
    if !TRIES! lss 30 goto wait_loop
    echo [LAUNCH] WARNING: Backend did not respond in 30 s — opening UI anyway.
)
echo [LAUNCH] Backend is up after !TRIES! second(s).
del /f /q "%BACKEND%\.boot_lock" >nul 2>&1

:: ── 4. Open the frontend ─────────────────────────────────────────────────
if exist "%TAURI_EXE%" (
    echo [LAUNCH] Starting Tauri app...
    start "" "%TAURI_EXE%"
    goto done
)

:: ── Fallback: React dev server + Chrome App Mode ─────────────────────────
echo [LAUNCH] Tauri .exe not found — using Chrome App Mode fallback.
echo [LAUNCH] Starting React dev server...
start /min "VIRUS_FRONTEND" cmd /k "cd /d "%FRONTEND%" && set BROWSER=none && npm start"

:: Give the dev server 12 s to compile
echo [LAUNCH] Waiting 12 s for React dev server...
timeout /t 12 /nobreak >nul

:: Open in Chrome as a standalone app window (no address bar / tabs)
echo [LAUNCH] Opening V.I.R.U.S. in Chrome App Mode...
start "" "chrome" --app=http://localhost:3000 --window-size=1280,800 --window-position=80,40 --no-first-run --disable-extensions

:done
echo.
echo [LAUNCH] V.I.R.U.S. is live. Good morning, sir.
echo.
endlocal
