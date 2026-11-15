import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "lifequest.db"
LOG_PATH = BASE_DIR / "reminder_worker.log"

def log(message):
    try:
        with LOG_PATH.open("a", encoding="utf-8") as stream:
            stream.write(f"[{datetime.now().isoformat(timespec='seconds')}] {message}\n")
    except OSError:
        pass

def main():
    try:
        from winotify import Notification, audio
    except Exception as exc:
        log(f"winotify import failed: {exc}")
        return 2

    if not DB_PATH.exists():
        log(f"Database not found: {DB_PATH}")
        return 0

    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        # Defensive migration for projects whose database has not yet been
        # opened by the updated desktop app.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
        if "reminder_at" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN reminder_at TEXT")
        if "reminder_sent" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN reminder_sent INTEGER NOT NULL DEFAULT 0")
        conn.commit()

        now = datetime.now().isoformat(timespec="minutes")
        rows = conn.execute(
            """SELECT id, title, due_date, reminder_at
               FROM tasks
               WHERE status='open'
                 AND source='local'
                 AND reminder_at IS NOT NULL
                 AND reminder_at <= ?
                 AND reminder_sent=0
               ORDER BY reminder_at, id""",
            (now,),
        ).fetchall()

        for row in rows:
            title = (row["title"] or "Your mission").strip()
            message = "It's time to work on this mission."
            if row["due_date"]:
                message += f" Due date: {row['due_date']}."
            try:
                toast = Notification(
                    app_id="LifeQuest",
                    title=f"⚔ Mission reminder: {title[:90]}",
                    msg=message,
                    duration="long",
                )
                toast.set_audio(audio.Default, loop=False)
                toast.show()
                # Mark only after the notification API accepted the toast.
                conn.execute(
                    "UPDATE tasks SET reminder_sent=1 WHERE id=? AND reminder_sent=0",
                    (row["id"],),
                )
                conn.commit()
                log(f"Sent reminder for task {row['id']}: {title}")
            except Exception as exc:
                log(f"Failed reminder for task {row['id']}: {exc}")
        return 0
    except Exception as exc:
        log(f"Worker error: {exc}")
        return 1
    finally:
        conn.close()

if __name__ == "__main__":
    raise SystemExit(main())