# Stop Solo demo — Clean up demo workspace

$ErrorActionPreference = 'Stop'
$demoDirs = Get-ChildItem -Path $env:TEMP -Directory -Filter "solo-demo-*" -ErrorAction SilentlyContinue

if ($demoDirs) {
    foreach ($d in $demoDirs) {
        Remove-Item -Path $d.FullName -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "Cleaned up: $($d.Name)"
    }
} else {
    Write-Host "No demo workspaces found."
}

Write-Host "Demo stopped."
exit 0
