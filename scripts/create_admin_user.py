"""Create or update an admin user with a hashed password."""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.auth import hash_password
from app.database import create_engine, get_session_factory
from app.models import AdminUser


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or update an admin user.")
    parser.add_argument("--username", help="Admin username")
    parser.add_argument("--password", help="Admin password (omit to be prompted securely)")
    parser.add_argument(
        "--inactive",
        action="store_true",
        help="Create/update as inactive user",
    )
    return parser.parse_args()


def prompt_if_missing(username: str | None, password: str | None) -> tuple[str, str]:
    user = (username or input("Username: ")).strip()
    if not user:
        raise ValueError("Username is required.")

    pwd = password or getpass.getpass("Password: ")
    if len(pwd) < 8:
        raise ValueError("Password must be at least 8 characters.")
    return user, pwd


def main() -> None:
    args = parse_args()
    username, password = prompt_if_missing(args.username, args.password)
    create_engine()
    session_factory = get_session_factory()

    with session_factory() as db:
        user = db.query(AdminUser).filter(AdminUser.username == username).first()
        if user is None:
            user = AdminUser(
                username=username,
                password_hash=hash_password(password),
                is_active=not args.inactive,
            )
            db.add(user)
            action = "created"
        else:
            user.password_hash = hash_password(password)
            user.is_active = not args.inactive
            action = "updated"

        db.commit()

    print(f"Admin user '{username}' {action}.")


if __name__ == "__main__":
    main()
