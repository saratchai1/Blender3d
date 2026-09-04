[CmdletBinding()]
param(
    [string]$BlenderExecutable = "",
    [switch]$NoPreview,
    [switch]$NoGlb
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Spec = Join-Path $RepoRoot "models\house_200sqm\house_spec.json"
$PascalGenerator = Join-Path $RepoRoot "models\house_200sqm\pascal\generate_scene.py"
$PascalValidator = Join-Path $RepoRoot "models\house_200sqm\pascal\validate_scene.py"
$BlenderBuilder = Join-Path $RepoRoot "models\house_200sqm\blender\build_house_v2.py"
$GeneratedDir = Join-Path $RepoRoot ".generated\house_200sqm"
$OutputDir = Join-Path $RepoRoot "models\house_200sqm\output"
$SceneJson = Join-Path $GeneratedDir "house_200sqm.pascal.json"
$BlendFile = Join-Path $OutputDir "house_200sqm.blend"
$GlbFile = Join-Path $OutputDir "house_200sqm.glb"
$PreviewFile = Join-Path $OutputDir "house_200sqm-preview.png"

New-Item -ItemType Directory -Force -Path $GeneratedDir | Out-Null
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    throw "uv was not found. Run .\scripts\setup.ps1 -InstallPrereqs first."
}

function Find-Blender {
    param([string]$ExplicitPath)
    if ($ExplicitPath) {
        if (-not (Test-Path $ExplicitPath -PathType Leaf)) { throw "Blender not found: $ExplicitPath" }
        return (Resolve-Path $ExplicitPath).Path
    }
    if ($env:BLENDER_EXECUTABLE -and (Test-Path $env:BLENDER_EXECUTABLE -PathType Leaf)) {
        return (Resolve-Path $env:BLENDER_EXECUTABLE).Path
    }
    $cmd = Get-Command blender -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $base = Join-Path $env:ProgramFiles "Blender Foundation"
    if (Test-Path $base) {
        $matches = @(Get-ChildItem -Path $base -Filter blender.exe -File -Recurse -ErrorAction SilentlyContinue | Sort-Object FullName -Descending)
        if ($matches.Count -gt 0) { return $matches[0].FullName }
    }
    return $null
}

$blender = Find-Blender -ExplicitPath $BlenderExecutable
if (-not $blender) {
    throw "Blender was not found. Run setup or pass -BlenderExecutable <path>."
}

Write-Host "1/3 Generate native Pascal scene graph"
& $uv.Source run python $PascalGenerator --spec $Spec --output $SceneJson
if ($LASTEXITCODE -ne 0) { throw "Pascal scene generation failed." }

Write-Host "2/3 Validate semantic graph and 200 sqm program"
& $uv.Source run python $PascalValidator $SceneJson
if ($LASTEXITCODE -ne 0) { throw "Pascal scene validation failed." }

Write-Host "3/3 Build Blender visual v2 model from the generated Pascal scene"
$builderArgs = @(
    "--background",
    "--python", $BlenderBuilder,
    "--",
    "--input", $SceneJson,
    "--output", $BlendFile
)
if (-not $NoGlb) { $builderArgs += @("--export-glb", $GlbFile) }
if (-not $NoPreview) { $builderArgs += @("--preview", $PreviewFile) }

& $blender @builderArgs
if ($LASTEXITCODE -ne 0) { throw "Blender house build failed (exit $LASTEXITCODE)." }

Write-Host ""
Write-Host "HOUSE 200 SQM VISUAL V2 BUILD COMPLETE"
Write-Host "Pascal scene: $SceneJson"
Write-Host "Blender:      $BlendFile"
if (-not $NoGlb) { Write-Host "GLB:          $GlbFile" }
if (-not $NoPreview) { Write-Host "Preview:      $PreviewFile" }
