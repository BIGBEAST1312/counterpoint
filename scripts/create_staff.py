# Create a staff account | Built by Hetank Patel
# AI use: Used AI for concept explanations, understanding syntax, and general debugging guidance.
"""python -m scripts.create_staff <username> "<Display name>" <assistant|lead|supervisor> [--email x@usask.ca]"""
import argparse
import getpass

from app.auth.models import ROLES, Staff
from app.auth.security import hash_password
from app.core.database import SessionLocal, init_db


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("username")
    p.add_argument("display_name")
    p.add_argument("role", choices=ROLES)
    p.add_argument("--email")
    a = p.parse_args()
    password = getpass.getpass("Password (8+ characters): ")
    if len(password) < 8:
        raise SystemExit("Password must be at least 8 characters.")
    init_db()
    db = SessionLocal()
    if db.query(Staff).filter_by(username=a.username.lower()).first():
        raise SystemExit(f"{a.username} already exists.")
    db.add(Staff(username=a.username.lower(), display_name=a.display_name, role=a.role, email=a.email,
                 password_hash=hash_password(password)))
    db.commit()
    print(f"Created {a.role} {a.username}.")


if __name__ == "__main__":
    main()
