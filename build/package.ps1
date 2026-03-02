param(
    [switch]$WithNative,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = if ($env:PYTHON) { $env:PYTHON } else { "python" }
$cmdArgs = @("$root\\build\\package.py")

if ($WithNative) {
    $cmdArgs += "--with-native"
}

if ($ExtraArgs) {
    $cmdArgs += $ExtraArgs
}

& $python @cmdArgs
exit $LASTEXITCODE
