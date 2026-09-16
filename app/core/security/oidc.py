"""Provider-neutral OpenID Connect authorization-code integration.

This module intentionally keeps OIDC at the identity boundary. It exchanges an
authorization code, validates the returned ID token against issuer metadata and
JWKS, and returns normalized identity claims to the identity service. No provider
secret is ever returned to the browser or written to logs/evidence.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

import jwt


class OIDCError(ValueError):
    pass


@dataclass(frozen=True)
class OIDCSettings:
    client_id: str
    issuer: str
    client_secret: str
    redirect_uri: str
    state_secret: str
    scopes: tuple[str, ...] = ("openid", "profile", "email")

    @classmethod
    def from_env(cls) -> "OIDCSettings":
        values = {
            "OIDC_CLIENT_ID": os.getenv("OIDC_CLIENT_ID", "").strip(),
            "OIDC_ISSUER": os.getenv("OIDC_ISSUER", "").strip().rstrip("/"),
            "OIDC_CLIENT_SECRET": os.getenv("OIDC_CLIENT_SECRET", ""),
            "OIDC_REDIRECT_URI": os.getenv("OIDC_REDIRECT_URI", "").strip(),
            "OIDC_STATE_SECRET": os.getenv("OIDC_STATE_SECRET", ""),
        }
        missing = [k for k, v in values.items() if not v]
        if missing:
            raise OIDCError("missing OIDC configuration: " + ", ".join(missing))
        if len(values["OIDC_STATE_SECRET"]) < 32:
            raise OIDCError("OIDC_STATE_SECRET must be at least 32 characters")
        return cls(**{
            "client_id": values["OIDC_CLIENT_ID"],
            "issuer": values["OIDC_ISSUER"],
            "client_secret": values["OIDC_CLIENT_SECRET"],
            "redirect_uri": values["OIDC_REDIRECT_URI"],
            "state_secret": values["OIDC_STATE_SECRET"],
        })


def _json_get(url: str, *, timeout: float = 5.0) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # pragma: no cover - network/provider dependent
        raise OIDCError("OIDC provider metadata request failed") from exc


def discover(settings: OIDCSettings) -> dict[str, Any]:
    metadata = _json_get(settings.issuer + "/.well-known/openid-configuration")
    if metadata.get("issuer", "").rstrip("/") != settings.issuer:
        raise OIDCError("OIDC issuer metadata mismatch")
    for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        if not metadata.get(key):
            raise OIDCError(f"OIDC provider metadata missing {key}")
    return metadata


def _sign(value: str, secret: str) -> str:
    return base64.urlsafe_b64encode(hmac.new(secret.encode(), value.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()


def make_state(settings: OIDCSettings, *, now: int | None = None) -> str:
    issued = int(time.time() if now is None else now)
    nonce = base64.urlsafe_b64encode(os.urandom(24)).rstrip(b"=").decode()
    payload = f"{issued}.{nonce}"
    return f"{payload}.{_sign(payload, settings.state_secret)}"


def verify_state(settings: OIDCSettings, state: str, *, now: int | None = None, max_age: int = 600) -> bool:
    try:
        issued_s, nonce, signature = state.split(".")
        payload = f"{issued_s}.{nonce}"
        expected = _sign(payload, settings.state_secret)
        issued = int(issued_s)
        current = int(time.time() if now is None else now)
        return hmac.compare_digest(signature, expected) and 0 <= current - issued <= max_age and bool(nonce)
    except (ValueError, TypeError):
        return False


def authorization_url(settings: OIDCSettings, metadata: dict[str, Any], state: str, nonce: str) -> str:
    params = {
        "response_type": "code",
        "client_id": settings.client_id,
        "redirect_uri": settings.redirect_uri,
        "scope": " ".join(settings.scopes),
        "state": state,
        "nonce": nonce,
    }
    return metadata["authorization_endpoint"] + "?" + urllib.parse.urlencode(params)


def extract_nonce(state: str) -> str:
    try:
        _, nonce, _ = state.split(".")
        return nonce
    except ValueError as exc:
        raise OIDCError("invalid OIDC state") from exc


def exchange_code(settings: OIDCSettings, metadata: dict[str, Any], code: str) -> dict[str, Any]:
    body = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.redirect_uri,
        "client_id": settings.client_id,
        "client_secret": settings.client_secret,
    }).encode()
    request = urllib.request.Request(
        metadata["token_endpoint"],
        data=body,
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # pragma: no cover - provider dependent
        raise OIDCError("OIDC authorization-code exchange failed") from exc
    if not data.get("id_token"):
        raise OIDCError("OIDC token response did not contain an id_token")
    return data


def validate_id_token(settings: OIDCSettings, metadata: dict[str, Any], id_token: str, *, nonce: str) -> dict[str, Any]:
    try:
        header = jwt.get_unverified_header(id_token)
        alg = header.get("alg")
        kid = header.get("kid")
        if alg not in {"RS256", "RS384", "RS512"} or not kid:
            raise OIDCError("unsupported OIDC ID token signing algorithm")
        jwks = _json_get(metadata["jwks_uri"])
        key = next((item for item in jwks.get("keys", []) if item.get("kid") == kid), None)
        if key is None:
            raise OIDCError("OIDC signing key not found")
        signing_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
        claims = jwt.decode(
            id_token,
            signing_key,
            algorithms=[alg],
            audience=settings.client_id,
            issuer=settings.issuer,
            options={"require": ["iss", "sub", "aud", "exp", "iat", "nonce"]},
        )
        if not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
            raise OIDCError("OIDC nonce mismatch")
        return claims
    except OIDCError:
        raise
    except jwt.PyJWTError as exc:
        raise OIDCError("invalid OIDC ID token") from exc


def normalize_identity(claims: dict[str, Any]) -> tuple[str, str]:
    subject = str(claims.get("sub", "")).strip()
    email = str(claims.get("email", "")).strip().lower()
    if not subject or "@" not in email:
        raise OIDCError("OIDC identity must contain sub and verified email")
    if claims.get("email_verified") is not True:
        raise OIDCError("OIDC email must be verified")
    return subject, email
