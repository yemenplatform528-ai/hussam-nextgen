import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.models.logistics import CarrierIntegration, CarrierEvent, Shipment
from app.engines.logistics import LogisticsProductionService, LogisticsError

class CarrierError(ValueError):
    pass

STATUS_MAP = {
    'picked_up': 'picked_up',
    'in_transit': 'in_transit',
    'out_for_delivery': 'out_for_delivery',
    'delivered': 'delivered',
    'failed': 'failed',
    'returned': 'returned',
}

class CarrierLifecycleService:
    """Provider-neutral carrier registry and signed event ingestion. Secrets stay outside the database."""
    def __init__(self, db: Session):
        self.db = db

    def register(self, tenant_id: int, code: str, name: str, secret_ref: str | None = None) -> CarrierIntegration:
        code = code.strip().lower()
        if not code or not name.strip():
            raise CarrierError('carrier code and name are required')
        if self.db.scalar(select(CarrierIntegration).where(CarrierIntegration.tenant_id == tenant_id, CarrierIntegration.code == code)):
            raise CarrierError('carrier integration already exists')
        x = CarrierIntegration(tenant_id=tenant_id, code=code, name=name.strip(), webhook_secret_ref=secret_ref, active=True)
        self.db.add(x)
        try:
            self.db.commit(); self.db.refresh(x); return x
        except IntegrityError:
            self.db.rollback(); raise CarrierError('carrier integration already exists')

    def _carrier(self, tenant_id: int, code: str) -> CarrierIntegration:
        x = self.db.scalar(select(CarrierIntegration).where(CarrierIntegration.tenant_id == tenant_id, CarrierIntegration.code == code.strip().lower(), CarrierIntegration.active.is_(True)))
        if not x: raise CarrierError('active carrier integration not found')
        return x

    @staticmethod
    def _canonical(payload: dict) -> bytes:
        return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')

    @classmethod
    def sign(cls, payload: dict, secret: str) -> str:
        return hmac.new(secret.encode('utf-8'), cls._canonical(payload), hashlib.sha256).hexdigest()

    @classmethod
    def verify_signature(cls, payload: dict, signature: str, secret: str) -> bool:
        if not signature or not secret: return False
        return hmac.compare_digest(cls.sign(payload, secret), signature.strip().removeprefix('sha256='))

    @staticmethod
    def secret_from_environment(code: str) -> str:
        key = 'CARRIER_WEBHOOK_SECRET_' + ''.join(ch if ch.isalnum() else '_' for ch in code.upper())
        value = os.getenv(key, '')
        if not value:
            raise CarrierError('carrier webhook secret is not configured')
        return value

    def ingest_event(self, tenant_id: int, carrier_code: str, *, external_event_id: str,
                     shipment_reference: str, event_type: str, payload: dict, signature: str,
                     location: str | None = None, note: str | None = None,
                     occurred_at: datetime | None = None, secret: str | None = None) -> Shipment:
        if not external_event_id or not shipment_reference or not event_type:
            raise CarrierError('carrier event identity is required')
        carrier = self._carrier(tenant_id, carrier_code)
        secret = secret or self.secret_from_environment(carrier.code)
        if not self.verify_signature(payload, signature, secret):
            raise CarrierError('invalid carrier webhook signature')
        existing = self.db.scalar(select(CarrierEvent).where(CarrierEvent.tenant_id == tenant_id, CarrierEvent.carrier_id == carrier.id, CarrierEvent.external_event_id == external_event_id))
        shipment = self.db.scalar(select(Shipment).where(Shipment.tenant_id == tenant_id, Shipment.reference == shipment_reference))
        if not shipment: raise CarrierError('shipment not found in tenant')
        if existing:
            if existing.payload_hash != hashlib.sha256(self._canonical(payload)).hexdigest():
                raise CarrierError('carrier event payload mismatch')
            return shipment
        mapped = STATUS_MAP.get(event_type)
        if not mapped: raise CarrierError('unsupported carrier event type')
        event_hash = hashlib.sha256(self._canonical(payload)).hexdigest()
        try:
            shipment = LogisticsProductionService(self.db).transition(tenant_id, shipment.id, mapped, event_id=f'carrier:{carrier.id}:{external_event_id}', location=location, note=note, occurred_at=occurred_at)
            self.db.add(CarrierEvent(tenant_id=tenant_id, carrier_id=carrier.id, shipment_id=shipment.id, external_event_id=external_event_id, event_type=event_type, payload_hash=event_hash))
            self.db.commit(); self.db.refresh(shipment); return shipment
        except LogisticsError as exc:
            raise CarrierError(str(exc)) from exc
        except IntegrityError:
            self.db.rollback()
            existing = self.db.scalar(select(CarrierEvent).where(CarrierEvent.tenant_id == tenant_id, CarrierEvent.carrier_id == carrier.id, CarrierEvent.external_event_id == external_event_id))
            if existing: return shipment
            raise CarrierError('carrier event conflict')
