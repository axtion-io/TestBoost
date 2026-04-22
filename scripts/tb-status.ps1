# TestBoost - Show current session status
# Usage: tb-status.ps1 <project_path>
param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$ProjectPath
)
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TestBoostRoot = Split-Path -Parent $ScriptDir

# Activate virtual environment
if (Test-Path "$TestBoostRoot\.venv\Scripts\Activate.ps1") {
    & "$TestBoostRoot\.venv\Scripts\Activate.ps1"
} elseif (Test-Path "$TestBoostRoot\venv\Scripts\Activate.ps1") {
    & "$TestBoostRoot\venv\Scripts\Activate.ps1"
}

Push-Location $TestBoostRoot
try {
    python -m testboost status $ProjectPath
    $exitCode = $LASTEXITCODE
} finally {
    Pop-Location
}

exit $exitCode
