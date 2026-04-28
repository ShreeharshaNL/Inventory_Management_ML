"""
Database connection, session management, and initialization.
Uses SQLAlchemy 2.0 async-compatible patterns.
"""

import logging
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from src.api.models import Base
from src.config import settings

logger = logging.getLogger(__name__)

# ─── Engine ────────────────────────────────────────────────────────────────────

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ─── Dependency (FastAPI) ──────────────────────────────────────────────────────

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── Context Manager (Scripts / Tests) ────────────────────────────────────────

@contextmanager
def get_db_context():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ─── Initialization ────────────────────────────────────────────────────────────

def create_tables():
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Tables created successfully.")


def drop_tables():
    logger.warning("Dropping all database tables!")
    Base.metadata.drop_all(bind=engine)


def check_connection():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection OK.")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False