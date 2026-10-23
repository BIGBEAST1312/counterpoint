# Shared infrastructure | Built by Aarya Patel (team lead), owned by no feature
# AI disclosure: with guidance of Claude (Anthropic).
"""Settings every feature reads. Change them with environment variables, not by editing code."""
import os
from pathlib import Path
from zoneinfo import ZoneInfo


def _load_dotenv() -> None:
    """Read KEY=value lines from a .env file in the project folder, if there is one.
    Real environment variables win. .env holds passwords, so it is never committed (.gitignore)."""
    env = Path(__file__).resolve().parents[2] / ".env"
    if not env.is_file():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

# SQLite file in the project folder by default. Any SQLAlchemy URL works (e.g. PostgreSQL).
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./counterpoint.db")

# The desk's local time zone. "Today", weekdays, opening hours and busiest hours all use it.
LOCAL_TZ = ZoneInfo(os.getenv("DESK_TIMEZONE", "America/Regina"))

# How long a staff sign-in lasts before they have to sign in again.
SESSION_HOURS = int(os.getenv("SESSION_HOURS", "12"))

# The desk has two counters.
COUNTERS = ["Counter 1", "Counter 2"]

# Problem types: one fixed list shared by the kiosk, ticket drafts, guides and the report.
PROBLEM_TYPES = {
    "password": "Password & NSID",
    "mfa": "MFA & sign-in",
    "wifi": "Wi-Fi (eduroam)",
    "email": "Email & Outlook",
    "device": "Laptop or phone setup",
    "printing": "Printing",
    "software": "Software & licences",
    "other": "Something else",
}

# ---- Walk-up queue (Mohit) ----
DEFAULT_VISIT_MINUTES = 10      # used for the estimate until a visit has finished today
RECENT_CALL_MINUTES = 30        # a counter "is calling" if it called someone this recently
MISSED_CALL_MINUTES = 5         # a called student who hasn't arrived by then is marked Gone

# ---- Fix guides (Priyesh) ----
GUIDE_MAX_STEPS = 20
GUIDE_REVIEW_DAYS = 90

# ---- Desk coverage (Aarya) ----
# Default opening hours by weekday (0 = Monday). None means closed all day.
DEFAULT_HOURS = {0: ("09:30", "21:00"), 1: ("09:30", "21:00"), 2: ("09:30", "21:00"), 3: ("09:30", "21:00"),
                 4: ("09:30", "21:00"), 5: ("10:00", "18:00"), 6: ("10:00", "18:00")}

# Optional email for supervisor notifications (US-33). If SMTP_HOST is empty, notifications are in-app only.
# Put these in a .env file (copy .env.example) rather than typing them every time.
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "counterpoint@localhost")
SMTP_TLS = os.getenv("SMTP_TLS", "1") != "0"   # set SMTP_TLS=0 only for a local test mail server
