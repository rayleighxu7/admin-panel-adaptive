from collections.abc import Generator

from sqlalchemy import create_engine as sa_create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def create_engine() -> Engine:
    global _engine, _SessionLocal

    url = settings.DATABASE_URL
    kwargs: dict = {}

    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10
        kwargs["pool_pre_ping"] = True

    _engine = sa_create_engine(url, echo=settings.DEBUG, **kwargs)
    _SessionLocal = sessionmaker(bind=_engine)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("Engine not initialised — call create_engine() first")
    return _engine


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a request-scoped DB session."""
    if _SessionLocal is None:
        raise RuntimeError("Engine not initialised — call create_engine() first")
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()


def dispose_engine() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _SessionLocal = None
