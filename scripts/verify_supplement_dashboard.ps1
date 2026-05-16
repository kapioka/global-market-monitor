[CmdletBinding()]
param(
    [string]$Html = "",
    [string]$EvidenceDir = "",
    [int]$Width = 1366,
    [int]$Height = 900,
    [string]$Channel = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
if (-not $Html) {
    $Html = Join-Path $RepoRoot "project\reports\supplement_dashboard.html"
}
if (-not $EvidenceDir) {
    $EvidenceDir = Join-Path $RepoRoot "docs\visual-evidence"
}

$HtmlPath = (Resolve-Path -LiteralPath $Html).Path
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
$EvidencePath = (Resolve-Path -LiteralPath $EvidenceDir).Path

function Stop-EnvironmentIssue {
    param(
        [string]$Reason,
        [string]$Command,
        [string]$ErrorText,
        [int]$ExitCode = 2
    )
    Write-Error @"
補足ダッシュボード検証を停止しました。
停止理由: $Reason
失敗したコマンド: $Command
エラー: $ErrorText
こちらで安全に続けられない理由: Playwright / Node / bundled Chromium の状態がPC環境に依存しており、ここで再インストールやPATH変更を繰り返すと既存環境を崩す可能性があります。
ユーザー側で必要な確認: npm/npx、Playwright CLI、bundled Chromium が利用可能か確認してください。通常は 'npx --no-install playwright install chromium' で導入します。
再開条件: 'npx --no-install playwright --version' と bundled Chromium での screenshot が成功すること。
"@
    exit $ExitCode
}

if (-not (Get-Command npx -ErrorAction SilentlyContinue)) {
    Stop-EnvironmentIssue -Reason "npx が見つかりません。" -Command "Get-Command npx" -ErrorText "npx not found"
}

Push-Location $RepoRoot
try {
    $versionOutput = & npx --no-install playwright --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Stop-EnvironmentIssue -Reason "Playwright CLI がローカル環境で利用できません。" -Command "npx --no-install playwright --version" -ErrorText ($versionOutput -join "`n")
    }

    $screens = @("history", "decision", "sector", "market", "audit")
    $date = Get-Date -Format "yyyyMMdd_HHmmss"
    $fileUrlBase = "file:///" + ($HtmlPath -replace "\\", "/")
    foreach ($screen in $screens) {
        $out = Join-Path $EvidencePath "${date}_${screen}_${Width}x${Height}.png"
        $url = "${fileUrlBase}#${screen}"
        $shotArgs = @("playwright", "screenshot", "--browser=chromium")
        if ($Channel) {
            $shotArgs += "--channel=$Channel"
        }
        $shotArgs += @("--viewport-size=${Width},${Height}", $url, $out)
        $shotOutput = & npx --no-install @shotArgs 2>&1
        if ($LASTEXITCODE -ne 0) {
            Stop-EnvironmentIssue -Reason "Playwright screenshot が失敗しました。" -Command "npx --no-install $($shotArgs -join ' ')" -ErrorText ($shotOutput -join "`n")
        }
    }

    $htmlText = Get-Content -LiteralPath $HtmlPath -Raw
    $required = @('id="history"', 'id="decision"', 'id="sector"', 'id="market"', 'id="audit"', 'id="supplementHistoryPayload"')
    $missing = @($required | Where-Object { $htmlText -notlike "*$_*" })
    if ($missing.Count -gt 0) {
        Write-Error "DOM静的チェックに失敗しました。欠落: $($missing -join ', ')"
        exit 1
    }

    Write-Host "verified screenshots: $EvidencePath"
}
finally {
    Pop-Location
}
