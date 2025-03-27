@echo off
:: Options Scanner Installation Script for Windows CMD
:: Run as Administrator

:: Check if running as admin
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Please run this script as Administrator
    pause
    exit /b
)

echo Installing prerequisites...
:: Check if Chocolatey is installed
where choco >nul 2>&1
if %errorLevel% neq 0 (
    echo Installing Chocolatey...
    @"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -InputFormat None -ExecutionPolicy Bypass -Command "[System.Net.ServicePointManager]::SecurityProtocol = 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))" && SET "PATH=%PATH%;%ALLUSERSPROFILE%\chocolatey\bin"
)

choco install -y git python --version=3.12
python -m pip install --upgrade pip
pip install virtualenv

echo Cloning repository...
set "installDir=%USERPROFILE%\Documents\OptionsScanner"
if exist "%installDir%" (
    rmdir /s /q "%installDir%"
)
git clone https://github.com/oghenetejiriorukpegmail/option-hybrid-scanner-NAS100.git "%installDir%"

echo Setting up virtual environment...
cd /d "%installDir%"
python -m venv .venv
call .venv\Scripts\activate.bat
pip install -r requirements.txt

echo Creating desktop shortcut...
set "shortcutPath=%USERPROFILE%\Desktop\Options Scanner.lnk"
set "iconPath=%installDir%\static\favicon.ico"

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%shortcutPath%'); $s.TargetPath = 'cmd.exe'; $s.Arguments = '/k \"cd /d \"%installDir%\" && call .venv\Scripts\activate.bat && python src/main.py --web\"'; $s.IconLocation = '%iconPath%'; $s.Save()"

echo Installation complete!
echo Double-click the "Options Scanner" shortcut on your desktop to launch the application.
pause