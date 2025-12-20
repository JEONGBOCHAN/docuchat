# -*- coding: utf-8 -*-
"""Database configuration and session management."""

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from src.core.config import get_settings

# Create Base class for declarative models
Base = declarative_base()

# Database path
_settings = get_settings()
_db_path = Path(_settings.database_url.replace("sqlite:///", ""))

# Ensure data directory exists
_db_path.parent.mkdir(parents=True, exist_ok=True)

# Create engine
engine = create_engine(
    _settings.database_url,
    connect_args={"check_same_thread": False},  # Needed for SQLite
    echo=_settings.debug,
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Get database session.

    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
