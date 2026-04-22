# 统一验证入口：优先使用本地虚拟环境，再运行 Python 验证脚本。
param(
    [switch]$SkipE2E,
    [switch]$OnlyE2E
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$LocalPython = Join-Path $Root ".venv\Scripts\python.exe"

if (Test-Path $LocalPython) {
    $Python = $LocalPython
} else {
    $Python = "python"
}

$ArgsList = @("scripts/verify.py")
if ($SkipE2E) {
    $ArgsList += "--skip-e2e"
}
if ($OnlyE2E) {
    $ArgsList += "--only-e2e"
}

& $Python @ArgsList
exit $LASTEXITCODE
