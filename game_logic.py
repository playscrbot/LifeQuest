from datetime import date, timedelta

XP_REWARDS = {"Easy": 10, "Medium": 25, "Hard": 50, "Epic": 100}

def level_from_xp(total_xp):
    # Level thresholds grow gradually: 100, 150, 200, 250...
    level, threshold, remaining = 1, 100, max(0, int(total_xp))
    while remaining >= threshold:
        remaining -= threshold
        level += 1
        threshold += 50
    return level, remaining, threshold

def xp_for_next_level(level):
    return 100 + (level - 1) * 50

def calculate_best_streak(date_strings):
    days = sorted({date.fromisoformat(d) for d in date_strings})
    if not days:
        return 0
    best = current = 1
    for prev, day in zip(days, days[1:]):
        if day == prev + timedelta(days=1):
            current += 1
        else:
            current = 1
        best = max(best, current)
    return best

def get_streak(date_strings):
    days = {date.fromisoformat(d) for d in date_strings}
    if not days:
        return 0
    today = date.today()
    cursor = today if today in days else today - timedelta(days=1)
    if cursor not in days:
        return 0
    streak = 0
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak

STREAK_MILESTONES = (3, 7, 14, 30, 60, 100)

def get_streak_status(date_strings, today=None):
    """Return current/best streak, missed days, and next milestone information."""
    today = today or date.today()
    days = {date.fromisoformat(value) for value in date_strings}

    cursor = today if today in days else today - timedelta(days=1)
    current = 0
    while cursor in days:
        current += 1
        cursor -= timedelta(days=1)

    ordered_days = sorted(days)
    best = calculate_best_streak([day.isoformat() for day in days])
    last_active = ordered_days[-1] if ordered_days else None

    # Count the most recent gap with no activity. If active today, compare
    # today with the previous active date; otherwise compare the last date to today.
    if last_active is None:
        missed_days = 0
    elif last_active == today and len(ordered_days) >= 2:
        missed_days = max(0, (ordered_days[-1] - ordered_days[-2]).days - 1)
    elif last_active < today:
        missed_days = max(0, (today - last_active).days - 1)
    else:
        missed_days = 0

    next_milestone = next((milestone for milestone in STREAK_MILESTONES if milestone > current), None)
    previous_milestone = max((milestone for milestone in STREAK_MILESTONES if milestone <= current), default=0)
    if next_milestone is None:
        progress, remaining = 1.0, 0
    else:
        span = next_milestone - previous_milestone
        progress = (current - previous_milestone) / span if span else 0.0
        remaining = next_milestone - current

    if current == 0 and last_active and missed_days > 0:
        status = f"Streak paused after {missed_days} missed day{'s' if missed_days != 1 else ''}."
    elif current > 0 and last_active == today:
        status = "You're active today. Keep the momentum going!"
    elif current > 0:
        status = "Complete an activity today to keep your streak alive."
    else:
        status = "Complete an activity to start your first streak."

    return {
        "current": current,
        "best": best,
        "missed_days": missed_days,
        "last_active": last_active.isoformat() if last_active else None,
        "today_active": today in days,
        "next_milestone": next_milestone,
        "remaining": remaining,
        "progress": max(0.0, min(1.0, progress)),
        "status": status,
    }

def check_achievements(db):
    tasks = db.get_tasks()
    completed = sum(
        1 for task in tasks
        if task["status"] == "done"
    )

    xp = db.get_total_xp()
    level = level_from_xp(xp)[0]
    streak = get_streak(db.get_completion_dates())
    
    checks = [
        ("first_task", completed >= 1),
        ("ten_tasks", completed >= 10),
        ("twenty_five", completed >= 25),
        ("seven_day", streak >= 7),

        ("level_five", level >= 5),
        ("level_ten", level >= 10),
        ("level_twenty", level >= 20),

        ("streak_14", streak >= 14),
        ("streak_30", streak >= 30),
        ("streak_60", streak >= 60),
        ("streak_100", streak >= 100),

        ("fifty_tasks", completed >= 50),
        ("hundred_tasks", completed >= 100),
    ]
    
    newly_unlocked = []

    for key, condition in checks:
        if condition and db.unlock_achievement(key):
            newly_unlocked.append(key)

    return newly_unlocked