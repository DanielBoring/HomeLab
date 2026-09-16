#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

$sourceConfig = Join-Path $PSScriptRoot "config.alloy"
$bookmarkDirectory = Join-Path $env:ProgramData "GrafanaLabs\Alloy\data\bookmarks"

function Get-AlloyServiceCommand {
    $service = Get-CimInstance -ClassName Win32_Service -Filter "Name='Alloy'" -ErrorAction SilentlyContinue
    if (-not $service) {
        return $null
    }

    $directCommandMatch = [regex]::Match(
        $service.PathName,
        '^\s*(?:"(?<executable>[^"]+)"|(?<executable>\S+))\s+run\s+(?:"(?<config>[^"]+)"|(?<config>\S+))'
    )
    if ($directCommandMatch.Success) {
        $executable = [Environment]::ExpandEnvironmentVariables($directCommandMatch.Groups["executable"].Value)
        $config = [Environment]::ExpandEnvironmentVariables($directCommandMatch.Groups["config"].Value)
    }
    else {
        $wrapperMatch = [regex]::Match(
            $service.PathName,
            '^\s*(?:"(?<executable>[^"]+)"|(?<executable>\S+))\s*$'
        )
        if (-not $wrapperMatch.Success) {
            throw "The existing Alloy service command could not be interpreted: $($service.PathName)"
        }

        $wrapperExecutable = [Environment]::ExpandEnvironmentVariables($wrapperMatch.Groups["executable"].Value)
        if ([IO.Path]::GetFileName($wrapperExecutable) -ne "alloy-service-windows-amd64.exe") {
            throw "The existing Alloy service command does not include a run configuration: $($service.PathName)"
        }
        if (-not (Test-Path -LiteralPath $wrapperExecutable)) {
            throw "The existing Alloy service references a missing service wrapper: $wrapperExecutable"
        }

        $registryPath = "Registry::HKEY_LOCAL_MACHINE\SOFTWARE\GrafanaLabs\Alloy"
        try {
            $registryKey = Get-Item -LiteralPath $registryPath -ErrorAction Stop
            $executable = [Environment]::ExpandEnvironmentVariables([string]$registryKey.GetValue($null))
            $arguments = @($registryKey.GetValue("Arguments"))
        }
        catch {
            throw "The Alloy service wrapper configuration could not be read from HKLM\SOFTWARE\GrafanaLabs\Alloy: $($_.Exception.Message)"
        }

        $runIndex = [Array]::IndexOf($arguments, "run")
        if ([string]::IsNullOrWhiteSpace($executable) -or $runIndex -lt 0 -or $runIndex + 1 -ge $arguments.Count) {
            throw "The Alloy service wrapper registry command does not contain an executable and run configuration."
        }

        $config = [Environment]::ExpandEnvironmentVariables([string]$arguments[$runIndex + 1])
        if ([string]::IsNullOrWhiteSpace($config) -or $config.StartsWith("-")) {
            throw "The Alloy service wrapper registry command has an invalid run configuration path."
        }
    }

    if (-not (Test-Path -LiteralPath $executable)) {
        throw "The existing Alloy service references a missing executable: $executable"
    }

    return @{
        Executable = $executable
        Config     = $config
    }
}

function Find-AlloyExecutable {
    foreach ($candidate in @(
        (Join-Path $env:ProgramFiles "GrafanaLabs\Alloy\alloy-windows-amd64.exe"),
        (Join-Path $env:ProgramFiles "GrafanaLabs\Alloy\alloy.exe")
    )) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    foreach ($commandName in @("alloy-windows-amd64.exe", "alloy.exe")) {
        $command = Get-Command $commandName -ErrorAction SilentlyContinue
        if ($command) {
            return $command.Source
        }
    }

    return $null
}

function Install-AlloyRelease {
    param(
        [string] $Reason
    )

    $alloyVersion = "1.19.2"
    $installerPath = Join-Path $env:TEMP "alloy-installer-windows-amd64-$alloyVersion.exe"
    $installerUrl = "https://github.com/grafana/alloy/releases/download/v$alloyVersion/alloy-installer-windows-amd64.exe"

    Write-Host "$Reason Installing Alloy $alloyVersion..."
    try {
        Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing
        $signature = Get-AuthenticodeSignature -LiteralPath $installerPath
        if ($signature.Status -ne "Valid" -or $signature.SignerCertificate.Subject -notlike "CN=Grafana Labs,*") {
            throw "The downloaded Alloy installer does not have a valid Grafana Labs signature."
        }

        $installer = Start-Process -FilePath $installerPath -ArgumentList "/S" -Wait -PassThru
        if ($installer.ExitCode -ne 0) {
            throw "The Alloy $alloyVersion installer failed with exit code $($installer.ExitCode)."
        }
    }
    finally {
        Remove-Item -LiteralPath $installerPath -Force -ErrorAction SilentlyContinue
    }
}

$serviceCommand = Get-AlloyServiceCommand
if (-not $serviceCommand) {
    $alloyExe = Find-AlloyExecutable
}

if (-not $serviceCommand -and -not $alloyExe) {
    Install-AlloyRelease -Reason "Alloy is not installed."
    $serviceCommand = Get-AlloyServiceCommand
    if (-not $serviceCommand) {
        throw "The Alloy installer did not register the Windows service."
    }
}

if (-not $serviceCommand) {
    throw "Alloy is installed, but its Windows service is not registered."
}

$alloyExe = $serviceCommand.Executable
$targetConfig = $serviceCommand.Config

& $alloyExe --version
$alloyStartExitCode = $LASTEXITCODE
if ($alloyStartExitCode -eq -1073741515) {
    Install-AlloyRelease -Reason "The installed Alloy binary cannot start because of the v1.19.0 Windows DLL packaging issue."
    $serviceCommand = Get-AlloyServiceCommand
    if (-not $serviceCommand) {
        throw "The Alloy service was not available after the upgrade."
    }

    $alloyExe = $serviceCommand.Executable
    $targetConfig = $serviceCommand.Config
    & $alloyExe --version
    if ($LASTEXITCODE -ne 0) {
        throw "Alloy still cannot start after the upgrade (exit code $LASTEXITCODE)."
    }
}
elseif ($alloyStartExitCode -ne 0) {
    throw "The installed Alloy executable could not start (exit code $alloyStartExitCode)."
}

if (-not (Test-Path -LiteralPath $sourceConfig)) {
    throw "Configuration file not found at $sourceConfig."
}

foreach ($endpoint in @(
    @{ Name = "Loki"; Port = 3100 },
    @{ Name = "Alloy Prometheus receiver"; Port = 9999 }
)) {
    $connection = Test-NetConnection -ComputerName "10.0.5.10" -Port $endpoint.Port -WarningAction SilentlyContinue
    if (-not $connection.TcpTestSucceeded) {
        throw "$($endpoint.Name) is not reachable at 10.0.5.10:$($endpoint.Port)."
    }
}

$validationOutput = & $alloyExe validate $sourceConfig 2>&1
$validationExitCode = $LASTEXITCODE
$validationOutput | ForEach-Object { Write-Host $_ }
if ($validationExitCode -ne 0) {
    throw "Alloy rejected the configuration (exit code $validationExitCode)."
}

New-Item -ItemType Directory -Path $bookmarkDirectory -Force | Out-Null
Copy-Item -LiteralPath $sourceConfig -Destination $targetConfig -Force
Restart-Service -Name "Alloy"

$service = Get-Service -Name "Alloy"
if ($service.Status -ne "Running") {
    throw "Alloy did not return to the Running state."
}

Write-Host "Alloy is running with the AD1 observability configuration."
