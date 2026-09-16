from time import time
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core.security.payment_webhook import sign_payload, verify_signature, PaymentWebhookSignatureError


def test_payment_webhook_signature_round_trip_and_tamper_rejection():
    raw = b'{"tenant_id":7,"provider":"wallet","event_id":"evt-1"}'
    ts = str(int(time()))
    secret = "s" * 32
    sig = sign_payload(raw_body=raw, timestamp=ts, secret=secret)
    verify_signature(raw_body=raw, timestamp=ts, signature="sha256=" + sig, secret=secret)
    try:
        verify_signature(raw_body=raw + b"x", timestamp=ts, signature=sig, secret=secret)
    except PaymentWebhookSignatureError:
        pass
    else:
        raise AssertionError("tampered webhook was accepted")


def test_payment_webhook_replay_window_is_enforced():
    raw = b"{}"
    secret = "s" * 32
    old = str(1_000_000)
    sig = sign_payload(raw_body=raw, timestamp=old, secret=secret)
    try:
        verify_signature(raw_body=raw, timestamp=old, signature=sig, secret=secret, now=1_000_301)
    except PaymentWebhookSignatureError:
        pass
    else:
        raise AssertionError("expired webhook was accepted")
