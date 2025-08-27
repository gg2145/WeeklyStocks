# Weekly Stocks - Run Script
# Activates virtual environment and runs the application

param(
    [switch]$Help = $false,
    [switch]$Setup = $false,
    [switch]$OpenReport = $false,
    [string]$LogLevel = "",
    [string]$Tickers = ""
)

if ($Help) {
    Write-Host "📊 Weekly Stocks - Run Script" -ForegroundColor Cyan
    Write-Host "=============================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor Green
    Write-Host "  .\scripts\run.ps1                    # Run with default settings"
    Write-Host "  .\scripts\run.ps1 -Setup             # Run setup first, then application"
    Write-Host "  .\scripts\run.ps1 -OpenReport        # Open HTML report after completion"
    Write-Host "  .\scripts\run.ps1 -LogLevel DEBUG    # Set log level (DEBUG, INFO, WARNING, ERROR)"
    Write-Host "  .\scripts\run.ps1 -Tickers 'AAPL,MSFT,GOOGL'  # Override tickers"
    Write-Host "  .\scripts\run.ps1 -Help              # Show this help"
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor Yellow
    Write-Host "  .\scripts\run.ps1 -Setup -OpenReport"
    Write-Host "  .\scripts\run.ps1 -LogLevel DEBUG -Tickers 'TSLA,NVDA,AMD'"
    exit 0
}

Write-Host "📊 Weekly Stocks - Application Runner" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

# Get project root directory
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "📁 Working directory: $ProjectRoot" -ForegroundColor Green

# Run setup if requested
if ($Setup) {
    Write-Host "🔧 Running setup first..." -ForegroundColor Blue
    & ".\scripts\dev-setup.ps1"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Setup failed" -ForegroundColor Red
        exit 1
    }
    Write-Host ""
}

# Check if virtual environment exists
$VenvPath = ".venv"
$ActivateScript = Join-Path $VenvPath "Scripts\Activate.ps1"

if (-not (Test-Path $ActivateScript)) {
    Write-Host "❌ Virtual environment not found at $VenvPath" -ForegroundColor Red
    Write-Host "   Run setup first: .\scripts\dev-setup.ps1" -ForegroundColor Yellow
    exit 1
}

# Activate virtual environment
Write-Host "🔄 Activating virtual environment..." -ForegroundColor Green
& $ActivateScript

# Check if activation was successful
if (-not $env:VIRTUAL_ENV) {
    Write-Host "❌ Failed to activate virtual environment" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Virtual environment activated: $env:VIRTUAL_ENV" -ForegroundColor Green

# Set environment variables if provided
if ($LogLevel) {
    $env:LOG_LEVEL = $LogLevel
    Write-Host "🔧 Set LOG_LEVEL to $LogLevel" -ForegroundColor Blue
}

if ($Tickers) {
    $env:TICKERS = $Tickers
    Write-Host "🔧 Set TICKERS to $Tickers" -ForegroundColor Blue
}

# Check if .env file exists
if (-not (Test-Path ".env")) {
    Write-Host "⚠️  .env file not found. Using defaults from .env.example" -ForegroundColor Yellow
    if (Test-Path ".env.example") {
        Write-Host "   Consider copying .env.example to .env and customizing it" -ForegroundColor Yellow
    }
}

# Run the application
Write-Host ""
Write-Host "🚀 Starting Weekly Stocks analysis..." -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green

$StartTime = Get-Date

try {
    # Run the main application
    python -m src.main
    $ExitCode = $LASTEXITCODE
    
    $EndTime = Get-Date
    $Duration = $EndTime - $StartTime
    
    if ($ExitCode -eq 0) {
        Write-Host ""
        Write-Host "✅ Analysis completed successfully!" -ForegroundColor Green
        Write-Host "⏱️  Total time: $($Duration.TotalSeconds.ToString('F1')) seconds" -ForegroundColor Blue
        
        # Find the most recent output directory
        $OutputDir = "output"
        if (Test-Path $OutputDir) {
            $TodayDir = Get-ChildItem $OutputDir | Sort-Object Name -Descending | Select-Object -First 1
            if ($TodayDir) {
                $ReportPath = Join-Path $TodayDir.FullName "weekly_stocks_report.html"
                
                Write-Host ""
                Write-Host "📁 Output files saved to: $($TodayDir.FullName)" -ForegroundColor Cyan
                
                # List generated files
                $GeneratedFiles = Get-ChildItem $TodayDir.FullName
                Write-Host "📄 Generated files:" -ForegroundColor Cyan
                foreach ($File in $GeneratedFiles) {
                    Write-Host "   - $($File.Name)" -ForegroundColor White
                }
                
                # Open report if requested
                if ($OpenReport -and (Test-Path $ReportPath)) {
                    Write-Host ""
                    Write-Host "🌐 Opening HTML report..." -ForegroundColor Green
                    Start-Process $ReportPath
                }
            }
        }
        
    } else {
        Write-Host ""
        Write-Host "❌ Analysis failed with exit code: $ExitCode" -ForegroundColor Red
        Write-Host "⏱️  Time elapsed: $($Duration.TotalSeconds.ToString('F1')) seconds" -ForegroundColor Blue
        Write-Host "📋 Check the logs for more details" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host ""
    Write-Host "❌ Application crashed: $($_.Exception.Message)" -ForegroundColor Red
    $ExitCode = 1
}

# Show log file location
$LogFile = "logs\app.log"
if (Test-Path $LogFile) {
    Write-Host ""
    Write-Host "📋 Log file: $LogFile" -ForegroundColor Blue
}

Write-Host ""
Write-Host "🔄 Deactivating virtual environment..." -ForegroundColor Green
deactivate

exit $ExitCode
