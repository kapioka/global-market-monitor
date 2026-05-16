[CmdletBinding()]
param(
    [string]$Python = "python",
    [string]$Summary = "",
    [string]$HistoryDir = "",
    [string]$Output = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path

$argsList = @("-m", "project.render_supplement_dashboard")
if ($Summary) {
    $argsList += @("--summary", $Summary)
}
if ($HistoryDir) {
    $argsList += @("--history-dir", $HistoryDir)
}
if ($Output) {
    $argsList += @("--output", $Output)
}

try {
    Push-Location $RepoRoot
    & $Python @argsList
    if ($LASTEXITCODE -ne 0) {
        throw "render command failed with exit code $LASTEXITCODE"
    }
}
catch {
    Write-Error @"
補足ダッシュボードの再生成を停止しました。
失敗したコマンド: $Python $($argsList -join ' ')
エラー: $($_.Exception.Message)
こちらで安全に続けられない理由: Python 解決先、依存、または入力レポートが現在のPC環境に依存している可能性があります。
ユーザー側で必要な確認: Python 3.11 以上、project/requirements.txt の依存、project/reports/report_summary.json の存在を確認してください。
再開条件: 上記が確認でき、同じコマンドが成功すること。
"@
    exit 1
}
finally {
    Pop-Location
}
