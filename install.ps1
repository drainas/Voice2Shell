# install.ps1 — Voice2Shell Windows Installer
$ErrorActionPreference = "Stop"

# ── Header ───────────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Voice2Shell — Installer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── Check Python 3.12+ ──────────────────────────────────────────────
$PythonCmd = $null
$PythonVersion = $null

foreach ($cmd in @("python", "python3")) {
    try {
        $raw = & $cmd --version 2>&1
        if ($raw -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -ge 3 -and $minor -ge 12) {
                $PythonCmd = $cmd
                $PythonVersion = "$major.$minor"
                break
            }
        }
    } catch {
        # command not found, try next
    }
}

if (-not $PythonCmd) {
    Write-Host "[X] Python 3.12+ is required but was not found." -ForegroundColor Red
    Write-Host ""
    Write-Host "    Install Python from https://www.python.org or run:" -ForegroundColor Yellow
    Write-Host "    winget install Python.Python.3.12" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-Host "[+] Found Python $PythonVersion ($PythonCmd)" -ForegroundColor Green

# ── Determine source directory ───────────────────────────────────────
$SrcDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "[+] Source directory: $SrcDir" -ForegroundColor Green

# ── Create install directory ─────────────────────────────────────────
$InstallDir = "$env:LOCALAPPDATA\Voice2Shell"

if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    Write-Host "[+] Created install directory: $InstallDir" -ForegroundColor Green
} else {
    Write-Host "[+] Install directory already exists: $InstallDir" -ForegroundColor Green
}

# ── Copy application files ───────────────────────────────────────────
$FilesToCopy = @("voice2shell.py", "platform_support.py", "requirements.txt")

foreach ($file in $FilesToCopy) {
    $src = Join-Path $SrcDir $file
    if (-not (Test-Path $src)) {
        Write-Host "[X] Missing source file: $src" -ForegroundColor Red
        exit 1
    }
    Copy-Item -Path $src -Destination $InstallDir -Force
    Write-Host "[+] Copied $file" -ForegroundColor Green
}

# ── Create virtual environment ───────────────────────────────────────
Write-Host ""
Write-Host "[*] Creating virtual environment..." -ForegroundColor Cyan
& $PythonCmd -m venv "$InstallDir\.venv"
Write-Host "[+] Virtual environment created" -ForegroundColor Green

# ── Upgrade pip and install requirements ─────────────────────────────
Write-Host "[*] Upgrading pip..." -ForegroundColor Cyan
& "$InstallDir\.venv\Scripts\pip.exe" install --upgrade pip | Out-Null
Write-Host "[+] pip upgraded" -ForegroundColor Green

Write-Host "[*] Installing requirements..." -ForegroundColor Cyan
& "$InstallDir\.venv\Scripts\pip.exe" install -r "$InstallDir\requirements.txt"
Write-Host "[+] Requirements installed" -ForegroundColor Green

# ── Install openai-whisper ───────────────────────────────────────────
Write-Host "[*] Installing openai-whisper..." -ForegroundColor Cyan
& "$InstallDir\.venv\Scripts\pip.exe" install openai-whisper
Write-Host "[+] openai-whisper installed" -ForegroundColor Green

# ── Create Start Menu shortcut ───────────────────────────────────────
Write-Host "[*] Creating Start Menu shortcut..." -ForegroundColor Cyan

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Voice2Shell.lnk")
$Shortcut.TargetPath = "$InstallDir\.venv\Scripts\pythonw.exe"
$Shortcut.Arguments = "`"$InstallDir\voice2shell.py`""
$Shortcut.WorkingDirectory = $InstallDir
$Shortcut.Description = "Voice2Shell — speak commands to your terminal"
$Shortcut.Save()

Write-Host "[+] Start Menu shortcut created" -ForegroundColor Green

# ── Done ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Installation complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Installed to: $InstallDir" -ForegroundColor White
Write-Host "  Find Voice2Shell in your Start Menu." -ForegroundColor White
Write-Host "  The Whisper model will download on first use." -ForegroundColor White
Write-Host ""
