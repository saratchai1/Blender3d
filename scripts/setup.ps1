[CmdletBinding()]
param(
    [switch]$InstallPrereqs,
    [string]$BlenderExecutable = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

function Resolve-Executable {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [string[]]$Candidates = @()
    )

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    foreach ($candidate in $Candidates) {
        if ($candidate -and (Test-Path $candidate -PathType Leaf)) {
            return (Resolve-Path $candidate).Path
        }
    }
    return $null
}

function Install-WingetPackage {
    param([Parameter(Mandatory = $true)][string]$Id)

    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "winget is not available. Install the prerequisite manually: $Id"
    }

    Write-Host "Installing $Id ..."
    & winget install --id $Id --exact --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "winget failed while installing $Id (exit $LASTEXITCODE)."
    }
}

function Find-Blender {
    param([string]$ExplicitPath = "")

    if ($ExplicitPath) {
        if (-not (Test-Path $ExplicitPath -PathType Leaf)) {
            throw "Blender executable does not exist: $ExplicitPath"
        }
        return (Resolve-Path $ExplicitPath).Path
    }

    if ($env:BLENDER_EXECUTABLE -and (Test-Path $env:BLENDER_EXECUTABLE -PathType Leaf)) {
        return (Resolve-Path $env:BLENDER_EXECUTABLE).Path
    }

    $command = Get-Command blender -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $base = Join-Path $env:ProgramFiles "Blender Foundation"
    if (Test-Path $base) {
        $matches = Get-ChildItem -Path $base -Filter blender.exe -File -Recurse -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending
        if ($matches.Count -gt 0) {
            return $matches[0].FullName
        }
    }

    return $null
}

$gitCandidates = @(
    "C:\Program Files\Git\cmd\git.exe",
    "C:\Program Files\Git\bin\git.exe"
)
$uvCandidates = @(
    (Join-Path $env:USERPROFILE ".local\bin\uv.exe"),
    (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links\uv.exe")
)

$git = Resolve-Executable -Name "git" -Candidates $gitCandidates
if (-not $git -and $InstallPrereqs) {
    Install-WingetPackage -Id "Git.Git"
    $git = Resolve-Executable -Name "git" -Candidates $gitCandidates
}
if (-not $git) {
    throw "Git was not found. Re-run with -InstallPrereqs or install Git manually."
}

$gitDir = Split-Path $git -Parent
if (($env:PATH -split ';') -notcontains $gitDir) {
    $env:PATH = "$gitDir;$env:PATH"
}

$uv = Resolve-Executable -Name "uv" -Candidates $uvCandidates
if (-not $uv -and $InstallPrereqs) {
    Install-WingetPackage -Id "astral-sh.uv"
    $uv = Resolve-Executable -Name "uv" -Candidates $uvCandidates
}
if (-not $uv) {
    throw "uv was not found. Re-run with -InstallPrereqs or install uv manually."
}

$blender = Find-Blender -ExplicitPath $BlenderExecutable
if (-not $blender -and $InstallPrereqs) {
    Install-WingetPackage -Id "BlenderFoundation.Blender"
    $blender = Find-Blender
}
if (-not $blender) {
    Write-Warning "Blender was not found. MCP dependencies will still be installed, but Blender tools cannot run yet."
} else {
    $env:BLENDER_EXECUTABLE = $blender
    $blenderDir = Split-Path $blender -Parent
    if (($env:PATH -split ';') -notcontains $blenderDir) {
        $env:PATH = "$blenderDir;$env:PATH"
    }
    Write-Host "Blender: $blender"
}

Write-Host "Syncing the pinned Python environment ..."
& $uv sync
if ($LASTEXITCODE -ne 0) {
    throw "uv sync failed (exit $LASTEXITCODE)."
}

$envLines = @("PYTHONUNBUFFERED=1")
if ($blender) {
    $envLines = @("BLENDER_EXECUTABLE=$blender") + $envLines
}
if (-not (Test-Path (Join-Path $RepoRoot ".env"))) {
    $envLines | Set-Content -Path (Join-Path $RepoRoot ".env") -Encoding UTF8
}

$serverEnv = @{ PYTHONUNBUFFERED = "1" }
if ($blender) {
    $serverEnv["BLENDER_EXECUTABLE"] = $blender
}

$config = @{
    mcpServers = @{
        blender3d = @{
            command = $uv
            args = @(
                "--directory",
                $RepoRoot,
                "run",
                "blender3d-control",
                "--stdio"
            )
            env = $serverEnv
        }
    }
}
$config | ConvertTo-Json -Depth 10 | Set-Content -Path (Join-Path $RepoRoot ".mcp.generated.json") -Encoding UTF8

if ($blender) {
    Write-Host "Running Blender MCP compatibility check ..."
    & $uv --directory $RepoRoot run blender3d-control --check-blender
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "The upstream Blender health check returned exit $LASTEXITCODE. Run .\scripts\doctor.ps1 for details."
    }
}

Write-Host ""
Write-Host "Setup complete."
Write-Host "Generated MCP config: $RepoRoot\.mcp.generated.json"
Write-Host "Start stdio MCP:       .\scripts\start.ps1"
Write-Host "Install KIRI 3DGS:     .\scripts\install-3dgs.ps1"
Write-Host "Run diagnostics:       .\scripts\doctor.ps1"
