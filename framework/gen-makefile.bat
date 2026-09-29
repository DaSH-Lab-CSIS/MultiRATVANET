@echo off
REM Phase 8 - Generate Makefile for MultiRATVANET Framework
REM This script runs opp_makemake to generate proper OMNeT++ Makefiles

setlocal enabledelayedexpansion

set OMNETPP_ROOT=D:\Desktop_PCBackup\Mari-Per\PhD_Research\Federated_Learning\Course_Work\Work@2026\Simulation\omnetpp-5.6.1
set OMNETPP_BIN=%OMNETPP_ROOT%\bin

if not exist "%OMNETPP_BIN%\opp_makemake.cmd" (
    echo ERROR: opp_makemake not found at %OMNETPP_BIN%
    echo Please verify OMNeT++ is installed at: %OMNETPP_ROOT%
    exit /b 1
)

echo.
echo === Phase 8: Makefile Generation ===
echo.
echo OMNeT++ Path: %OMNETPP_ROOT%
echo opp_makemake: %OMNETPP_BIN%\opp_makemake.cmd
echo.

REM Set PATH to include OMNeT++ tools
set PATH=%OMNETPP_BIN%;%PATH%

REM Clean old Makefile
if exist "Makefile" del Makefile
if exist "Makefile.inc" del Makefile.inc

echo Running opp_makemake...
echo.

REM Run opp_makemake with full paths to frameworks
call "%OMNETPP_BIN%\opp_makemake.cmd" -f --deep -O out ^
    -I "D:\Desktop_PCBackup\Mari-Per\PhD_Research\Federated_Learning\Course_Work\Work@2026\Simulation\inet-4.2.2-src\inet4\src" ^
    -I "D:\Desktop_PCBackup\Mari-Per\PhD_Research\Federated_Learning\Course_Work\Work@2026\Simulation\veins-5.2\veins-veins-5.2\src" ^
    -I "D:\Desktop_PCBackup\Mari-Per\PhD_Research\Federated_Learning\Course_Work\Work@2026\Simulation\Simu5G-1.1.0\Simu5G-1.1.0\src" ^
    -L "D:\Desktop_PCBackup\Mari-Per\PhD_Research\Federated_Learning\Course_Work\Work@2026\Simulation\inet-4.2.2-src\inet4\src" ^
    -L "D:\Desktop_PCBackup\Mari-Per\PhD_Research\Federated_Learning\Course_Work\Work@2026\Simulation\veins-5.2\veins-veins-5.2\src" ^
    -L "D:\Desktop_PCBackup\Mari-Per\PhD_Research\Federated_Learning\Course_Work\Work@2026\Simulation\Simu5G-1.1.0\Simu5G-1.1.0\src"

if errorlevel 1 (
    echo ERROR: opp_makemake failed
    exit /b 1
)

echo.
echo === Makefile Generated Successfully ===
echo.
echo Generated files:
if exist "Makefile" (
    echo   ✓ Makefile
) else (
    echo   ✗ Makefile NOT FOUND
    exit /b 1
)

if exist "Makefile.inc" (
    echo   ✓ Makefile.inc
)

echo.
echo Next: Run build.bat to compile the framework
echo.

endlocal
