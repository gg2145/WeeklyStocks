# Weekly Stocks - Development Setup Script
# Creates virtual environment and installs dependencies

param(
    [switch]$Force = $false
)

Write-Host "🚀 Weekly Stocks - Development Setup" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

# Get project root directory
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "📁 Project directory: $ProjectRoot" -ForegroundColor Green

# Check if Python is available
try {
    $PythonVersion = python --version 2>&1
    Write-Host "✅ Python found: $PythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python not found. Please install Python 3.8+ and add it to PATH." -ForegroundColor Red
    exit 1
}

# Check Python version
$VersionMatch = $PythonVersion -match "Python (\d+)\.(\d+)"
if ($VersionMatch) {
    $MajorVersion = [int]$Matches[1]
    $MinorVersion = [int]$Matches[2]
    
    if ($MajorVersion -lt 3 -or ($MajorVersion -eq 3 -and $MinorVersion -lt 8)) {
        Write-Host "❌ Python 3.8+ required. Found: $PythonVersion" -ForegroundColor Red
        exit 1
    }
}

# Virtual environment setup
$VenvPath = ".venv"

if (Test-Path $VenvPath) {
    if ($Force) {
        Write-Host "🗑️  Removing existing virtual environment..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force $VenvPath
    } else {
        Write-Host "📦 Virtual environment already exists at $VenvPath" -ForegroundColor Yellow
        Write-Host "   Use -Force to recreate it" -ForegroundColor Yellow
        
        # Try to activate existing environment
        $ActivateScript = Join-Path $VenvPath "Scripts\Activate.ps1"
        if (Test-Path $ActivateScript) {
            Write-Host "🔄 Activating existing virtual environment..." -ForegroundColor Green
            & $ActivateScript
            
            # Check if requirements need updating
            Write-Host "📋 Checking dependencies..." -ForegroundColor Blue
            pip install -r requirements.txt --upgrade
            
            Write-Host "✅ Setup complete! Virtual environment is ready." -ForegroundColor Green
            Write-Host ""
            Write-Host "To run the application:" -ForegroundColor Cyan
            Write-Host "  .\scripts\run.ps1" -ForegroundColor White
            exit 0
        }
    }
}

# Create virtual environment
Write-Host "📦 Creating virtual environment..." -ForegroundColor Blue
python -m venv $VenvPath

if (-not (Test-Path $VenvPath)) {
    Write-Host "❌ Failed to create virtual environment" -ForegroundColor Red
    exit 1
}

# Activate virtual environment
$ActivateScript = Join-Path $VenvPath "Scripts\Activate.ps1"
if (-not (Test-Path $ActivateScript)) {
    Write-Host "❌ Virtual environment activation script not found" -ForegroundColor Red
    exit 1
}

Write-Host "🔄 Activating virtual environment..." -ForegroundColor Green
& $ActivateScript

# Upgrade pip
Write-Host "⬆️  Upgrading pip..." -ForegroundColor Blue
python -m pip install --upgrade pip

# Install dependencies
Write-Host "📋 Installing dependencies..." -ForegroundColor Blue
if (Test-Path "requirements.txt") {
    pip install -r requirements.txt
} else {
    Write-Host "❌ requirements.txt not found" -ForegroundColor Red
    exit 1
}

# Create .env file if it doesn't exist
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Write-Host "📝 Creating .env file from template..." -ForegroundColor Blue
        Copy-Item ".env.example" ".env"
        Write-Host "✅ Created .env file. You can customize it as needed." -ForegroundColor Green
    } else {
        Write-Host "⚠️  .env.example not found. You may need to create .env manually." -ForegroundColor Yellow
    }
}

# Create output and logs directories
$OutputDir = "output"
$LogsDir = "logs"

if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
    Write-Host "📁 Created output directory" -ForegroundColor Green
}

if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir | Out-Null
    Write-Host "📁 Created logs directory" -ForegroundColor Green
}

Write-Host ""
Write-Host "✅ Development setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Customize .env file with your preferred tickers" -ForegroundColor White
Write-Host "2. Run the application: .\scripts\run.ps1" -ForegroundColor White
Write-Host ""
Write-Host "Virtual environment is now active." -ForegroundColor Green
Write-Host "To deactivate later, run: deactivate" -ForegroundColor Yellow
