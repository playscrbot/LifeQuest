# Run this script once from PowerShell to register the background reminder task.
# It creates a per-user scheduled task that checks reminders every five minutes
# and again whenever the user signs in.

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Worker = Join-Path $ProjectDir "reminder_worker.py"
$Python = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $Python) {
    $Python = (Get-Command python.exe -ErrorAction Stop).Source
}
if (-not (Test-Path $Worker)) {
    throw "Could not find reminder_worker.py in $ProjectDir"
}

$TaskName = "LifeQuest Background Reminders"
$Action = New-ScheduledTaskAction -Execute $Python -Argument "`"$Worker`"" -WorkingDirectory $ProjectDir
$AtLogon = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Repeating = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 2) `
    -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger @($AtLogon, $Repeating) `
    -Principal $Principal -Settings $Settings -Description "Checks LifeQuest mission reminders." -Force | Out-Null

Write-Host "LifeQuest background reminders are installed." -ForegroundColor Green
Write-Host "The worker checks every five minutes while you are signed in."
Write-Host "You can close the LifeQuest window; the scheduled worker runs separately."
