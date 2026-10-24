# Feature 2 · Ticket drafts & shift handover | Owner: Hetank Patel
# AI use: Used AI for concept explanations, understanding syntax, and general debugging guidance.
from app.core.config import PROBLEM_TYPES

from .models import TicketDraft


def summary_line(d: TicketDraft) -> str:
    """One-line summary for the TeamDynamix title, e.g. 'Wi-Fi (eduroam): can't connect on Android 14'."""
    first = " ".join(d.reported.split())
    if len(first) > 70:
        first = first[:67].rstrip() + "..."
    return f"{PROBLEM_TYPES.get(d.problem_type, d.problem_type)}: {first}"


def ticket_text(d: TicketDraft) -> str:
    """The text the assistant pastes into TeamDynamix (US-07 test 1)."""
    return "\n".join([
        f"Summary: {summary_line(d)}",
        "",
        "Student reported:",
        d.reported.strip(),
        "",
        "What I did:",
        d.what_i_did.strip(),
        "",
        f"Outcome: {d.outcome}",
    ])
