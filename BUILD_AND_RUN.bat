@echo off
REM Build and Launch OMNeT++ Simulation Script
REM This script builds the MultiRATVANET framework and launches OMNeT++ IDE

setlocal enabledelayedexpansion

set ROOT=d:\Desktop_PCBackup\Mari-Per\PhD_Research\Federated_Learning\Course_Work\Work@2026\Simulation
set FRAMEWORK_DIR=%ROOT%\MultiRATVANET\framework
set OMNETPP_DIR=%ROOT%\omnetpp-5.6.1
set SIMULATIONS_DIR=%ROOT%\MultiRATVANET\simulations

echo.
echo ====================================================
echo  MultiRATVANET Build and Launch Script
echo ====================================================
echo.
echo Root Dir:       %ROOT%
echo Framework Dir:  %FRAMEWORK_DIR%
echo OMNeT++ Dir:    %OMNETPP_DIR%
echo.

REM Step 1: Build Framework
echo [1/3] Building MultiRATVANET Framework DLL...
echo ====================================================
cd /d %FRAMEWORK_DIR%

REM Launch MSYS2 bash to run make
%OMNETPP_DIR%\tools\win64\msys2_shell.cmd -mingw64 -here -c "make clean && make -j4"

if exist "%FRAMEWORK_DIR%\out\libmultiratvanet.dll" (
    echo.
    echo [SUCCESS] libmultiratvanet.dll created!
    echo Location: %FRAMEWORK_DIR%\out\libmultiratvanet.dll
) else (
    echo.
    echo [ERROR] Build failed - DLL not created!
    echo Check build_new.log for details.
    pause
    exit /b 1
)

echo.
echo [2/3] Setting OMNeT++ environment...
echo ====================================================

REM Set OMNeT++ environment
set PATH=%OMNETPP_DIR%\bin;%PATH%
set OMNETPP_ROOT=%OMNETPP_DIR%

echo.
echo [3/3] Launching OMNeT++ IDE...
echo ====================================================
echo Opening OMNeT++ with simulations project...
echo.

REM Launch OMNeT++ IDE pointing to simulations directory
cd /d %SIMULATIONS_DIR%
start "" "%OMNETPP_DIR%\bin\omnetpp.cmd"

echo.
echo OMNeT++ is launching...
echo.
echo Next steps in OMNeT++ IDE:
echo   1. File > Open Project > Select the simulations folder
echo   2. Right-click project > Build Project
echo   3. In simulation folder, open omnetpp.ini
echo   4. Select a configuration (e.g., Highway_LowLatency)
echo   5. Click Run or Run in GUI mode (debug icon)
echo.
pause
