#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

$sourceConfig = Join-Path $PSScriptRoot "config.alloy"
$bookmarkDirectory = Join-Path $env:ProgramData "GrafanaLabs\Alloy\data\bookmarks"

function Get-AlloyServiceCommand {
    $service = Get-CimInstance -ClassName Win32_Service -Filter "Name='Alloy'" -ErrorAction SilentlyContinue
    if (-not $service) {
        return $null
    }

    $match = [regex]::Match(
        $service.PathName,
        '^\s*(?:"(?<executable>[^"]+)"|(?<executable>\S+))\s+run\s+(?:"(?<config>[^"]+)"|(?<config>\S+))'
    )
    if (-not $match.Success) {
        throw "The existing Alloy service command could not be interpreted: $($service.PathName)"
    }

    $executable = [Environment]::ExpandEnvironmentVariables($match.Groups["executable"].Value)
    $config = [Environment]::ExpandEnvironmentVariables($match.Groups["config"].Value)
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

$serviceCommand = Get-AlloyServiceCommand
if (-not $serviceCommand) {
    $alloyExe = Find-AlloyExecutable
}

if (-not $serviceCommand -and -not $alloyExe) {
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        throw "Alloy is not installed and winget.exe is unavailable."
    }

    Write-Host "Alloy is not installed. Installing it with WinGet..."
    & winget.exe install --id GrafanaLabs.Alloy --exact --silent --accept-package-agreements --accept-source-agreements
    $wingetExitCode = $LASTEXITCODE
    $serviceCommand = Get-AlloyServiceCommand
    if (-not $serviceCommand) {
        throw "WinGet did not make Alloy available (exit code $wingetExitCode)."
    }
}

if (-not $serviceCommand) {
    throw "Alloy is installed, but its Windows service is not registered."
}

$alloyExe = $serviceCommand.Executable
$targetConfig = $serviceCommand.Config

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

& $alloyExe validate $sourceConfig
if ($LASTEXITCODE -ne 0) {
    throw "Alloy rejected the configuration."
}

New-Item -ItemType Directory -Path $bookmarkDirectory -Force | Out-Null
Copy-Item -LiteralPath $sourceConfig -Destination $targetConfig -Force
Restart-Service -Name "Alloy"

$service = Get-Service -Name "Alloy"
if ($service.Status -ne "Running") {
    throw "Alloy did not return to the Running state."
}

Write-Host "Alloy is running with the AD1 observability configuration."
