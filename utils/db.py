"""
Database helper for Streamlit.
Provides a cached SQLAlchemy engine and session factory.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import streamlit as st

from config import Config


def _resolve_database_url():
    """Return a database URL.

    Uses SQLite by default (stored in the project directory).
    This works well for Streamlit Cloud as long as you understand
    the ephemeral-storage limitation.
    """
    url = os.getenv("DATABASE_URL", "sqlite:///certigenius.db")
    return url


@st.cache_resource
def init_connection():
    """Initialize and cache the database engine + tables.

    This runs once and reuses the engine across all reruns.
    Returns the SQLAlchemy engine.
    """
    engine = create_engine(
        _resolve_database_url(),
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=3,
    )

    # Ensure upload directories exist (for file-based storage)
    _ensure_directories()

    return engine


def _ensure_directories():
    """Create required directories if they don't exist."""
    for path in [
        os.path.join(os.getcwd(), Config.UPLOAD_FOLDER, "templates"),
        os.path.join(os.getcwd(), Config.UPLOAD_FOLDER, "participants"),
        os.path.join(os.getcwd(), Config.CERTIFICATE_FOLDER),
    ]:
        os.makedirs(path, exist_ok=True)


def get_session():
    """Create a new database session from the cached engine."""
    engine = init_connection()
    Session = sessionmaker(bind=engine)
    return Session()
