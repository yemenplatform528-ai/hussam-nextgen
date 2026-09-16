import os
from typing import Generator
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.core.db.config import DatabaseSettings
from app.core.db.session import make_engine, make_session_factory
from app.core.security.auth_context import authenticate_context
from app.core.security.jwt import InvalidToken, decode_hs256

_engine = None
_factory = None

def get_session() -> Generator[Session, None, None]:
    global _engine, _factory
    if _factory is None:
        settings = DatabaseSettings.from_env()
        _engine = make_engine(settings)
        _factory = make_session_factory(_engine)
    db = _factory()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

from fastapi import Cookie

def get_context(authorization: str | None = Header(default=None), hussam_token: str | None = Cookie(default=None), db: Session = Depends(get_session)):
    if not authorization and hussam_token:
        authorization = "Bearer " + hussam_token
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="authentication required")
    secret = os.getenv("JWT_SECRET", "")
    try:
        claims = decode_hs256(authorization[7:].strip(), secret)
        return authenticate_context(db, claims)
    except (InvalidToken, ValueError):
        raise HTTPException(status_code=401, detail="invalid authentication token")
    except PermissionError:
        raise HTTPException(status_code=403, detail="active tenant membership required")
