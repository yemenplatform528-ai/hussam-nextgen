from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db.config import DatabaseSettings

def make_engine(settings: DatabaseSettings):
    return create_engine(
        settings.url,
        echo=settings.echo,
        pool_pre_ping=settings.pool_pre_ping,
        future=True,
    )

def make_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

@contextmanager
def transaction(factory):
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
