# Options Scanner Installation Script
# Run with: powershell -ExecutionPolicy Bypass -File install.ps1

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Please run this script as Administrator" -ForegroundColor Red
    exit 1
}

# Install prerequisites
Write-Host "Installing prerequisites..." -ForegroundColor Cyan
if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))
}

choco install -y git python --version=3.12
pip install virtualenv

# Clone repository
Write-Host "Cloning repository..." -ForegroundColor Cyan
$installDir = "$env:USERPROFILE\Documents\OptionsScanner"
if (Test-Path $installDir) {
    Remove-Item $installDir -Recurse -Force
}
git clone https://github.com/oghenetejiriorukpegmail/option-hybrid-scanner-NAS100.git $installDir

# Create virtual environment
Write-Host "Setting up virtual environment..." -ForegroundColor Cyan
cd $installDir
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

# Create desktop shortcut
Write-Host "Creating desktop shortcut..." -ForegroundColor Cyan
$shortcutPath = "$env:USERPROFILE\Desktop\Options Scanner.lnk"
$WScriptShell = New-Object -ComObject WScript.Shell
$shortcut = $WScriptShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "powershell.exe"
$shortcut.Arguments = "-NoExit -Command `"cd '$installDir'; .\.venv\Scripts\activate; python src/main.py --web`""
$shortcut.IconLocation = "$installDir\static\favicon.ico"
$shortcut.Save()

Write-Host "Installation complete!" -ForegroundColor Green
Write-Host "Double-click the 'Options Scanner' shortcut on your desktop to launch the application." -ForegroundColor Yellow