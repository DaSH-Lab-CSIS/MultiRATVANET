@echo off
REM ============================================================================
REM MultiRATVANET Build Script using OMNeT++ MinGW + MSYS2
REM ============================================================================

setlocal enabledelayedexpansion

cd /d "%~dp0.."
set "PROJECT_ROOT=%cd%"
set "SIMULATION_ROOT=%PROJECT_ROOT%\.."
set "OMNETPP_ROOT=%SIMULATION_ROOT%\omnetpp-5.6.1"
set "FRAMEWORK_DIR=%PROJECT_ROOT%\framework"
set "MSYS2_SHELL=%OMNETPP_ROOT%\tools\win64\msys2_shell.cmd"

echo.
echo ============================================================
echo   MultiRATVANET Build
echo ============================================================
echo.
echo Project: %PROJECT_ROOT%
echo Framework: %FRAMEWORK_DIR%
echo.

if not exist "%OMNETPP_ROOT%" (
    echo ERROR: Cannot find OMNeT++ at: %OMNETPP_ROOT%
    pause
    exit /b 1
)

if not exist "%MSYS2_SHELL%" (
    echo ERROR: Cannot find MSYS2 shell at: %MSYS2_SHELL%
    pause
    exit /b 1
)

REM BEST APPROACH: Use OMNeT++ IDE
echo.
echo RECOMMENDED: Use OMNeT++ IDE for building
echo   1. Open: %OMNETPP_ROOT%\bin\omnetpp.cmd
echo   2. File ^> Open Projects from File System
echo   3. Select: MultiRATVANET/framework
echo   4. Right-click framework ^> Build Project
echo.
echo.
echo OR manually open MSYS2 shell:
echo   "%MSYS2_SHELL%" -mingw64
echo.
echo Then in the shell:
echo   cd framework
echo   mingw32-make -f GNUmakefile -j4
echo.

REM Open MSYS2 shell for manual build
call "%MSYS2_SHELL%" -mingw64

endlocal

