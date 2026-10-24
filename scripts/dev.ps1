<#
.SYNOPSIS
  One-command local setup + run for Windows (also works in PowerShell 7 on macOS/Linux).
.DESCRIPTION
  Checks prerequisites, creates the Python venv, installs dependencies, ensures the Postgres database exists,
  runs Alembic migrations, optionally seeds Zoho, then starts the backend (:8000) and frontend (:3000).
.PARAMETER Mock         Run with ZOHO_MODE=mock (no Zoho credentials needed; in-memory seeded CRM).
.PARAMETER Seed         Run scripts/seed_zoho.py first (live mode only).
.PARAMETER SkipInstall  Skip pip/npm install.
.PARAMETER NoStart      Set everything up but do not start the servers.
.PARAMETER Test         Run the backend test suite and exit.
.PARAMETER Stop         Stop servers started by a previous run.
.EXAMPLE
  .\scripts\dev.ps1 -Mock
  .\scripts\dev.ps1 -Seed
#>
[CmdletBinding()]
param(
  [switch]$Mock,
  [switch]$Seed,
  [switch]$SkipInstall,
  [switch]$NoStart,
  [switch]$Test,
  [switch]$Stop
)
$ErrorActionPreference = "Stop"
$Root     = Split-Path -Parent $PSScriptRoot
$Backend  = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$PidFile  = Join-Path $Root ".dev-pids"
$IsWin    = ($env:OS -eq "Windows_NT")

function Step([string]$m) { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Ok([string]$m)   { Write-Host "    $m" -ForegroundColor Green }
function Warn([string]$m) { Write-Host "    $m" -ForegroundColor Yellow }

function Invoke-Checked([string]$Exe, [string[]]$Arguments, [string]$WorkDir) {
  Push-Location $WorkDir
  try {
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $Exe $($Arguments -join ' ')" }
  } finally { Pop-Location }
}

function Find-Python {
  $candidates = @(
    @{ Exe = "py";         Args = @("-3.12") },
    @{ Exe = "python3.12"; Args = @() },
    @{ Exe = "python";     Args = @() },
    @{ Exe = "python3";    Args = @() }
  )
  foreach ($c in $candidates) {
    if (-not (Get-Command $c.Exe -ErrorAction SilentlyContinue)) { continue }
    try { $v = (& $c.Exe @($c.Args) --version 2>&1) | Out-String } catch { continue }
    if ($v -match "Python 3\.12\.") { return $c }
  }
  throw "Python 3.12 was not found. Install it from https://www.python.org/downloads/ (tick 'Add to PATH')."
}

if ($Stop) {
  if (Test-Path $PidFile) {
    foreach ($id in (Get-Content $PidFile)) {
      if ($IsWin) {
        # /T kills the whole tree (npm.cmd -> node, uvicorn --reload -> worker)
        & taskkill /PID $id /T /F 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { Ok "stopped $id (and children)" } else { Warn "pid $id already gone" }
      } else {
        try { Stop-Process -Id ([int]$id) -Force -ErrorAction Stop; Ok "stopped $id" } catch { Warn "pid $id already gone" }
      }
    }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
  } else { Warn "no .dev-pids file; nothing to stop" }
  return
}

# ---------------------------------------------------------------- prerequisites
Step "Checking prerequisites"
$py = Find-Python
Ok "Python 3.12 found ($($py.Exe) $($py.Args -join ' '))"
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "Node.js 20+ not found. Install from https://nodejs.org/" }
$nodeMajor = [int](((node --version) -replace "^v", "").Split(".")[0])
if ($nodeMajor -lt 20) { throw "Node.js 20+ required (found $(node --version))." }
Ok "Node $(node --version)"
$npm = if ($IsWin) { "npm.cmd" } else { "npm" }

# ---------------------------------------------------------------- env files
Step "Environment files"
$envFile = Join-Path $Backend ".env"
if (-not (Test-Path $envFile)) {
  Copy-Item (Join-Path $Backend ".env.example") $envFile
  Warn "Created backend\.env from .env.example. Add GROQ_API_KEY / GEMINI_API_KEY (and Zoho credentials for live mode)."
} else { Ok "backend\.env exists" }
$feEnv = Join-Path $Frontend ".env.local"
if (-not (Test-Path $feEnv)) { Copy-Item (Join-Path $Frontend ".env.example") $feEnv; Ok "Created frontend\.env.local" }

if ($Mock) { $env:ZOHO_MODE = "mock"; Ok "ZOHO_MODE=mock for this run" }

# ---------------------------------------------------------------- backend deps
Step "Backend virtual environment"
$venv = Join-Path $Backend ".venv"
$venvPy = if ($IsWin) { Join-Path $venv "Scripts\python.exe" } else { Join-Path $venv "bin/python" }
if (-not (Test-Path $venvPy)) { Invoke-Checked $py.Exe (@($py.Args) + @("-m", "venv", $venv)) $Backend }
if (-not $SkipInstall) {
  Invoke-Checked $venvPy @("-m", "pip", "install", "--quiet", "--upgrade", "pip") $Backend
  Invoke-Checked $venvPy @("-m", "pip", "install", "--quiet", "-r", "requirements.txt") $Backend
  Ok "Python dependencies installed"
}

if ($Test) {
  Step "Running backend tests"
  Invoke-Checked $venvPy @("-m", "pytest", "-q") $Backend
  return
}

# ---------------------------------------------------------------- postgres
Step "PostgreSQL"
$dbUrl = $env:DATABASE_URL
if (-not $dbUrl) {
  $line = Get-Content $envFile | Where-Object { $_ -match "^\s*DATABASE_URL\s*=" } | Select-Object -First 1
  if ($line) { $dbUrl = ($line -split "=", 2)[1].Trim() }
}
if ($dbUrl -notmatch "^postgresql\+asyncpg://([^:/@]+):([^@]*)@([^:/]+):?(\d+)?/([\w\-]+)") {
  throw "DATABASE_URL must look like postgresql+asyncpg://user:password@localhost:5432/autoagent"
}
$dbUser, $dbPass, $dbHost, $dbPort, $dbName = $Matches[1], $Matches[2], $Matches[3], $(if ($Matches[4]) { $Matches[4] } else { "5432" }), $Matches[5]
$tcp = New-Object System.Net.Sockets.TcpClient
try {
  $tcp.Connect($dbHost, [int]$dbPort)
} catch {
  throw "PostgreSQL is not reachable at ${dbHost}:${dbPort}. Start the service (Windows: Services > postgresql-x64-16) and retry."
} finally { $tcp.Dispose() }
Ok "PostgreSQL reachable at ${dbHost}:${dbPort}"
if (Get-Command psql -ErrorAction SilentlyContinue) {
  $env:PGPASSWORD = $dbPass
  $exists = (& psql -h $dbHost -p $dbPort -U $dbUser -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$dbName'" 2>&1 | Out-String).Trim()
  if ($exists -eq "1") { Ok "database '$dbName' exists" }
  else {
    & psql -h $dbHost -p $dbPort -U $dbUser -d postgres -c "CREATE DATABASE `"$dbName`"" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not create database '$dbName'. Check the user/password in DATABASE_URL." }
    Ok "created database '$dbName'"
  }
  Remove-Item Env:PGPASSWORD
} else { Warn "psql not on PATH: make sure database '$dbName' exists (CREATE DATABASE $dbName;)." }

Step "Database migrations"
Invoke-Checked $venvPy @("-m", "alembic", "upgrade", "head") $Backend
Ok "alembic upgrade head done"

# ---------------------------------------------------------------- seed
if ($Seed) {
  Step "Seeding Zoho CRM"
  if ($Mock) { Warn "Mock mode seeds its in-memory CRM automatically; skipping Zoho seed." }
  else { Invoke-Checked $venvPy @((Join-Path $Root "scripts/seed_zoho.py")) $Root }
}

# ---------------------------------------------------------------- frontend deps
Step "Frontend dependencies"
if (-not $SkipInstall) { Invoke-Checked $npm @("install", "--no-audit", "--no-fund") $Frontend; Ok "npm packages installed" }

if ($NoStart) { Ok "Setup complete (-NoStart)."; return }

# ---------------------------------------------------------------- start
Step "Starting servers"
$pids = @()
$be = Start-Process -FilePath $venvPy -ArgumentList @("-m", "uvicorn", "app.main:app", "--reload", "--port", "8000") -WorkingDirectory $Backend -PassThru
$fe = Start-Process -FilePath $npm -ArgumentList @("run", "dev") -WorkingDirectory $Frontend -PassThru
$pids += $be.Id, $fe.Id
Set-Content -Path $PidFile -Value $pids

$healthy = $false
foreach ($i in 1..40) {
  Start-Sleep -Seconds 1
  try { $h = Invoke-RestMethod "http://localhost:8000/api/health" -TimeoutSec 2; $healthy = $true; break } catch { }
}
if ($healthy) { Ok "Backend health: $($h.status) (zoho_mode=$($h.zoho_mode), db=$($h.db))" }
else { Warn "Backend did not answer on /api/health within 40s; check its console window." }
Write-Host "`nBackend : http://localhost:8000/api/health`nChat UI : http://localhost:3000`nStop    : .\scripts\dev.ps1 -Stop" -ForegroundColor Green
