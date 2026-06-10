# CryptoVault - Run all PostgreSQL schema files in order
# Usage: cd Projectdb; .\setup_database.ps1

$Psql = "C:\Program Files\PostgreSQL\18\bin\psql.exe"
$DbName = "cryptovault_db"
$DbUser = "postgres"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Test-Path $Psql)) {
    Write-Error "psql not found at $Psql. Update the path in setup_database.ps1."
    exit 1
}

Write-Host "Creating database if needed..."
& $Psql -U $DbUser -tc "SELECT 1 FROM pg_database WHERE datname = '$DbName'" | Out-Null
$dbExists = & $Psql -U $DbUser -tAc "SELECT 1 FROM pg_database WHERE datname = '$DbName'"
if (-not $dbExists) {
    & $Psql -U $DbUser -c "CREATE DATABASE $DbName"
}

$files = @(
    "schema_postgres.sql",
    "schema_crypto.sql",
    "schema_deposit_features.sql",
    "schema_multi_wallets.sql"
)

foreach ($f in $files) {
    $path = Join-Path $ScriptDir $f
    Write-Host "`n=== Running $f ===" -ForegroundColor Cyan
    & $Psql -U $DbUser -d $DbName -f $path
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed running $f"
        exit $LASTEXITCODE
    }
}

Write-Host "`nDatabase setup complete: $DbName" -ForegroundColor Green
