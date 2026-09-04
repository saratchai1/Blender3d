param(
    [string]$Destination = ".external/pascal"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$lockPath = Join-Path $repoRoot "integrations/pascal/pascal-lock.json"
$destinationRoot = if ([System.IO.Path]::IsPathRooted($Destination)) {
    $Destination
} else {
    Join-Path $repoRoot $Destination
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "git is required. Install Git and run this script again."
}

if (-not (Test-Path $lockPath)) {
    throw "Pascal lock file not found: $lockPath"
}

$lock = Get-Content $lockPath -Raw | ConvertFrom-Json
New-Item -ItemType Directory -Path $destinationRoot -Force | Out-Null

foreach ($component in $lock.components) {
    $name = [string]$component.name
    $repository = [string]$component.repository
    $commit = [string]$component.commit

    if ($repository -notmatch '^https://github\.com/pascalorg/[A-Za-z0-9._-]+\.git$') {
        throw "Refusing unexpected Pascal repository URL for '$name': $repository"
    }

    if ($commit -notmatch '^[0-9a-fA-F]{40}$') {
        throw "Invalid pinned commit for '$name': $commit"
    }

    $target = Join-Path $destinationRoot $name
    Write-Host "`n[$name] $repository @ $commit"

    if (-not (Test-Path $target)) {
        git clone --filter=blob:none --no-checkout $repository $target
        if ($LASTEXITCODE -ne 0) { throw "git clone failed for $name" }
    } else {
        if (-not (Test-Path (Join-Path $target ".git"))) {
            throw "Destination exists but is not a Git repository: $target"
        }

        $origin = (git -C $target remote get-url origin).Trim()
        if ($LASTEXITCODE -ne 0 -or $origin -ne $repository) {
            throw "Existing checkout '$target' has unexpected origin '$origin'. Expected '$repository'."
        }
    }

    git -C $target fetch --depth 1 origin $commit
    if ($LASTEXITCODE -ne 0) { throw "git fetch failed for $name @ $commit" }

    git -C $target checkout --detach $commit
    if ($LASTEXITCODE -ne 0) { throw "git checkout failed for $name @ $commit" }

    $actual = (git -C $target rev-parse HEAD).Trim()
    if ($actual -ne $commit) {
        throw "Commit verification failed for $name. Expected $commit, got $actual"
    }

    Write-Host "[$name] READY: $actual"
}

Write-Host "`nPascal snapshots are ready under: $destinationRoot"
Write-Host "They are local development checkouts and are intentionally not committed to Blender3d."
