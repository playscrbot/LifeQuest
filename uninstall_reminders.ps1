$TaskName = "LifeQuest Background Reminders"
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "LifeQuest background reminder task removed."
