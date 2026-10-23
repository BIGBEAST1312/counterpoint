# Give a staff member an email address | Built by Hetank Patel
# AI use: Used AI for concept explanations, understanding syntax, and general debugging guidance.
"""python -m scripts.set_email <username> <email>

Supervisors get an email for every status change (US-33) only if they have an email address.
The demo accounts have none, so use this, e.g.  python -m scripts.set_email chewy chewy@usask.ca"""
import sys

from app.auth.models import Staff
from app.core.database import SessionLocal, init_db


def main() -> None:
    if len(sys.argv) != 3 or "@" not in sys.argv[2]:
        raise SystemExit("Usage: python -m scripts.set_email <username> <email>")
    username, email = sys.argv[1].lower(), sys.argv[2].strip()
    init_db()
    db = SessionLocal()
    staff = db.query(Staff).filter_by(username=username).first()
    if staff is None:
        raise SystemExit(f"No staff member called {username}. Run python -m scripts.seed_demo first?")
    staff.email = email
    db.commit()
    print(f"{staff.display_name} ({staff.role}) will now get emails at {email}.")


if __name__ == "__main__":
    main()
