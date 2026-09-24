"""Shared server-authoritative mutation lifecycle primitives.

This module deliberately does not execute domain mutations. It only records
the lifecycle/evidence boundary so offline clients can remain explicit about
draft/pending/conflict state while domain services retain authority.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.models.core import AuditRecord, MutationRecord


ALLOWED_STATES = {"draft", "pending", "confirmed", "failed", "conflict"}


def canonical_request_hash(operation: str, actor_id: str, body: object) -> str:
    payload = {"operation": operation, "actor_id": actor_id, "body": body}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


class MutationLifecycleError(ValueError):
    pass


class MutationLifecycleService:
    def __init__(self, db):
        self.db = db

    def reserve(self, tenant_id: int, actor_id: str, operation: str, mutation_key: str, request_hash: str):
        key = str(mutation_key).strip()
        if not key or len(key) > 255:
            raise MutationLifecycleError("mutation key must be between 1 and 255 characters")
        if len(request_hash) != 64:
            raise MutationLifecycleError("mutation request hash is invalid")
        try:
            int(request_hash, 16)
        except ValueError:
            raise MutationLifecycleError("mutation request hash is invalid")
        try:
            with self.db.begin_nested():
                record = MutationRecord(
                    tenant_id=tenant_id,
                    actor_id=actor_id,
                    operation=operation,
                    mutation_key=key,
                    request_hash=request_hash.lower(),
                    state="pending",
                    response_json="{}",
                )
                self.db.add(record)
                self.db.flush()
                self.db.add(AuditRecord(
                    tenant_id=tenant_id,
                    actor_id=actor_id,
                    action="mutation_reserved",
                    subject="mutation",
                    subject_id=str(record.id),
                    metadata_json=json.dumps({
                        "operation": operation,
                        "mutation_key": key,
                        "request_hash": request_hash.lower(),
                        "state": "pending",
                    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
                ))
                self.db.flush()
                return record, False
        except IntegrityError:
            record = self.db.scalar(select(MutationRecord).where(
                MutationRecord.tenant_id == tenant_id,
                MutationRecord.mutation_key == key,
            ))
            if record is None:
                raise MutationLifecycleError("mutation reservation could not be resolved")
            if record.request_hash != request_hash.lower():
                raise MutationLifecycleError("mutation key was already used for a different request")
            self.db.add(AuditRecord(
                tenant_id=tenant_id,
                actor_id=actor_id,
                action="mutation_replayed",
                subject="mutation",
                subject_id=str(record.id),
                metadata_json=json.dumps({
                    "operation": record.operation,
                    "mutation_key": key,
                    "request_hash": request_hash.lower(),
                    "state": record.state,
                }, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
            ))
            self.db.flush()
            return record, True

    def transition(self, record: MutationRecord, state: str, *, resource_type=None, resource_id=None, response=None):
        if state not in ALLOWED_STATES:
            raise MutationLifecycleError("invalid mutation lifecycle state")
        previous_state = record.state
        if record.state == "confirmed" and state != "confirmed":
            raise MutationLifecycleError("confirmed mutation cannot move backward")
        if record.state == "conflict" and state not in {"conflict", "confirmed"}:
            raise MutationLifecycleError("conflict mutation requires explicit resolution")
        record.state = state
        if resource_type is not None:
            record.resource_type = resource_type
        if resource_id is not None:
            record.resource_id = str(resource_id)
        if response is not None:
            record.response_json = json.dumps(response, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        record.updated_at = datetime.now(timezone.utc)
        self.db.add(AuditRecord(
            tenant_id=record.tenant_id,
            actor_id=record.actor_id,
            action="mutation_transitioned",
            subject="mutation",
            subject_id=str(record.id),
            metadata_json=json.dumps({
                "operation": record.operation,
                "mutation_key": record.mutation_key,
                "from_state": previous_state,
                "to_state": state,
                "resource_type": record.resource_type,
                "resource_id": record.resource_id,
            }, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        ))
        self.db.flush()
        return record
