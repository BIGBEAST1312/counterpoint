# Feature 5 · Desk coverage | Owner: Aarya Patel
# AI disclosure: with guidance of Claude (Anthropic).
"""US-33: tell the supervisor when an assistant checks in, checks out, goes on break or lunch,
steps away or comes back, with the time it happened.

Every change becomes a row in the supervisor's in-app feed. If an email server is configured
(SMTP_HOST), each supervisor with an email address also gets an email. Email failures are
logged and never block the status change.
"""
import logging
import smtplib
from email.message import EmailMessage

from app.core import config
from app.core.clock import fmt_time, local

from .models import AT_LUNCH, AWAY, OFF_SHIFT, ON_BREAK, ON_DESK, STEPPED_AWAY

log = logging.getLogger("counterpoint.notify")


def describe(name: str, old: str, new: str, at, back_at=None) -> tuple[str, str]:
    """(kind, message) for one status change, e.g. ("on_break", "Sam went on break at 2:05 p.m.")."""
    when = fmt_time(at)
    if new == ON_DESK and old == OFF_SHIFT:
        kind, text = "checked_in", f"{name} checked in at {when}"
    elif new == OFF_SHIFT:
        kind, text = "checked_out", f"{name} checked out at {when}"
    elif new == ON_DESK and old in AWAY:
        kind, text = "back", f"{name} came back to the desk at {when}"
    elif new == ON_BREAK:
        kind, text = "on_break", f"{name} went on break at {when}"
    elif new == AT_LUNCH:
        kind, text = "at_lunch", f"{name} went to lunch at {when}"
    elif new == STEPPED_AWAY:
        kind, text = "stepped_away", f"{name} stepped away at {when}"
    else:
        kind, text = "changed", f"{name} changed status at {when}"
    if back_at is not None and new in AWAY:
        text += f" (back at {fmt_time(back_at)})"
    return kind, text if text.endswith(".") else text + "."


def email_enabled() -> bool:
    return bool(config.SMTP_HOST)


def send_email(recipients: list[str], message: str, at) -> bool:
    """Send one notification email. Runs as a background task after the response is sent."""
    if not email_enabled() or not recipients:
        return False
    msg = EmailMessage()
    msg["Subject"] = f"Counterpoint: {message}"
    msg["From"] = config.SMTP_FROM
    msg["To"] = ", ".join(recipients)
    msg.set_content(f"{message}\n\nTime: {local(at):%A %d %B %Y, %H:%M} (desk time)\n\n"
                    "Sent automatically by Counterpoint when a desk assistant's status changes.")
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as smtp:
            if config.SMTP_TLS:
                smtp.starttls()
            if config.SMTP_USER:
                smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
            smtp.send_message(msg)
        return True
    except Exception as exc:  # never let email problems break the desk
        log.warning("Could not email supervisor notification: %s", exc)
        return False
