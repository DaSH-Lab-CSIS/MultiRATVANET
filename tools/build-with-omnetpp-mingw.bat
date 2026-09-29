@echo off
REM Build script using embedded OMNeT++ MinGW toolchain
REM This script sets up the environment to use the MinGW included with OMNeT++

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set ROOT_DIR=%SCRIPT_DIR%..
set OMNETPP_ROOT=D:\Desktop_PCBackup\Mari-Per\PhD_Research\Federated_Learning\Course_Work\Work@2026\Simulation\omnetpp-5.6.1

echo.
echo === MultiRATVANET Build Using OMNeT++ Embedded MinGW ===
echo.
echo Root: %ROOT_DIR%
echo OMNeT++: %OMNETPP_ROOT%
echo.

REM Setup MinGW paths from embedded OMNeT++ installation
set MINGW_BIN=%OMNETPP_ROOT%\tools\win64\mingw64\bin
set MINGW_LIB=%OMNETPP_ROOT%\tools\win64\mingw64\lib
set PATH=%MINGW_BIN%;%OMNETPP_ROOT%\bin;%PATH%

echo MinGW bin: %MINGW_BIN%
echo.

REM Verify compiler is available
echo Checking compiler...
"%MINGW_BIN%\g++.exe" --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: g++ not found at %MINGW_BIN%\g++.exe
    exit /b 1
)
echo ✓ Compiler found: g++.exe
echo.

REM Change to framework directory
cd /d "%ROOT_DIR%\framework" || exit /b 1

REM Clean if requested
if "%1"=="--clean" (
    echo Cleaning...
    if exist "out" rmdir /s /q out >nul
    echo ✓ Cleaned
    echo.
)

REM Display make version
echo Make version:
"%MINGW_BIN%\mingw32-make.exe" --version 2>nul || "make.exe" --version 2>nul || echo WARNING: make not found
echo.

REM Run make with proper environment
echo Starting build...
echo.

"%MINGW_BIN%\mingw32-make.exe" -f GNUmakefile -j4

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    echo.
    exit /b 1
)

echo.
echo ✓ Build successful!
echo Output: %ROOT_DIR%\framework\out\libmultiratvanet.dll
echo.
