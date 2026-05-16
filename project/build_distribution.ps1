$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$buildRoot = Join-Path $projectRoot "build"
$distRoot = Join-Path $projectRoot "dist"
$releaseRoot = Join-Path $projectRoot "release"
$appName = "GlobalMarketMonitor"
$packageRoot = Join-Path $releaseRoot "$appName-win64"
$zipPath = Join-Path $releaseRoot "$appName-win64.zip"
$runnerRoot = Join-Path $buildRoot "pyinstaller-runner"
$excludes = @(
  "pytest",
  "_pytest",
  "hypothesis",
  "torch",
  "torchvision",
  "torchaudio",
  "onnxruntime",
  "tensorflow",
  "tensorboard",
  "cv2",
  "moviepy",
  "imageio",
  "imageio_ffmpeg",
  "av",
  "openpyxl",
  "PIL",
  "tkinter"
)

function Resolve-PythonCommand {
  $candidates = @(
    @{ Command = "py"; Arguments = @("-3") },
    @{ Command = "python"; Arguments = @() }
  )

  foreach ($candidate in $candidates) {
    $resolved = Get-Command $candidate.Command -ErrorAction SilentlyContinue
    if ($null -ne $resolved) {
      return $candidate
    }
  }

  throw "Python launcher was not found. Install Python 3 and ensure 'py' or 'python' is available in PATH."
}

New-Item -ItemType Directory -Force -Path $buildRoot, $distRoot, $releaseRoot, $runnerRoot | Out-Null

$pyiArgs = @(
  "-m", "PyInstaller",
  "--noconfirm",
  "--clean",
  "--onedir",
  "--name", $appName,
  "--distpath", $distRoot,
  "--workpath", $buildRoot,
  "--specpath", $buildRoot,
  "--add-data", "$PSScriptRoot\config.yaml;project"
)
foreach ($module in $excludes) {
  $pyiArgs += "--exclude-module"
  $pyiArgs += $module
}
$pyiArgs += "$PSScriptRoot\main.py"

$python = Resolve-PythonCommand

Push-Location $runnerRoot
try {
  & $python.Command @($python.Arguments + $pyiArgs)
}
finally {
  Pop-Location
}

if (Test-Path $packageRoot) {
  Remove-Item $packageRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $packageRoot | Out-Null

$builtAppRoot = Join-Path $distRoot $appName
Copy-Item (Join-Path $builtAppRoot "*") $packageRoot -Recurse -Force
New-Item -ItemType Directory -Force -Path (Join-Path $packageRoot "project") | Out-Null
Copy-Item (Join-Path $PSScriptRoot "config.yaml") (Join-Path $packageRoot "project\config.yaml") -Force
Copy-Item (Join-Path $PSScriptRoot "README.md") (Join-Path $packageRoot "README.md") -Force

if (Test-Path $zipPath) {
  Remove-Item $zipPath -Force
}
Compress-Archive -Path (Join-Path $packageRoot "*") -DestinationPath $zipPath -Force

Write-Host "Package directory: $packageRoot"
Write-Host "Zip archive: $zipPath"
