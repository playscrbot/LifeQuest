# LifeQuest — Windows desktop reminders

## What this adds
- Optional reminder date/time on each local mission (`YYYY-MM-DD HH:MM`).
- A background worker that checks the same `lifequest.db` file every five minutes.
- Windows toast notifications even after the LifeQuest window is closed.
- Editing a mission resets its reminder delivery state. Completed/deleted missions are not notified.
- Trello cards remain read-only and do not receive local reminders.

## Setup
1. Keep `main.py`, `database.py`, `game_logic.py`, the existing LifeQuest support files, and the new reminder files in the **same project folder**.
2. Open PowerShell in that folder.
3. Activate the same virtual environment used to run LifeQuest.
4. Install the notification dependency:

   `python -m pip install winotify`

5. Run the installer once:

   `powershell -ExecutionPolicy Bypass -File .\install_reminders.ps1`

6. Start LifeQuest normally with `python main.py`.
7. Add or edit a local mission and set a reminder, e.g. `2026-11-16 09:30`.

The scheduled worker checks every five minutes. If a reminder time falls between checks, it can arrive up to about five minutes late. If the PC is asleep, powered off, or Windows notifications are disabled/blocked, delivery may be delayed or suppressed. The worker runs while the user is signed in; it is not a cloud service.

## Remove background startup
Run:

`powershell -ExecutionPolicy Bypass -File .\uninstall_reminders.ps1`

This removes the scheduled task only. It does not delete your LifeQuest data or reminder settings.

## Logs
If a notification does not appear, inspect `reminder_worker.log` in this folder. Also check Windows Settings → System → Notifications and make sure notifications are enabled.

## Existing database
The updated `database.py` adds `reminder_at` and `reminder_sent` columns using additive SQLite migrations. Existing tasks, XP, notes, and integration records are preserved.