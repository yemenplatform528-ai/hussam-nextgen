from datetime import datetime, timezone
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.models.core import Tenant
from app.core.models.developer_platform import DeveloperExtension, DeveloperExtensionVersion
from app.core.persistence import Base
from app.api.routes.developer_platform import validate_extension_dependency_contract

def test_extension_dependency_contract_resolves_only_active_same_tenant_version():
    e=create_engine("sqlite+pysqlite:///:memory:",future=True)
    Base.metadata.create_all(e); db=sessionmaker(e,expire_on_commit=False)()
    db.add(Tenant(id=20,name="Dev",status="active"))
    ext=DeveloperExtension(id="consumer",tenant_id=20,code="consumer",name="Consumer",extension_type="module",capabilities=[],permissions=[],market_scope=[],created_by="u1")
    dep=DeveloperExtension(id="base",tenant_id=20,code="base",name="Base",extension_type="module",capabilities=[],permissions=[],market_scope=[],created_by="u1")
    db.add_all([ext,dep]); db.flush()
    db.add(DeveloperExtensionVersion(id="base-v",extension_id=dep.id,version="1.2.3",manifest={},source_hash="b"*64,compatibility={},test_status="passed",test_evidence_hash="e"*64,test_source_hash="b"*64,test_run_id="run-base",tested_at=datetime.now(timezone.utc),release_status="active",created_by="u1")); db.commit()
    validate_extension_dependency_contract(db,ext,{"dependencies":[{"extension":"base","version":"1.2.3"}]},{"api":"1.0"},resolve_active=True)
    with pytest.raises(HTTPException,match="active dependency"):
        validate_extension_dependency_contract(db,ext,{"dependencies":[{"extension":"missing","version":"1.0.0"}]},{"api":"1.0"},resolve_active=True)
    with pytest.raises(HTTPException,match="cannot depend on itself"):
        validate_extension_dependency_contract(db,ext,{"dependencies":[{"extension":"consumer"}]},{},resolve_active=False)
