$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Assert-NativeCommandSucceeded {
    param([string]$Step)
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE. The bot was not installed."
    }
}

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python was not found. Install Python 3.11+ from python.org and enable 'Add Python to PATH'."
}

py -3 -m venv .venv
Assert-NativeCommandSucceeded "Creating the Python environment"

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
Assert-NativeCommandSucceeded "Updating pip"

& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
Assert-NativeCommandSucceeded "Installing Python dependencies"

if (-not (Test-Path config.json)) {
    Copy-Item config.example.json config.json
}

Write-Host "Installed successfully. Next: .\run-bot.ps1"
