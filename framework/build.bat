@echo off
REM Build script for MultiRATVANET Framework
REM Requires MSYS2 MinGW environment

cd /d "%~dp0"

echo ==========================================
echo MultiRATVANET Framework Build
echo ==========================================
echo.

REM Run build in MSYS2 MinGW shell
call ..\..\..\omnetpp-5.6.1\tools\win64\msys2_shell.cmd -mingw64 -c "cd framework && bash build_and_log.sh && exit"

if %errorlevel% equ 0 (
    echo.
    echo ==========================================
    echo BUILD COMPLETED SUCCESSFULLY
    echo ==========================================
    dir /s out\libmultiratvanet.dll
) else (
    echo.
    echo ==========================================
    echo BUILD FAILED
    echo ==========================================
    exit /b %errorlevel%
)
