# Launch OMNeT++ IDE
# PowerShell version

param([switch]$Shell = $false)

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
$SimulationRoot = Split-Path -Parent $ProjectRoot
$OmnetppRoot = Join-Path $SimulationRoot "omnetpp-5.6.1"

Write-Host ""
Write-Host "============================================================"
Write-Host "  OMNeT++ IDE Launcher"
Write-Host "============================================================"
Write-Host ""
Write-Host "OMNeT++ Root: $OmnetppRoot"
Write-Host ""

# Verify OMNeT++ exists
if (-not (Test-Path $OmnetppRoot)) {
    Write-Host "ERROR: Cannot find OMNeT++ at: $OmnetppRoot" -ForegroundColor Red
    exit 1
}

$MingwenvCmd = Join-Path $OmnetppRoot "mingwenv.cmd"
if (-not (Test-Path $MingwenvCmd)) {
    Write-Host "ERROR: Cannot find mingwenv.cmd at: $MingwenvCmd" -ForegroundColor Red
    exit 1
}

Write-Host "Launching OMNeT++ environment..." -ForegroundColor Green
Write-Host ""
Write-Host "Inside the MSYS2 shell, run one of:"
Write-Host "  cd bin && omnetpp.cmd     (launch IDE)"
Write-Host "  bin/omnetpp.cmd           (launch IDE)"
Write-Host ""

# Launch mingwenv shell
& cmd /c "`"$MingwenvCmd`""
