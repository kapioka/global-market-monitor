param(
    [switch]$InstallTools,
    [switch]$Strict,
    [switch]$SkipDependencyAudit,
    [switch]$AllowProtectedDecisionDiff,
    [string]$ExpectedTag = "",
    [string]$Python = "python"
)

$ErrorActionPreference = "Continue"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$securityDir = Join-Path $repoRoot ".tmp\security"
New-Item -ItemType Directory -Force $securityDir | Out-Null

$summary = [ordered]@{
    generated_at = (Get-Date).ToString("s")
    repo_root = $repoRoot.Path
    strict = [bool]$Strict
    allow_protected_decision_diff = [bool]$AllowProtectedDecisionDiff
    expected_tag = $ExpectedTag
    publish_readiness = "pass"
    blockers = @()
    warnings = @()
    tools = [ordered]@{}
    checks = [ordered]@{}
    outputs = [ordered]@{}
    affects_push = $false
}

function Add-Blocker {
    param([string]$Message)
    $script:summary.blockers += $Message
    $script:summary.publish_readiness = "fail"
}

function Add-Warning {
    param([string]$Message)
    $script:summary.warnings += $Message
}

function Test-Tool {
    param([string]$Name)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) {
        $summary.tools[$Name] = @{ status = "available"; path = $cmd.Source }
        return $true
    }
    $summary.tools[$Name] = @{ status = "missing" }
    return $false
}

function Invoke-Capture {
    param(
        [string]$Name,
        [string]$OutputPath,
        [scriptblock]$Command
    )
    $ErrorActionPreference = "Continue"
    $out = & $Command 2>&1
    $code = $LASTEXITCODE
    if ($null -eq $code) { $code = 0 }
    $out | Set-Content -Encoding UTF8 $OutputPath
    $summary.outputs[$Name] = $OutputPath
    return @{ exit_code = $code; output = @($out) }
}

function Invoke-GitGrep {
    param(
        [string]$Name,
        [string]$Pattern,
        [string]$OutputFile
    )
    $result = Invoke-Capture $Name $OutputFile { git grep -n -I -E $Pattern }
    $lines = @($result.output | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    return @{ exit_code = $result.exit_code; lines = $lines }
}

function ConvertTo-JsonFile {
    param([object]$Value, [string]$Path)
    $Value | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 $Path
    $summary.outputs[(Split-Path $Path -Leaf)] = $Path
}

if ($InstallTools) {
    $installLog = Join-Path $securityDir "install-security-tools.txt"
    $install = Invoke-Capture "install_tools" $installLog { & $Python -m pip install -r requirements-security.txt }
    if ($install.exit_code -ne 0) {
        Add-Warning "Failed to install Python security tools from requirements-security.txt. Continuing with available tools."
    }
}

$statusShort = @(git status --short)
$tagsAtHead = @(git tag --points-at HEAD)
$headFuller = @(git log -1 --format=fuller)
$metadata = @(git log --all --format="%h %an <%ae> | %cn <%ce>" | Sort-Object -Unique)
$emailHits = @(git log --all --format="%ae%n%ce" | Select-String -Pattern "personal-mail-domain-placeholder|personal-user-placeholder" -CaseSensitive:$false)

$gitInfo = [ordered]@{
    status_short = $statusShort
    tags_at_head = $tagsAtHead
    head = $headFuller
    metadata = $metadata
    personal_email_hits = @($emailHits | ForEach-Object { $_.Line })
}
$summary.checks.git_metadata = $gitInfo
ConvertTo-JsonFile $gitInfo (Join-Path $securityDir "git-metadata.json")

if ($statusShort.Count -gt 0) {
    Add-Warning "Working tree is not clean during audit."
}
if (-not [string]::IsNullOrWhiteSpace($ExpectedTag) -and $tagsAtHead -notcontains $ExpectedTag) {
    Add-Blocker "$ExpectedTag tag does not point at HEAD."
}
if ($emailHits.Count -gt 0) {
    Add-Blocker "Personal email metadata was found in git history."
}

$secretPattern = "api[_-]?key|secret|token|password|passwd|bearer|authorization|cookie|client_secret|private[_-]?key|access[_-]?key|refresh[_-]?token|OPENAI_API_KEY|ALPHA_VANTAGE|FRED_API_KEY|GITHUB_TOKEN|AWS_ACCESS_KEY|AWS_SECRET|GOOGLE_APPLICATION_CREDENTIALS" # pragma: allowlist secret
$strongSecretPattern = "\b" + "sk-" + "[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{20,}|gh[pousr]_[A-Za-z0-9_]{20,}|BEGIN (RSA |EC |OPENSSH |DSA |)?PRIVATE KEY|AKIA[0-9A-Z]{16}"
$pathPattern = "[A-Z]:\\|Users\\|personal-user-placeholder|personal-mail-domain-placeholder|Desktop|Downloads|OneDrive|AppData|\.env|\.pfx|\.pem|\.key|\.crt"
$timesfmPattern = "TimesFM|timesfm|times_fm|forecast_support|overblock_suspicion|special_case_risk|forecast_disagreement"
$investmentPattern = "\u8CB7\u3048|\u8CB7\u3046\u3079\u304D|\u5FC5\u305A|guaranteed|guarantee|profit|\u5132\u304B\u308B|\u52DD\u3066\u308B|\u6295\u8CC7\u52A9\u8A00|\u81EA\u52D5\u58F2\u8CB7|execute trade|order|broker|\u58F2\u8CB7\u6307\u793A|\u6210\u529F\u78BA\u7387"

if (Test-Tool "gitleaks") {
    $gitleaksGit = Join-Path $securityDir "gitleaks-git-history.json"
    $gitleaksDir = Join-Path $securityDir "gitleaks-working-tree.json"
    $gitResult = Invoke-Capture "gitleaks_git" $gitleaksGit { gitleaks git --redact --report-format json --report-path $gitleaksGit . }
    $dirResult = Invoke-Capture "gitleaks_dir" $gitleaksDir { gitleaks dir --redact --report-format json --report-path $gitleaksDir . }
    $summary.checks.gitleaks = @{ git_exit_code = $gitResult.exit_code; dir_exit_code = $dirResult.exit_code; status = "ran" }
    if ($gitResult.exit_code -ne 0 -or $dirResult.exit_code -ne 0) {
        Add-Blocker "gitleaks reported findings or failed."
    }
} else {
    $summary.checks.gitleaks = @{ status = "missing"; release_blocker = $false }
}

if (Test-Tool "detect-secrets") {
    $detectOutput = Join-Path $securityDir "detect-secrets.baseline.json"
    $detectResult = Invoke-Capture "detect_secrets_scan" $detectOutput {
        detect-secrets scan --all-files `
            --exclude-files '^(\.tmp|\.mypy_cache|\.ruff_cache|project[\\/]reports|project[\\/]cache|project[\\/]runtime|project[\\/]\.runtime|\.git|archive|docs[\\/]visual-evidence)([\\/]|$)|^docs[\\/]market_data_storage_(baseline|migration_result)\.json$'
    }
    $detectFindingCount = 0
    try {
        $detectJson = Get-Content $detectOutput -Raw | ConvertFrom-Json
        foreach ($prop in $detectJson.results.PSObject.Properties) {
            $detectFindingCount += @($prop.Value).Count
        }
    } catch {
        $detectFindingCount = -1
    }
    $summary.checks.detect_secrets = @{ status = "ran"; exit_code = $detectResult.exit_code; output = $detectOutput; finding_count = $detectFindingCount }
    if ($detectResult.exit_code -ne 0) {
        Add-Warning "detect-secrets scan returned a non-zero exit code. Review .tmp/security/detect-secrets.baseline.json."
    }
    if ($detectFindingCount -gt 0) {
        Add-Blocker "detect-secrets reported potential secrets. Review .tmp/security/detect-secrets.baseline.json."
    }
} else {
    $summary.checks.detect_secrets = @{ status = "missing"; release_blocker = $false }
}

if (Test-Tool "trufflehog") {
    $truffleOut = Join-Path $securityDir "trufflehog-git.json"
    $truffleResult = Invoke-Capture "trufflehog_git" $truffleOut { trufflehog git file://. --results=verified,unknown --json }
    $summary.checks.trufflehog = @{ status = "ran"; exit_code = $truffleResult.exit_code; output = $truffleOut }
    if ($truffleResult.exit_code -ne 0) {
        Add-Warning "trufflehog returned a non-zero exit code. Review .tmp/security/trufflehog-git.json."
    }
} else {
    $summary.checks.trufflehog = @{ status = "missing"; release_blocker = $false }
}

$fallbackSecrets = Invoke-GitGrep "fallback_secret_grep" $secretPattern (Join-Path $securityDir "fallback-git-grep-secrets.txt")
$strongSecrets = Invoke-GitGrep "strong_secret_grep" $strongSecretPattern (Join-Path $securityDir "strong-secret-grep.txt")
$localPaths = Invoke-GitGrep "local_path_grep" $pathPattern (Join-Path $securityDir "fallback-git-grep-local-paths.txt")
$timesfm = Invoke-GitGrep "timesfm_grep" $timesfmPattern (Join-Path $securityDir "timesfm-git-grep.txt")
$investment = Invoke-GitGrep "investment_wording_grep" $investmentPattern (Join-Path $securityDir "investment-wording-git-grep.txt")

$summary.checks.fallback_secret_grep = @{ status = "ran"; hit_count = $fallbackSecrets.lines.Count }
$summary.checks.strong_secret_grep = @{ status = "ran"; hit_count = $strongSecrets.lines.Count }
$summary.checks.local_path_grep = @{ status = "ran"; hit_count = $localPaths.lines.Count }
$summary.checks.timesfm_grep = @{ status = "ran"; hit_count = $timesfm.lines.Count }
$summary.checks.investment_wording_grep = @{ status = "ran"; hit_count = $investment.lines.Count }

if ($strongSecrets.lines.Count -gt 0) {
    Add-Blocker "Strong secret patterns were found."
}

$forbiddenTimesFm = @($timesfm.lines | Where-Object {
    $_ -notmatch "^docs/experimental_timesfm_evaluation.md:" -and
    $_ -notmatch "^docs/github_publish_readiness_checklist.md:" -and
    $_ -notmatch "^docs/release_operation_hardening_v0\.7\.3.md:" -and
    $_ -notmatch "^RELEASE_NOTES_v0\.7\.[12]\.md:" -and
    $_ -notmatch "^docs/security_audit_v0\.7\.2.md:" -and
    $_ -notmatch "^README.md:" -and
    $_ -notmatch "^project/tests/test_report_generator.py:" -and
    $_ -notmatch "^scripts/security_audit.ps1:"
})
if ($forbiddenTimesFm.Count -gt 0) {
    Add-Blocker "TimesFM-related normal functionality references were found."
}

$trackedArtifacts = @(git ls-files | Select-String -Pattern "project/reports|project/cache|\.tmp|\.runtime|__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache|\.zip|\.log|\.sqlite|\.db|\.parquet" -CaseSensitive:$false)
$summary.checks.generated_artifacts = @{ status = "ran"; hit_count = $trackedArtifacts.Count; hits = @($trackedArtifacts | ForEach-Object { $_.Line }) }
if ($trackedArtifacts.Count -gt 0) {
    Add-Blocker "Generated/cache artifacts are tracked."
}

$thresholdDiff = @(git diff -- project/risk_line_thresholds_active.json project/risk_line_thresholds_proposed.json)
$summary.checks.threshold_json_diff = @{ status = "ran"; diff_line_count = $thresholdDiff.Count }
if ($thresholdDiff.Count -gt 0) {
    Add-Blocker "Threshold JSON files have diffs."
}

$protectedDecisionPaths = @(
    "project/reliability_policy.py",
    "project/spot_signal.py",
    "project/action_schema.py",
    "project/threshold_decision_policy.py"
)
$protectedDecisionDiff = @(
    git diff -- @protectedDecisionPaths
    git diff --cached -- @protectedDecisionPaths
)
$protectedDecisionStatus = @(git status --short -- @protectedDecisionPaths)
$summary.checks.protected_decision_diff = @{
    status = "ran"
    paths = $protectedDecisionPaths
    diff_line_count = $protectedDecisionDiff.Count
    status_entries = $protectedDecisionStatus
    explicitly_allowed = [bool]$AllowProtectedDecisionDiff
}
if ($protectedDecisionDiff.Count -gt 0 -or $protectedDecisionStatus.Count -gt 0) {
    if ($AllowProtectedDecisionDiff) {
        Add-Warning "Protected decision-surface diffs were explicitly allowed for this audit; review them manually before publication."
    } else {
        Add-Blocker "Protected decision-surface files have unapproved diffs. Re-run only with -AllowProtectedDecisionDiff after explicit user authorization for that exact scope."
    }
}

$reqTimesFm = @(Select-String -Path "project/requirements.txt","project/requirements-dev.txt","project/requirements-lock.txt","pyproject.toml" -Pattern "timesfm|times-fm|torch|jax|flax|tensorflow" -CaseSensitive:$false -ErrorAction SilentlyContinue)
$summary.checks.requirements_timesfm = @{ status = "ran"; hit_count = $reqTimesFm.Count; hits = @($reqTimesFm | ForEach-Object { "$($_.Path):$($_.LineNumber):$($_.Line)" }) }
if ($reqTimesFm.Count -gt 0) {
    Add-Blocker "Forbidden ML/TimesFM dependencies were found in requirements."
}

if ($SkipDependencyAudit) {
    $summary.checks.dependency_audit = @{ status = "skipped_by_option" }
} else {
    $pipCheckOut = Join-Path $securityDir "pip-check.txt"
    $pipCheck = Invoke-Capture "pip_check" $pipCheckOut { & $Python -m pip check }
    $summary.checks.pip_check = @{ status = "ran"; exit_code = $pipCheck.exit_code; output = $pipCheckOut }
    if ($pipCheck.exit_code -ne 0) {
        Add-Warning "pip check reported an environment issue. Review .tmp/security/pip-check.txt."
    }
    $pipAuditAvailable = $false
    try {
        & $Python -m pip_audit --version *> $null
        if ($LASTEXITCODE -eq 0) { $pipAuditAvailable = $true }
    } catch {
        $pipAuditAvailable = $false
    }
    if ($pipAuditAvailable) {
        $auditReq = Join-Path $securityDir "pip-audit-requirements.json"
        $auditReqResult = Invoke-Capture "pip_audit_requirements" $auditReq { & $Python -m pip_audit -r project/requirements.txt --format json --output $auditReq }
        $summary.checks.pip_audit_requirements = @{ status = "ran"; exit_code = $auditReqResult.exit_code; output = $auditReq }
        if ($auditReqResult.exit_code -ne 0) {
            Add-Warning "pip-audit reported findings for project/requirements.txt."
        }

        if (Test-Path "project/requirements-lock.txt") {
            $filteredDir = Join-Path $securityDir "pip-audit-lock-filtered"
            $filterLog = Join-Path $securityDir "pip-audit-lock-filter.txt"
            $filterResult = Invoke-Capture "pip_audit_lock_filter" $filterLog { & $Python project/audit_requirements.py --source project/requirements-lock.txt --output-dir $filteredDir }
            $filteredReq = Join-Path $filteredDir "requirements-lock.pip-audit.txt"
            if ($filterResult.exit_code -eq 0 -and (Test-Path $filteredReq)) {
                $auditLock = Join-Path $securityDir "pip-audit-lock.json"
                $auditLockResult = Invoke-Capture "pip_audit_lock" $auditLock { & $Python -m pip_audit -r $filteredReq --no-deps --format json --output $auditLock }
                $summary.checks.pip_audit_lock = @{ status = "ran"; exit_code = $auditLockResult.exit_code; output = $auditLock }
                if ($auditLockResult.exit_code -ne 0) {
                    Add-Warning "pip-audit reported findings for filtered requirements-lock.txt."
                }
            } else {
                Add-Warning "Could not build filtered pip-audit lock input."
            }
        }
    } else {
        $summary.checks.pip_audit = @{ status = "missing"; release_blocker = $false }
        Add-Warning "pip-audit is not installed. Run with -InstallTools to enable dependency vulnerability audit."
    }
}

if ($Strict -and $summary.blockers.Count -gt 0) {
    $exitCode = 2
} else {
    $exitCode = 0
}

$summaryPath = Join-Path $securityDir "security_audit_summary.json"
ConvertTo-JsonFile $summary $summaryPath

$mdPath = Join-Path $securityDir "security_audit_summary.md"
$md = @(
    "# Security Audit Summary",
    "",
    "- generated_at: $($summary.generated_at)",
    "- publish_readiness: $($summary.publish_readiness)",
    "- strict: $($summary.strict)",
    "- blockers: $($summary.blockers.Count)",
    "- warnings: $($summary.warnings.Count)",
    "",
    "## Tools",
    ($summary.tools.GetEnumerator() | ForEach-Object { "- $($_.Key): $($_.Value.status)" }),
    "",
    "## Blockers",
    ($(if ($summary.blockers.Count -eq 0) { "- none" } else { $summary.blockers | ForEach-Object { "- $_" } })),
    "",
    "## Warnings",
    ($(if ($summary.warnings.Count -eq 0) { "- none" } else { $summary.warnings | ForEach-Object { "- $_" } }))
)
$md | Set-Content -Encoding UTF8 $mdPath
$summary.outputs["security_audit_summary.md"] = $mdPath

Write-Output ($summary | ConvertTo-Json -Depth 20)
exit $exitCode
