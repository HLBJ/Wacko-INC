param(
    [switch]$SkipPytest
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = Get-Command python -ErrorAction SilentlyContinue
$node = Get-Command node -ErrorAction SilentlyContinue

$codexPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$codexNode = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"

if (-not $python -and (Test-Path $codexPython)) {
    $python = [pscustomobject]@{ Source = $codexPython }
}
if (-not $node -and (Test-Path $codexNode)) {
    $node = [pscustomobject]@{ Source = $codexNode }
}

if (-not $python) {
    throw "Python was not found."
}
if (-not $node) {
    throw "Node.js was not found."
}

Write-Host "Checking Python syntax..."
& $python.Source -m compileall api services database agents llm.py

Write-Host "Checking JavaScript syntax..."
& $node.Source --check api\static\app.js

Write-Host "Checking FastAPI import..."
& $python.Source -c "from api.main import app; print(app.title)"

if (-not $SkipPytest -and (Test-Path "tests")) {
    Write-Host "Running pytest..."
    & $python.Source -m pytest
}

Write-Host "All checks passed."
