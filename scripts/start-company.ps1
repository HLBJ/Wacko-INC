param(
    [int]$Port = 8199,
    [string]$HostName = "127.0.0.1",
    [switch]$StartOllama
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$startDev = Join-Path $PSScriptRoot "start-dev.ps1"

function Test-PortOpen {
    param([string]$Address, [int]$PortNumber)

    $client = $null
    try {
        $client = [System.Net.Sockets.TcpClient]::new()
        $connect = $client.BeginConnect($Address, $PortNumber, $null, $null)
        if (-not $connect.AsyncWaitHandle.WaitOne(500)) {
            return $false
        }
        $client.EndConnect($connect)
        return $true
    } catch {
        return $false
    } finally {
        if ($client) {
            $client.Close()
        }
    }
}

Set-Location $root

if ($StartOllama -and -not (Test-PortOpen -Address "127.0.0.1" -PortNumber 11434)) {
    $ollama = Get-Command ollama -ErrorAction SilentlyContinue
    if ($ollama) {
        Write-Host "Starting Ollama in the background..."
        Start-Process -FilePath $ollama.Source -ArgumentList @("serve") -WindowStyle Hidden | Out-Null
        Start-Sleep -Seconds 3
    } else {
        Write-Host "Ollama command was not found. Start Ollama manually when you want agents to run."
    }
}

Write-Host "Launching Wacko Inc OS. Agent workflows need Ollama; dashboard and deterministic checks do not."
& $startDev -Port $Port -HostName $HostName
