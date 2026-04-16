param(
  [switch]$NoBuild,
  [switch]$NoSeed,
  [switch]$AutoSecrets
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$envFile = Join-Path $root ".env"
$envExample = Join-Path $root ".env.example"

if (-not (Test-Path $envFile)) {
  Copy-Item $envExample $envFile
  Write-Host "Created .env from .env.example"
}

function Update-EnvVar([string]$key, [string]$value) {
  $pattern = "(?m)^$key=.*$"
  $replacement = "$key=$value"
  $content = Get-Content $envFile -Raw
  if ($content -match $pattern) {
    $content = [regex]::Replace($content, $pattern, $replacement)
  } else {
    $content = $content.TrimEnd() + "`r`n$replacement`r`n"
  }
  Set-Content -Path $envFile -Value $content
}

$envContent = Get-Content $envFile -Raw
$needsJwt = $envContent -match "JWT_SECRET=replace_with_strong_secret"
$needsFernet = $envContent -match "FERNET_KEY=replace_with_fernet_key"

if ($AutoSecrets) {
  if ($needsJwt) {
    $jwtBytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($jwtBytes)
    $jwtSecret = ([BitConverter]::ToString($jwtBytes)).Replace("-", "").ToLower()
    Update-EnvVar "JWT_SECRET" $jwtSecret
    Write-Host "Generated JWT_SECRET"
  }
  if ($needsFernet) {
    $fernetBytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($fernetBytes)
    $fernet = [Convert]::ToBase64String($fernetBytes)
    $fernet = $fernet.Replace("+", "-").Replace("/", "_")
    Update-EnvVar "FERNET_KEY" $fernet
    Write-Host "Generated FERNET_KEY"
  }

  $envContent = Get-Content $envFile -Raw
  $needsJwt = $envContent -match "JWT_SECRET=replace_with_strong_secret"
  $needsFernet = $envContent -match "FERNET_KEY=replace_with_fernet_key"
}

if ($needsJwt -or $needsFernet) {
  Write-Host "Generate secrets and update .env (JWT_SECRET, FERNET_KEY)."
  Write-Host "Example Fernet key:" 
  Write-Host 'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
  if ($needsJwt) { Write-Host "JWT_SECRET is still a placeholder." }
  if ($needsFernet) { Write-Host "FERNET_KEY is still a placeholder." }
  throw "Please update .env before running the stack."
}

if ($NoBuild) {
  docker compose up -d
} else {
  docker compose up -d --build
}

if (-not $NoSeed) {
  Write-Host "Seeding database..."
  docker compose exec -T api python -m app.core.bootstrap
}
