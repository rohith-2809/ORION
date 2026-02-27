$ErrorActionPreference = "Stop"

$source = "\\wsl$\Ubuntu\home\rohith\ORION"
$dest = "G:\ORION_USB"

Write-Host "Creating ORION Folder Architecture on $dest..." -ForegroundColor Cyan

# 1. Create Core Directories
$folders = @(
    "bin",
    "core",
    "env",
    "memory",
    "models",
    "orion_ui",
    "storage\outputs",
    "storage\jobs",
    "storage\docs",
    "logs"
)

foreach ($f in $folders) {
    New-Item -ItemType Directory -Force -Path "$dest\$f" | Out-Null
    Write-Host "Created: $dest\$f"
}

Write-Host "`nCopying ORION System Files using Robocopy... (This may take a minute)" -ForegroundColor Cyan

# Use Robocopy for deep paths and robustness.
# /E = copy subdirectories including empty
# /MT:8 = multithreaded copied
# /NP = no progress (cleaner logs)
# /NFL /NDL = no file/dir logging
# /XD = exclude directories

robocopy "$source" "$dest\bin" *.bat *.sh *.ps1 /XD "*" /NP /NFL /NDL | Out-Null
robocopy "$source" "$dest\core" *.py requirements.txt /XD "*" /NP /NFL /NDL | Out-Null
robocopy "$source" "$dest\memory" *.json /XD "*" /NP /NFL /NDL | Out-Null

if (Test-Path "$source\jobs") {
    robocopy "$source\jobs" "$dest\storage\jobs" /E /NP /NFL /NDL | Out-Null
}

if (Test-Path "$source\models") {
    robocopy "$source\models" "$dest\models" /E /NP /NFL /NDL | Out-Null
}

if (Test-Path "$source\orion") {
    # Skip node_modules because it causes path length errors.
    robocopy "$source\orion" "$dest\orion_ui" /E /XD "node_modules" /NP /NFL /NDL | Out-Null
}

Write-Host "Copying dependencies... (ORION-env) [This takes time!]" -ForegroundColor Yellow
if (Test-Path "$source\ORION-env") {
    robocopy "$source\ORION-env" "$dest\env\ORION-env" /E /NP /NFL /NDL | Out-Null
}

Write-Host "`n=======================================================" -ForegroundColor Green
Write-Host "✅ ORION Migration Complete!" -ForegroundColor Green
Write-Host "Your system has been successfully moved to G:\ORION_USB" -ForegroundColor Green
Write-Host "Next Step: Update the launch scripts in G:\ORION_USB\bin to CD into the USB drive (e.g., /mnt/g/ORION_USB) instead of the home directory." -ForegroundColor Yellow
Write-Host "Note: You will need to run 'npm install' inside G:\ORION_USB\orion_ui before starting the frontend." -ForegroundColor Yellow
Write-Host "=======================================================" -ForegroundColor Green
Pause
