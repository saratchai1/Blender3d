[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

if (Test-Path (Join-Path $RepoRoot ".env")) {
    foreach ($line in Get-Content (Join-Path $RepoRoot ".env")) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }
        $parts = $trimmed.Split("=", 2)
        [Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim().Trim('"'), "Process")
    }
}

$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    $candidate = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links\uv.exe"
    if (Test-Path $candidate -PathType Leaf) {
        $uv = Get-Item $candidate
    }
}
if (-not $uv) {
    throw "uv was not found. Run .\scripts\setup.ps1 first."
}

$uvPath = if ($uv.Source) { $uv.Source } else { $uv.FullName }
Write-Host "Installing pinned KIRI 3DGS Render 5.1.0 for Blender 5.1+ ..."
Write-Host "The release package is about 771 MB and is cached after checksum verification."

& $uvPath --directory $RepoRoot run blender3d-control --install-3dgs
if ($LASTEXITCODE -ne 0) {
    throw "3DGS installation failed. Run .\scripts\doctor.ps1 and inspect the error above."
}

Write-Host "3DGS installation command completed."
Write-Host "Run .\scripts\doctor.ps1 to verify that Blender registers the KIRI import operator."
