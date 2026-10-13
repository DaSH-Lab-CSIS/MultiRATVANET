@echo off
REM ============================================================================
REM MultiRATVANET - launch the simulation in the OMNeT++ GUI (Qtenv).
REM Runs tools\run-gui.sh inside OMNeT++'s bundled MinGW bash.
REM
REM Start the SUMO daemon first (sumo-launchd.bat), then:
REM   run-gui.bat                        (opens Qtenv; pick a config)
REM   run-gui.bat MultiRatHighway_Base   (opens Qtenv on that config)
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
"%BASH%" -lc "bash tools/run-gui.sh %1 %2 %3 %4"
popd
endlocal
