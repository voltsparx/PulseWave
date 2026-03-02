param(
    [switch]$WithNative
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if ($WithNative) {
    python "$root\\build\\package.py" --with-native
} else {
    python "$root\\build\\package.py"
}

