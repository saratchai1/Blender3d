[CmdletBinding()]
param(
    [switch]$Http,
    [int]$Port = 10849,
    [string]$HostAddress = "127.0.0.1",
    [switch]$Debug
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

function Import-DotEnv {
    param([string]$Path)
    if (-not (Test-Path $Path -PathType Leaf)) {
        return
    }
    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }
        $parts = $trimmed.Split("=", 2)
        [Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim().Trim('"'), "Process")
    }
}

Import-DotEnv -Path (Join-Path $RepoRoot ".env")

$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    $candidates = @(
        (Join-Path $env:USERPROFILE ".local\bin\uv.exe"),
        (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links\uv.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate -PathType Leaf) {
            $uv = Get-Item $candidate
            break
        }
    }
}
if (-not $uv) {
    throw "uv was not found. Run .\scripts\setup.ps1 first."
}

$uvPath = if ($uv.Source) { $uv.Source } else { $uv.FullName }
$argsList = @("--directory", $RepoRoot, "run", "blender3d-control")

if ($Http) {
    $argsList += @("--http", "--host", $HostAddress, "--port", "$Port")
} else {
    $argsList += "--stdio"
}
if ($Debug) {
    $argsList += "--debug"
}

& $uvPath @argsList
exit $LASTEXITCODE
