"""Database engine and session creation; SQLite locally, PostgreSQL in deployment."""
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def create_db_engine(url: str | None = None):
    url = url or os.getenv('DATABASE_URL', 'sqlite:///./data/startup_support.db')
    if url.startswith('postgresql://'):
        url = url.replace('postgresql://', 'postgresql+psycopg://', 1)
    elif url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql+psycopg://', 1)
    if url.startswith('sqlite:///') and url != 'sqlite:///:memory:':
        db_file = url.removeprefix('sqlite:///')
        Path(db_file).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={'check_same_thread': False} if url.startswith('sqlite:') else {}, pool_pre_ping=True)
    if url.startswith('sqlite:'):
        from sqlalchemy import event
        @event.listens_for(engine, 'connect')
        def enable_foreign_keys(dbapi_connection, _):
            cur = dbapi_connection.cursor()
            cur.execute('PRAGMA foreign_keys=ON')
            cur.close()
    return engine


engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session():
    with SessionLocal() as session:
        yield session
