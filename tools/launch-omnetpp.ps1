# Launch OMNeT++ Build Environment
# PowerShell version

param([switch]$Shell = $false)

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
$SimulationRoot = Split-Path -Parent $ProjectRoot
$OmnetppRoot = Join-Path $SimulationRoot "omnetpp-5.6.1"

Write-Host ""
Write-Host "============================================================"
Write-Host "  OMNeT++ Build Environment"
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

Write-Host "Launching build environment..." -ForegroundColor Green
Write-Host ""
Write-Host "BUILD THE FRAMEWORK:"
Write-Host "  cd MultiRATVANET/framework"
Write-Host "  make -j4"
Write-Host ""
Write-Host "RUN A SIMULATION:"
Write-Host "  cd MultiRATVANET/simulations"
Write-Host "  omnetpp -u Cmdenv -c Highway_CoveragePriority omnetpp.ini"
Write-Host ""

# Launch mingwenv shell
& cmd /c "`"$MingwenvCmd`""
