"""Initialize local database schema from SQLAlchemy models."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import create_engine
from app.models import Base


def main() -> None:
    engine = create_engine()
    Base.metadata.create_all(bind=engine)
    print("Database schema initialized.")
    print(f"Connected database: {engine.url}")


if __name__ == "__main__":
    main()