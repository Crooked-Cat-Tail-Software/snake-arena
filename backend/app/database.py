"""Database engine/session setup for Snake Arena.

Uses Postgres via SQLAlchemy + psycopg2. Configure with the DATABASE_URL
environment variable, e.g. postgresql://user:password@host:5432/dbname.
See docker-compose.yml at the repo root for a ready-to-run local Postgres,
or README.md for pointing this at one you already have.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Matches the credentials/db name docker-compose.yml's `db` service
# creates, reachable at localhost:5432 when that service is running
# locally (its port is published to the host). If you changed the host
# port in docker-compose.yml (e.g. because something else was already
# using 5432), update it here too. Override for any other Postgres
# server.
DEFAULT_DATABASE_URL = "postgresql://snake_arena:snake_arena@localhost:5432/snake_arena"
DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session, closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
