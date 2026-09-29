@echo off
REM MultiRATVANET Build Script for Windows (MinGW)
REM Usage: build.bat [--test] [--clean]

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set ROOT_DIR=%SCRIPT_DIR:~0,-1%
set OMNETPP_BIN=%ROOT_DIR%\external\omnetpp-5.6.1\bin
set INET_DIR=%ROOT_DIR%\external\inet-4.2.2
set VEINS_DIR=%ROOT_DIR%\external\veins-5.2
set SIMU5G_DIR=%ROOT_DIR%\external\simu5g-1.1.0

echo.
echo === Building MultiRATVANET Framework ===
echo Root: %ROOT_DIR%
echo.

cd /d "%ROOT_DIR%\framework" || exit /b 1

REM Add OMNeT++ to PATH
set PATH=%OMNETPP_BIN%;%PATH%

REM Check if --clean flag is passed
if "%1"=="--clean" (
    echo Cleaning...
    if exist "out" rmdir /s /q out
    if exist "Makefile" del Makefile
    if exist "Makefile.inc" del Makefile.inc
    echo ✓ Cleaned
)

REM Check for opp_makemake
where opp_makemake >nul 2>&1
if errorlevel 1 (
    echo ERROR: opp_makemake not found!
    echo Please verify OMNeT++ path: %OMNETPP_BIN%
    exit /b 1
)

echo Generating Makefile...
opp_makemake -f --deep -O out ^
    -I "%INET_DIR%\src" ^
    -I "%VEINS_DIR%\src" ^
    -I "%SIMU5G_DIR%\src" ^
    -L "%INET_DIR%\src" ^
    -L "%VEINS_DIR%\src" ^
    -L "%SIMU5G_DIR%\src" || exit /b 1

echo Compiling (parallel build)...
mingw32-make -j4 || exit /b 1

if exist "out\libmultiratvanet.dll" (
    echo.
    echo ✓ Build successful
    echo Output: out\libmultiratvanet.dll
) else (
    echo ERROR: Build completed but output not found!
    exit /b 1
)

REM Run tests if --test flag
if "%1"=="--test" (
    echo.
    echo Running unit tests...
    cd "%ROOT_DIR%\tests\unit"
    mingw32-make -j4
)

endlocal
