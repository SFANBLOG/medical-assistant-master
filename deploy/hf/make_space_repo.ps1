# =====================================================================
#  Assemble the Hugging Face Space repo: copy demo-required files from
#  the main repo into the target dir, then place Dockerfile + HF README.
#  Usage: powershell -File deploy\hf\make_space_repo.ps1 [-Dst <dir>]
#  Default target: medical-assistant-hf (sibling of the main repo)
# =====================================================================
param(
    [string]$Dst = ""
)
$ErrorActionPreference = "Stop"
# $PSScriptRoot = <repo>\deploy\hf  ->  repo root is 2 levels up
$Src = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not $Dst) {
    $Dst = Join-Path (Split-Path $Src -Parent) "medical-assistant-hf"
}
Write-Host "Source repo : $Src"
Write-Host "Target dir  : $Dst"

# Whitelist (repo-root relative): backend / frontend / entrypoints / configs
$items = @(
    "backend", "frontend", "scripts",
    "wsgi.py", "gunicorn.conf.py", "requirements.txt",
    ".env.example", ".gitignore", "LICENSE", "docker-compose.yml"
)
# Exclusions: dev artifacts / large files / not needed for demo
$excludeDirs = @("__pycache__", "node_modules", "dist", ".venv*", ".idea", ".run", ".workbuddy", "ai_models")
$excludeFiles = @("*.db", "*.pkl", "*.index", ".env")

if (Test-Path $Dst) { Remove-Item -Recurse -Force $Dst }
New-Item -ItemType Directory -Force -Path $Dst | Out-Null

foreach ($it in $items) {
    $s = Join-Path $Src $it
    if (-not (Test-Path $s)) { Write-Host "SKIP (not found): $it"; continue }
    if ((Get-Item $s).PSIsContainer) {
        $robocopyArgs = @($s, (Join-Path $Dst $it), "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/XD") + $excludeDirs + @("/XF") + $excludeFiles
        & robocopy @robocopyArgs | Out-Null
        if ($LASTEXITCODE -gt 7) { throw "robocopy failed: $it (code=$LASTEXITCODE)" }
    } else {
        Copy-Item $s -Destination (Join-Path $Dst $it) -Force
    }
    Write-Host "COPIED: $it"
}

# Dockerfile + HF README at repo root
Copy-Item (Join-Path $PSScriptRoot "Dockerfile") (Join-Path $Dst "Dockerfile") -Force
Copy-Item (Join-Path $PSScriptRoot "README.hf.md") (Join-Path $Dst "README.md") -Force
Write-Host "PLACED: Dockerfile / README.md (HF frontmatter)"

# Seed-data integrity check (12 KBs, 148 md docs must ship)
$docCount = (Get-ChildItem (Join-Path $Dst "backend\data\uploads") -Recurse -File -Filter *.md -ErrorAction SilentlyContinue | Measure-Object).Count
Write-Host "uploads md count: $docCount (expected 148)"
if ($docCount -lt 100) { throw "seed docs incomplete, check backend/data/uploads copy" }

Write-Host ""
Write-Host "DONE. Next steps:"
Write-Host "   cd `"$Dst`""
Write-Host "   git init -b main; git add -A; git commit -m 'deploy: HF Space demo'"
Write-Host "   git remote add space https://huggingface.co/spaces/<username>/<space-name>"
Write-Host "   git push space main   # auth user=HF username, password=HF write token"
