# TestBoost - Agent mode: write one generation prompt per gap (or per surviving-mutant class with --killer)
# Usage: tb-context.ps1 <project_path> [--files ...] [--killer] [--verbose]
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

if (-not (Test-Path -LiteralPath $ProjectPath)) {
    Write-Host "Error: project path not found: $ProjectPath"
    exit 1
}
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path

Push-Location $TestBoostRoot
try {
    python -m testboost context $ProjectPath @ExtraArgs
    $exitCode = $LASTEXITCODE
} finally {
    Pop-Location
}

if ($exitCode -ne 0) {
    Write-Host ""
    Write-Host "[TESTBOOST_FAILED:exit_code=$exitCode:step=context]"
    Write-Host "CRITICAL: TestBoost command 'context' failed. Do NOT proceed with this step manually."
}

exit $exitCode
