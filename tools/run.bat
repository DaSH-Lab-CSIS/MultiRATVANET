@echo off
REM MultiRATVANET Run Script for Windows
REM Usage: run.bat <CONFIG_NAME> [SIM_TIME]
REM Example: run.bat Highway_CoveragePriority 70s

setlocal enabledelayedexpansion

if "%1"=="" (
    echo Usage: run.bat ^<CONFIG_NAME^> [SIM_TIME]
    echo.
    echo Available configs:
    echo   Highway_CoveragePriority
    echo   Highway_Ensemble
    echo   Highway_ML
    echo   UrbanGrid_Base
    echo   UrbanGrid_CoveragePriority
    echo   UrbanGrid_Ensemble
    echo   ElectronicCity_Base
    echo   ElectronicCity_CoveragePriority
    echo.
    exit /b 1
)

set CONFIG=%1
set SIM_TIME=%2
if "!SIM_TIME!"=="" set SIM_TIME=100s
set SUMO_PORT=9998

set ROOT_DIR=%~dp0..

echo Launching OMNeT++ simulation: !CONFIG!
echo Simulation time: !SIM_TIME!
echo.

REM Create results directory
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a%%b)
set TIMESTAMP=!mydate!_!mytime!
set RESULTS_DIR=!ROOT_DIR!\results\!CONFIG!_!TIMESTAMP!
mkdir "!RESULTS_DIR!" 2>nul

REM Save config snapshot
copy "!ROOT_DIR!\simulations\omnetpp.ini" "!RESULTS_DIR!\run-settings.ini" >nul

REM Run simulation
cd /d "!ROOT_DIR!"
"!ROOT_DIR!\framework\out\libmultiratvanet.dll" ^
    -c "!CONFIG!" ^
    -u Cmdenv ^
    -n "simulations:framework\src" ^
    --sim-time-limit="!SIM_TIME!" ^
    -r 0 ^
    **.vector-recording=true ^
    **.scalar-recording=true

echo.
echo ✓ Simulation complete
echo Results: !RESULTS_DIR!

endlocal
