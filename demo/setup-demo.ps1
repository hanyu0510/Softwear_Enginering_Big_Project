param([switch]$Reset)
& (Join-Path $PSScriptRoot 'demo.ps1') setup -Reset:$Reset
exit $LASTEXITCODE
