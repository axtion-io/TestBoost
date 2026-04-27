# TestBoost - Generate killer tests for surviving mutants
# Usage: tb-killer.ps1 <project_path> [--max-tests N] [--verbose]
param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$ProjectPath,
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$ExtraArgs
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
    python -m testboost killer $ProjectPath @ExtraArgs
    $exitCode = $LASTEXITCODE
} finally {
    Pop-Location
}

if ($exitCode -ne 0) {
    Write-Host ""
    Write-Host "[TESTBOOST_FAILED:exit_code=$exitCode:step=killer]"
    Write-Host "CRITICAL: TestBoost command 'killer' failed. Do NOT proceed with this step manually."
}

exit $exitCode
