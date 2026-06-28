param(
    [int]$Port = 8199
)

$root = Split-Path -Parent $PSScriptRoot
$runtimeFile = Join-Path (Join-Path $root ".wacko") "dev-server.json"

if (Test-Path $runtimeFile) {
    try {
        $server = Get-Content -Path $runtimeFile -Raw | ConvertFrom-Json
        if ($server.pid) {
            $process = Get-Process -Id $server.pid -ErrorAction SilentlyContinue
            if ($process) {
                Write-Host "Stopping Wacko Inc OS $($process.ProcessName) ($($server.pid)) at $($server.url)..."
                Stop-Process -Id $server.pid -Force
            }
        }
    } finally {
        Remove-Item -Path $runtimeFile -Force -ErrorAction SilentlyContinue
    }
}

$connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if (-not $connections) {
    Write-Host "No listener found on port $Port."
    exit 0
}

$processIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($processId in $processIds) {
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($process) {
        Write-Host "Stopping $($process.ProcessName) ($processId) on port $Port..."
        Stop-Process -Id $processId -Force
    }
}
