"""Initialize local database schema from SQLAlchemy models."""

from app.database import create_engine
from app.models import Base


def main() -> None:
    engine = create_engine()
    Base.metadata.create_all(bind=engine)
    print("Database schema initialized.")
    print(f"Connected database: {engine.url}")


if __name__ == "__main__":
    main()