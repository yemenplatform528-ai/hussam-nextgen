import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

class InvalidToken(ValueError):
    pass

@dataclass(frozen=True)
class TokenClaims:
    sub: str
    tenant_id: int
    exp: int
    issuer: str | None = None

def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()

def encode_hs256(claims: dict, secret: str) -> str:
    if len(secret) < 32:
        raise ValueError("JWT secret must be at least 32 characters")
    header = {"alg": "HS256", "typ": "JWT"}
    h = _b64encode(json.dumps(header, separators=(",", ":")).encode())
    p = _b64encode(json.dumps(claims, separators=(",", ":")).encode())
    msg = f"{h}.{p}".encode()
    sig = hmac.new(secret.encode(), msg, hashlib.sha256).digest()
    return f"{h}.{p}.{_b64encode(sig)}"

def decode_hs256(token: str, secret: str, *, now: int | None = None) -> TokenClaims:
    if len(secret) < 32:
        raise ValueError("JWT secret must be at least 32 characters")
    try:
        h, p, s = token.split(".")
        expected = hmac.new(secret.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64decode(s)):
            raise InvalidToken("invalid signature")
        header = json.loads(_b64decode(h))
        if header.get("alg") != "HS256":
            raise InvalidToken("unsupported algorithm")
        data = json.loads(_b64decode(p))
        sub = str(data["sub"])
        tenant_id = int(data["tenant_id"])
        exp = int(data["exp"])
        if exp <= int(time.time() if now is None else now):
            raise InvalidToken("token expired")
        return TokenClaims(sub=sub, tenant_id=tenant_id, exp=exp, issuer=data.get("iss"))
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        raise InvalidToken("malformed token")
