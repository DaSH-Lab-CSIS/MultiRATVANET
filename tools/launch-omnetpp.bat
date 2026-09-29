@echo off
REM ============================================================================
REM Launch OMNeT++ Build Environment using mingwenv
REM ============================================================================

cd /d "%~dp0..\.."
set OMNETPP_ROOT=%CD%\omnetpp-5.6.1

echo.
echo ============================================================
echo   OMNeT++ Build Environment
echo ============================================================
echo.
echo OMNeT++ Root: %OMNETPP_ROOT%
echo.
echo Inside the shell that opens, build the framework with:
echo.
echo   cd MultiRATVANET/framework
echo   make -j4
echo.
echo Or run a simulation:
echo.
echo   cd MultiRATVANET/simulations
echo   omnetpp -u Cmdenv -c Highway_CoveragePriority omnetpp.ini
echo.

REM Launch mingwenv to set up build environment
call "%OMNETPP_ROOT%\mingwenv.cmd"




