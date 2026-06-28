param(
    [int]$Port = 8199,
    [string]$HostName = "127.0.0.1"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $codexPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path $codexPython) {
        $python = [pscustomobject]@{ Source = $codexPython }
    }
}

if (-not $python) {
    throw "Python was not found. Install Python or run from the Codex desktop runtime."
}

function Test-PortAvailable {
    param([string]$Address, [int]$PortNumber)

    $listener = $null
    try {
        $ipAddress = [System.Net.IPAddress]::Parse($Address)
        $listener = [System.Net.Sockets.TcpListener]::new($ipAddress, $PortNumber)
        $listener.Start()
        return $true
    } catch {
        return $false
    } finally {
        if ($listener) {
            $listener.Stop()
        }
    }
}

$selectedPort = $Port
while ($selectedPort -le ($Port + 50) -and -not (Test-PortAvailable -Address $HostName -PortNumber $selectedPort)) {
    Write-Host "Port $selectedPort is already in use, trying $($selectedPort + 1)..."
    $selectedPort++
}

if ($selectedPort -gt ($Port + 50)) {
    throw "No free port found between $Port and $($Port + 50)."
}

Write-Host "Starting Wacko Inc OS at http://$HostName`:$selectedPort/"
$runtimeDir = Join-Path $root ".wacko"
$runtimeFile = Join-Path $runtimeDir "dev-server.json"
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

$process = $null
try {
    $process = Start-Process `
        -FilePath $python.Source `
        -ArgumentList @("-m", "uvicorn", "api.main:app", "--host", $HostName, "--port", $selectedPort) `
        -WorkingDirectory $root `
        -NoNewWindow `
        -PassThru

    @{
        pid = $process.Id
        port = $selectedPort
        host = $HostName
        url = "http://$HostName`:$selectedPort/"
        started_at = (Get-Date).ToString("o")
    } | ConvertTo-Json | Set-Content -Path $runtimeFile -Encoding UTF8

    Write-Host "Press Ctrl+C or close this window to stop Wacko Inc OS and release port $selectedPort."
    Wait-Process -Id $process.Id
} finally {
    if ($process -and -not $process.HasExited) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path $runtimeFile) {
        Remove-Item -Path $runtimeFile -Force -ErrorAction SilentlyContinue
    }
}
