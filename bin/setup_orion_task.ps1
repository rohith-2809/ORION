<#
.SYNOPSIS
    Sets up a Windows Scheduled Task to automatically start the ORION system on user logon.

.DESCRIPTION
    This script registers a new scheduled task named "OrionSystemStartup" that triggers
    when the current user logs into Windows. It executes the existing start_orion.bat
    script which launches the WSL backend, Windows agent, and frontend.

    NOTE: MUST BE RUN AS ADMINISTRATOR.
#>

$TaskName = "OrionSystemStartup"
$BatPath = "\\wsl$\Ubuntu\home\rohith\ORION\start_orion.bat"
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$BatPath`""

# Check if running as Admin
$currentUser = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $currentUser.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "Please run this script as Administrator to create the Scheduled Task." -ForegroundColor Red
    Pause
    Exit
}

# Unregister existing task if it exists
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Write-Host "Removing existing task: $TaskName" -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Register the new task
try {
    Register-ScheduledTask -TaskName $TaskName -Trigger $Trigger -Action $Action -Description "Launches the ORION Cognitive Core at Startup."
    Write-Host "Successfully registered Scheduled Task: $TaskName" -ForegroundColor Green
    Write-Host "ORION will automatically start when you next log in." -ForegroundColor Cyan
} catch {
    Write-Host "Failed to register Scheduled Task. Error: $_" -ForegroundColor Red
}

Pause
