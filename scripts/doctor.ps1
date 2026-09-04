[CmdletBinding()]
param()

$ErrorActionPreference = "Continue"
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

function Find-Blender {
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

Import-DotEnv -Path (Join-Path $RepoRoot ".env")
$coreOk = $true
$threeDgsOk = $false

Write-Host "=== Blender3d Control Doctor ==="
Write-Host "Repo: $RepoRoot"
Write-Host ""

$git = Get-Command git -ErrorAction SilentlyContinue
if ($git) {
    & $git.Source --version
} else {
    Write-Host "FAIL: git not found"
    $coreOk = $false
}

$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    $uvCandidate = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links\uv.exe"
    if (Test-Path $uvCandidate -PathType Leaf) {
        $uv = Get-Item $uvCandidate
    }
}
if ($uv) {
    $uvPath = if ($uv.Source) { $uv.Source } else { $uv.FullName }
    & $uvPath --version
} else {
    Write-Host "FAIL: uv not found"
    $coreOk = $false
}

$blender = Find-Blender
if ($blender) {
    $env:BLENDER_EXECUTABLE = $blender
    Write-Host "Blender executable: $blender"
    & $blender --version | Select-Object -First 3
} else {
    Write-Host "FAIL: Blender not found. Set BLENDER_EXECUTABLE or run setup with -InstallPrereqs."
    $coreOk = $false
}

if ($uv) {
    Write-Host ""
    Write-Host "Checking Python packages ..."
    & $uvPath --directory $RepoRoot run python -c "import blender3d_control, blender_mcp; print('blender3d_control=' + blender3d_control.__version__); print('blender_mcp_import=OK')"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAIL: Python package import check failed"
        $coreOk = $false
    }
}

if ($uv -and $blender) {
    Write-Host ""
    Write-Host "Checking upstream Blender MCP discovery ..."
    $blenderDir = Split-Path $blender -Parent
    if (($env:PATH -split ';') -notcontains $blenderDir) {
        $env:PATH = "$blenderDir;$env:PATH"
    }
    & $uvPath --directory $RepoRoot run blender3d-control --check-blender
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARN: upstream --check-blender returned $LASTEXITCODE"
    }
}

if ($blender) {
    Write-Host ""
    Write-Host "Checking Blender-side KIRI/3DGS operators ..."
    & $blender --background --python (Join-Path $RepoRoot "blender\check_3dgs.py")
    if ($LASTEXITCODE -eq 0) {
        $threeDgsOk = $true
        Write-Host "3DGS: READY"
    } elseif ($LASTEXITCODE -eq 2) {
        Write-Host "3DGS: NOT READY - run .\scripts\install-3dgs.ps1, then re-run doctor."
    } else {
        Write-Host "3DGS: CHECK FAILED (exit $LASTEXITCODE)"
    }
}

Write-Host ""
Write-Host "=== Summary ==="
Write-Host ("Core MCP: " + $(if ($coreOk) { "READY" } else { "NOT READY" }))
Write-Host ("KIRI 3DGS: " + $(if ($threeDgsOk) { "READY" } else { "NOT READY" }))

if (-not $coreOk) {
    exit 1
}
if (-not $threeDgsOk) {
    exit 2
}
exit 0
