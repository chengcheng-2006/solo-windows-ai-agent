# Solo Doctor — Prerequisites check
# Run this before setting up Solo

$script:ErrorActionPreference = 'Stop'
$script:PassCount = 0
$script:FailCount = 0

function Write-Check {
    param([string]$Name, [bool]$Pass, [string]$Detail)
    $icon = if ($Pass) { '✅' } else { '❌' }
    Write-Host "${icon} ${Name}: $Detail"
    if ($Pass) { $script:PassCount++ } else { $script:FailCount++ }
}

Write-Host "===== Solo Doctor Check =====" -ForegroundColor Cyan
Write-Host ""

# OS
Write-Check -Name "Windows" -Pass $true -Detail "Detected $([System.Environment]::OSVersion.VersionString)"

# PowerShell version
$psVer = $PSVersionTable.PSVersion
Write-Check -Name "PowerShell" -Pass ($psVer.Major -ge 5) -Detail "$psVer"

# Git
$gitVer = git --version 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Check -Name "Git" -Pass $true -Detail $gitVer
} else {
    Write-Check -Name "Git" -Pass $false -Detail "Not found in PATH"
}

# Python
$pyVer = python --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Check -Name "Python" -Pass $true -Detail "$pyVer"
} else {
    Write-Check -Name "Python" -Pass $false -Detail "Not found in PATH"
}

# Node.js
$nodeVer = node --version 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Check -Name "Node.js" -Pass $true -Detail $nodeVer
} else {
    Write-Check -Name "Node.js" -Pass $false -Detail "Not found in PATH"
}

# Docker (optional)
$dockerVer = docker --version 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Check -Name "Docker" -Pass $true -Detail $dockerVer
} else {
    Write-Check -Name "Docker" -Pass $false -Detail "Not found (optional)"
}

# .env file
$envFile = Join-Path $PSScriptRoot "..\.env.example"
if (Test-Path $envFile) {
    Write-Check -Name ".env.example" -Pass $true -Detail "Found"
} else {
    Write-Check -Name ".env.example" -Pass $false -Detail "Missing"
}

# C: drive space
$cDrive = Get-PSDrive C -ErrorAction SilentlyContinue
if ($cDrive) {
    $freeGB = [math]::Round($cDrive.Free / 1GB, 1)
    Write-Check -Name "C: disk space" -Pass ($freeGB -gt 5) -Detail "${freeGB} GB free"
}

Write-Host ""
Write-Host "===== Result: ${script:PassCount} pass, ${script:FailCount} fail =====" -ForegroundColor Cyan
if ($script:FailCount -gt 0) { exit 1 }
exit 0
