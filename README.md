# LifeQuest
**Turn your existing productivity into a game.**
LifeQuest is a local-first productivity RPG built with **Python, Tkinter, and SQLite**. It adds a progression layer to everyday work through experience points (XP), levels, streaks, achievements, daily challenges, and activity statistics.

The project also includes a **read-only Trello integration**. LifeQuest can import cards from a Trello board and periodically check for updates while the desktop app is running. You can keep managing your work in Trello while LifeQuest turns that work into game progress.

> **Current status:** MVP with local task management, notes, gamification, and Trello read-only polling sync. The Trello connection has not been validated against every account or board configuration. See [Known limitations](#known-limitations).

---

## Contents

- [What LifeQuest does](#what-lifequest-does)
- [Features](#features)
- [Daily streaks and activity calendar](#daily-streaks-and-activity-calendar)
- [How the game system works](#how-the-game-system-works)
- [Requirements](#requirements)
- [Installation and launch](#installation-and-launch)
- [First steps](#first-steps)
- [Trello integration](#trello-integration)
- [Notion integration](#notion-integration)
- [Automatic Trello synchronization](#automatic-trello-synchronization)
- [How Trello tasks are interpreted](#how-trello-tasks-are-interpreted)
- [Project structure](#project-structure)
- [Data storage and privacy](#data-storage-and-privacy)
- [Troubleshooting](#troubleshooting)
- [Known limitations](#known-limitations)
- [Development notes](#development-notes)
- [Possible next steps](#possible-next-steps)

---

## What LifeQuest does

Most task managers record what you need to do. LifeQuest adds a progression layer to that work.

You can:

1. Create and complete tasks inside LifeQuest, or keep tasks in Trello and import them.
2. Assign difficulty to local tasks.
3. Earn XP when eligible tasks are completed.
4. Level up as your XP total increases.
5. Build streaks by maintaining activity across days.
6. Unlock achievements and claim a daily challenge reward.
7. Review your XP activity and basic productivity statistics.

LifeQuest is designed to complement an existing workflow, not force you to abandon it.

## Features

### Local task management
- Create tasks and organize them by difficulty.
- Track completion and task progression.
- Distinguish locally created tasks from Trello-imported tasks.

### Gamification
- XP rewards based on task difficulty.
- Level progression.
- Current and best streak tracking.
- Achievement unlocks.
- Daily challenge reward.
- XP activity history and basic statistics.

### Reward shop
- Spend earned XP on real-life rewards such as a movie, a purchase, or a day trip.
- Includes a starter catalog of rewards at different XP prices.
- Create and remove your own custom rewards.
- Confirm purchases before redeeming them.
- Shows your available XP balance and recent redemptions.
- XP spent in the shop reduces the spendable balance, but **does not reduce lifetime XP or player level**.

### Daily streaks and activity calendar
- Records a dated activity event when a local task is completed, a Trello card transitions from open to complete during sync, or a daily challenge is claimed.
- Calculates current and best consecutive-day streaks.
- Detects missed calendar days after the last active date.
- Unlocks permanent streak badges at 3, 7, 14, 30, 60, and 100 consecutive active days.
- Displays a GitHub-style heatmap for the last 365 days, with darker/lighter cells showing activity volume.
- Existing task completion timestamps are backfilled into the activity ledger when the updated app first opens.

A day counts as active when at least one qualifying activity is completed on that date. Multiple completions on one date still count as one streak day, while the heatmap shows their activity volume. Reward redemptions and XP spending do not count as completed activities.

### Notes
- Keep supporting notes alongside your productivity workflow.

### Trello read-only integration
- Connect using a Trello API key and read-only authorization token.
- Choose a board and load its lists.
- Select which list or lists represent completed work.
- Import cards into LifeQuest.
- Manually sync or enable periodic auto-sync.
- Open, edit, and complete Trello cards in Trello; LifeQuest does not write changes back.

### Local-first storage
- Application data is stored in a SQLite database on your computer.
- Core local features work without an internet connection.
- Trello features require an internet connection.

---

## How the game system works

### XP rewards

The current reward configuration is:

| Difficulty | XP |
|---|---:|
| Easy | 10 XP |
| Medium | 25 XP |
| Hard | 50 XP |
| Epic | 100 XP |

These values are defined in `game_logic.py` and can be adjusted as the game balance evolves.

### Level progression

LifeQuest uses increasing XP thresholds for successive levels. Later levels require more XP than earlier ones.

### Completion and XP rules

- A local task awards XP when it is completed, subject to the app's task rules.
- A Trello card awards XP when LifeQuest detects an open-to-completed transition during synchronization.
- Re-syncing a card does not repeatedly award XP for the same completion.
- Cards that were already completed when first imported are marked completed but do **not** grant retroactive XP.

The last rule prevents importing an old Trello board from instantly granting XP for every historical completed card.

### Streaks, achievements, and daily challenge

LifeQuest tracks activity streaks and achievement progress. The daily challenge reward in this MVP is claimed by the user; the app does not yet automatically verify every possible challenge condition.

---

## Requirements

- **Python:** 3.9 or newer recommended.
- **Tkinter:** required for the desktop interface. It is included with many standard Python installations, but some Linux distributions package it separately.
- **Internet connection:** needed only for Trello connection and synchronization.
- **Trello account:** required only if you want to use the Trello integration.

The current project uses Python's standard library for its core functionality. No `pip install` step is expected.

### Check your Python installation

```bash
python --version
```

On some systems, use:

```bash
python3 --version
```

To check whether Tkinter is available:

```bash
python -m tkinter
```

If a small Tkinter test window appears, Tkinter is available.

---

## Installation and launch

### 1. Extract the project

Extract the downloaded ZIP file into a folder, for example:

```text
LifeQuest/
```

### 2. Open a terminal in that folder

The folder should contain `main.py`, `database.py`, `game_logic.py`, `trello_client.py`, and the other project files.

### 3. Launch LifeQuest

Windows:

```bash
python main.py
```

macOS / Linux (depending on your Python installation):

```bash
python3 main.py
```

### 4. Database creation

LifeQuest creates its SQLite database automatically when it starts. The database file is named:

```text
lifequest.db
```

Keep this file if you want to preserve your local tasks, notes, and progression data. Deleting it resets the locally stored app data.

---

## First steps

A suggested first run:

1. Launch LifeQuest.
2. Create a small local task.
3. Choose a difficulty.
4. Complete the task and check that XP changes.
5. Explore your level, streak, achievements, notes, and statistics.
6. If you use Trello, follow the integration instructions below.

Start with a low-risk test task before importing a large Trello board.

---

## Trello integration

LifeQuest's Trello integration is **read-only**. It retrieves board, list, and card information. It does not create, edit, move, archive, or complete Trello cards.

### Step 1: Get a Trello API key

1. Sign in to Trello.
2. Open the Trello developer portal: <https://trello.com/apps/admin>.
3. Create or open an app / Power-Up configuration as required by Trello.
4. Copy the API key shown for the app.

Official API introduction:
<https://developer.atlassian.com/cloud/trello/guides/rest-api/api-introduction/>

### Step 2: Connect from LifeQuest

1. Open the **Trello** section in LifeQuest.
2. Choose **Connect Trello**.
3. Paste your API key.
4. Choose the option to generate a read-only token.
5. Trello opens an authorization page in your browser.
6. Review the requested permissions and approve if you agree.
7. Copy the token Trello displays.
8. Return to LifeQuest, paste the token, and complete the connection.

The authorization flow requests read access. Do not share your API key or token with anyone.

Official authorization guide:
<https://developer.atlassian.com/cloud/trello/guides/rest-api/authorization/>

### Step 3: Select a board

1. After connecting, choose the Trello board you want to import.
2. Load the board's lists.
3. Identify the list or lists that mean a task is finished in your workflow.
4. Select those completion lists.
5. Run **Sync now** to import the cards.

For example, if your board has `To Do`, `Doing`, and `Done`, select `Done` as a completion list.

### Step 4: Check the imported tasks

Open the task view and look for the source indicator. Locally created tasks and Trello tasks are distinguished so you can tell where each task came from.

Trello tasks are managed in Trello. Use Trello to edit a card, change its list, or mark it complete; then synchronize LifeQuest to refresh the imported information.


## Notion integration
LifeQuest can import rows from a Notion database through a read-only internal integration.

1. Create an internal integration in Notion and grant it **Read content** capability.
2. Share the target database with that integration using the database's Share/Connections controls.
3. Paste the integration's internal token into the **Notion Integration** panel and click **Connect Notion**.
4. Copy the database ID from its Notion URL, paste it into **Database ID**, and click **Load database**.
5. Click **Sync Notion** to import or refresh database rows.

LifeQuest uses Notion API version `2025-09-03`. It retrieves the database's first data source and queries that data source. If a database contains multiple data sources, the first returned source is currently selected. Page title, rich-text description, date, status/select, and page URL are interpreted when present. Completed statuses recognized by default are Done, Complete, Completed, Finished, and Closed.

Credentials are held in memory only and cleared when LifeQuest closes. Imported Notion tasks are read-only in LifeQuest; this integration does not create, edit, archive, or delete Notion pages. Newly observed open-to-completed transitions award the default Medium task XP once. Tasks already completed on first import do not grant retroactive XP. Sync is manual; Notion auto-sync and webhooks are not included.

A Notion integration can only access pages and databases explicitly shared with it. A successful token connection does not grant access to the entire workspace.

---

## Automatic Trello synchronization

LifeQuest can periodically check the selected Trello board while the app is open.

### Start auto-sync

1. Connect Trello.
2. Select a board.
3. Load its lists.
4. Select the list or lists that represent completed work.
5. Click **Start auto-sync**.

LifeQuest performs a sync immediately, then schedules another check every 60 seconds by default.

Click **Stop auto-sync** to stop scheduled checks.

### Change the polling interval

Open `config.py` and find:

```python
TRELLO_AUTO_SYNC_SECONDS = 60
```

Change `60` to the desired number of seconds. For example:

```python
TRELLO_AUTO_SYNC_SECONDS = 120
```

That sets the interval to two minutes. Keep the interval reasonable to avoid unnecessary API requests.

### Important: polling is not a webhook

Auto-sync uses **scheduled polling**:

- LifeQuest asks Trello for updates at the configured interval.
- It works only while LifeQuest is running and connected.
- It stops when you stop auto-sync, disconnect, or close the app.
- It does not run as a background Windows service.
- It does not synchronize while your computer is off or LifeQuest is closed.

A webhook-based architecture could provide event-driven updates in a future version, but it requires a publicly reachable server endpoint and additional deployment/security work. Polling is simpler for this desktop MVP.

### Responsiveness and database safety

The Trello network request runs on a background thread so the interface does not need to wait for the network response. Database updates are applied on the Tkinter main thread, avoiding unsafe concurrent use of the SQLite connection.

---

## How Trello tasks are interpreted

The current integration follows these rules:

| Trello condition | LifeQuest behavior |
|---|---|
| Card is on a selected completion list | Imported as completed |
| Card has `dueComplete` set to true | Imported as completed |
| Card is on another active list and is not due-complete | Imported as open |
| Card is archived (`closed`) | Skipped; archive status is not treated as completion |
| Card is already complete on first import | Marked complete, with no retroactive XP |
| Previously open card becomes complete on a later sync | Completion is recorded and XP is awarded once |
| Same card is synchronized repeatedly | Existing imported task is updated; duplicate task / XP is avoided |

### Difficulty mapping

The integration uses Trello labels to infer difficulty when recognized labels are present:

- `epic` → Epic
- `hard` → Hard
- `easy` → Easy
- No recognized difficulty label → Medium

If your board uses a different label convention, the mapping can be customized in the code later.

### Read-only boundary

LifeQuest does not send Trello write requests. Completing a task in LifeQuest does not complete the corresponding Trello card, and changing a Trello card does not instantly change LifeQuest until the next sync.

---

## Project structure

```text
LifeQuest/
├── main.py             # Tkinter interface and application orchestration
├── database.py         # SQLite setup, migrations, and task persistence
├── game_logic.py       # XP, levels, streaks, and achievement logic
├── trello_client.py    # Read-only Trello API client
├── config.py           # App configuration, including auto-sync interval
├── README.md           # Project documentation
└── lifequest.db        # Created automatically when the app runs
```

### Responsibilities

**`main.py`**
- Builds the desktop interface.
- Coordinates local tasks, notes, and game progression.
- Manages Trello connection, board/list selection, and sync controls.
- Schedules auto-sync and displays sync results.

**`database.py`**
- Creates and updates the SQLite schema.
- Stores local and imported tasks.
- Identifies Trello cards using their external IDs.
- Prevents duplicate imported cards and repeated XP awards.

**`game_logic.py`**
- Defines XP rewards and level calculations.
- Contains progression-related logic such as streaks and achievements.

**`trello_client.py`**
- Communicates with Trello's REST API.
- Retrieves member, board, list, and card data.
- Contains read operations only.

**`config.py`**
- Stores configuration values such as the Trello polling interval.

---

## Data storage and privacy

### Local data

LifeQuest stores application data in `lifequest.db`, a SQLite database in the project directory. This includes local app data such as tasks, notes, and progression records.

### Trello credentials

In the current implementation, the Trello API key and token are kept in application memory while LifeQuest is running. They are not written to the LifeQuest SQLite database and are cleared when the application closes.

This is an MVP limitation: you may need to connect again after restarting the app.

### Network activity

The app contacts Trello when you connect, load boards/lists/cards, or run manual/automatic synchronization. Local task management does not require Trello.

### Backups

To back up local LifeQuest data, close the app and copy `lifequest.db` to a safe location. To restore it, close LifeQuest and place the backup database back in the project folder.

Do not edit the SQLite database manually while LifeQuest is running.

---

## Troubleshooting

### `python` is not recognized

Python may not be installed or may not be on your system PATH. Install Python and enable the option to add Python to PATH, or try `python3` where appropriate.

### `No module named tkinter`

Your Python installation does not include Tkinter.

- On many Windows installations, reinstall or modify Python and include Tcl/Tk support.
- On Debian/Ubuntu-based Linux systems, the package is commonly named `python3-tk`.
- On macOS, use a Python distribution that includes Tk support.

### LifeQuest window does not open

1. Open a terminal in the project folder.
2. Run `python main.py` (or `python3 main.py`).
3. Read the full error message printed in the terminal.
4. Check that all project `.py` files are in the same folder.

If the application exits with a traceback, keep the complete traceback; the final few lines alone may not show the root cause.

### Trello connection fails

Check the following:

- The API key was copied correctly.
- The token was generated through Trello's authorization page.
- You approved read access.
- The token was pasted without extra spaces or missing characters.
- Your network can reach Trello.
- The account has access to the board you are trying to load.

If Trello returns an authorization or rate-limit error, wait if necessary and try again. Do not post your API key or token in a public issue or chat.

### Trello board or list does not appear

- Confirm the connected Trello account can access the board.
- Reconnect if the token is invalid or expired.
- Load the board's lists after selecting the board.
- Confirm that the board is not closed or inaccessible.

### A Trello task is not marked complete

Check whether:
- The card is in one of the completion lists selected in LifeQuest, or
- The card's due date is marked complete in Trello (`dueComplete`).

A list named `Done` is not automatically considered complete unless you select it in LifeQuest.

### XP was not awarded for an imported completed card

That is expected if the card was already completed when it was first imported. LifeQuest does not grant XP retroactively for historical completed cards.

For a card that was imported as open, XP should be awarded when a later sync detects that it has become complete. Repeated syncs should not award the same completion repeatedly.

### Auto-sync is not running

- Confirm that auto-sync is started.
- Confirm that Trello is still connected.
- Keep LifeQuest open.
- Check the configured interval in `config.py`.
- Remember that auto-sync is polling, not a background service; it cannot run while the app is closed.

---

## Known limitations

This is an evolving MVP. Current limitations include:

- Trello integration is read-only; there is no write-back to Trello.
- Trello credentials are not persisted between app sessions.
- Auto-sync works only while the desktop app is open.
- Sync uses polling, not webhooks.
- The daily challenge is user-confirmed rather than automatically verified.
- Reward redemption is local to LifeQuest; it does not make purchases or book experiences for the user.
- Trello difficulty inference depends on recognized labels; otherwise cards default to Medium.
- There is no full conflict-resolution interface for differences between local and external task data.
- The integration has not been verified against every Trello workspace, board permission setup, or account configuration.

---

## Development notes

### Run from source

```bash
python main.py
```

### Check Python syntax

From the project directory:

```bash
python -m py_compile main.py database.py game_logic.py trello_client.py config.py
```

### Database changes

The database layer includes migration logic for adding Trello-related task metadata to an existing database. Keep a backup of `lifequest.db` before making schema changes during development.

### Safe integration principle

The Trello client is intentionally read-only. Keep external task mutations out of `trello_client.py` unless the product direction explicitly changes and the user experience includes clear permission and confirmation controls.

---

## Possible next steps

1. **Validate a real Trello connection** — test with an actual board and verify imports, completion detection, and auto-sync behavior.
2. **Improve sync visibility** — show last successful sync time, next scheduled sync, imported/updated counts, and actionable errors.
3. **Persist credentials securely** — use the operating system's credential store rather than plain text or the SQLite database.
4. **Add more integrations** — consider Notion or other task sources after the Trello workflow is stable.
5. **Improve task identity and conflict handling** — make source ownership and duplicate handling more transparent.
6. **Expand the RPG layer** — quests, milestones, skill trees, rewards, and challenge verification.
7. **Add tests** — automate tests for database migrations, XP idempotency, Trello response handling, and sync edge cases.

These are proposals, not promises about features already implemented.

---

## License

No license has been specified yet. If you plan to publish or distribute LifeQuest, choose and add an appropriate license before presenting the project as open source.


## Weekly Leaderboard

The Weekly Leaderboard page adds five personal performance metrics:

1. **Best-performing week** — the Monday–Sunday week with the highest positive XP earned.
2. **Average weekly XP** — total positive XP divided by the number of calendar weeks from the first recorded XP week through the current week. Weeks with zero XP are included.
3. **Percentage improvement** — current week's XP compared with the previous calendar week. If the previous week had zero XP and the current week has XP, the page displays "New momentum" instead of an undefined percentage.
4. **Most productive category** — the category with the most positive XP earned, with a category breakdown below.
5. **Longest period of consistency** — the longest consecutive run of dates with a qualifying activity, using the same activity rules as the Streaks page.

### Productivity categories

Local missions now have a category field: General, Work, Learning, Health, Creative, Finance, Household, or Personal. Existing databases are migrated additively; old missions are assigned **General**. Trello cards use their Trello list name as the category. Daily Challenge XP is grouped under **Daily Challenge**.

Weekly scores count positive XP earnings only. Reward redemptions and other negative XP entries do not lower a week's performance score. This is a personal history for this LifeQuest profile; it does not compare separate users or sync a global ranking.


## Dashboard enhancements

The dashboard now includes all-time completed missions, XP earned during the current Monday–Sunday week, and missions completed during the current week. It also shows the unlocked achievement badges and the next locked achievement, with a live progress hint. If no achievement has been unlocked yet, the first achievement is presented as the first goal. The Achievements page and dashboard use the same achievement catalogue.