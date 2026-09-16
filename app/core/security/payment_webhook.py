import hashlib
import hmac
import json
import os
import time
from typing import Mapping


class PaymentWebhookSignatureError(ValueError):
    pass


def _load_secrets() -> dict[str, str]:
    raw = os.getenv("PAYMENT_WEBHOOK_SECRETS_JSON", "").strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PaymentWebhookSignatureError("invalid PAYMENT_WEBHOOK_SECRETS_JSON") from exc
    if not isinstance(value, dict) or any(not isinstance(k, str) or not isinstance(v, str) or not v for k, v in value.items()):
        raise PaymentWebhookSignatureError("PAYMENT_WEBHOOK_SECRETS_JSON must map string keys to non-empty secrets")
    return value


def secret_for(*, provider: str, tenant_id: int, secrets: Mapping[str, str] | None = None) -> str:
    values = dict(secrets) if secrets is not None else _load_secrets()
    secret = values.get(f"{provider}:{tenant_id}")
    if not secret:
        raise PaymentWebhookSignatureError("payment webhook secret is not configured")
    if len(secret) < 32:
        raise PaymentWebhookSignatureError("payment webhook secret must be at least 32 characters")
    return secret


def sign_payload(*, raw_body: bytes, timestamp: str, secret: str) -> str:
    if not secret or len(secret) < 32:
        raise PaymentWebhookSignatureError("payment webhook secret must be at least 32 characters")
    message = timestamp.encode("utf-8") + b"." + raw_body
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_signature(*, raw_body: bytes, timestamp: str, signature: str, secret: str, now: int | None = None, tolerance_seconds: int = 300) -> None:
    if not timestamp.isdigit():
        raise PaymentWebhookSignatureError("invalid webhook timestamp")
    issued = int(timestamp)
    current = int(time.time()) if now is None else now
    if abs(current - issued) > tolerance_seconds:
        raise PaymentWebhookSignatureError("webhook timestamp outside replay window")
    expected = sign_payload(raw_body=raw_body, timestamp=timestamp, secret=secret)
    provided = signature.strip().removeprefix("sha256=")
    if not hmac.compare_digest(provided, expected):
        raise PaymentWebhookSignatureError("invalid webhook signature")
