@echo off
REM ============================================================================
REM MultiRATVANET - build the framework as a SHARED library (libmultiratvanet.dll)
REM Runs tools\build-so.sh inside OMNeT++'s bundled MinGW bash.
REM
REM Usage: build-so.bat [MODE]     MODE = release (default) | debug
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
"%BASH%" -lc "bash tools/build-so.sh %1"
popd
endlocal
