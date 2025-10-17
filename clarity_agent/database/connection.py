from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from ..config.settings import settings
from ..utils.logging import logger

# A real app would get this from settings, but we'll hardcode for the hackathon
DATABASE_URL = "postgresql+asyncpg://user:password@localhost/clarity_agent_db"

try:
    engine = create_engine(DATABASE_URL.replace("+asyncpg", ""))
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info("Database connection pool created.")
except Exception as e:
    logger.error("Failed to create database connection pool", error=str(e))

@contextmanager
def get_db_session() -> Session:
    """Provides a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error("Database session error", error=str(e))
        raise
    finally:
        session.close()

def create_tables():
    """Create all database tables if they don't exist."""
    from .models import Base
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified/created successfully.")
    except Exception as e:
        logger.error("Failed to create database tables", error=str(e))