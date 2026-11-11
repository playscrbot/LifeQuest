# LifeQuest
A local-first productivity RPG built with Python, Tkinter and SQLite.

## Features in this MVP
- Task manager with Easy / Medium / Hard / Epic difficulty
- XP rewards and level progression
- Notes
- Achievement unlocks
- Daily challenge reward
- Current and best streak tracking
- XP activity history and basic statistics
- Persistent local SQLite database

## Requirements
- Python 3.9+
- Tkinter (usually included with standard Python installations)

## Run
```bash
python main.py
```

The `lifequest.db` database is created automatically in the project folder.

## Notes
- XP is awarded once when a task is completed.
- Completed tasks are protected from editing/deletion to preserve progression history.
- The daily challenge reward is currently a once-per-day claim. Challenge completion is user-confirmed in this MVP; automatic condition verification is planned for a later iteration.
- The app works offline. AI challenge generation is not included yet.