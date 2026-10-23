# Demo data for trying Counterpoint locally | Owner: Priyesh Patel
# AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the team.
"""Creates demo staff and, for each feature that is merged, some data to try it with:
visits for the last two weeks and this week so far, a few guides, drafts and today's shift.

    python -m scripts.seed_demo          (from the project folder)

Assistants: aarya, priyesh, mohit, nate, rurik, palak, laaiba, oliver
Supervisors: chewy, tom            Password for everyone: counterpoint
"""
import random
from datetime import date, datetime, timedelta, timezone

from app.auth.models import Staff
from app.auth.security import hash_password
from app.core import clock
from app.core.config import LOCAL_TZ, PROBLEM_TYPES
from app.core.database import SessionLocal, import_feature, init_db

# Each part of the demo data is added only if its feature has been merged.
queue = import_feature("queue", "models")
guides = import_feature("guides", "models")
tickets = import_feature("tickets", "models")
coverage = import_feature("coverage", "logic")
timeaway = import_feature("coverage", "timeaway")     # E11, Deliverable 3

PASSWORD = "counterpoint"
ASSISTANTS = ["Aarya", "Priyesh", "Mohit", "Nate", "Rurik", "Palak", "Laaiba", "Oliver"]
SUPERVISORS = ["Chewy", "Tom"]
STAFF = [(n.lower(), n, "assistant") for n in ASSISTANTS] + [(n.lower(), n, "supervisor") for n in SUPERVISORS]


def main() -> None:
    init_db()
    db = SessionLocal()
    if db.query(Staff).count():
        print("Database already has staff; delete counterpoint.db to start again.")
        return
    people = {}
    for username, name, role in STAFF:
        people[username] = Staff(username=username, display_name=name, role=role,
                                 password_hash=hash_password(PASSWORD))
        db.add(people[username])
    db.commit()

    today = clock.local_today()
    now = clock.utcnow()
    if queue:
        add_visits(db, today)
    if guides:
        add_guides(db, people, now)
    if tickets:
        add_drafts_and_notes(db, people, now)
    db.commit()
    if coverage:
        add_todays_shift(db, people, today, now)
    if timeaway:
        add_time_away(db, people, today, now)
    print("Demo data ready.")
    print("Assistants:  " + ", ".join(n.lower() for n in ASSISTANTS))
    print("Supervisors: " + ", ".join(n.lower() for n in SUPERVISORS))
    print(f"Password for everyone: {PASSWORD}")


def add_visits(db, today) -> None:
    """Two past weeks of walk-ups, busier around lunch and on Tuesdays (feeds the weekly report)."""
    DONE, GONE, LEFT, Visit = queue.DONE, queue.GONE, queue.LEFT, queue.Visit
    rng = random.Random(370)
    monday = clock.week_start(today) - timedelta(days=14)
    n_by_day: dict[date, int] = {}
    for d in range(21):            # two full past weeks plus this week up to yesterday
        day = monday + timedelta(days=d)
        if day >= today:
            break
        if day.weekday() >= 5 and rng.random() < .5:
            continue
        for _ in range(rng.randint(12, 22) + (8 if day.weekday() == 1 else 0)):
            hour = rng.choice([10, 11, 11, 12, 12, 12, 13, 13, 14, 15, 16, 17, 18, 19])
            arrived = datetime(day.year, day.month, day.day, hour, rng.randint(0, 59), tzinfo=LOCAL_TZ).astimezone(timezone.utc)
            wait = rng.choice([2, 4, 6, 8, 10, 12, 15, 20, 25, 35])
            fate = rng.random()
            status = DONE if fate > .09 else (LEFT if fate > .04 else GONE)
            called = arrived + timedelta(minutes=wait) if status != LEFT else None
            n_by_day[day] = n_by_day.get(day, 0) + 1
            db.add(Visit(ticket_date=day, ticket_no=n_by_day[day], first_name="Demo", status=status,
                         problem_type=rng.choice(list(PROBLEM_TYPES)), arrived_at=arrived, called_at=called,
                         counter=rng.choice(["Counter 1", "Counter 2"]) if called else None,
                         served_at=called if status == DONE else None,
                         finished_at=(called or arrived) + timedelta(minutes=rng.randint(5, 18))))


def add_guides(db, people, now) -> None:
    Guide, GuideStep = guides.Guide, guides.GuideStep
    demo = [
        ("MFA: re-register a new phone", "mfa", "Does the student have their new phone with them?",
         ["Ask the student to sign in to the MFA setup page on a desk computer.", "Check their identity with photo ID.",
          "Remove the old phone from their sign-in methods.", "Add the new phone with the authenticator app.",
          "Send a test sign-in request and have them approve it.", "Confirm they can reach PAWS and email.",
          "Write the ticket draft with outcome Solved."]),
        ("eduroam on Android 14", "wifi", "", ["Forget the eduroam network.", "Re-add eduroam: EAP method PEAP, phase 2 MSCHAPV2.",
          "Set CA certificate to 'Use system certificates' and domain usask.ca.", "Sign in with NSID@usask.ca and password."]),
        ("Outlook keeps asking for a password", "email", "", ["Close Outlook.", "Clear saved USask credentials from the credential manager.",
          "Reopen Outlook and sign in once with MFA."]),
    ]
    for title, ptype, before, steps in demo:
        g = Guide(title=title, problem_type=ptype, before_you_start=before, created_by_id=people["priyesh"].id,
                  created_at=now - timedelta(days=120), reviewed_at=now - timedelta(days=120 if ptype == "email" else 10))
        g.steps = [GuideStep(position=i, text=t) for i, t in enumerate(steps, 1)]
        db.add(g)


def add_drafts_and_notes(db, people, now) -> None:
    TicketDraft, HandoverNote = tickets.TicketDraft, tickets.HandoverNote
    db.add(TicketDraft(author_id=people["rurik"].id, problem_type="printing", reported="Can't release print jobs at Murray",
                       what_i_did="Re-added the printer, job released", outcome="Solved", created_at=now - timedelta(hours=2)))
    db.add(TicketDraft(author_id=people["rurik"].id, problem_type="software", reported="SPSS licence expired",
                       what_i_did="Checked licence server; needs ICT", outcome="Escalated", created_at=now - timedelta(hours=1)))
    db.add(HandoverNote(author_id=people["palak"].id, text="Printer 2 jammed; Facilities called, no fix yet",
                        category="Equipment", urgent=True, created_at=now - timedelta(hours=3)))


def add_todays_shift(db, people, today, now) -> None:
    """Today's shift so far. Each change goes through the coverage rules, so the supervisors'
    notification feed shows it with its time. Times are kept within today."""
    start = max(clock.local_midnight_utc(today) + timedelta(minutes=1), now - timedelta(hours=5))
    at = lambda minutes: min(now, start + timedelta(minutes=minutes))  # noqa: E731
    plan = [("palak", "on_desk", 0, None), ("aarya", "on_desk", 20, None), ("rurik", "on_desk", 45, None),
            ("priyesh", "on_desk", 70, None), ("mohit", "on_desk", 95, None),
            ("palak", "off_shift", 200, None), ("mohit", "at_lunch", 260, 60), ("rurik", "on_break", 285, 25)]
    for who, status, minute, back_in in plan:
        when = at(minute)
        back = when + timedelta(minutes=back_in) if back_in else None
        coverage.set_status(db, people[who], status, back, True, when)


def add_time_away(db, people, today, now) -> None:
    """Time away (E11): one sick report for tomorrow, one request waiting, one approved."""
    timeaway.report_absence(db, people["laaiba"], "sick", today + timedelta(days=1), "13:00", "17:00",
                            "Should be fine by Thursday", now - timedelta(hours=1))
    monday = clock.week_start(today) + timedelta(days=7)
    timeaway.request_time_off(db, people["oliver"], monday, monday + timedelta(days=2), "Midterm week", now - timedelta(hours=2))
    req, _ = timeaway.request_time_off(db, people["palak"], today + timedelta(days=4), today + timedelta(days=5),
                                       "Family visiting", now - timedelta(days=1))
    timeaway.decide_time_off(db, people["chewy"], req, True, "", now - timedelta(hours=20))


if __name__ == "__main__":
    main()
