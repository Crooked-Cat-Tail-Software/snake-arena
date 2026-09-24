"""Database engine/session setup for Snake Arena.

Configure with either:
  - DATABASE_URL -- a full connection string, e.g.
    postgresql://user:password@host:5432/dbname. This is the default path
    (see docker-compose.yml at the repo root for a ready-to-run local
    Postgres, or README.md for pointing this at one you already have).
  - DB_HOST (plus optionally DB_PORT, DB_USER, DB_PASSWORD, DB_NAME) --
    built into a connection string instead, taking priority over
    DATABASE_URL whenever DB_HOST is set. This is what the AWS deployment
    uses (see infra/aws/02-app.yaml), since the RDS endpoint isn't known
    until deploy time and the password comes from AWS Secrets Manager
    rather than a plain environment variable.
"""
import os
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Matches the credentials/db name docker-compose.yml's `db` service
# creates, reachable at localhost:5432 when that service is running
# locally (its port is published to the host). If you changed the host
# port in docker-compose.yml (e.g. because something else was already
# using 5432), update it here too. Override for any other Postgres
# server.
DEFAULT_DATABASE_URL = "postgresql://snake_arena:snake_arena@localhost:5432/snake_arena"


def _database_url_from_env() -> str:
    db_host = os.environ.get("DB_HOST")
    if db_host:
        # Split-var form -- see module docstring. Values are URL-encoded
        # since AWS Secrets Manager-generated passwords can contain
        # characters (e.g. "@", "/") that would otherwise break the URL.
        db_port = os.environ.get("DB_PORT", "5432")
        db_user = os.environ.get("DB_USER", "snake_arena")
        db_password = os.environ.get("DB_PASSWORD", "")
        db_name = os.environ.get("DB_NAME", "snake_arena")
        return (
            f"postgresql://{quote_plus(db_user)}:{quote_plus(db_password)}"
            f"@{db_host}:{db_port}/{db_name}"
        )
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


DATABASE_URL = _database_url_from_env()

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
