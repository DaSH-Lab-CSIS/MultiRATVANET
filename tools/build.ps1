# Build MultiRATVANET using OMNeT++ mingwenv approach
# PowerShell version

param(
    [switch]$Shell = $false,
    [switch]$Clean = $false
)

Write-Host ""
Write-Host "============================================================"
Write-Host "  MultiRATVANET Build via OMNeT++ mingwenv"
Write-Host "============================================================"
Write-Host ""

# Get paths
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$PROJECT_ROOT = (Get-Item $SCRIPT_DIR).Parent.FullName
$SIMULATION_ROOT = (Get-Item $PROJECT_ROOT).Parent.FullName
$OMNETPP_ROOT = Join-Path $SIMULATION_ROOT "omnetpp-5.6.1"
$MSYS2_SHELL = Join-Path $OMNETPP_ROOT "tools\win64\msys2_shell.cmd"
$FRAMEWORK_DIR = Join-Path $PROJECT_ROOT "framework"

Write-Host "[1/4] Project: $PROJECT_ROOT"
Write-Host "[2/4] Framework: $FRAMEWORK_DIR"
Write-Host "[3/4] OMNeT++: $OMNETPP_ROOT"
Write-Host ""

# Verify paths
if (-not (Test-Path $OMNETPP_ROOT)) {
    Write-Host "ERROR: Cannot find OMNeT++ at: $OMNETPP_ROOT" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $MSYS2_SHELL)) {
    Write-Host "ERROR: Cannot find MSYS2 at: $MSYS2_SHELL" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $FRAMEWORK_DIR)) {
    Write-Host "ERROR: Cannot find framework at: $FRAMEWORK_DIR" -ForegroundColor Red
    exit 1
}

Write-Host "Paths verified!" -ForegroundColor Green
Write-Host ""

# Handle shell flag
if ($Shell) {
    Write-Host "Opening MSYS2 MinGW shell..."
    Write-Host ""
    Write-Host "Run inside shell:"
    Write-Host "  cd framework"
    Write-Host "  mingw32-make -f GNUmakefile -j4"
    Write-Host ""
    & cmd /c "`"$MSYS2_SHELL`" -mingw64"
    exit 0
}

# Convert Windows path to MSYS2 path format
function Convert-ToMSYSPath {
    param([string]$Path)
    $Path = $Path -replace '\\', '/'
    $Path = $Path -replace '^([A-Z]):', { ("/" + [char]::ToLower($args[0].Groups[1].Value)) }
    return $Path
}

$FRAMEWORK_MSYS = Convert-ToMSYSPath $FRAMEWORK_DIR

Write-Host "Running build..."
Write-Host ""

# Build command with MSYS2 path format
$BUILD_CMD = "cd '$FRAMEWORK_MSYS' && mingw32-make -f GNUmakefile -j4"

# Run build
& cmd /c "`"$MSYS2_SHELL`" -mingw64 -c `"$BUILD_CMD`""
$BUILD_EXIT = $LASTEXITCODE

Write-Host ""
Write-Host ""

if ($BUILD_EXIT -eq 0) {
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  SUCCESS: Build completed!" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    
    $DLL_PATH = Join-Path $FRAMEWORK_DIR "out\libmultiratvanet.dll"
    if (Test-Path $DLL_PATH) {
        $DLL_SIZE = (Get-Item $DLL_PATH).Length
        Write-Host "Output: $DLL_PATH"
        Write-Host "Size: $DLL_SIZE bytes"
        
        if ($DLL_SIZE -gt 500000) {
            Write-Host "Status: Ready for simulation!" -ForegroundColor Green
        }
    } else {
        Write-Host "WARNING: DLL not found at expected location" -ForegroundColor Yellow
        Write-Host "Check: $FRAMEWORK_DIR\out\"
    }
    
    Write-Host ""
    Write-Host "Next: .\tools\run.bat Highway_CoveragePriority 70s"
    Write-Host ""
} else {
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host "  FAILED: Build did not complete" -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Try:"
    Write-Host "  .\tools\build.ps1 -Shell"
    Write-Host "Then in the shell:"
    Write-Host "  cd framework"
    Write-Host "  mingw32-make -f GNUmakefile -j4"
    Write-Host ""
}

exit $BUILD_EXIT

