# Set up supervisor email (US-33) | Built by Aarya Patel (team lead)
# AI disclosure: with guidance of Claude (Anthropic).
"""Give a supervisor (or shift lead) an email address and send a test email.

    python -m scripts.email_setup chewy you@gmail.com

Needs the mail settings in .env first (copy .env.example to .env and fill it in).
"""
import argparse
import logging

from app.auth.models import Staff
from app.core import clock, config
from app.core.database import SessionLocal, init_db


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    p = argparse.ArgumentParser(description="Set a staff member's email and send a test notification.")
    p.add_argument("username")
    p.add_argument("email")
    a = p.parse_args()
    init_db()
    db = SessionLocal()
    staff = db.query(Staff).filter_by(username=a.username.lower()).first()
    if staff is None:
        raise SystemExit(f"No staff member called {a.username!r}. Run python -m scripts.seed_demo first?")
    staff.email = a.email
    db.commit()
    print(f"{staff.display_name}'s email is now {a.email}.")
    if staff.role != "supervisor":
        print("Note: this account gets emails about its own time-off decisions. Status and time-away notifications go to supervisors.")
    if not config.SMTP_HOST:
        raise SystemExit("Email is off: SMTP_HOST isn't set. Copy .env.example to .env, fill it in, and run this again.")
    from app.coverage import notify
    ok = notify.send_email([a.email], f"test email for {staff.display_name}. Notifications work.",
                           clock.utcnow())
    if ok:
        print(f"Test email sent to {a.email}. Check the inbox (and spam).")
    else:
        raise SystemExit("The test email failed (see the message above). Check SMTP_HOST, SMTP_USER and SMTP_PASSWORD in .env.")


if __name__ == "__main__":
    main()
