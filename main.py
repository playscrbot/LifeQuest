import tkinter as tk
from tkinter import ttk, messagebox

from typing import List, Dict, Optional
from datetime import date, datetime, timedelta

import urllib.parse
import webbrowser
import threading
import queue

from database import Database
from game_logic import XP_REWARDS, level_from_xp, xp_for_next_level, check_achievements, get_streak, get_streak_status, STREAK_MILESTONES

from trello_client import TrelloClient, TrelloAPIError
from config import TRELLO_AUTO_SYNC_SECONDS

BG = "#11111b"
PANEL = "#1b1b2b"
PANEL2 = "#24243a"
PURPLE = "#8b5cf6"
PURPLE_DARK = "#6d43c5"
TEXT = "#f4f1ff"
MUTED = "#aaa5bd"
GREEN = "#4ade80"
RED = "#fb7185"
GOLD = "#fbbf24"

ACHIEVEMENTS = [
    ("first_task", "First Blood", "Complete your first mission", "◇"),
    ("ten_tasks", "Getting Serious", "Complete 10 missions", "⚔"),
    ("twenty_five", "Task Slayer", "Complete 25 missions", "☠"),
    ("streak_3", "Getting Started", "Maintain a 3-day streak", "✦"),
    ("seven_day", "One Week Strong", "Maintain a 7-day streak", "🔥"),
    ("streak_14", "Fortnight Force", "Maintain a 14-day streak", "⚔"),
    ("streak_30", "Monthly Master", "Maintain a 30-day streak", "🏆"),
    ("streak_60", "Unstoppable", "Maintain a 60-day streak", "💎"),
    ("streak_100", "Legendary", "Maintain a 100-day streak", "👑"),
    ("level_five", "Rising Hero", "Reach level 5", "★"),
    ("fifty_tasks", "Master of Tasks", "Complete 50 missions", "♛"),
]

class LifeQuestApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LifeQuest — Your Personal Productivity RPG")
        self.geometry("1120x760")
        self.minsize(920, 650)
        self.configure(bg=BG)
        self.db = Database()
        self.trello_client = None  # Credentials are held in memory only.
        self.trello_member = None
        self.trello_boards = []
        self.trello_lists = []
        self.trello_selected_board_id = None
        self.trello_done_list_ids = set()
        self.trello_auto_sync = False
        self.trello_sync_in_progress = False
        self.trello_sync_queue = queue.Queue()
        self.trello_auto_sync_seconds = TRELLO_AUTO_SYNC_SECONDS
        self.trello_auto_after_id = None
        self.trello_status = "Auto-sync is off"
        self.current_page = "Dashboard"
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._style()
        self._layout()
        self.show_dashboard()

    def _style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background=PANEL, foreground=TEXT, fieldbackground=PANEL,
                        rowheight=34, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=PANEL2, foreground=MUTED,
                        relief="flat", font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", PURPLE_DARK)])
        style.configure("TCombobox", fieldbackground=PANEL2, background=PANEL2,
                        foreground=TEXT, arrowcolor=TEXT)

    def _layout(self):
        self.sidebar = tk.Frame(self, bg="#171725", width=210)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        tk.Label(self.sidebar, text="⚔ LIFEQUEST", bg="#171725", fg=TEXT,
                 font=("Segoe UI", 17, "bold")).pack(anchor="w", padx=20, pady=(26, 4))
        tk.Label(self.sidebar, text="YOUR PERSONAL RPG", bg="#171725", fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=21, pady=(0, 28))
        self.nav_buttons = {}
        for name, icon in [("Dashboard", "⌂"), ("Tasks", "☑"), ("Notes", "▤"), ("Streaks", "¥"), 
                           ("Statistics", "▥"), ("Integration", "↔"), ("Achievements", "◇"), ("Reward Shop", "★")]:
            b = tk.Button(self.sidebar, text=f"  {icon}   {name}", anchor="w",
                          command=lambda n=name: self.navigate(n), bg="#171725", fg=MUTED,
                          activebackground=PANEL2, activeforeground=TEXT, relief="flat",
                          bd=0, padx=16, pady=13, font=("Segoe UI", 10, "bold"), cursor="hand2")
            b.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[name] = b
        tk.Frame(self.sidebar, bg="#333047", height=1).pack(fill="x", padx=18, pady=18)
        tk.Label(self.sidebar, text="MAKE PROGRESS.\nEARN YOUR NEXT LEVEL.", justify="left",
                 bg="#171725", fg="#77728c", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=20)
        self.main = tk.Frame(self, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)

        # Scrollable page area: every page is rendered inside this frame, so
        # long dashboards and pages can be reached without changing each page.
        scroll_host = tk.Frame(self.main, bg=BG)
        scroll_host.pack(fill="both", expand=True)
        
        self.content_canvas = tk.Canvas(
            scroll_host, bg=BG, highlightthickness=0, borderwidth=0,
            yscrollincrement=24
        )
        self.content_scrollbar = ttk.Scrollbar(
            scroll_host, orient="vertical", command=self.content_canvas.yview
        )
        self.content_canvas.configure(yscrollcommand=self.content_scrollbar.set)
        self.content_scrollbar.pack(side="right", fill="y")
        self.content_canvas.pack(side="left", fill="both", expand=True)
        
        self.content = tk.Frame(self.content_canvas, bg=BG)
        self.content_window = self.content_canvas.create_window(
            (28, 25), window=self.content, anchor="nw"
        )

        self.content.bind(
            "<Configure>",
            lambda _event: self.content_canvas.configure(
                scrollregion=self.content_canvas.bbox("all")
            )
        )
        self.content_canvas.bind(
            "<Configure>",
            lambda event: self.content_canvas.itemconfigure(
                self.content_window, width=max(1, event.width - 56)
            )
        )
        
        # Mouse-wheel support on Windows/macOS and Linux.
        self.bind_all("<MouseWheel>", self._on_content_mousewheel)
        self.bind_all("<Button-4>", self._on_content_mousewheel)
        self.bind_all("<Button-5>", self._on_content_mousewheel)

    def _on_content_mousewheel(self, event):
        if event.num == 4:
            self.content_canvas.yview_scroll(-3, "units")
        elif event.num == 5:
            self.content_canvas.yview_scroll(3, "units")
        elif event.delta:
            # Windows reports multiples of 120; macOS commonly reports smaller values.
            step = -1 * int(event.delta / 120) if abs(event.delta) >= 120 else (-1 if event.delta > 0 else 1)
            self.content_canvas.yview_scroll(step * 3, "units")

    def navigate(self, page):
        self.current_page = page
        for n, b in self.nav_buttons.items():
            b.configure(bg=PANEL2 if n == page else "#171725",
                        fg=TEXT if n == page else MUTED)
        self.clear_content()
        {"Dashboard": self.show_dashboard, "Tasks": self.show_tasks,
         "Notes": self.show_notes, "Streaks": self.show_streaks, "Statistics": self.show_statistics, 
         "Integration": self.show_trello, "Achievements": self.show_achievements, "Reward Shop": self.show_reward_shop}[page]()

    def clear_content(self):
        for w in self.content.winfo_children():
            w.destroy()

    def header(self, title, subtitle):
        tk.Label(self.content, text=title, bg=BG, fg=TEXT,
                 font=("Segoe UI", 24, "bold")).pack(anchor="w")
        tk.Label(self.content, text=subtitle, bg=BG, fg=MUTED,
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 20))

    def card(self, parent, title, value, color=TEXT, subtitle=None):
        f = tk.Frame(parent, bg=PANEL, padx=18, pady=15)
        tk.Label(f, text=title.upper(), bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(f, text=value, bg=PANEL, fg=color,
                 font=("Segoe UI", 23, "bold")).pack(anchor="w", pady=(6, 0))
        if subtitle:
            tk.Label(f, text=subtitle, bg=PANEL, fg=MUTED,
                     font=("Segoe UI", 8)).pack(anchor="w", pady=(2, 0))
        return f

    def _player_stats(self):
        total_xp = self.db.get_total_xp()
        level, current, needed = level_from_xp(total_xp)
        return total_xp, level, current, needed

    def show_dashboard(self):
        self.navigate_style("Dashboard")
        check_achievements(self.db)
        self.header("Your Dashboard", "Every task completed is progress earned.")

        xp, level, current, needed = self._player_stats()
        tasks = self.db.get_tasks()
        completed = [t for t in tasks if t["status"] == "done"]
        pending = [t for t in tasks if t["status"] == "open"]
        streak = get_streak(self.db.get_completion_dates())

        # Weekly totals use the same Monday-to-Sunday window as Weekly Leaderboard.
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        weekly_xp = 0
        for event in self.db.get_all_earned_xp_events():
            try:
                event_date = datetime.fromisoformat(event["created_at"]).date()
            except (TypeError, ValueError):
                continue
            if event_date >= week_start and event_date <= today:
                weekly_xp += int(event["amount"])
        
        weekly_completed = 0
        for task in completed:
            stamp = task.get("completed_at")
            if not stamp:
                continue
            try:
                completed_day = datetime.fromisoformat(stamp).date()
            except (TypeError, ValueError):
                continue
            if week_start <= completed_day <= today:
                weekly_completed += 1

        row = tk.Frame(self.content, bg=BG)
        row.pack(fill="x", pady=(0, 18))

        for title, value, color, sub in [
            ("Player level", f"LVL {level}", PURPLE, f"{xp:,} total XP"),
            ("Tasks completed", str(len(completed)), GREEN, "All-time victories"),
            ("Current streak", f"{streak} days", GOLD, "Consecutive active days"),
            ("Pending missions", str(len(pending)), TEXT, "Ready when you are")]:
            self.card(row, title, value, color, sub).pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        progress = tk.Frame(self.content, bg=PANEL, padx=18, pady=5)
        progress.pack(fill="x", pady=(0, 4))
        
        # Dedicated weekly performance snapshot.
        days_elapsed = max(1, (today - week_start).days + 1)
        average_daily_xp = round(weekly_xp / days_elapsed)
        weekly_panel = tk.Frame(
            self.content, bg=PANEL, padx=18, pady=14,
            highlightthickness=1, highlightbackground="#343149"
        )
        weekly_panel.pack(fill="x", pady=(0, 14))
        
        weekly_heading = tk.Frame(weekly_panel, bg=PANEL)
        weekly_heading.pack(fill="x")
        tk.Label(
            weekly_heading, text="THIS WEEK AT A GLANCE",
            bg=PANEL, fg=TEXT, font=("Segoe UI", 11, "bold")
        ).pack(side="left")
        tk.Label(
            weekly_heading, text=f"{week_start.strftime('%b %d')} – {today.strftime('%b %d')}",
            bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")
        ).pack(side="right")
        
        weekly_metrics = tk.Frame(weekly_panel, bg=PANEL)
        weekly_metrics.pack(fill="x", pady=(11, 0))
        weekly_metrics.grid_columnconfigure((0, 1, 2), weight=1, uniform="weekly_metric")
        
        weekly_cards = [
            ("MISSIONS COMPLETED", str(weekly_completed), GREEN,
             "Missions finished this week"),
            ("XP EARNED", f"+{weekly_xp:,}", PURPLE,
             "Total XP collected since Monday"),
            ("AVERAGE XP / DAY", f"{average_daily_xp:,}", GOLD,
             f"Daily average across {days_elapsed} day{'s' if days_elapsed != 1 else ''}"),
        ]
        for index, (label, value, color, hint) in enumerate(weekly_cards):
            metric = tk.Frame(weekly_metrics, bg=PANEL2, padx=14, pady=11)
            metric.grid(row=0, column=index, sticky="nsew",
                        padx=(0 if index == 0 else 6, 0 if index == 2 else 6))
            tk.Label(metric, text=label, bg=PANEL2, fg=MUTED,
                     font=("Segoe UI", 8, "bold")).pack(anchor="w")
            tk.Label(metric, text=value, bg=PANEL2, fg=color,
                     font=("Segoe UI", 21, "bold")).pack(anchor="w", pady=(5, 1))
            tk.Label(metric, text=hint, bg=PANEL2, fg=MUTED,
                     font=("Segoe UI", 8), wraplength=220,
                     justify="left").pack(anchor="w")
        
        progress = tk.Frame(self.content, bg=PANEL, padx=18, pady=13)
        progress.pack(fill="x", pady=(0, 14))
        tk.Label(progress, text=f"LEVEL {level} PROGRESS", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(progress, text=f"{current} / {needed} XP to next level",
                 bg=PANEL, fg=TEXT, font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(6, 7))
        bar_bg = tk.Frame(progress, bg="#35334a", height=10)
        bar_bg.pack(fill="x")
        bar_bg.pack_propagate(False)
        ratio = min(1, current / needed) if needed else 1
        tk.Frame(bar_bg, bg=PURPLE, width=max(4, int(650 * ratio))).pack(side="left", fill="y")
            
        lower = tk.Frame(self.content, bg=BG)
        lower.pack(fill="both", expand=True)
        left = tk.Frame(lower, bg=PANEL, padx=16, pady=14)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        right = tk.Frame(lower, bg=PANEL, padx=16, pady=14)
        right.pack(side="left", fill="both", expand=True)
        tk.Label(left, text="TODAY'S MISSIONS", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 10))
        
        today = [t for t in pending if t["due_date"] == date.today().isoformat()]
        if not today:
            tk.Label(left, text="No missions due today. Add a task to get started.",
                     bg=PANEL, fg=MUTED, wraplength=350).pack(anchor="w", pady=10)
        for t in today[:6]:
            tk.Label(left, text=f"• {t['title']}   +{t['xp']} XP", bg=PANEL, fg=TEXT,
                     font=("Segoe UI", 10)).pack(anchor="w", pady=5)
        tk.Button(left, text="Open mission board →", command=lambda: self.navigate("Tasks"),
                  bg=PURPLE_DARK, fg="white", relief="flat", padx=12, pady=8).pack(anchor="w", pady=(12, 0))
        
        tk.Label(right, text="DAILY CHALLENGE", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 10))
        challenge = self.db.get_daily_challenge()
        tk.Label(right, text=challenge["title"], bg=PANEL, fg=GOLD,
                 font=("Segoe UI", 13, "bold"), wraplength=350).pack(anchor="w")
        tk.Label(right, text=challenge["description"], bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9), wraplength=350, justify="left").pack(anchor="w", pady=(7, 10))
        tk.Label(right, text=f"Reward: +{challenge['xp']} XP bonus", bg=PANEL, fg=GREEN,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        
        if not challenge["claimed"]:
            tk.Button(right, text="Claim challenge reward", command=self.claim_challenge,
                      bg=PURPLE_DARK, fg="white", relief="flat", padx=12, pady=8).pack(anchor="w", pady=12)
        else:
            tk.Label(right, text="✓ Today's reward claimed", bg=PANEL, fg=GREEN).pack(anchor="w", pady=12)

        # Always show the next locked achievement; before the first unlock this is the first target.
        unlocked_rows = self.db.get_unlocked_achievements()
        unlocked_keys = {item["key"] for item in unlocked_rows}
        next_achievement = next((item for item in ACHIEVEMENTS if item[0] not in unlocked_keys), None)
        next_panel = tk.Frame(self.content, bg="#24213a", padx=16, pady=11)
        next_panel.pack(fill="x", pady=(0, 12))
        tk.Label(next_panel, text="NEXT ACHIEVEMENT", bg="#24213a", fg=GOLD,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        if next_achievement:
            key, name, description, icon = next_achievement
            tk.Label(next_panel, text=f"{icon}  {name}", bg="#24213a", fg=TEXT,
                     font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(4, 2))
            tk.Label(next_panel, text=description, bg="#24213a", fg=MUTED,
                     font=("Segoe UI", 9)).pack(anchor="w")
            # Add a useful live progress hint for the next achievement.
            progress_hint = ""
            if key in ("first_task", "ten_tasks", "twenty_five", "fifty_tasks"):
                target = {"first_task": 1, "ten_tasks": 10, "twenty_five": 25, "fifty_tasks": 50}[key]
                progress_hint = f"{len(completed)} / {target} missions completed"
            elif key.startswith("streak_") or key == "seven_day":
                target = {"streak_3": 3, "seven_day": 7, "streak_14": 14,
                          "streak_30": 30, "streak_60": 60, "streak_100": 100}[key]
                from game_logic import calculate_best_streak
                best_streak = calculate_best_streak(self.db.get_completion_dates())
                progress_hint = f"{best_streak} / {target} consecutive active days"
            elif key == "level_five":
                progress_hint = f"Level {level} / 5"
            if progress_hint:
                tk.Label(next_panel, text=progress_hint, bg="#24213a", fg=GREEN,
                         font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(5, 0))
        else:
            tk.Label(next_panel, text="All achievements unlocked. You've conquered every current milestone!",
                     bg="#24213a", fg=GREEN, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(5, 0))

        # XP explainer: make the purpose of earning XP visible, not just the number.
        xp_panel = tk.Frame(self.content, bg="#211f35", padx=18, pady=14,
                            highlightthickness=1, highlightbackground="#393451")
        xp_panel.pack(fill="x", pady=(0, 14))
                
        xp_intro = tk.Frame(xp_panel, bg="#211f35")
        xp_intro.pack(fill="x")
        tk.Label(xp_intro, text="WHY YOUR XP MATTERS", bg="#211f35", fg=GOLD,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(
            xp_intro,
            text="XP turns the work you do into visible progress.",
            bg="#211f35", fg=TEXT, font=("Segoe UI", 13, "bold")
        ).pack(anchor="w", pady=(4, 3))
        tk.Label(
            xp_intro,
            text="Every completed mission adds to your journey. Small actions build momentum; bigger challenges move you forward faster.",
            bg="#211f35", fg=MUTED, font=("Segoe UI", 9),
            wraplength=900, justify="left"
        ).pack(anchor="w")
                
        xp_benefits = tk.Frame(xp_panel, bg="#211f35")
        xp_benefits.pack(fill="x", pady=(12, 0))
        xp_benefits.grid_columnconfigure((0, 1, 2), weight=1, uniform="xp_benefit")
                
        benefits = [
            ("⬆  LEVEL UP", "Earn XP to advance through levels. Each new level takes more XP than the last."),
            ("🏅  REACH MILESTONES", "Your XP contributes to level-based milestones, including the Level 5 achievement."),
            ("🎁  CLAIM REWARDS", "Use your spendable XP in the Reward Shop for rewards you choose."),
        ]
        for index, (title, description) in enumerate(benefits):
            benefit = tk.Frame(xp_benefits, bg="#2b2942", padx=12, pady=10)
            benefit.grid(row=0, column=index, sticky="nsew",
                         padx=(0 if index == 0 else 6, 0 if index == 2 else 6))
            tk.Label(benefit, text=title, bg="#2b2942", fg=TEXT,
                     font=("Segoe UI", 8, "bold")).pack(anchor="w")
            tk.Label(benefit, text=description, bg="#2b2942", fg=MUTED,
                     font=("Segoe UI", 8), wraplength=230,
                     justify="left").pack(anchor="w", pady=(5, 0))
                
        tk.Label(
            xp_panel,
            text="Tip: XP spent in the Reward Shop reduces your spendable balance, but never takes away levels you've already earned.",
            bg="#211f35", fg=GREEN, font=("Segoe UI", 8, "bold"),
            wraplength=900, justify="left"
        ).pack(anchor="w", pady=(11, 0))

    def navigate_style(self, page):
        for n, b in self.nav_buttons.items():
            b.configure(bg=PANEL2 if n == page else "#171725",
                        fg=TEXT if n == page else MUTED)

    def claim_challenge(self):
        challenge = self.db.get_daily_challenge()
        if self.db.claim_challenge(challenge["day"]):
            self.db.add_xp(challenge["xp"], "Daily challenge")
            messagebox.showinfo("Challenge complete", f"You earned {challenge['xp']} bonus XP!")
            self.show_dashboard()

    def show_tasks(self):
        self.navigate_style("Tasks")
        self.header("Mission Board", "Turn intentions into missions. Complete them to earn XP.")
        top = tk.Frame(self.content, bg=BG)
        top.pack(fill="x", pady=(0, 14))
        tk.Button(top, text="+ Add mission", command=self.add_task_dialog, bg=PURPLE_DARK,
                  fg="white", relief="flat", padx=14, pady=9).pack(side="left")
        tk.Label(top, text="  Difficulty determines XP reward.", bg=BG, fg=MUTED).pack(side="left")
        tree = ttk.Treeview(self.content, columns=("title", "category", "difficulty", "due", "xp", "status", "source"), show="headings")
        for col, label, width in [
            ("title", "MISSION", 250), ("category", "CATEGORY", 125), ("difficulty", "DIFFICULTY", 95),
            ("due", "DUE DATE", 105), ("xp", "REWARD", 85),
            ("status", "STATUS", 90), ("source", "SOURCE", 90)
        ]:
            tree.heading(col, text=label) 
            tree.column(col, width=width, anchor="w" if col == "title" else "center")
        tree.pack(fill="both", expand=True)
        for t in self.db.get_tasks():
            source_label = "Local" if t.get("source", "local") == "local" else "Trello"
            tree.insert("", "end", iid=str(t["id"]), values=(
                t["title"], t.get("category", "General"), t["difficulty"], t["due_date"] or "—",
                f"+{t['xp']} XP", "Completed" if t["status"] == "done" else "Open",
                source_label
            ))
        # Use a separate title list to keep the table readable.
        titles = {str(t["id"]): t["title"] for t in self.db.get_tasks()}
        tree.configure(displaycolumns=("title", "category", "difficulty", "due", "xp", "status", "source"))
        actions = tk.Frame(self.content, bg=BG)
        actions.pack(fill="x", pady=12)
        tk.Button(actions, text="Complete selected", command=lambda: self.complete_task(tree, titles),
                  bg=GREEN, fg="#102018", relief="flat", padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(actions, text="Edit selected", command=lambda: self.edit_task(tree),
                  bg=PANEL2, fg=TEXT, relief="flat", padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(actions, text="Delete selected", command=lambda: self.delete_task(tree),
                  bg="#512b3a", fg="#ffdce4", relief="flat", padx=12, pady=8).pack(side="left")
        
        # Show task titles in a visible first column via heading replacement.
        tree["columns"] = ("title", "category", "difficulty", "due", "xp", "status", "source")
        for col, label, width in [("title","MISSION",330),("category","CATEGORY",125),("difficulty","DIFFICULTY",95),
                                  ("due","DUE DATE",105),("xp","REWARD",85),("status","STATUS",90),("source","SOURCE",90)]:
            tree.heading(col, text=label); tree.column(col, width=width, anchor="w" if col=="title" else "center")
        for t in self.db.get_tasks():
            tree.item(str(t["id"]), values=(t["title"], t.get("category", "General"), t["difficulty"], t["due_date"] or "—",
                      f"+{t['xp']} XP", "Completed" if t["status"] == "done" else "Open", source_label))

    def add_task_dialog(self, existing=None):
        win = tk.Toplevel(self); win.title("Mission details"); win.configure(bg=PANEL)
        win.geometry("430x390"); win.resizable(False, False); win.transient(self); win.grab_set()
        tk.Label(win, text="MISSION DETAILS", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=22, pady=(20, 12))
        fields = tk.Frame(win, bg=PANEL); fields.pack(fill="x", padx=22)
        tk.Label(fields, text="Title", bg=PANEL, fg=MUTED).pack(anchor="w")
        title = tk.Entry(fields, bg=PANEL2, fg=TEXT, insertbackground=TEXT, relief="flat")
        title.pack(fill="x", ipady=8, pady=(4, 12))
        tk.Label(fields, text="Description", bg=PANEL, fg=MUTED).pack(anchor="w")
        desc = tk.Text(fields, height=3, bg=PANEL2, fg=TEXT, insertbackground=TEXT, relief="flat")
        desc.pack(fill="x", pady=(4, 12))
        tk.Label(fields, text="Difficulty", bg=PANEL, fg=MUTED).pack(anchor="w")
        difficulty = ttk.Combobox(fields, values=list(XP_REWARDS), state="readonly")
        difficulty.set("Easy"); difficulty.pack(fill="x", pady=(4, 12))
        tk.Label(fields, text="Category", bg=PANEL, fg=MUTED).pack(anchor="w")
        category = ttk.Combobox(
            fields,
            values=["General", "Work", "Learning", "Health", "Creative", "Finance", "Household", "Personal"],
            state="readonly"
        )
        category.set("General"); category.pack(fill="x", pady=(4, 12))
        tk.Label(fields, text="Due date (YYYY-MM-DD, optional)", bg=PANEL, fg=MUTED).pack(anchor="w")
        due = tk.Entry(fields, bg=PANEL2, fg=TEXT, insertbackground=TEXT, relief="flat")
        due.pack(fill="x", ipady=7, pady=(4, 14))
        if existing:
            title.insert(0, existing["title"]); desc.insert("1.0", existing["description"] or "")
            difficulty.set(existing["difficulty"]); category.set(existing.get("category", "General"))
            due.insert(0, existing["due_date"] or "")
        def save():
            name = title.get().strip()
            if not name:
                messagebox.showwarning("Missing title", "Give this mission a title.", parent=win); return
            d = due.get().strip()
            if d:
                try: datetime.strptime(d, "%Y-%m-%d")
                except ValueError:
                    messagebox.showwarning("Invalid date", "Use YYYY-MM-DD.", parent=win); return
            payload = (name, desc.get("1.0", "end").strip(), difficulty.get(), category.get(), d or None, XP_REWARDS[difficulty.get()])
            if existing: self.db.update_task(existing["id"], *payload)
            else: self.db.add_task(*payload)
            win.destroy(); self.show_tasks()
        tk.Button(win, text="Save mission", command=save, bg=PURPLE_DARK, fg="white",
                  relief="flat", padx=18, pady=9).pack(anchor="e", padx=22, pady=12)

    def complete_task(self, tree, titles):
        sel = tree.selection()
        if not sel: messagebox.showinfo("Select a mission", "Choose an open mission first."); return
        task_id = int(sel[0])
        task = self.db.get_task(task_id)
        if task and task.get("source", "local") != "local":
            messagebox.showinfo("Trello task is read-only",
                    "Complete this card in Trello, then sync LifeQuest.")
            return
        if task and task["status"] == "open":
            self.db.complete_task(task_id)
            self.db.add_xp(task["xp"], f"Completed: {task['title']}", task.get("category", "General"))
            unlocked = check_achievements(self.db)
            msg = f"Mission completed!\n+{task['xp']} XP earned."
            if unlocked: msg += "\n\nAchievement unlocked: " + ", ".join(unlocked)
            messagebox.showinfo("Victory!", msg)
            self.show_tasks()
        else: messagebox.showinfo("Already completed", "This mission has already been completed.")

    def edit_task(self, tree):
        sel = tree.selection()
        if not sel: messagebox.showinfo("Select a mission", "Choose a mission to edit."); return
        task = self.db.get_task(int(sel[0]))
        if task and task.get("source", "local") != "local":
            messagebox.showinfo("Trello task is read-only", "Edit this card in Trello. LifeQuest only reads it.")
        if task and task["status"] == "open": self.add_task_dialog(task)
        else: messagebox.showinfo("Cannot edit", "Completed missions are locked to preserve XP history.")

    def delete_task(self, tree):
        sel = tree.selection()
        if not sel: messagebox.showinfo("Select a mission", "Choose a mission to delete."); return
        task = self.db.get_task(int(sel[0]))
        if task and task.get("source", "local") != "local":
            messagebox.showinfo("Trello task is read-only", "Remove or archive this card in Trello. LifeQuest will not delete it.")
            return
        if task and task["status"] == "done":
            messagebox.showwarning("Protected mission", "Completed missions cannot be deleted in this version."); return
        if messagebox.askyesno("Delete mission", "Delete this mission?"):
            self.db.delete_task(int(sel[0])); self.show_tasks()

    def show_notes(self):
        self.navigate_style("Notes")
        self.header("Notes", "Capture ideas before they disappear.")
        wrap = tk.Frame(self.content, bg=BG); wrap.pack(fill="both", expand=True)
        left = tk.Frame(wrap, bg=PANEL, width=280, padx=12, pady=12); left.pack(side="left", fill="y", padx=(0, 12)); left.pack_propagate(False)
        right = tk.Frame(wrap, bg=PANEL, padx=14, pady=14); right.pack(side="left", fill="both", expand=True)
        tk.Button(left, text="+ New note", command=lambda: self.new_note(), bg=PURPLE_DARK,
                  fg="white", relief="flat", padx=12, pady=8).pack(fill="x", pady=(0, 10))
        notes = self.db.get_notes()
        lb = tk.Listbox(left, bg=PANEL2, fg=TEXT, selectbackground=PURPLE_DARK,
                        relief="flat", font=("Segoe UI", 10), activestyle="none")
        lb.pack(fill="both", expand=True)
        for n in notes: lb.insert("end", n["title"])
        title = tk.Entry(right, bg=PANEL2, fg=TEXT, insertbackground=TEXT, relief="flat",
                         font=("Segoe UI", 13, "bold"))
        title.pack(fill="x", ipady=9, pady=(0, 10))
        body = tk.Text(right, bg=PANEL2, fg=TEXT, insertbackground=TEXT, relief="flat",
                       wrap="word", font=("Segoe UI", 10))
        body.pack(fill="both", expand=True)
        selected = {"id": None}
        def load(_=None):
            if not lb.curselection(): return
            n = notes[lb.curselection()[0]]
            selected["id"] = n["id"]
            title.delete(0, "end"); title.insert(0, n["title"])
            body.delete("1.0", "end"); body.insert("1.0", n["body"])
        lb.bind("<<ListboxSelect>>", load)
        def save():
            name = title.get().strip()
            if not name: messagebox.showwarning("Missing title", "Enter a note title."); return
            if selected["id"]: self.db.update_note(selected["id"], name, body.get("1.0", "end").strip())
            else: self.db.add_note(name, body.get("1.0", "end").strip())
            messagebox.showinfo("Saved", "Note saved.")
            self.show_notes()
        def delete():
            if selected["id"] and messagebox.askyesno("Delete note", "Delete this note?"):
                self.db.delete_note(selected["id"]); self.show_notes()
        buttons = tk.Frame(right, bg=PANEL); buttons.pack(fill="x", pady=(10, 0))
        tk.Button(buttons, text="Save note", command=save, bg=PURPLE_DARK, fg="white", relief="flat", padx=12, pady=7).pack(side="left")
        tk.Button(buttons, text="Delete note", command=delete, bg="#512b3a", fg="#ffdce4", relief="flat", padx=12, pady=7).pack(side="left", padx=8)
        if notes: lb.selection_set(0); load()
        self._notes_new = lambda: (selected.update({"id": None}), title.delete(0, "end"),
                                           body.delete("1.0", "end"), lb.selection_clear(0, "end"))
        # Replace the button command with the editor-aware blank-note action.
        for child in left.winfo_children():
            if isinstance(child, tk.Button):
                child.configure(command=self._notes_new)

    def new_note(self):
        self.show_notes()
        # New note editor is empty and ready to save.
        # selected id remains None.

    def show_trello(self):
        self.navigate_style("Trello")
        self.header("Trello Integration", "Read your Trello boards and turn cards into LifeQuest missions.")
        if not self.trello_client:
            panel = tk.Frame(self.content, bg=PANEL, padx=24, pady=24)
            panel.pack(fill="x", pady=8)
            tk.Label(panel, text="CONNECT YOUR TRELLO ACCOUNT", bg=PANEL, fg=TEXT,
                     font=("Segoe UI", 15, "bold")).pack(anchor="w")
            tk.Label(panel, text="LifeQuest requests read-only access. It will never create, edit, move, archive or delete Trello cards.",
                     bg=PANEL, fg=MUTED, wraplength=650, justify="left").pack(anchor="w", pady=(10, 16))
            tk.Button(panel, text="Connect Trello", command=self.connect_trello_dialog,
                      bg=PURPLE_DARK, fg="white", relief="flat", padx=16, pady=10).pack(anchor="w")
            tk.Label(self.content, text="You'll need a Trello API key and a read-only token. Credentials stay in memory and are cleared when LifeQuest closes.",
                     bg=BG, fg=MUTED, wraplength=700, justify="left").pack(anchor="w", pady=12)
            return
    
        panel = tk.Frame(self.content, bg=PANEL, padx=18, pady=16)
        panel.pack(fill="x", pady=(0, 14))
        member_name = (self.trello_member or {}).get("fullName", "Trello account")
        tk.Label(panel, text=f"CONNECTED AS {member_name}", bg=PANEL, fg=GREEN,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(panel, text="Choose a board and tell LifeQuest which Trello lists represent completed work.",
                 bg=PANEL, fg=MUTED, wraplength=700).pack(anchor="w", pady=(5, 12))
    
        board_row = tk.Frame(panel, bg=PANEL); board_row.pack(fill="x")
        tk.Label(board_row, text="BOARD", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 12))
        board_names = [b["name"] for b in self.trello_boards]
        self.trello_board_combo = ttk.Combobox(board_row, values=board_names, state="readonly", width=42)
        self.trello_board_combo.pack(side="left")
        if board_names:
            selected_index = next((i for i, b in enumerate(self.trello_boards)
                                   if b["id"] == self.trello_selected_board_id), 0)
            self.trello_board_combo.current(selected_index)
            self.trello_selected_board_id = self.trello_boards[selected_index]["id"]
        self.trello_board_combo.bind("<<ComboboxSelected>>", self.on_trello_board_changed)
        tk.Button(board_row, text="Load lists", command=self.load_trello_lists,
                  bg=PANEL2, fg=TEXT, relief="flat", padx=12, pady=7).pack(side="left", padx=8)
        tk.Button(board_row, text="Disconnect", command=self.disconnect_trello,
                  bg="#512b3a", fg="#ffdce4", relief="flat", padx=12, pady=7).pack(side="right")
    
        lists_panel = tk.Frame(self.content, bg=PANEL, padx=18, pady=14)
        lists_panel.pack(fill="x", pady=(0, 14))
        tk.Label(lists_panel, text="COMPLETED LISTS", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(lists_panel, text="Select one or more lists such as Done or Completed. Trello's due-date completion flag also counts.",
                 bg=PANEL, fg=MUTED, wraplength=700).pack(anchor="w", pady=(4, 8))
        self.trello_lists_box = tk.Listbox(lists_panel, selectmode="multiple", height=5,
                                           bg=PANEL2, fg=TEXT, selectbackground=PURPLE_DARK,
                                           relief="flat", activestyle="none", exportselection=False)
        self.trello_lists_box.pack(fill="x")
        self.trello_list_ids = []
        if self.trello_lists:
            for i, item in enumerate(self.trello_lists):
                self.trello_lists_box.insert("end", item["name"])
                if item["id"] in self.trello_done_list_ids or (
                    not self.trello_done_list_ids and any(
                        k in item["name"].lower() for k in ("done", "complete", "finished")
                    )
                ):
                    self.trello_lists_box.selection_set(i)
        actions = tk.Frame(self.content, bg=BG); actions.pack(fill="x", pady=2)
        tk.Button(actions, text="↻ Sync now", command=self.sync_trello,
                  bg=PURPLE_DARK, fg="white", relief="flat", padx=16, pady=10).pack(side="left")
        tk.Button(actions, text="Start auto-sync", command=self.start_trello_auto_sync,
                  bg=PANEL2, fg=TEXT, relief="flat", padx=12, pady=10).pack(side="left", padx=8)
        tk.Button(actions, text="Stop auto-sync", command=self.stop_trello_auto_sync,
                  bg="#512b3a", fg="#ffdce4", relief="flat", padx=12, pady=10).pack(side="left")
        tk.Label(self.content, text=f"{self.db.get_trello_task_count()} Trello cards imported",
                 bg=BG, fg=MUTED).pack(anchor="w", pady=(12, 2))
        tk.Label(self.content, text=self.trello_status, bg=BG, fg=GREEN if self.trello_auto_sync else MUTED,
                 wraplength=700, justify="left").pack(anchor="w")
        tk.Label(self.content, text="Auto-sync checks Trello every 60 seconds while LifeQuest is open. Credentials remain in memory. Trello cards are never edited by LifeQuest.",
                 bg=BG, fg=MUTED, wraplength=700, justify="left").pack(anchor="w", pady=(8, 0))
        if board_names and not self.trello_lists:
            self.load_trello_lists()

    def connect_trello_dialog(self):
        win = tk.Toplevel(self)
        win.title("Connect Trello — read-only")
        win.configure(bg=PANEL); win.geometry("540x430"); win.resizable(False, False)
        win.transient(self); win.grab_set()
        tk.Label(win, text="CONNECT TRELLO", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=22, pady=(20, 8))
        tk.Label(win, text="1. Create or open a Trello Power-Up to obtain an API key.",
                 bg=PANEL, fg=MUTED, wraplength=490, justify="left").pack(anchor="w", padx=22, pady=4)
        tk.Button(win, text="Open Trello developer portal",
                  command=lambda: webbrowser.open("https://trello.com/apps/admin"),
                  bg=PANEL2, fg=TEXT, relief="flat", padx=10, pady=7).pack(anchor="w", padx=22, pady=4)
        tk.Label(win, text="API key", bg=PANEL, fg=TEXT).pack(anchor="w", padx=22, pady=(12, 3))
        key_entry = tk.Entry(win, bg=PANEL2, fg=TEXT, insertbackground=TEXT, relief="flat")
        key_entry.pack(fill="x", padx=22, ipady=8)
        tk.Label(win, text="2. Generate a token with read-only permission.",
                 bg=PANEL, fg=MUTED).pack(anchor="w", padx=22, pady=(12, 4))
        def open_auth():
            key = key_entry.get().strip()
            if not key:
                messagebox.showwarning("API key required", "Enter your Trello API key first.", parent=win); return
            params = urllib.parse.urlencode({
                "expiration": "30days", "scope": "read", "response_type": "token",
                "key": key, "name": "LifeQuest"
            })
            webbrowser.open("https://trello.com/1/authorize?" + params)
        tk.Button(win, text="Generate read-only token", command=open_auth,
                bg=PANEL2, fg=TEXT, relief="flat", padx=10, pady=7).pack(anchor="w", padx=22)
        tk.Label(win, text="Paste the token Trello gives you below.", bg=PANEL, fg=TEXT).pack(anchor="w", padx=22, pady=(12, 3))
        token_entry = tk.Entry(win, bg=PANEL2, fg=TEXT, insertbackground=TEXT, relief="flat", show="•")
        token_entry.pack(fill="x", padx=22, ipady=8)
        tk.Label(win, text="Credentials are kept only in memory for this app session. Never share your token.",
                bg=PANEL, fg=GOLD, wraplength=490, justify="left").pack(anchor="w", padx=22, pady=10)
        def connect():
            try:
                client = TrelloClient(key_entry.get(), token_entry.get())
                member = client.get_member()
                boards = client.get_boards()
                self.trello_client = client
                self.trello_member = member
                self.trello_boards = boards
                self.trello_lists = []
                win.destroy()
                self.show_trello()
                if not boards:
                    messagebox.showinfo("No boards found", "The connected Trello account has no open boards available.")
            except (TrelloAPIError, ValueError) as exc:
                messagebox.showerror("Trello connection failed", str(exc), parent=win)
        tk.Button(win, text="Connect & load boards", command=connect,
                bg=PURPLE_DARK, fg="white", relief="flat", padx=16, pady=9).pack(anchor="e", padx=22, pady=(0, 18))

    def disconnect_trello(self):
        self.stop_trello_auto_sync()
        self.trello_client: TrelloClient | None = None
        
        self.trello_member = None
        self.trello_boards = []
        self.trello_lists = []
        self.trello_selected_board_id = None
        self.trello_done_list_ids = set()
        self.show_trello()
    
    def on_trello_board_changed(self, _event=None):
        board = self._selected_trello_board()
        if board:
            self.trello_selected_board_id = board["id"]
            self.trello_lists = []
            self.trello_done_list_ids = set()

    def _selected_trello_board(self):
        # The board selection is stored separately so scheduled sync still works
        # after the user navigates away from the Trello page.
        if self.current_page == "Trello" and hasattr(self, "trello_board_combo"):
            try:
                if self.trello_board_combo.winfo_exists():
                    name = self.trello_board_combo.get()
                    board = next((b for b in self.trello_boards if b["name"] == name), None)
                    if board:
                        self.trello_selected_board_id = board["id"]
                        return board
            except tk.TclError:
                pass
        return next((b for b in self.trello_boards
                     if b["id"] == self.trello_selected_board_id), None)

    def load_trello_lists(self):
        board = self._selected_trello_board()
        if board is None:
            messagebox.showinfo("Choose a board", "Select a Trello board first.")
            return
        
        if self.trello_client is None:
            messagebox.showinfo("Connect Trello", "Connect your Trello account first.")
            return
        
        try:
            board_id = board["id"]
            
            self.trello_selected_board_id = board_id
            self.trello_lists = self.trello_client.get_lists(board_id)

            self.trello_done_list_ids = {
                item["id"]
                for item in self.trello_lists
                if any(
                    keyword in item["name"].lower()
                    for keyword in ("done", "complete", "finished")
                )
            }

            self.show_trello()
        except TrelloAPIError as exc:
            messagebox.showerror("Could not load lists", str(exc))

    def sync_trello(self, automatic=False):
        """Fetch cards off the UI thread; apply database updates on Tk's main thread."""
        board = self._selected_trello_board()
        if not board:
            if not automatic:
                messagebox.showinfo("Choose a board", "Select a Trello board first.")
            return
        if self.trello_sync_in_progress:
            return
        if not self.trello_lists:
            if not automatic:
                self.load_trello_lists()
            return
        # Read visible selection when the Trello page is open; otherwise reuse
        # the saved list selection for background polling.
        if self.current_page == "Trello" and hasattr(self, "trello_lists_box"):
            try:
                if self.trello_lists_box.winfo_exists():
                    selected = set(self.trello_lists_box.curselection())
                    self.trello_done_list_ids = {
                        self.trello_lists[i]["id"] for i in selected if i < len(self.trello_lists)
                    }
            except tk.TclError:
                pass
        completed_list_ids = set(self.trello_done_list_ids)
        list_names = {item["id"]: item["name"] for item in self.trello_lists}
        self.trello_sync_in_progress = True
        self.trello_status = f"Syncing {board['name']}..."
        if self.current_page == "Trello":
            self.show_trello_status()
        
        client = self.trello_client
        board_id = board["id"]
        board_name = board["name"]

        if client is None:
            self.trello_sync_in_progress = False
            return
    
        def worker():
            try:
                cards = client.get_cards(board_id)
                self.trello_sync_queue.put(("success", board_name, cards, completed_list_ids, list_names, automatic))
            except Exception as exc:
                self.trello_sync_queue.put(("error", str(exc), None, None, None, automatic))
    
        threading.Thread(target=worker, daemon=True).start()
        self.after(150, self._poll_trello_sync_queue)

    def _poll_trello_sync_queue(self):
        try:
            result = self.trello_sync_queue.get_nowait()
        except queue.Empty:
            if self.trello_sync_in_progress:
                self.after(150, self._poll_trello_sync_queue)
            return
    
        self.trello_sync_in_progress = False
        kind, first, cards, completed_list_ids, list_names, automatic = result
        if kind == "error":
            self.trello_status = f"Last sync failed: {first}"
            if not automatic:
                messagebox.showerror("Trello sync failed", first)
            if self.current_page == "Trello":
                self.show_trello()
            self._schedule_next_auto_sync()
            return
    
        board_name = first
        imported = updated = newly_completed = skipped_archived = 0
        try:
            for card in cards:
                # Trello's `closed` flag means archived, not completed.
                if card.get("closed"):
                    skipped_archived += 1
                    continue
                is_completed = bool(card.get("dueComplete")) or card.get("idList") in completed_list_ids
                outcome, awarded = self.db.sync_trello_card(
                    card, list_names.get(card.get("idList"), ""), is_completed
                )
                if outcome == "imported":
                    imported += 1
                else:
                    updated += 1
                if awarded:
                    newly_completed += 1
    
            unlocked = check_achievements(self.db)
            self.trello_status = (
                f"Last sync successful: {datetime.now().strftime('%H:%M:%S')} — "
                f"{len(cards)} cards checked; {newly_completed} new completion rewards."
            )
            if self.current_page == "Trello":
                self.show_trello()
            if not automatic:
                summary = (
                    f"Board: {board_name}\nCards received: {len(cards)}\n"
                    f"New imports: {imported}\nUpdated: {updated}\n"
                    f"New completions rewarded: {newly_completed}\n"
                    f"Archived cards skipped: {skipped_archived}"
                )
                if unlocked:
                    summary += "\n\nAchievements unlocked: " + ", ".join(unlocked)
                messagebox.showinfo("Trello sync complete", summary)
        except Exception as exc:
            self.trello_status = f"Could not save Trello sync: {exc}"
            if not automatic:
                messagebox.showerror("Sync processing failed", str(exc))
            if self.current_page == "Trello":
                self.show_trello()
        self._schedule_next_auto_sync()

    def show_trello_status(self):
        # Re-rendering is intentionally avoided while the background request is running.
        # The status is shown on the next Trello page render or after sync completion.
        pass
    
    def start_trello_auto_sync(self):
        if not self.trello_client:
            messagebox.showinfo("Connect Trello", "Connect your Trello account first.")
            return
        if not self._selected_trello_board():
            messagebox.showinfo("Choose a board", "Select a Trello board first.")
            return
        if not self.trello_lists:
            self.load_trello_lists()
            if not self.trello_lists:
                return
        self.trello_auto_sync = True
        self.trello_status = "Auto-sync is on: checking every 60 seconds."
        self.sync_trello(automatic=True)
        if self.current_page == "Trello":
            self.show_trello()
    
    def stop_trello_auto_sync(self):
        self.trello_auto_sync = False
        if self.trello_auto_after_id is not None:
            try:
                self.after_cancel(self.trello_auto_after_id)
            except tk.TclError:
                pass
            self.trello_auto_after_id = None
        self.trello_status = "Auto-sync is off."
        if self.current_page == "Trello":
            self.show_trello()

    def _schedule_next_auto_sync(self):
        if self.trello_auto_after_id is not None:
            try:
                self.after_cancel(self.trello_auto_after_id)
            except tk.TclError:
                pass
            self.trello_auto_after_id = None
        if self.trello_auto_sync and self.trello_client:
            self.trello_auto_after_id = self.after(
                self.trello_auto_sync_seconds * 1000, self._run_scheduled_trello_sync
            )
    
    def _run_scheduled_trello_sync(self):
        self.trello_auto_after_id = None
        if self.trello_auto_sync and self.trello_client:
            self.sync_trello(automatic=True)
    
    def on_close(self):
        self.trello_auto_sync = False
        self.trello_client = None
        try:
            self.db.close()
        finally:
            self.destroy()

    def show_streaks(self):
        self.navigate_style("Streaks")
        check_achievements(self.db)
        self.header("Daily Streaks", "Consistency is built one active day at a time. Complete at least one activity each day.")
    
        today = date.today()
        dates = self.db.get_activity_dates()
        status = get_streak_status(dates, today)
        counts = self.db.get_activity_counts(
            (today - timedelta(days=364)).isoformat(), today.isoformat()
        )
    
        summary = tk.Frame(self.content, bg=BG)
        summary.pack(fill="x", pady=(0, 15))
        for title, value, color, subtitle in [
            ("Current streak", f'{status["current"]} days', GOLD, "Consecutive active days"),
            ("Best streak", f'{status["best"]} days', GREEN, "Your personal record"),
            ("Missed days", str(status["missed_days"]), RED if status["missed_days"] else MUTED,
             "Since your last active day"),
            ("Next milestone", f'{status["next_milestone"]} days' if status["next_milestone"] else "All earned",
             PURPLE, f'{status["remaining"]} more active days' if status["next_milestone"] else "Legend status")]:
            self.card(summary, title, value, color, subtitle).pack(
                side="left", fill="both", expand=True, padx=(0, 9)
            )
    
        status_panel = tk.Frame(self.content, bg=PANEL, padx=16, pady=12)
        status_panel.pack(fill="x", pady=(0, 15))
        tk.Label(status_panel, text=status["status"], bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        if status["next_milestone"]:
            milestone_line = (
                f'Next badge: {status["next_milestone"]}-day streak  ·  '
                f'{status["remaining"]} active day(s) to go'
            )
            tk.Label(status_panel, text=milestone_line, bg=PANEL, fg=MUTED,
                     font=("Segoe UI", 8)).pack(anchor="w", pady=(4, 7))
            bar_bg = tk.Frame(status_panel, bg="#35334a", height=8)
            bar_bg.pack(fill="x")
            bar_bg.pack_propagate(False)
            tk.Frame(bar_bg, bg=PURPLE,
                     width=max(3, int(700 * status["progress"]))).pack(side="left", fill="y")
        else:
            tk.Label(status_panel, text="You've unlocked every current streak milestone.",
                     bg=PANEL, fg=GOLD, font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 0))
    
        tk.Label(self.content, text="ACTIVITY CALENDAR · LAST 365 DAYS",
                 bg=BG, fg=TEXT, font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(2, 8))
        heatmap_panel = tk.Frame(self.content, bg=PANEL, padx=14, pady=12)
        heatmap_panel.pack(fill="x")
        canvas_width = 810
        canvas_height = 142
        canvas = tk.Canvas(heatmap_panel, width=canvas_width, height=canvas_height,
                           bg=PANEL, highlightthickness=0)
        canvas.pack(anchor="w")
        colors = ["#29283a", "#174b38", "#1f7048", "#2ea866", "#55d68b"]
        start_day = today - timedelta(days=364)
        grid_start = start_day - timedelta(days=start_day.weekday())
        cell = 10
        gap = 4
        left = 34
        top = 27
    
        # Weekday labels: Monday, Wednesday, Friday.
        for label, weekday in [("Mon", 0), ("Wed", 2), ("Fri", 4)]:
            canvas.create_text(0, top + weekday * (cell + gap) + cell / 2,
                               text=label, fill=MUTED, anchor="w",
                               font=("Segoe UI", 7))
    
        month_seen = set()
        for offset in range(365):
            day = start_day + timedelta(days=offset)
            week_col = (day - grid_start).days // 7
            weekday = day.weekday()
            x = left + week_col * (cell + gap)
            y = top + weekday * (cell + gap)
            count = counts.get(day.isoformat(), 0)
            intensity = 0 if count == 0 else min(4, count)
            fill = colors[intensity]
            canvas.create_rectangle(x, y, x + cell, y + cell, fill=fill,
                                    outline="#343247", width=1)
            month_key = (day.year, day.month)
            if day.day <= 7 and month_key not in month_seen:
                canvas.create_text(x, 8, text=day.strftime("%b"),
                                   fill=MUTED, anchor="w",
                                   font=("Segoe UI", 7))
                month_seen.add(month_key)
    
        legend = tk.Frame(heatmap_panel, bg=PANEL)
        legend.pack(anchor="e", fill="x", pady=(6, 0))
        tk.Label(legend, text="Less", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 7)).pack(side="left", padx=(0, 5))
        for color in colors:
            swatch = tk.Canvas(legend, width=11, height=11, bg=PANEL, highlightthickness=0)
            swatch.pack(side="left", padx=2)
            swatch.create_rectangle(1, 1, 10, 10, fill=color, outline=color)
        tk.Label(legend, text="More", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 7)).pack(side="left", padx=(5, 0))
    
        tk.Label(self.content, text="STREAK MILESTONE BADGES",
                 bg=BG, fg=TEXT, font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(16, 8))
        unlocked = {item["key"] for item in self.db.get_unlocked_achievements()}
        milestone_info = [
            (3, "Getting Started", "Build your first three-day streak.", "✦"),
            (7, "One Week Strong", "Stay active for seven consecutive days.", "🔥"),
            (14, "Fortnight Force", "Two weeks of consistency.", "⚔"),
            (30, "Monthly Master", "A full month of daily progress.", "🏆"),
            (60, "Unstoppable", "Two months of showing up.", "💎"),
            (100, "Legendary", "Reach one hundred consecutive active days.", "👑"),
        ]
        badges = tk.Frame(self.content, bg=BG)
        badges.pack(fill="x")
        for i, (days, name, description, icon) in enumerate(milestone_info):
            key = "seven_day" if days == 7 else f"streak_{days}"
            earned = key in unlocked
            panel = tk.Frame(badges, bg=PANEL if earned else "#181824", padx=12, pady=10)
            panel.grid(row=i // 3, column=i % 3, sticky="nsew", padx=4, pady=4)
            badges.grid_columnconfigure(i % 3, weight=1)
            tk.Label(panel, text=icon, bg=panel["bg"],
                     fg=GOLD if earned else "#555166",
                     font=("Segoe UI", 19)).pack(anchor="w")
            tk.Label(panel, text=f"{days}-Day · {name}", bg=panel["bg"],
                     fg=TEXT if earned else MUTED,
                     font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(3, 2))
            tk.Label(panel, text=description, bg=panel["bg"], fg=MUTED,
                     wraplength=205, justify="left",
                     font=("Segoe UI", 8)).pack(anchor="w")
            tk.Label(panel, text="UNLOCKED" if earned else "LOCKED",
                     bg=panel["bg"], fg=GREEN if earned else "#77728c",
                     font=("Segoe UI", 7, "bold")).pack(anchor="w", pady=(6, 0))
    
        recent = self.db.get_recent_activities(6)
        tk.Label(self.content, text="RECENT COMPLETED ACTIVITIES",
                 bg=BG, fg=TEXT, font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(15, 7))
        recent_panel = tk.Frame(self.content, bg=PANEL, padx=14, pady=10)
        recent_panel.pack(fill="x")
        if not recent:
            tk.Label(recent_panel, text="No completed activities yet. Finish a mission to light up your calendar.",
                         bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w")
        else:
            for activity in recent:
                row = tk.Frame(recent_panel, bg=PANEL)
                row.pack(fill="x", pady=3)
                tk.Label(row, text=activity["title"], bg=PANEL, fg=TEXT,
                         font=("Segoe UI", 9)).pack(side="left")
                tk.Label(row, text=activity["completed_at"][:16].replace("T", "  "),
                         bg=PANEL, fg=MUTED, font=("Segoe UI", 8)).pack(side="right")

    def show_reward_shop(self):
        self.navigate_style("Reward Shop")
        self.header("Reward Shop", "Turn the XP you earn into real-life rewards. You decide what is worth saving for.")
    
        balance = self.db.get_available_xp()
        lifetime = self.db.get_total_xp()
        summary = tk.Frame(self.content, bg=PANEL, padx=18, pady=14)
        summary.pack(fill="x", pady=(0, 16))
        wallet = tk.Frame(summary, bg=PANEL)
        wallet.pack(side="left", fill="x", expand=True)
        tk.Label(wallet, text="AVAILABLE TO SPEND", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(wallet, text=f"{balance:,} XP", bg=PANEL, fg=GOLD,
                 font=("Segoe UI", 25, "bold")).pack(anchor="w", pady=(3, 0))
        tk.Label(wallet, text=f"{lifetime:,} lifetime XP earned · purchases do not reduce your level",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", pady=(2, 0))
        tk.Button(summary, text="+ Create your own reward", command=self.add_reward_dialog,
                  bg=PURPLE_DARK, fg=TEXT, activebackground=PURPLE, activeforeground=TEXT,
                  relief="flat", bd=0, padx=14, pady=10,
                  font=("Segoe UI", 9, "bold"), cursor="hand2").pack(side="right", padx=(12, 0))
    
        tk.Label(self.content, text="REWARDS YOU CAN UNLOCK", bg=BG, fg=TEXT,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(3, 9))
        table_wrap = tk.Frame(self.content, bg=PANEL, padx=10, pady=10)
        table_wrap.pack(fill="both", expand=True)
        columns = ("title", "description", "cost", "kind")
        tree = ttk.Treeview(table_wrap, columns=columns, show="headings", height=11, selectmode="browse")
        tree.heading("title", text="REWARD")
        tree.heading("description", text="WHAT IT MEANS")
        tree.heading("cost", text="COST")
        tree.heading("kind", text="TYPE")
        tree.column("title", width=245, minwidth=180)
        tree.column("description", width=390, minwidth=180)
        tree.column("cost", width=95, anchor="center")
        tree.column("kind", width=95, anchor="center")
        scrollbar = ttk.Scrollbar(table_wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        for reward in self.db.get_rewards():
            tree.insert("", "end", iid=str(reward["id"]),
                        values=(reward["title"], reward["description"],
                                f'{reward["cost"]:,} XP',
                                "Built-in" if reward["is_default"] else "Custom"))
    
        actions = tk.Frame(self.content, bg=BG)
        actions.pack(fill="x", pady=(12, 0))
    
        def redeem_selected():
            selected = tree.selection()
            if not selected:
                messagebox.showinfo("Choose a reward", "Select a reward from the list first.")
                return
            reward_id = int(selected[0])
            values = tree.item(selected[0], "values")
            title, cost_text = values[0], values[2]
            if not messagebox.askyesno(
                "Redeem this reward?",
                f"Spend {cost_text} on:\n\n{title}\n\nThis deducts XP from your available balance. Your level will not decrease."
            ):
                return
            success, message = self.db.redeem_reward(reward_id)
            if success:
                messagebox.showinfo("Reward unlocked!", f"{message}\n\nEnjoy it. You earned this.")
                self.show_reward_shop()
            else:
                messagebox.showwarning("Not enough XP", message)
    
        def delete_selected():
            selected = tree.selection()
            if not selected:
                messagebox.showinfo("Choose a reward", "Select one of your custom rewards first.")
                return
            reward = self.db._dict(self.db.conn.execute(
                "SELECT * FROM rewards WHERE id=?", (int(selected[0]),)
            ).fetchone())
            if not reward or reward["is_default"]:
                messagebox.showinfo("Built-in reward", "Built-in rewards cannot be removed.")
                return
            if messagebox.askyesno("Remove custom reward?", f'Remove "{reward["title"]}" from your shop?'):
                self.db.delete_reward(reward["id"])
                self.show_reward_shop()
    
        tk.Button(actions, text="Redeem selected reward", command=redeem_selected,
                  bg=GREEN, fg="#102018", activebackground=GREEN, relief="flat",
                  bd=0, padx=16, pady=10, font=("Segoe UI", 9, "bold"),
                  cursor="hand2").pack(side="left")
        tk.Button(actions, text="Remove custom reward", command=delete_selected,
                  bg=PANEL2, fg=MUTED, activebackground=PANEL2, relief="flat",
                  bd=0, padx=14, pady=10, font=("Segoe UI", 9),
                  cursor="hand2").pack(side="left", padx=(9, 0))
    
        recent = self.db.get_reward_redemptions(5)
        if recent:
            tk.Label(self.content, text="RECENTLY REDEEMED", bg=BG, fg=MUTED,
                     font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(15, 5))
            for item in recent[:3]:
                tk.Label(self.content,
                         text=f'✓  {item["reward_title"]}  ·  {item["cost"]:,} XP  ·  {item["redeemed_at"][:16]}',
                         bg=BG, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", pady=2)

    def add_reward_dialog(self):
        win = tk.Toplevel(self)
        win.title("Create a reward")
        win.configure(bg=BG)
        win.geometry("440x370")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()
        tk.Label(win, text="Create your own reward", bg=BG, fg=TEXT,
                 font=("Segoe UI", 17, "bold")).pack(anchor="w", padx=22, pady=(20, 4))
        tk.Label(win, text="Choose something you genuinely look forward to.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=22, pady=(0, 15))
        fields = tk.Frame(win, bg=BG)
        fields.pack(fill="x", padx=22)
        tk.Label(fields, text="REWARD NAME", bg=BG, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        title = tk.Entry(fields, bg=PANEL2, fg=TEXT, insertbackground=TEXT,
                         relief="flat", font=("Segoe UI", 10))
        title.pack(fill="x", ipady=8, pady=(5, 12))
        tk.Label(fields, text="DESCRIPTION (OPTIONAL)", bg=BG, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        description = tk.Entry(fields, bg=PANEL2, fg=TEXT, insertbackground=TEXT,
                               relief="flat", font=("Segoe UI", 10))
        description.pack(fill="x", ipady=8, pady=(5, 12))
        tk.Label(fields, text="XP COST", bg=BG, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        cost = tk.Entry(fields, bg=PANEL2, fg=TEXT, insertbackground=TEXT,
                        relief="flat", font=("Segoe UI", 10))
        cost.pack(fill="x", ipady=8, pady=(5, 15))
        cost.insert(0, "300")
    
        def save():
            name = title.get().strip()
            try:
                amount = int(cost.get().strip())
                if amount <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Invalid XP cost", "Enter a whole number greater than zero.", parent=win)
                return
            if not name:
                messagebox.showerror("Missing reward name", "Give your reward a name.", parent=win)
                return
            self.db.add_reward(name, description.get(), amount)
            win.destroy()
            self.show_reward_shop()
    
        tk.Button(win, text="Add reward to shop", command=save,
                  bg=PURPLE_DARK, fg=TEXT, activebackground=PURPLE,
                  relief="flat", bd=0, padx=16, pady=10,
                  font=("Segoe UI", 9, "bold"), cursor="hand2").pack(anchor="e", padx=22)

    def show_weekly_leaderboard(self):
        self.navigate_style("Weekly Leaderboard")
        self.header("Weekly Leaderboard",
                    "Your performance, measured week by week. XP spending is excluded from every score.")
    
        events = self.db.get_all_earned_xp_events()
        today = date.today()
        this_monday = today - timedelta(days=today.weekday())
        previous_monday = this_monday - timedelta(days=7)
        weekly_totals = {}
        first_week = this_monday
    
        for event in events:
            try:
                event_day = datetime.fromisoformat(event["created_at"]).date()
            except (TypeError, ValueError):
                continue
            week_start = event_day - timedelta(days=event_day.weekday())
            weekly_totals[week_start] = weekly_totals.get(week_start, 0) + int(event["amount"])
            first_week = min(first_week, week_start)
    
        current_xp = weekly_totals.get(this_monday, 0)
        previous_xp = weekly_totals.get(previous_monday, 0)
        if previous_xp:
            improvement = (current_xp - previous_xp) / previous_xp * 100
            improvement_text = f"{improvement:+.1f}%"
            improvement_color = GREEN if improvement >= 0 else RED
            improvement_sub = f"{current_xp:,} XP this week vs {previous_xp:,} last week"
        elif current_xp:
            improvement_text, improvement_color = "New momentum", GREEN
            improvement_sub = "You earned XP this week; last week was zero."
        else:
            improvement_text, improvement_color = "0.0%", MUTED
            improvement_sub = "No XP earned this week or last week."
    
        week_count = max(1, ((this_monday - first_week).days // 7) + 1)
        average_xp = sum(weekly_totals.values()) / week_count if events else 0
    
        if weekly_totals:
            best_week, best_xp = max(weekly_totals.items(), key=lambda item: (item[1], item[0]))
            best_label = f"{best_xp:,} XP"
            best_sub = f"{best_week.strftime('%d %b')} – {(best_week + timedelta(days=6)).strftime('%d %b %Y')}"
        else:
            best_week = None
            best_label, best_sub = "0 XP", "Complete a mission to set your record."
    
        active_days = sorted({date.fromisoformat(value) for value in self.db.get_activity_dates()})
        best_streak = 0
        best_start = best_end = None
        run_start = run_end = None
        run_length = 0
        for day in active_days:
            if run_end is not None and day == run_end + timedelta(days=1):
                run_end, run_length = day, run_length + 1
            else:
                run_start = run_end = day
                run_length = 1
            if run_length > best_streak:
                best_streak = run_length
                best_start, best_end = run_start, run_end

        if best_start is not None and best_end is not None:
            streak_sub = (
                f"{best_start.strftime('%d %b %Y')} – "
                f"{best_end.strftime('%d %b %Y')}"
            )
        else:
            streak_sub = "No completed activities recorded yet."

        categories = self.db.get_productivity_category_totals()
        if categories:
            category_label = categories[0]["category"]
            category_sub = f'{categories[0]["xp"]:,} XP · {categories[0]["events"]} earning events'
        else:
            category_label, category_sub = "No category yet", "Earn XP from a categorized mission."
    
        metrics = tk.Frame(self.content, bg=BG)
        metrics.pack(fill="x", pady=(0, 12))
        cards = [
            ("BEST-PERFORMING WEEK", best_label, GOLD, best_sub),
            ("AVERAGE WEEKLY XP", f"{average_xp:,.1f}", PURPLE, f"Across {week_count} calendar weeks"),
            ("WEEK-ON-WEEK IMPROVEMENT", improvement_text, improvement_color, improvement_sub),
        ]
        for i, (title, value, color, sub) in enumerate(cards):
            self.card(metrics, title, value, color, sub).grid(row=0, column=i, sticky="nsew", padx=(0, 9))
            metrics.grid_columnconfigure(i, weight=1)
    
        second = tk.Frame(self.content, bg=BG)
        second.pack(fill="x", pady=(0, 15))
        for i, (title, value, color, sub) in enumerate([
            ("MOST PRODUCTIVE CATEGORY", category_label, GREEN, category_sub),
            ("LONGEST CONSISTENCY", f"{best_streak} days", TEXT, streak_sub),
        ]):
            self.card(second, title, value, color, sub).grid(row=0, column=i, sticky="nsew", padx=(0, 9))
            second.grid_columnconfigure(i, weight=1)
    
        tk.Label(self.content, text="WEEKLY XP RANKINGS", bg=BG, fg=TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 7))
        tk.Label(self.content, text="Ranked by XP earned · weeks run Monday to Sunday",
                 bg=BG, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", pady=(0, 7))
        table_wrap = tk.Frame(self.content, bg=PANEL, padx=12, pady=10)
        table_wrap.pack(fill="both", expand=True)
        tree = ttk.Treeview(table_wrap, columns=("rank", "week", "xp", "activity"),
                            show="headings", height=8)
        for col, label, width in [
            ("rank", "#", 45), ("week", "WEEK", 230),
            ("xp", "XP EARNED", 130), ("activity", "PERFORMANCE", 250)
        ]:
            tree.heading(col, text=label)
            tree.column(col, width=width, anchor="center")
        scrollbar = ttk.Scrollbar(table_wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
        # Actual leaderboard ranking: highest-earning weeks appear first.
        ranked_weeks = sorted(weekly_totals.items(), key=lambda item: (item[1], item[0]), reverse=True)[:12]
        for rank, (week_start, amount) in enumerate(ranked_weeks, start=1):
            week_end = week_start + timedelta(days=6)
            label = f"{week_start.strftime('%d %b')} – {week_end.strftime('%d %b %Y')}"
            if week_start == this_monday:
                label += "  (Current)"
            status = "Current week · in progress" if week_start == this_monday else (
                "Personal best" if rank == 1 else "Completed week"
            )
            tree.insert("", "end", values=(rank, label, f"{amount:,}", status))
    
        if not ranked_weeks:
            tree.insert("", "end", values=("—", "No recorded weeks yet", "0", "Complete a mission to begin"))
    
        tk.Label(self.content, text="CATEGORY BREAKDOWN", bg=BG, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(12, 5))
        if categories:
            for item in categories[:5]:
                line = tk.Frame(self.content, bg=PANEL, padx=12, pady=7)
                line.pack(fill="x", pady=2)
                tk.Label(line, text=item["category"], bg=PANEL, fg=TEXT,
                         font=("Segoe UI", 9, "bold")).pack(side="left")
                tk.Label(line, text=f'{item["xp"]:,} XP · {item["events"]} events',
                         bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(side="right")
        else:
            tk.Label(self.content, text="Your category rankings will appear after you earn XP.",
                     bg=BG, fg=MUTED).pack(anchor="w")

    def show_achievements(self):
        self.navigate_style("Achievements")
        check_achievements(self.db)
        self.header("Achievements", "Milestones earned through consistent progress.")
        unlocked = {a["key"] for a in self.db.get_unlocked_achievements()}
        achievements = [
            ("first_task","First Blood","Complete your first mission","◇"),
            ("ten_tasks","Getting Serious","Complete 10 missions","⚔"),
            ("twenty_five","Task Slayer","Complete 25 missions","☠"),
            ("seven_day","Consistency King","Maintain a 7-day streak","🔥"),
            ("level_five","Rising Hero","Reach level 5","★"),
            ("level_ten","Epic Hero","Reach level 10","★"),
            ("level_twenty","Legendary Hero","Reach level 20","★"),
            ("streak_14","Fortnight Force","Maintain a 14-day streak","⚔"),
            ("streak_30","Monthly Master","Maintain a 30-day streak","🏆"),
            ("streak_60","Unstoppable","Maintain a 60-day streak","💎"),
            ("streak_100","Legendary","Maintain a 100-day streak","👑"),
            ("fifty_tasks","Master of Tasks","Complete 50 missions","♛"),
            ("hundred_tasks","Task Conqueror","Complete 100 missions","☠"),
        ]

        grid = tk.Frame(self.content, bg=BG); grid.pack(fill="both", expand=True)
        for i, (key, name, desc, icon) in enumerate(achievements):
            unlocked_now = key in unlocked
            f = tk.Frame(grid, bg=PANEL if unlocked_now else "#181824", padx=18, pady=18)
            f.grid(row=i//2, column=i%2, sticky="nsew", padx=7, pady=7)
            grid.grid_columnconfigure(i%2, weight=1); grid.grid_rowconfigure(i//2, weight=1)
            tk.Label(f, text=icon, bg=f["bg"], fg=GOLD if unlocked_now else "#555166",
                     font=("Segoe UI", 25)).pack(anchor="w")
            tk.Label(f, text=name, bg=f["bg"], fg=TEXT if unlocked_now else MUTED,
                     font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(8, 3))
            tk.Label(f, text=desc, bg=f["bg"], fg=MUTED, wraplength=330,
                     font=("Segoe UI", 9)).pack(anchor="w")
            tk.Label(f, text="UNLOCKED" if unlocked_now else "LOCKED",
                     bg=f["bg"], fg=GREEN if unlocked_now else "#77728c",
                     font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(12, 0))

    def show_statistics(self):
        self.navigate_style("Statistics")
        self.header("Statistics", "A clearer picture of your consistency.")
        tasks = self.db.get_tasks()
        done = [t for t in tasks if t["status"] == "done"]
        xp, level, current, needed = self._player_stats()
        streak = get_streak(self.db.get_completion_dates())
        row = tk.Frame(self.content, bg=BG); row.pack(fill="x")
        for title, value, color, sub in [
            ("Total XP", f"{xp:,}", PURPLE, "Lifetime experience"),
            ("Completed", str(len(done)), GREEN, "Missions completed"),
            ("Completion rate", f"{round(len(done)/len(tasks)*100) if tasks else 0}%", GOLD, "Completed / all missions"),
            ("Best streak", f"{self.db.get_best_streak()} days", TEXT, "Personal record")]:
            self.card(row, title, value, color, sub).pack(side="left", fill="both", expand=True, padx=(0, 10))
        tk.Label(self.content, text="RECENT XP ACTIVITY", bg=BG, fg=TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(28, 10))
        activity = tk.Frame(self.content, bg=PANEL, padx=16, pady=12); activity.pack(fill="both", expand=True)
        for item in self.db.get_xp_history(12):
            line = tk.Frame(activity, bg=PANEL); line.pack(fill="x", pady=6)
            tk.Label(line, text=item["reason"], bg=PANEL, fg=TEXT,
                     font=("Segoe UI", 10)).pack(side="left")
            amount = item["amount"]
            color = GREEN if amount >= 0 else RED
            sign = "+" if amount > 0 else ""
            tk.Label(line, text=f"{sign}{amount:,} XP", bg=PANEL, fg=color,
                     font=("Segoe UI", 10, "bold")).pack(side="right")
            tk.Label(activity, text=item["created_at"], bg=PANEL, fg=MUTED,
                     font=("Segoe UI", 8)).pack(anchor="w")

if __name__ == "__main__":
    app = LifeQuestApp()
    app.mainloop()