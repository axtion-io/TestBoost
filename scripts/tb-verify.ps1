# TestBoost - Verify an integrity token
# Usage: tb-verify.ps1 <project_path> <token>
param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$ProjectPath,
    [Parameter(Mandatory=$true, Position=1)]
    [string]$Token
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
    python -m testboost verify $ProjectPath $Token
    $exitCode = $LASTEXITCODE
} finally {
    Pop-Location
}

exit $exitCode
