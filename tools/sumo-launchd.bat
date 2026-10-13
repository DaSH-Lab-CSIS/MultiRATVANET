@echo off
REM ============================================================================
REM MultiRATVANET - start the Veins SUMO launch daemon (Windows wrapper).
REM Runs tools\sumo-launchd.sh inside OMNeT++'s bundled MinGW bash.
REM
REM Usage: sumo-launchd.bat [PORT] [SUMO_BINARY]
REM   e.g. sumo-launchd.bat 9998 sumo-gui.exe   (default)
REM        sumo-launchd.bat 9998 sumo.exe       (headless)
REM ============================================================================
setlocal
pushd "%~dp0.."
set "BASH=..\omnetpp-5.6.1\tools\win64\usr\bin\bash.exe"
if not exist "%BASH%" (
    echo ERROR: bundled bash not found at %BASH%
    popd & endlocal & exit /b 1
)
set MSYSTEM=MINGW64
set CHERE_INVOKING=1
"%BASH%" -lc "bash tools/sumo-launchd.sh %1 %2"
popd
endlocal
