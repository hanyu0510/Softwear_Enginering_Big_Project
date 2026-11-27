param([ValidateSet('setup','start','stop')][string]$Operation, [switch]$Reset)
$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot 'launcher.py'
$options = @($Operation)
if ($Reset) { $options += '--reset' }
$env:PYTHONUTF8 = '1'
if (Get-Command py.exe -ErrorAction SilentlyContinue) {
    & py.exe -3 $launcher @options
} elseif (Get-Command python.exe -ErrorAction SilentlyContinue) {
    & python.exe $launcher @options
} else {
    Write-Error 'Python 3.11-3.13 is required. See demo/README.md.'
}
exit $LASTEXITCODE
