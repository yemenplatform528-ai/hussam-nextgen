from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.models.documents import BusinessDocument, DocumentVersion, DocumentLink
from app.core.models.governance import OutboxEvent


class DocumentError(ValueError):
    pass


@dataclass(frozen=True)
class DocumentPayload:
    storage_key: str
    content: bytes
    content_type: str
    metadata: dict | None = None


class DocumentEngine:
    """Tenant-scoped business-record metadata and immutable content-version registry.

    Blob bytes remain in an external/object storage system; this engine stores only
    the trusted content hash, storage pointer and business-record lifecycle.
    """
    def __init__(self, db: Session):
        self.db = db

    def _emit(self, tenant_id: int, event_type: str, document_id: int, payload: dict):
        from uuid import uuid4
        self.db.add(OutboxEvent(
            event_id=str(uuid4()), tenant_id=tenant_id, event_type=event_type,
            aggregate_type="business_document", aggregate_id=str(document_id),
            payload=payload, published=False,
        ))

    def create(self, tenant_id: int, *, document_type: str, reference: str, title: str, metadata: dict | None = None) -> BusinessDocument:
        if tenant_id <= 0 or not document_type or not reference or not title:
            raise DocumentError("valid tenant, type, reference and title are required")
        if self.db.scalar(select(BusinessDocument).where(BusinessDocument.tenant_id == tenant_id, BusinessDocument.reference == reference)):
            raise DocumentError("duplicate document reference")
        d = BusinessDocument(tenant_id=tenant_id, document_type=document_type, reference=reference,
                             title=title, status="draft", current_version=0, metadata_json=metadata or {})
        self.db.add(d)
        try:
            self.db.flush()
            self._emit(tenant_id, "document.created", d.id, {"reference": reference, "document_type": document_type})
            self.db.commit(); self.db.refresh(d); return d
        except IntegrityError:
            self.db.rollback(); raise DocumentError("duplicate document reference")

    def _get(self, tenant_id: int, document_id: int, lock: bool = False) -> BusinessDocument:
        q = select(BusinessDocument).where(BusinessDocument.id == document_id, BusinessDocument.tenant_id == tenant_id)
        if lock:
            q = q.with_for_update()
        d = self.db.scalar(q)
        if d is None:
            raise DocumentError("document not found in tenant")
        return d

    @staticmethod
    def _hash(content: bytes) -> str:
        return sha256(content).hexdigest()

    def add_version(self, tenant_id: int, document_id: int, payload: DocumentPayload) -> DocumentVersion:
        d = self._get(tenant_id, document_id, lock=True)
        if d.status != "draft":
            raise DocumentError("only draft documents can receive new versions")
        if not payload.storage_key or not payload.content_type or len(payload.content) < 0:
            raise DocumentError("valid document payload is required")
        version = d.current_version + 1
        v = DocumentVersion(tenant_id=tenant_id, document_id=d.id, version=version,
                            storage_key=payload.storage_key, content_sha256=self._hash(payload.content),
                            content_type=payload.content_type, size_bytes=len(payload.content),
                            metadata_json=payload.metadata or {}, immutable=True)
        self.db.add(v)
        d.current_version = version
        self._emit(tenant_id, "document.version_added", d.id, {"reference": d.reference, "version": version, "sha256": v.content_sha256})
        try:
            self.db.commit(); self.db.refresh(v); return v
        except IntegrityError:
            self.db.rollback(); raise DocumentError("document version conflict")

    def finalize(self, tenant_id: int, document_id: int) -> BusinessDocument:
        d = self._get(tenant_id, document_id, lock=True)
        if d.status != "draft":
            raise DocumentError("only draft documents can be finalized")
        if d.current_version <= 0:
            raise DocumentError("document must have a version before finalization")
        d.status = "finalized"; d.finalized_at = datetime.now(timezone.utc)
        self._emit(tenant_id, "document.finalized", d.id, {"reference": d.reference, "version": d.current_version})
        self.db.commit(); return d

    def void(self, tenant_id: int, document_id: int) -> BusinessDocument:
        d = self._get(tenant_id, document_id, lock=True)
        if d.status == "void":
            raise DocumentError("document is already void")
        d.status = "void"
        self._emit(tenant_id, "document.voided", d.id, {"reference": d.reference, "version": d.current_version})
        self.db.commit(); return d

    def link(self, tenant_id: int, document_id: int, *, aggregate_type: str, aggregate_id: str, relation: str = "attachment") -> DocumentLink:
        d = self._get(tenant_id, document_id)
        if not aggregate_type or not aggregate_id or not relation:
            raise DocumentError("valid aggregate link is required")
        existing = self.db.scalar(select(DocumentLink).where(
            DocumentLink.tenant_id == tenant_id, DocumentLink.document_id == d.id,
            DocumentLink.aggregate_type == aggregate_type, DocumentLink.aggregate_id == str(aggregate_id),
            DocumentLink.relation == relation,
        ))
        if existing:
            return existing
        link = DocumentLink(tenant_id=tenant_id, document_id=d.id, aggregate_type=aggregate_type,
                            aggregate_id=str(aggregate_id), relation=relation)
        self.db.add(link)
        try:
            self.db.flush(); self._emit(tenant_id, "document.linked", d.id, {"reference": d.reference, "aggregate_type": aggregate_type, "aggregate_id": str(aggregate_id), "relation": relation})
            self.db.commit(); self.db.refresh(link); return link
        except IntegrityError:
            self.db.rollback()
            existing = self.db.scalar(select(DocumentLink).where(DocumentLink.tenant_id == tenant_id, DocumentLink.document_id == d.id, DocumentLink.aggregate_type == aggregate_type, DocumentLink.aggregate_id == str(aggregate_id), DocumentLink.relation == relation))
            if existing: return existing
            raise DocumentError("document link conflict")

    def verify_content(self, tenant_id: int, version_id: int, content: bytes) -> bool:
        v = self.db.scalar(select(DocumentVersion).where(DocumentVersion.id == version_id, DocumentVersion.tenant_id == tenant_id))
        if v is None:
            raise DocumentError("document version not found in tenant")
        return self._hash(content) == v.content_sha256 and len(content) == v.size_bytes
