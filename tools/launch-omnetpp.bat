@echo off
REM ============================================================================
REM Launch OMNeT++ IDE via external junction
REM ============================================================================
REM
REM This script launches OMNeT++ IDE using the external/ junction, keeping
REM everything organized and avoiding duplicate paths.
REM
REM Usage:
REM   .\launch-omnetpp.bat                (launch IDE)
REM   .\launch-omnetpp.bat shell          (open MinGW shell)
REM
REM ============================================================================

cd /d "%~dp0.."

if "%1" == "shell" (
    REM Open MinGW shell via mingwenv
    .\external\omnetpp-5.6.1\mingwenv.cmd
) else (
    REM Launch IDE
    .\external\omnetpp-5.6.1\bin\omnetpp.cmd
)
