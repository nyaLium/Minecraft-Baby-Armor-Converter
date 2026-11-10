@echo off
chcp 65001 >nul 2>nul
setlocal enabledelayedexpansion
title Baby Armor Converter
rem keep the caller's working directory so relative paths (dropped files/folders) still resolve
set "HERE=%~dp0"
set "PYTHONIOENCODING=utf-8"

rem ---- locate a Python interpreter -------------------------------------
rem 1) the bundled portable interpreter: nothing has to be installed
set "PYEXE="
set "PYARGS="
if exist "%HERE%_engine\python\python.exe" set "PYEXE=%HERE%_engine\python\python.exe"

rem 2) a normal Python installation
if not defined PYEXE (
    where py >nul 2>nul
    if not errorlevel 1 (
        set "PYEXE=py"
        set "PYARGS=-3"
    )
)
if not defined PYEXE (
    where python >nul 2>nul
    if not errorlevel 1 set "PYEXE=python"
)
if not defined PYEXE (
    if exist "%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" (
        set "PYEXE=%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
    )
)
if not defined PYEXE (
    echo.
    echo [ERROR] No Python found and the portable interpreter is missing.
    echo Expected here:  %HERE%_engine\python\python.exe
    echo.
    echo Re-extract the whole zip and keep the _engine folder next to this bat,
    echo or install Python 3 and add it to PATH.
    echo.
    pause
    exit /b 1
)

rem ---- Chinese Windows -> Chinese console (set ABC_EN=1 to force English) ----
set "LANGARG="
set "LOCALE="
for /f "tokens=2,*" %%A in ('reg query "HKCU\Control Panel\International" /v LocaleName 2^>nul ^| findstr /i "LocaleName"') do set "LOCALE=%%B"
if defined LOCALE if /i "!LOCALE:~0,2!"=="zh" set "LANGARG=--zh"
if defined ABC_EN set "LANGARG=--en"

rem ---- run the converter -------------------------------------------------
rem no argument -> the engine converts .\equipment
rem dropped folder(s) / png(s) -> those instead
"%PYEXE%" %PYARGS% -X utf8 "%HERE%_engine\babyfy.py" %LANGARG% %*
set "RC=%ERRORLEVEL%"

echo.
pause
endlocal & exit /b %RC%
