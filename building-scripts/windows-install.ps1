param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CommandArgs
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = if ($env:PYTHON) { $env:PYTHON } else { "python" }

function Invoke-Manage {
    param([string[]]$ArgsToPass)
    & $python "$scriptDir\manage.py" @ArgsToPass
    exit $LASTEXITCODE
}

function Ask-YesNo {
    param(
        [string]$Prompt,
        [bool]$DefaultYes = $false
    )
    while ($true) {
        $suffix = if ($DefaultYes) { "[Y/n]" } else { "[y/N]" }
        $raw = Read-Host "$Prompt $suffix"
        if ([string]::IsNullOrWhiteSpace($raw)) {
            return $DefaultYes
        }
        switch -Regex ($raw.Trim().ToLowerInvariant()) {
            "^(y|yes)$" { return $true }
            "^(n|no)$" { return $false }
            default { Write-Host "Please answer y or n." }
        }
    }
}

if ($CommandArgs.Count -gt 0) {
    Invoke-Manage -ArgsToPass $CommandArgs
}

Write-Host "PulseWave-11 Windows Setup"
Write-Host "1) test"
Write-Host "2) install"
Write-Host "3) upgrade"
Write-Host "4) update"
Write-Host "5) uninstall"
Write-Host "6) doctor"
$choice = Read-Host "Choose an option [1-6]"

switch ($choice) {
    "1" {
        $manageArgs = @("test")
        if (Ask-YesNo -Prompt "Build with native extension?" -DefaultYes:$false) {
            $manageArgs += "--with-native"
        }
        Invoke-Manage -ArgsToPass $manageArgs
    }
    "2" {
        $manageArgs = @("install")
        Write-Host "Install location:"
        Write-Host "1) local bin (default: ~/.local/bin)"
        Write-Host "2) custom location"
        $locChoice = Read-Host "Choose [1-2]"
        if ($locChoice -eq "2") {
            $customBin = Read-Host "Enter custom bin directory"
            if ([string]::IsNullOrWhiteSpace($customBin)) {
                Write-Error "Custom bin directory cannot be empty."
                exit 1
            }
            $manageArgs += @("--bin-dir", $customBin)
        }
        if (-not (Ask-YesNo -Prompt "Add install directory to PATH?" -DefaultYes:$true)) {
            $manageArgs += "--no-path"
        }
        if (Ask-YesNo -Prompt "Build with native extension?" -DefaultYes:$false) {
            $manageArgs += "--with-native"
        }
        if (Ask-YesNo -Prompt "Skip build and use existing dist binary?" -DefaultYes:$false) {
            $manageArgs += "--skip-build"
        }
        Invoke-Manage -ArgsToPass $manageArgs
    }
    "3" {
        $manageArgs = @("upgrade")
        if (Ask-YesNo -Prompt "Use custom bin directory override?" -DefaultYes:$false) {
            $customBin = Read-Host "Enter custom bin directory"
            if ([string]::IsNullOrWhiteSpace($customBin)) {
                Write-Error "Custom bin directory cannot be empty."
                exit 1
            }
            $manageArgs += @("--bin-dir", $customBin)
        }
        if (-not (Ask-YesNo -Prompt "Update PATH during upgrade?" -DefaultYes:$true)) {
            $manageArgs += "--no-path"
        }
        if (Ask-YesNo -Prompt "Build with native extension?" -DefaultYes:$false) {
            $manageArgs += "--with-native"
        }
        if (Ask-YesNo -Prompt "Skip build and use existing dist binary?" -DefaultYes:$false) {
            $manageArgs += "--skip-build"
        }
        Invoke-Manage -ArgsToPass $manageArgs
    }
    "4" {
        $manageArgs = @("update")
        if (Ask-YesNo -Prompt "Sync repo with git pull before update?" -DefaultYes:$false) {
            $manageArgs += "--sync-repo"
            $gitRemote = Read-Host "Git remote [origin]"
            if ([string]::IsNullOrWhiteSpace($gitRemote)) { $gitRemote = "origin" }
            $manageArgs += @("--remote", $gitRemote)
            $gitBranch = Read-Host "Git branch (optional, blank for default)"
            if (-not [string]::IsNullOrWhiteSpace($gitBranch)) {
                $manageArgs += @("--branch", $gitBranch)
            }
        }
        Write-Host "Install location:"
        Write-Host "1) existing/default location"
        Write-Host "2) custom location"
        $locChoice = Read-Host "Choose [1-2]"
        if ($locChoice -eq "2") {
            $customBin = Read-Host "Enter custom bin directory"
            if ([string]::IsNullOrWhiteSpace($customBin)) {
                Write-Error "Custom bin directory cannot be empty."
                exit 1
            }
            $manageArgs += @("--bin-dir", $customBin)
        }
        if (-not (Ask-YesNo -Prompt "Update PATH during update?" -DefaultYes:$true)) {
            $manageArgs += "--no-path"
        }
        if (Ask-YesNo -Prompt "Build with native extension?" -DefaultYes:$false) {
            $manageArgs += "--with-native"
        }
        if (Ask-YesNo -Prompt "Skip build and use existing dist binary?" -DefaultYes:$false) {
            $manageArgs += "--skip-build"
        }
        Invoke-Manage -ArgsToPass $manageArgs
    }
    "5" {
        $manageArgs = @("uninstall")
        if (Ask-YesNo -Prompt "Use custom bin directory?" -DefaultYes:$false) {
            $customBin = Read-Host "Enter custom bin directory"
            if ([string]::IsNullOrWhiteSpace($customBin)) {
                Write-Error "Custom bin directory cannot be empty."
                exit 1
            }
            $manageArgs += @("--bin-dir", $customBin)
        }
        if (Ask-YesNo -Prompt "Keep PATH unchanged?" -DefaultYes:$false) {
            $manageArgs += "--keep-path"
        }
        if (Ask-YesNo -Prompt "Purge config directory too?" -DefaultYes:$false) {
            $manageArgs += "--purge-config"
        }
        Invoke-Manage -ArgsToPass $manageArgs
    }
    "6" {
        Invoke-Manage -ArgsToPass @("doctor")
    }
    default {
        Write-Error "Invalid option: $choice"
        exit 1
    }
}
