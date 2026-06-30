param(
    [int]$SecopLimit = 80,
    [int]$CompranetLimit = 80,
    [switch]$NoPersistence
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$pythonExe = Join-Path $repoRoot '.venv313\Scripts\python.exe'
if (-not (Test-Path $pythonExe)) {
    throw 'No se encontro .venv313\\Scripts\\python.exe. Crea o activa el entorno Python 3.13 antes de ejecutar.'
}

$configPath = Join-Path $repoRoot 'config\config.json'
$tempConfigPath = Join-Path $repoRoot 'config\config.runtime.productive.json'

$config = Get-Content $configPath -Raw | ConvertFrom-Json
$config.sources.secop2.mode = 'online'
$config.sources.secop2.enabled = $true
$config.sources.secop2.limit = $SecopLimit

$config.sources.compranet.mode = 'online'
$config.sources.compranet.enabled = $true
$config.sources.compranet.limit = $CompranetLimit

$config.persistence.enabled = -not $NoPersistence.IsPresent

$config | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 $tempConfigPath

try {
    & $pythonExe main.py --config $tempConfigPath --enable-persistence --once
}
finally {
    if (Test-Path $tempConfigPath) {
        Remove-Item $tempConfigPath -Force
    }
}
