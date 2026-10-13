@echo off
REM ============================================================================
REM MultiRATVANET Framework Build - Automated
REM ============================================================================

setlocal enabledelayedexpansion

cd /d "%~dp0"
set SCRIPT_DIR=%CD%

echo.
echo ============================================================
echo   MultiRATVANET Framework Build (Automated)
echo ============================================================
echo.
echo Project: %SCRIPT_DIR%
echo.

REM Check if mingwenv exists
if not exist "..\omnetpp-5.6.1\mingwenv.cmd" (
    echo ERROR: OMNeT++ 5.6.1 not found!
    echo Expected: %SCRIPT_DIR%\..\omnetpp-5.6.1\mingwenv.cmd
    exit /b 1
)

REM Check if framework directory exists
if not exist "framework" (
    echo ERROR: Framework directory not found!
    exit /b 1
)

REM Check if GNUmakefile exists
if not exist "framework\GNUmakefile" (
    echo ERROR: GNUmakefile not found in framework directory!
    exit /b 1
)

echo Building framework...
echo.

REM Create a temporary build script
set TEMP_SCRIPT=%TEMP%\multirat_build_%RANDOM%.sh
(
    echo #!/bin/bash
    echo set -e
    echo.
    echo echo "Navigating to framework directory..."
    echo cd /d/Desktop_PCBackup/Mari-Per/PhD_Research/Federated_Learning/Course_Work/Work@2026/Simulation/MultiRATVANET/framework
    echo.
    echo echo "Running: make -j4"
    echo make -j4
    echo.
    echo echo ""
    echo echo "=========================================================="
    echo echo "  BUILD COMPLETE"
    echo echo "=========================================================="
    echo if [ -f "out/libmultiratvanet.dll" ]; then
    echo   echo "✓ Output created: $(ls -lh out/libmultiratvanet.dll)"
    echo fi
) > "%TEMP_SCRIPT%"

REM Run the build via MSYS2
call ..\omnetpp-5.6.1\mingwenv.cmd bash "%TEMP_SCRIPT%"

REM Clean up
del /q "%TEMP_SCRIPT%" 2>nul

echo.
echo Done!
