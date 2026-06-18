<#
.SYNOPSIS
  28teamworks を Azure App Service (Linux) に一発デプロイする。

.DESCRIPTION
  フロントビルド → static へコピー → requirements.txt 生成 → ステージング
  → 正スラッシュ ZIP 作成 (makezip.py) → az webapp deploy → URL 検証。
  config（環境変数・startup・Always On）は初回設定済みのため触らない。

  ハマりどころ対策が組み込み済み:
    - Compress-Archive は使わず Python zipfile で正スラッシュ ZIP（No module named 'app' 回避）
    - 起動コマンドは python -m uvicorn（初回設定済み・本スクリプトでは変更しない）
    - deploy は --async + 自前の URL ポーリングで判定（deploy の誤報失敗を無視）

.PARAMETER App           Web App 名（既定: teamworks-app）
.PARAMETER ResourceGroup リソースグループ（既定: 28teamworks-rg）
.PARAMETER SkipBuild     フロントの npm build をスキップ（static が最新の時）
.PARAMETER UploadDb      backend/app.db を /home/data/app.db へアップロード（seed の入れ替え時のみ）

.EXAMPLE
  pwsh scripts\deploy.ps1
  pwsh scripts\deploy.ps1 -SkipBuild
  pwsh scripts\deploy.ps1 -UploadDb      # ローカルで seed 済みの DB を反映
#>
param(
  [string]$App = "teamworks-app",
  [string]$ResourceGroup = "28teamworks-rg",
  [switch]$SkipBuild,
  [switch]$UploadDb
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot   # プロジェクトルート（scripts/ の親）
$frontend = Join-Path $root "frontend"
$backend  = Join-Path $root "backend"
$static   = Join-Path $backend "static"
$stage    = Join-Path $env:TEMP "tw-stage"
$zip      = Join-Path $env:TEMP "tw-deploy.zip"
$hostUrl  = "https://$App.azurewebsites.net"

function Step($m) { Write-Host "`n=== $m ===" -ForegroundColor Cyan }

# 1. フロントビルド
if (-not $SkipBuild) {
  Step "Frontend build (npm run build)"
  Push-Location $frontend
  if (-not (Test-Path "node_modules")) { npm install; if (-not $?) { throw "npm install failed" } }
  npm run build; if (-not $?) { throw "npm run build failed" }
  Pop-Location
} else { Step "Frontend build SKIPPED" }

# 2. dist → backend/static
Step "Copy dist -> backend/static"
if (Test-Path $static) { Remove-Item -Recurse -Force $static }
Copy-Item -Recurse (Join-Path $frontend "dist") $static

# 3. requirements.txt
Step "uv export -> requirements.txt"
Push-Location $backend
uv export --no-hashes -o requirements.txt; if (-not $?) { throw "uv export failed" }
Pop-Location

# 4. ステージング（不要物を除外）
Step "Stage backend (exclude venv/cache/db/env)"
if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
robocopy $backend $stage /E `
  /XD ".venv" "__pycache__" ".pytest_cache" ".ruff_cache" "tests" ".git" "node_modules" `
  /XF "*.pyc" "*.db" "*.bak" "*.db-journal" ".env" "*.log" | Out-Null
$global:LASTEXITCODE = 0   # robocopy は 0-7 が正常終了

# 5. 正スラッシュ ZIP（Compress-Archive は使わない）
Step "Build forward-slash ZIP (makezip.py)"
python (Join-Path $PSScriptRoot "makezip.py") $stage $zip
if (-not $?) { throw "makezip.py failed (backslash entries?)" }

# 6. デプロイ（--async + URL ポーリングで判定）
Step "az webapp deploy ($App)"
az webapp deploy --name $App --resource-group $ResourceGroup --src-path $zip --type zip --async true | Out-Null
if (-not $?) { throw "az webapp deploy failed to enqueue" }

# 6b. (任意) seed 済み DB をアップロード
if ($UploadDb) {
  Step "Upload backend/app.db -> /home/data/app.db"
  $localDb = Join-Path $backend "app.db"
  if (-not (Test-Path $localDb)) { throw "backend/app.db not found. Run: cd backend; uv run python seed.py" }
  $tok = az account get-access-token --resource https://management.azure.com --query accessToken -o tsv
  az webapp stop --name $App --resource-group $ResourceGroup | Out-Null
  Start-Sleep -Seconds 5
  Invoke-RestMethod -Uri "https://$App.scm.azurewebsites.net/api/vfs/data/app.db" `
    -Method Put -Headers @{ Authorization = "Bearer $tok"; "If-Match" = "*" } `
    -InFile $localDb -ContentType "application/octet-stream"
  az webapp start --name $App --resource-group $ResourceGroup | Out-Null
}

# 7. URL 検証（deploy の終了コードではなく実際の応答で判定）
Step "Verify $hostUrl (cold start ~1-2 min)"
$ok = $false
for ($i = 1; $i -le 20; $i++) {
  try {
    $r = Invoke-WebRequest -Uri "$hostUrl/" -TimeoutSec 20 -UseBasicParsing -ErrorAction Stop
    if ($r.StatusCode -eq 200) { Write-Host "[$i] HTTP 200 - app is up" -ForegroundColor Green; $ok = $true; break }
    Write-Host "[$i] HTTP $($r.StatusCode)"
  } catch {
    $code = $_.Exception.Response.StatusCode.value__
    Write-Host "[$i] $(if ($code) { "HTTP $code" } else { 'waiting...' })"
  }
  Start-Sleep -Seconds 12
}

if ($ok) {
  Write-Host "`nDEPLOY OK -> $hostUrl" -ForegroundColor Green
} else {
  Write-Host "`nApp not responding 200 yet. Check logs:" -ForegroundColor Yellow
  Write-Host "  StartupLogs/*_failure.log の ContainerStream に Python traceback" -ForegroundColor Yellow
  Write-Host "  exit 127 = deps/command 不在 / exit 1 = import 時にクラッシュ" -ForegroundColor Yellow
  exit 1
}
