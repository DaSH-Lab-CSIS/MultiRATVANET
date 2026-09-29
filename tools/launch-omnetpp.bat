@echo off
REM ============================================================================
REM Launch OMNeT++ IDE using mingwenv
REM ============================================================================

cd /d "%~dp0..\.."
set OMNETPP_ROOT=%CD%\omnetpp-5.6.1

echo.
echo ============================================================
echo   Launching OMNeT++ Environment
echo ============================================================
echo.
echo OMNeT++ Root: %OMNETPP_ROOT%
echo.
echo After the shell opens, you can:
echo   - Run: bin\omnetpp.cmd         (to launch IDE)
echo   - Or run: make -j4              (to build)
echo.

REM Launch mingwenv to set up environment
call "%OMNETPP_ROOT%\mingwenv.cmd"




