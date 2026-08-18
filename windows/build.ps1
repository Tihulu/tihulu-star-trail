param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

$BuildRoot = Join-Path $RepoRoot "build\windows"
$DistRoot = Join-Path $RepoRoot "release-dist"
$SpecRoot = Join-Path $BuildRoot "spec"
$WorkRoot = Join-Path $BuildRoot "work"
$IconPath = Join-Path $BuildRoot "tihulu-star-trail.ico"

Remove-Item -Recurse -Force $BuildRoot -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $BuildRoot, $DistRoot, $SpecRoot, $WorkRoot | Out-Null

& $Python -c "from PIL import Image; image=Image.open(r'src/tihulu_star_trail/assets/tihulu-star-trail.png').convert('RGBA'); image.save(r'$IconPath', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"
if ($LASTEXITCODE -ne 0) { throw "Could not create the Windows icon." }

$Version = (& $Python -c "import tihulu_star_trail; print(tihulu_star_trail.__version__)").Trim()
if (-not $Version) { throw "Could not determine the application version." }

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "Tihulu Star Trail" `
    --icon $IconPath `
    --collect-data tihulu_star_trail `
    --collect-all imageio_ffmpeg `
    --hidden-import rawpy `
    --distpath $DistRoot `
    --workpath $WorkRoot `
    --specpath $SpecRoot `
    release/desktop_entry.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }

$BuiltExe = Join-Path $DistRoot "Tihulu Star Trail.exe"
$ReleaseExe = Join-Path $DistRoot "Tihulu-Star-Trail-$Version-windows-x86_64.exe"
if (-not (Test-Path $BuiltExe)) { throw "Expected executable was not created: $BuiltExe" }
Move-Item -Force $BuiltExe $ReleaseExe

Write-Host "Built $ReleaseExe"
