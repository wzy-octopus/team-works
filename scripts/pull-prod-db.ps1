<#
.SYNOPSIS
  Download the latest production SQLite database copy for local inspection.

.DESCRIPTION
  Pulls /home/data/app.db from the Azure App Service Kudu VFS API and overwrites
  the same local file every time. This script does not modify production data.

.PARAMETER App
  Azure Web App name. Default: teamworks-app

.PARAMETER OutFile
  Local destination file. Default: C:\tmp\teamworks-prod-app.db

.PARAMETER Open
  Open the downloaded DB with the Windows default application.

.EXAMPLE
  pwsh scripts\pull-prod-db.ps1
  pwsh scripts\pull-prod-db.ps1 -Open
#>
param(
  [string]$App = "teamworks-app",
  [string]$OutFile = "C:\tmp\teamworks-prod-app.db",
  [switch]$Open
)

$ErrorActionPreference = "Stop"

function Step($Message) {
  Write-Host "`n=== $Message ===" -ForegroundColor Cyan
}

Step "Get Azure access token"
$token = az account get-access-token --resource https://management.azure.com --query accessToken -o tsv
if (-not $token) {
  throw "Failed to get Azure access token. Run 'az login' first."
}

$outDir = Split-Path -Parent $OutFile
if ($outDir -and -not (Test-Path -LiteralPath $outDir)) {
  New-Item -ItemType Directory -Force -Path $outDir | Out-Null
}

Step "Download production DB"
$headers = @{ Authorization = "Bearer $token" }
$uri = "https://$App.scm.azurewebsites.net/api/vfs/data/app.db"
$tmpFile = "$OutFile.download"

if (Test-Path -LiteralPath $tmpFile) {
  Remove-Item -LiteralPath $tmpFile -Force
}

Invoke-WebRequest -Uri $uri -Headers $headers -OutFile $tmpFile

if (-not (Test-Path -LiteralPath $tmpFile)) {
  throw "Download failed: $tmpFile was not created."
}

Move-Item -LiteralPath $tmpFile -Destination $OutFile -Force
$item = Get-Item -LiteralPath $OutFile

Write-Host ""
Write-Host "Downloaded latest production DB copy:" -ForegroundColor Green
Write-Host "  $($item.FullName)"
Write-Host "  Size: $($item.Length) bytes"
Write-Host "  Updated: $($item.LastWriteTime)"
Write-Host ""
Write-Host "Open this fixed file in A5:SQL Mk-2. Re-run this script to refresh it."

if ($Open) {
  Step "Open DB"
  Start-Process -FilePath $OutFile
}
