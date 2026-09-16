from hashlib import sha256
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.persistence import Base
import app.core.models
from app.core.models.documents import BusinessDocument, DocumentVersion, DocumentLink
from app.core.models.governance import OutboxEvent
from app.engines.documents import DocumentEngine, DocumentError, DocumentPayload


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        session.add_all([__import__("app.core.models.core", fromlist=["Tenant"]).Tenant(id=1, name="A", status="active"), __import__("app.core.models.core", fromlist=["Tenant"]).Tenant(id=2, name="B", status="active")])
        session.commit()
        yield session

def test_document_version_hash_size_and_outbox(db):
    e = DocumentEngine(db)
    d = e.create(1, document_type="invoice", reference="INV-DOC-1", title="Invoice")
    v = e.add_version(1, d.id, DocumentPayload("s3://bucket/key", b"hello", "application/pdf"))
    assert v.version == 1
    assert v.size_bytes == 5
    assert v.content_sha256 == sha256(b"hello").hexdigest()
    assert e.verify_content(1, v.id, b"hello") is True
    assert e.verify_content(1, v.id, b"tampered") is False
    assert db.query(OutboxEvent).count() == 2


def test_finalized_documents_are_immutable(db):
    e = DocumentEngine(db)
    d = e.create(1, document_type="receipt", reference="REC-1", title="Receipt")
    e.add_version(1, d.id, DocumentPayload("key/1", b"one", "text/plain"))
    e.finalize(1, d.id)
    with pytest.raises(DocumentError):
        e.add_version(1, d.id, DocumentPayload("key/2", b"two", "text/plain"))


def test_cannot_finalize_without_version(db):
    e = DocumentEngine(db)
    d = e.create(1, document_type="contract", reference="CON-1", title="Contract")
    with pytest.raises(DocumentError):
        e.finalize(1, d.id)


def test_tenant_isolation_for_documents(db):
    e = DocumentEngine(db)
    d = e.create(1, document_type="invoice", reference="T1-1", title="T1")
    with pytest.raises(DocumentError):
        e.finalize(2, d.id)
    assert db.query(BusinessDocument).filter_by(tenant_id=1).count() == 1


def test_document_reference_unique_per_tenant(db):
    e = DocumentEngine(db)
    e.create(1, document_type="invoice", reference="SAME", title="A")
    with pytest.raises(DocumentError):
        e.create(1, document_type="invoice", reference="SAME", title="B")
    d = e.create(2, document_type="invoice", reference="SAME", title="Other")
    assert d.tenant_id == 2


def test_links_are_idempotent_and_tenant_scoped(db):
    e = DocumentEngine(db)
    d = e.create(1, document_type="delivery_note", reference="DN-1", title="DN")
    a = e.link(1, d.id, aggregate_type="shipment", aggregate_id="S1", relation="evidence")
    b = e.link(1, d.id, aggregate_type="shipment", aggregate_id="S1", relation="evidence")
    assert a.id == b.id
    with pytest.raises(DocumentError):
        e.link(2, d.id, aggregate_type="shipment", aggregate_id="S1")
    assert db.query(DocumentLink).count() == 1
