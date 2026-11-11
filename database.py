import sqlite3
from datetime import date, datetime
from pathlib import Path

DB_PATH = Path(__file__).with_name("lifequest.db")

class Database:
    def __init__(self, path=DB_PATH):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        self._seed_challenge()
        self._seed_rewards()

    def _create_tables(self):
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            difficulty TEXT NOT NULL,
            due_date TEXT,
            xp INTEGER NOT NULL,
            category TEXT NOT NULL DEFAULT 'General',
            status TEXT NOT NULL DEFAULT 'open',
            completed_at TEXT,
            created_at TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'local',
            external_id TEXT,
            source_url TEXT,
            source_updated_at TEXT,
            source_completed INTEGER NOT NULL DEFAULT 0,
            xp_awarded INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT DEFAULT '',
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS xp_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount INTEGER NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'General'
        );
        CREATE TABLE IF NOT EXISTS achievements (
            key TEXT PRIMARY KEY,
            unlocked_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS challenges (
            day TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            xp INTEGER NOT NULL,
            claimed INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            cost INTEGER NOT NULL CHECK(cost > 0),
            is_default INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS reward_redemptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reward_title TEXT NOT NULL,
            cost INTEGER NOT NULL,
            redeemed_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_type TEXT NOT NULL,
            activity_id TEXT NOT NULL,
            title TEXT NOT NULL,
            completed_at TEXT NOT NULL,
            UNIQUE(activity_type, activity_id)
        );
        """)
        # Safe, additive migration for databases created by earlier LifeQuest versions.
        existing = {row["name"] for row in self.conn.execute("PRAGMA table_info(tasks)")}
        migrations = {
            "category": "TEXT NOT NULL DEFAULT 'General'",
            "source": "TEXT NOT NULL DEFAULT 'local'",
            "external_id": "TEXT",
            "source_url": "TEXT",
            "source_updated_at": "TEXT",
            "source_completed": "INTEGER NOT NULL DEFAULT 0",
            "xp_awarded": "INTEGER NOT NULL DEFAULT 0",
        }
        for column, definition in migrations.items():
            if column not in existing:
                self.conn.execute(f"ALTER TABLE tasks ADD COLUMN {column} {definition}")
        xp_columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(xp_history)")}
        if "category" not in xp_columns:
                    self.conn.execute("ALTER TABLE xp_history ADD COLUMN category TEXT NOT NULL DEFAULT 'General'")
        self.conn.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_external_source
                             ON tasks(source, external_id) WHERE external_id IS NOT NULL""")
        self.conn.commit()

    def _seed_challenge(self):
        today = date.today().isoformat()
        row = self.conn.execute("SELECT day FROM challenges WHERE day=?", (today,)).fetchone()
        if not row:
            self.conn.execute("INSERT INTO challenges(day,title,description,xp) VALUES(?,?,?,?)",
                              (today, "Clear three missions", "Complete any three open missions today. Small wins add up.", 40))
            self.conn.commit()

    def _seed_rewards(self):
        defaults = [
            ("Enjoy a favourite meal", "Order or prepare something you genuinely love.", 150),
            ("Take a guilt-free gaming break", "Enjoy a session of your favourite game.", 200),
            ("Watch a movie", "Pick a film, get comfortable, and enjoy the show.", 300),
            ("Buy something you've wanted", "Put your saved-up reward toward a small wish-list purchase.", 500),
            ("Get a book or hobby item", "Pick up something that supports a hobby or curiosity.", 400),
            ("Spend an afternoon with a friend", "Make time for someone whose company you enjoy.", 600),
            ("Take a day trip", "Explore somewhere new and make a day of it.", 1000),
            ("Plan a special experience", "Save up for a concert, event, class, or memorable outing.", 2000),
        ]
        for title, description, cost in defaults:
            exists = self.conn.execute(
                "SELECT id FROM rewards WHERE title=? AND is_default=1", (title,)
            ).fetchone()
            if not exists:
                self.conn.execute(
                    "INSERT INTO rewards(title,description,cost,is_default,created_at) VALUES(?,?,?,?,?)",
                    (title, description, cost, 1, datetime.now().isoformat(timespec="seconds"))
                )
        self.conn.commit()

    def _dict(self, row):
        return dict(row) if row else None

    def add_task(self, title, description, difficulty, category, due_date, xp):
        cur = self.conn.execute("""INSERT INTO tasks(title,description,difficulty,category,due_date,xp,created_at)
            VALUES(?,?,?,?,?,?,?)""", (title, description, difficulty, category, due_date, xp, datetime.now().isoformat(timespec="seconds")))
        self.conn.commit()
        return cur.lastrowid

    def update_task(self, task_id, title, description, difficulty, category, due_date, xp):
        self.conn.execute("""UPDATE tasks SET title=?,description=?,difficulty=?,category=?,due_date=?,xp=?
            WHERE id=? AND status='open'""", (title, description, difficulty, category, due_date, xp, task_id))
        self.conn.commit()

    def delete_task(self, task_id):
        self.conn.execute("DELETE FROM tasks WHERE id=? AND status='open'", (task_id,))
        self.conn.commit()

    def get_tasks(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM tasks ORDER BY status, due_date IS NULL, due_date, id DESC")]

    def get_task(self, task_id):
        return self._dict(self.conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())

    def complete_task(self, task_id):
        now = datetime.now().isoformat(timespec="seconds")
        row = self.conn.execute(
            "SELECT title FROM tasks WHERE id=? AND status='open' AND source='local'", (task_id,)
        ).fetchone()
        if row is None:
            return False
        self.conn.execute(
            "UPDATE tasks SET status='done',completed_at=? WHERE id=? AND status='open'",
            (now, task_id)
        )
        self._record_activity('task', task_id, row['title'], now)
        self.conn.commit()
        return True

    def _record_activity(self, activity_type, activity_id, title, completed_at=None):
        timestamp = completed_at or datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            "INSERT OR IGNORE INTO activity_log(activity_type,activity_id,title,completed_at) VALUES(?,?,?,?)",
            (activity_type, str(activity_id), title, timestamp)
        )

    def add_note(self, title, body):
        cur = self.conn.execute("INSERT INTO notes(title,body,updated_at) VALUES(?,?,?)",
                                (title, body, datetime.now().isoformat(timespec="seconds")))
        self.conn.commit()
        return cur.lastrowid

    def update_note(self, note_id, title, body):
        self.conn.execute("UPDATE notes SET title=?,body=?,updated_at=? WHERE id=?",
                          (title, body, datetime.now().isoformat(timespec="seconds"), note_id))
        self.conn.commit()

    def delete_note(self, note_id):
        self.conn.execute("DELETE FROM notes WHERE id=?", (note_id,))
        self.conn.commit()

    def get_notes(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM notes ORDER BY updated_at DESC")]

    def add_xp(self, amount, reason, category="General"):
        self.conn.execute("INSERT INTO xp_history(amount,reason,category,created_at) VALUES(?,?,?,?)",
                          (amount, reason, category, datetime.now().isoformat(timespec="seconds")))
        self.conn.commit()

    def get_total_xp(self):
        row = self.conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END),0) AS total FROM xp_history"
        ).fetchone()
        return row["total"]

    def get_available_xp(self):
        # Wallet balance is lifetime XP earned minus redeemed XP.
        row = self.conn.execute("SELECT COALESCE(SUM(amount),0) AS total FROM xp_history").fetchone()
        return row["total"]

    def get_xp_history(self, limit=20):
        return [dict(r) for r in self.conn.execute("SELECT * FROM xp_history ORDER BY id DESC LIMIT ?", (limit,))]

    def get_rewards(self):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM rewards ORDER BY cost ASC, is_default DESC, title COLLATE NOCASE"
        )]

    def get_all_earned_xp_events(self):
        """Positive XP events only; XP spending never counts as weekly performance."""
        return [dict(r) for r in self.conn.execute(
            "SELECT amount, reason, created_at, category FROM xp_history WHERE amount > 0 ORDER BY created_at"
        )]
    
    def get_productivity_category_totals(self):
        return [dict(r) for r in self.conn.execute(
            """SELECT category, SUM(amount) AS xp, COUNT(*) AS events
               FROM xp_history WHERE amount > 0
               GROUP BY category ORDER BY xp DESC, events DESC, category COLLATE NOCASE"""
        )]
    
    def add_reward(self, title, description, cost):
        title = title.strip()
        description = description.strip()
        cost = int(cost)
        if not title:
            raise ValueError("Give your reward a name.")
        if cost <= 0:
            raise ValueError("Reward cost must be greater than zero.")
        cur = self.conn.execute(
            "INSERT INTO rewards(title,description,cost,is_default,created_at) VALUES(?,?,?,0,?)",
            (title, description, cost, datetime.now().isoformat(timespec="seconds"))
        )
        self.conn.commit()
        return cur.lastrowid
    
    def delete_reward(self, reward_id):
        cur = self.conn.execute(
            "DELETE FROM rewards WHERE id=? AND is_default=0", (reward_id,)
        )
        self.conn.commit()
        return cur.rowcount == 1

    def redeem_reward(self, reward_id):
        """Atomically spend wallet XP and record a redemption."""
        now = datetime.now().isoformat(timespec="seconds")
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            reward = self.conn.execute("SELECT * FROM rewards WHERE id=?", (reward_id,)).fetchone()
            if reward is None:
                self.conn.rollback()
                return False, "That reward is no longer available."
            balance = self.conn.execute(
                "SELECT COALESCE(SUM(amount),0) AS total FROM xp_history"
            ).fetchone()["total"]
            if balance < reward["cost"]:
                self.conn.rollback()
                return False, (
                    f"You need {reward['cost']:,} XP, but have {balance:,} XP. "
                    f"Earn {reward['cost'] - balance:,} more XP first."
                )
            self.conn.execute(
                "INSERT INTO xp_history(amount,reason,created_at) VALUES(?,?,?)",
                (-reward["cost"], f"Reward redeemed: {reward['title']}", now)
            )
            self.conn.execute(
                "INSERT INTO reward_redemptions(reward_title,cost,redeemed_at) VALUES(?,?,?)",
                (reward["title"], reward["cost"], now)
            )
            self.conn.commit()
            return True, f"Redeemed: {reward['title']} (-{reward['cost']:,} XP)"
        except Exception:
            self.conn.rollback()
            raise

    def get_reward_redemptions(self, limit=10):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM reward_redemptions ORDER BY id DESC LIMIT ?", (limit,)
        )]

    def get_daily_challenge(self):
        self._seed_challenge()

        row = self.conn.execute(
            "SELECT * FROM challenges WHERE day=?",
            (date.today().isoformat(),)
        ).fetchone()

        if row is None:
            raise RuntimeError("Today's daily challenge could not be created.")
        
        return dict(row)

    def claim_challenge(self, day):
        cur = self.conn.execute("UPDATE challenges SET claimed=1 WHERE day=? AND claimed=0", (day,))
        self.conn.commit()
        return cur.rowcount == 1

    def get_activity_dates(self):
        rows = self.conn.execute(
            "SELECT DISTINCT substr(completed_at,1,10) AS day FROM activity_log ORDER BY day"
        )
        return [r['day'] for r in rows]
    
    def get_activity_counts(self, start_day, end_day):
        rows = self.conn.execute(
            "SELECT substr(completed_at,1,10) AS day, COUNT(*) AS count FROM activity_log "
            "WHERE substr(completed_at,1,10) BETWEEN ? AND ? GROUP BY day",
            (start_day, end_day)
        )
        return {r['day']: r['count'] for r in rows}
    
    def get_recent_activities(self, limit=12):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM activity_log ORDER BY completed_at DESC, id DESC LIMIT ?", (limit,)
        )]

    def get_completion_dates(self):
        rows = self.conn.execute("SELECT DISTINCT substr(completed_at,1,10) AS day FROM tasks WHERE status='done' AND completed_at IS NOT NULL")
        return [r["day"] for r in rows]

    def get_best_streak(self):
        from game_logic import calculate_best_streak
        return calculate_best_streak(self.get_completion_dates())

    def get_unlocked_achievements(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM achievements")]

    def unlock_achievement(self, key):
        cur = self.conn.execute("INSERT OR IGNORE INTO achievements(key,unlocked_at) VALUES(?,?)",
                                (key, datetime.now().isoformat(timespec="seconds")))
        self.conn.commit()
        return cur.rowcount == 1

    def sync_trello_card(self, card, list_name, is_completed):
        """Upsert one Trello card. XP is granted once on a later open -> completed transition."""
        from game_logic import XP_REWARDS
        external_id = card["id"]
        title = card.get("name") or "Untitled Trello card"
        description = card.get("desc") or ""
        due = (card.get("due") or "")[:10] or None
        url = card.get("url") or card.get("shortUrl") or ""
        updated = card.get("dateLastActivity") or ""
        labels = " ".join((label.get("name") or "") for label in card.get("labels", []))
        label_text = labels.lower()
        if "epic" in label_text:
            difficulty = "Epic"
        elif "hard" in label_text:
            difficulty = "Hard"
        elif "easy" in label_text:
            difficulty = "Easy"
        else:
            difficulty = "Medium"
        xp = XP_REWARDS[difficulty]
        now = datetime.now().isoformat(timespec="seconds")
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE source='trello' AND external_id=?", (external_id,)
        ).fetchone()
    
        if row is None:
            # Existing completed cards are imported as completed but do not award retroactive XP.
            self.conn.execute(
                """INSERT INTO tasks
                   (title,description,difficulty,due_date,xp,category,status,completed_at,created_at,
                    source,external_id,source_url,source_updated_at,source_completed,xp_awarded)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
                (title, description, difficulty, due, xp, list_name or "Trello",
                "done" if is_completed else "open", None, now,
                "trello", external_id, url, updated, int(bool(is_completed)))
            )
            self.conn.commit()
            return "imported", False
    
        was_completed = bool(row["source_completed"])
        already_awarded = bool(row["xp_awarded"])
        award_xp = bool(is_completed) and not was_completed and not already_awarded
        new_status = "done" if is_completed else "open"
        completed_at = now if award_xp else (row["completed_at"] if is_completed else None)
    
        self.conn.execute(
            """UPDATE tasks SET title=?,description=?,difficulty=?,due_date=?,xp=?,category=?,status=?,
               completed_at=?,source_url=?,source_updated_at=?,source_completed=?,
               xp_awarded=CASE WHEN ? THEN 1 ELSE xp_awarded END
               WHERE id=?""",
            (title, description, difficulty, due, xp, list_name or "Trello", new_status, completed_at, url,
             updated, int(bool(is_completed)), int(award_xp), row["id"])
        )
        if award_xp:
            self.conn.execute(
                "INSERT INTO xp_history(amount,reason,created_at,category) VALUES(?,?,?,?)",
                (xp, f"Trello completed: {title}", now, list_name or "Trello")
            )
            self._record_activity('trello_task', external_id, title, now)
        self.conn.commit()
        return ("updated" if not award_xp else "completed"), award_xp
    
    def get_trello_task_count(self):
        row = self.conn.execute("SELECT COUNT(*) AS n FROM tasks WHERE source='trello'").fetchone()
        return row["n"]

    def close(self):
        self.conn.close()