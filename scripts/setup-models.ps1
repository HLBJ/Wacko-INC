param(
    [switch]$Fast
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    throw "Ollama was not found. Install Ollama first, then run this script again."
}

$models = if ($Fast) {
    @("qwen2.5:3b", "qwen2.5-coder:3b")
} else {
    @(
        $env:OLLAMA_MANAGER_MODEL,
        $env:OLLAMA_REVIEWER_MODEL,
        $env:OLLAMA_DEVELOPER_MODEL,
        $env:OLLAMA_SECURITY_MODEL,
        $env:OLLAMA_TESTING_MODEL
    ) | Where-Object { $_ }
}

if (-not $models -or $models.Count -eq 0) {
    $models = @("qwen2.5:3b", "qwen2.5-coder:3b")
}

$models = $models | Select-Object -Unique
foreach ($model in $models) {
    Write-Host "Installing Ollama model: $model"
    & $ollama.Source pull $model
}

Write-Host "Model setup complete."
