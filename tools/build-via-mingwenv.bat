@echo off
REM ============================================================================
REM MultiRATVANET Build Script Using OMNeT++ mingwenv.cmd Approach
REM ============================================================================
REM
REM This script builds MultiRATVANET using the OMNeT++ embedded MinGW/MSYS2
REM environment setup (same as mingwenv.cmd).
REM
REM Usage:
REM   .\tools\build-via-mingwenv.bat              (build in current window)
REM   .\tools\build-via-mingwenv.bat -interactive (open MSYS2 shell after build)
REM   .\tools\build-via-mingwenv.bat -shell       (open MSYS2 shell for manual build)
REM
REM ============================================================================

setlocal enabledelayedexpansion

REM Get the OMNeT++ root - resolve parent directory properly
for /f "tokens=*" %%i in ('cd') do set "PROJECT_ROOT=%%i"

REM Calculate paths using pushd/popd for proper resolution
pushd "%PROJECT_ROOT%\.."
for /f "tokens=*" %%i in ('cd') do set "SIMULATION_ROOT=%%i"
popd

set "OMNETPP_ROOT=%SIMULATION_ROOT%\omnetpp-5.6.1"
set "MSYS2_SHELL=%OMNETPP_ROOT%\tools\win64\msys2_shell.cmd"

echo.
echo ============================================================
echo   MultiRATVANET Build via OMNeT++ mingwenv Approach
echo ============================================================
echo.

REM Verify OMNeT++ is available
if not exist "%OMNETPP_ROOT%" (
    echo ERROR: Cannot find OMNeT++ at: %OMNETPP_ROOT%
    echo.
    echo Expected structure:
    echo   .../Simulation/
    echo     -- MultiRATVANET/
    echo        -- framework/
    echo     -- omnetpp-5.6.1/        (Should be here)
    echo     -- inet-4.2.2-src/
    echo     -- sumo-1_24_0/
    echo.
    pause
    exit /b 1
)

if not exist "%MSYS2_SHELL%" (
    echo ERROR: Cannot find MSYS2 shell at: %MSYS2_SHELL%
    pause
    exit /b 1
)

echo [1/3] OMNeT++ root: %OMNETPP_ROOT%
echo [1/3] MSYS2 shell: %MSYS2_SHELL%
echo [2/3] Project root: %PROJECT_ROOT%
echo [3/3] Building in: %PROJECT_ROOT%\framework
echo.

REM Check for -shell flag (open MSYS2 without building)
if "%1" == "-shell" (
    echo Opening MSYS2 MinGW shell for manual build...
    echo.
    echo Inside shell, run:
    echo   cd framework
    echo   mingw32-make -f GNUmakefile -j4
    echo.
    call "%MSYS2_SHELL%" -mingw64
    exit /b 0
)

REM Run the build via MSYS2 shell
REM The -c flag runs a command in the shell (non-interactive mode)
echo Running build...
echo.

call "%MSYS2_SHELL%" -mingw64 -c "cd '%PROJECT_ROOT%\framework' && mingw32-make -f GNUmakefile -j4"

REM Capture exit code
set BUILD_EXIT_CODE=!ERRORLEVEL!

echo.
echo.
if !BUILD_EXIT_CODE! == 0 (
    echo ============================================================
    echo   SUCCESS: Build completed successfully!
    echo ============================================================
    echo.
    echo Output: framework\out\libmultiratvanet.dll
    
    REM Verify DLL was created
    if exist "framework\out\libmultiratvanet.dll" (
        for /F "usebackq" %%A in ('framework\out\libmultiratvanet.dll') do set "DLL_SIZE=%%~zA"
        echo Size: !DLL_SIZE! bytes
        if !DLL_SIZE! GTR 500000 (
            echo Status: Ready for simulation ✓
        )
    )
    echo.
    echo Next step: .\tools\run.bat Highway_CoveragePriority 70s
) else (
    echo ╔══════════════════════════════════════════════════════════════╗
    echo ║  ❌ BUILD FAILED (exit code: !BUILD_EXIT_CODE!)             ║
    echo ╚══════════════════════════════════════════════════════════════╝
    echo.
    echo Troubleshooting:
    echo   1. Check error messages above
    echo   2. Verify framework\GNUmakefile exists
    echo   3. Verify external\ junctions are accessible
    echo   4. Try: .\tools\build-via-mingwenv.bat -shell
    echo      Then run: mingw32-make -f GNUmakefile -j4 (verbose)
)

echo.

REM Check for -interactive flag (keep shell open after build)
if "%1" == "-interactive" (
    echo Opening MSYS2 shell for inspection...
    echo.
    call "%MSYS2_SHELL%" -mingw64
)

exit /b !BUILD_EXIT_CODE!
