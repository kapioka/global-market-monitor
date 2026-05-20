param(
    [string]$Python = "py -3.13",
    [string]$Requirements = "project\requirements-lock.txt",
    [string]$OutputDir = ".tmp\pip-audit",
    [switch]$GenerateOnly
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$pythonParts = $Python -split "\s+"
$pythonExe = $pythonParts[0]
$pythonArgs = @()
if ($pythonParts.Count -gt 1) {
    $pythonArgs = $pythonParts[1..($pythonParts.Count - 1)]
}

& $pythonExe @pythonArgs "project\audit_requirements.py" --source $Requirements --output-dir $OutputDir
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$auditRequirements = Join-Path $OutputDir "requirements-lock.pip-audit.txt"
if ($GenerateOnly) {
    Write-Host "Generated pip-audit input only: $auditRequirements"
    exit 0
}

$auditAvailable = & $pythonExe @pythonArgs -c "import importlib.util; raise SystemExit(0 if importlib.util.find_spec('pip_audit') else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Error "pip-audit is not installed for '$Python'. Install it in the selected Python environment, then rerun this script. To only generate the filtered requirements, run with -GenerateOnly."
    exit 1
}

& $pythonExe @pythonArgs -m pip_audit -r $auditRequirements --no-deps
exit $LASTEXITCODE
