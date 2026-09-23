from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from app.api.dependencies import get_context, get_session
from app.core.models.yemen_capability import MarketCapabilityActivation, PlatformCapability
from app.core.models.market import MarketContext
from app.core.services.capabilities import CapabilityService
from app.core.models.developer_platform import (
    DeveloperExtension,
    DeveloperExtensionVersion,
    DeveloperExtensionAudit,
)

router = APIRouter(prefix="/developer", tags=["developer-platform"])

ALLOWED_EXTENSION_TYPES = {"config", "module", "adapter", "platform"}
ALLOWED_TEST_STATUS = {"pending", "passed", "failed"}
ALLOWED_RELEASE_STATUS = {"draft", "sandbox", "published", "active", "suspended", "rolled_back"}
ALLOWED_MANIFEST_KEYS = {
    "capabilities",
    "permissions",
    "market_scope",
    "dependencies",
    "ui",
    "workflows",
    "tools",
    "events",
    "jobs",
    "adapters",
    "hus_source",
    "tests",
    "configuration",
}

def developer_guard(ctx):
    if ctx.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="developer platform requires owner or admin role")

def validate_manifest(extension: DeveloperExtension, manifest: dict, registered_codes: set[str] | None = None):
    unknown = sorted(set(manifest) - ALLOWED_MANIFEST_KEYS)
    if unknown:
        raise HTTPException(status_code=400, detail={"unknown_manifest_keys": unknown})

    capabilities = manifest.get("capabilities", extension.capabilities)
    permissions = manifest.get("permissions", extension.permissions)
    market_scope = manifest.get("market_scope", extension.market_scope)

    if not isinstance(capabilities, list) or not all(isinstance(x, str) for x in capabilities):
        raise HTTPException(status_code=400, detail="manifest capabilities must be a string list")
    if not isinstance(permissions, list) or not all(isinstance(x, str) for x in permissions):
        raise HTTPException(status_code=400, detail="manifest permissions must be a string list")
    if not isinstance(market_scope, list) or not all(isinstance(x, str) for x in market_scope):
        raise HTTPException(status_code=400, detail="manifest market_scope must be a string list")

    if not set(capabilities).issubset(set(extension.capabilities)):
        raise HTTPException(status_code=400, detail="manifest capability exceeds extension declaration")
    if not set(permissions).issubset(set(extension.permissions)):
        raise HTTPException(status_code=400, detail="manifest permission exceeds extension declaration")
    if extension.market_scope and not set(market_scope).issubset(set(extension.market_scope)):
        raise HTTPException(status_code=400, detail="manifest market scope exceeds extension declaration")

    if registered_codes is not None:
        declared_yemen = {x for x in capabilities if x.startswith("yem_")}
        unknown_yemen = sorted(declared_yemen - registered_codes)
        if unknown_yemen:
            raise HTTPException(status_code=400, detail={"unregistered_yemen_capabilities": unknown_yemen})

    hus_source = manifest.get("hus_source")
    if hus_source is not None and not isinstance(hus_source, str):
        raise HTTPException(status_code=400, detail="hus_source must be text when provided")

class ExtensionIn(BaseModel):
    code: str = Field(min_length=2, max_length=120, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    extension_type: str = "module"
    market_scope: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)

class CapabilityActivationIn(BaseModel):
    configuration: dict = Field(default_factory=dict)

class VersionIn(BaseModel):
    version: str = Field(min_length=1, max_length=40)
    manifest: dict = Field(default_factory=dict)
    source_hash: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
    compatibility: dict = Field(default_factory=dict)
    test_status: str = "pending"
    rollback_version: str | None = None

@router.get("/capabilities")
def list_capabilities(ctx=Depends(get_context), db=Depends(get_session)):
    developer_guard(ctx)
    rows = CapabilityService(db).list_active()
    return {"items": [{"code": x.code, "category": x.category, "name": x.name, "description": x.description, "market_scope": x.market_scope, "config_schema": x.config_schema} for x in rows]}

@router.get("/market-capabilities/{market_code}")
def list_market_capabilities(market_code: str, ctx=Depends(get_context), db=Depends(get_session)):
    developer_guard(ctx)
    market = db.scalar(select(MarketContext).where(MarketContext.code == market_code.upper()))
    if not market:
        raise HTTPException(status_code=404, detail="market not found")
    rows = db.execute(
        select(MarketCapabilityActivation, PlatformCapability)
        .join(PlatformCapability, PlatformCapability.id == MarketCapabilityActivation.capability_id)
        .where(MarketCapabilityActivation.market_id == market.id)
        .order_by(PlatformCapability.category, PlatformCapability.code)
    ).all()
    return {"market": market.code, "items": [
        {"code": capability.code, "category": capability.category, "name": capability.name,
         "status": activation.status, "configuration": activation.configuration,
         "market_scope": capability.market_scope}
        for activation, capability in rows
    ]}

@router.post("/market-capabilities/{market_code}/{capability_code}/activate", status_code=201)
def activate_market_capability(market_code: str, capability_code: str, body: CapabilityActivationIn, ctx=Depends(get_context), db=Depends(get_session)):
    developer_guard(ctx)
    market = db.scalar(select(MarketContext).where(MarketContext.code == market_code.upper()))
    if not market:
        raise HTTPException(status_code=404, detail="market not found")
    if market.status != "active":
        raise HTTPException(status_code=409, detail="market must be active before capability activation")
    service = CapabilityService(db)
    capability = service.get_active(capability_code)
    if not capability:
        raise HTTPException(status_code=404, detail="active capability not found")
    try:
        service.validate_market_scope(market, capability)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    activation = service.db.scalar(select(MarketCapabilityActivation).where(
        MarketCapabilityActivation.market_id == market.id,
        MarketCapabilityActivation.capability_id == capability.id,
    ))
    if activation:
        activation.status = "active"
        activation.configuration = body.configuration
        activation.activated_by = ctx.user_id
    else:
        activation = MarketCapabilityActivation(
            id=uuid4().hex,
            market_id=market.id,
            capability_id=capability.id,
            status="active",
            configuration=body.configuration,
            activated_by=ctx.user_id,
        )
        db.add(activation)
    db.commit()
    return {"market": market.code, "capability": capability.code, "status": activation.status, "configuration": activation.configuration}

@router.post("/market-capabilities/{market_code}/{capability_code}/suspend")
def suspend_market_capability(market_code: str, capability_code: str, ctx=Depends(get_context), db=Depends(get_session)):
    developer_guard(ctx)
    activation = db.scalar(
        select(MarketCapabilityActivation).join(PlatformCapability, PlatformCapability.id == MarketCapabilityActivation.capability_id).join(MarketContext, MarketContext.id == MarketCapabilityActivation.market_id).where(
            MarketContext.code == market_code.upper(), PlatformCapability.code == capability_code
        )
    )
    if not activation:
        raise HTTPException(status_code=404, detail="market capability activation not found")
    activation.status = "suspended"
    db.commit()
    return {"market": market_code.upper(), "capability": capability_code, "status": activation.status}

@router.get("/extensions")
def list_extensions(ctx=Depends(get_context), db=Depends(get_session)):
    developer_guard(ctx)
    rows = db.scalars(
        select(DeveloperExtension)
        .where(DeveloperExtension.tenant_id == ctx.tenant_id)
        .order_by(DeveloperExtension.code)
    ).all()
    return {
        "items": [
            {
                "id": x.id,
                "code": x.code,
                "name": x.name,
                "type": x.extension_type,
                "status": x.status,
                "market_scope": x.market_scope,
                "capabilities": x.capabilities,
            }
            for x in rows
        ]
    }

@router.post("/extensions", status_code=201)
def create_extension(body: ExtensionIn, ctx=Depends(get_context), db=Depends(get_session)):
    developer_guard(ctx)
    if body.extension_type not in ALLOWED_EXTENSION_TYPES:
        raise HTTPException(status_code=400, detail="invalid extension_type")
    if db.scalar(
        select(DeveloperExtension).where(
            DeveloperExtension.tenant_id == ctx.tenant_id,
            DeveloperExtension.code == body.code,
        )
    ):
        raise HTTPException(status_code=409, detail="extension code already exists")

    x = DeveloperExtension(
        id=uuid4().hex,
        tenant_id=ctx.tenant_id,
        code=body.code,
        name=body.name,
        description=body.description,
        extension_type=body.extension_type,
        market_scope=body.market_scope,
        capabilities=body.capabilities,
        permissions=body.permissions,
        created_by=ctx.user_id,
    )
    db.add(x)
    db.flush()
    db.add(DeveloperExtensionAudit(
        extension_id=x.id,
        actor_id=ctx.user_id,
        action="created",
        details={"code": x.code},
    ))
    db.commit()
    return {"id": x.id, "code": x.code, "status": x.status}

@router.post("/extensions/{extension_id}/versions", status_code=201)
def create_version(extension_id: str, body: VersionIn, ctx=Depends(get_context), db=Depends(get_session)):
    developer_guard(ctx)
    x = db.scalar(
        select(DeveloperExtension).where(
            DeveloperExtension.id == extension_id,
            DeveloperExtension.tenant_id == ctx.tenant_id,
        )
    )
    if not x:
        raise HTTPException(status_code=404, detail="extension not found")
    if body.test_status not in ALLOWED_TEST_STATUS:
        raise HTTPException(status_code=400, detail="invalid test_status")
    registered = set(db.scalars(select(PlatformCapability.code).where(PlatformCapability.status == "active")).all())
    validate_manifest(x, body.manifest, registered_codes=registered)

    existing = db.scalar(
        select(DeveloperExtensionVersion).where(
            DeveloperExtensionVersion.extension_id == x.id,
            DeveloperExtensionVersion.version == body.version,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="extension version already exists")

    v = DeveloperExtensionVersion(
        id=uuid4().hex,
        extension_id=x.id,
        version=body.version,
        manifest=body.manifest,
        source_hash=body.source_hash.lower(),
        compatibility=body.compatibility,
        test_status=body.test_status,
        rollback_version=body.rollback_version,
        created_by=ctx.user_id,
    )
    db.add(v)
    x.status = "testing"
    db.add(DeveloperExtensionAudit(
        extension_id=x.id,
        actor_id=ctx.user_id,
        action="version_created",
        version=body.version,
        details={"source_hash": v.source_hash, "test_status": v.test_status},
    ))
    db.commit()
    return {
        "id": v.id,
        "extension_id": x.id,
        "version": v.version,
        "status": v.release_status,
        "source_hash": v.source_hash,
    }

@router.post("/extensions/{extension_id}/versions/{version}/publish")
def publish_version(extension_id: str, version: str, ctx=Depends(get_context), db=Depends(get_session)):
    developer_guard(ctx)
    x, v = _get_version(db, ctx.tenant_id, extension_id, version)
    if not v:
        raise HTTPException(status_code=404, detail="extension version not found")
    if v.test_status != "passed":
        raise HTTPException(status_code=409, detail="version must pass tests before publish")
    if v.release_status not in {"draft", "sandbox"}:
        raise HTTPException(status_code=409, detail="version is not publishable from its current state")

    v.release_status = "published"
    x.status = "published"
    db.add(DeveloperExtensionAudit(
        extension_id=x.id,
        actor_id=ctx.user_id,
        action="published",
        version=version,
    ))
    db.commit()
    return {"id": x.id, "version": version, "status": v.release_status}

@router.post("/extensions/{extension_id}/versions/{version}/activate")
def activate_version(extension_id: str, version: str, ctx=Depends(get_context), db=Depends(get_session)):
    developer_guard(ctx)
    x, v = _get_version(db, ctx.tenant_id, extension_id, version)
    if not v:
        raise HTTPException(status_code=404, detail="extension version not found")
    if v.release_status != "published":
        raise HTTPException(status_code=409, detail="version must be published before activation")

    active = db.scalars(
        select(DeveloperExtensionVersion).where(
            DeveloperExtensionVersion.extension_id == x.id,
            DeveloperExtensionVersion.release_status == "active",
        )
    ).all()
    for current in active:
        current.release_status = "suspended"
        current.rollback_version = version
        db.add(DeveloperExtensionAudit(
            extension_id=x.id,
            actor_id=ctx.user_id,
            action="suspended",
            version=current.version,
            details={"replacement": version},
        ))

    v.release_status = "active"
    x.status = "active"
    db.add(DeveloperExtensionAudit(
        extension_id=x.id,
        actor_id=ctx.user_id,
        action="activated",
        version=version,
        details={"replaced_versions": [current.version for current in active]},
    ))
    db.commit()
    return {"id": x.id, "version": version, "status": v.release_status}

@router.post("/extensions/{extension_id}/versions/{version}/suspend")
def suspend_version(extension_id: str, version: str, ctx=Depends(get_context), db=Depends(get_session)):
    developer_guard(ctx)
    x, v = _get_version(db, ctx.tenant_id, extension_id, version)
    if not v:
        raise HTTPException(status_code=404, detail="extension version not found")
    if v.release_status != "active":
        raise HTTPException(status_code=409, detail="only an active version can be suspended")
    v.release_status = "suspended"
    x.status = "suspended"
    db.add(DeveloperExtensionAudit(
        extension_id=x.id,
        actor_id=ctx.user_id,
        action="suspended",
        version=version,
    ))
    db.commit()
    return {"id": x.id, "version": version, "status": v.release_status}

@router.post("/extensions/{extension_id}/rollback")
def rollback_extension(extension_id: str, ctx=Depends(get_context), db=Depends(get_session)):
    developer_guard(ctx)
    x = db.scalar(
        select(DeveloperExtension).where(
            DeveloperExtension.id == extension_id,
            DeveloperExtension.tenant_id == ctx.tenant_id,
        )
    )
    if not x:
        raise HTTPException(status_code=404, detail="extension not found")

    active = db.scalars(
        select(DeveloperExtensionVersion).where(
            DeveloperExtensionVersion.extension_id == x.id,
            DeveloperExtensionVersion.release_status == "active",
        )
    ).all()
    target_version = next((v.rollback_version for v in active if v.rollback_version), None)
    if not target_version:
        target_version = db.scalar(
            select(DeveloperExtensionVersion.rollback_version)
            .where(
                DeveloperExtensionVersion.extension_id == x.id,
                DeveloperExtensionVersion.rollback_version.is_not(None),
            )
            .order_by(DeveloperExtensionVersion.created_at.desc())
        )
    if not target_version:
        raise HTTPException(status_code=409, detail="no rollback target recorded")

    target = db.scalar(
        select(DeveloperExtensionVersion).where(
            DeveloperExtensionVersion.extension_id == x.id,
            DeveloperExtensionVersion.version == target_version,
            DeveloperExtensionVersion.test_status == "passed",
            DeveloperExtensionVersion.release_status.in_({"published", "suspended", "rolled_back"}),
        )
    )
    if not target:
        raise HTTPException(status_code=409, detail="rollback target is not releasable")

    for current in active:
        current.release_status = "rolled_back"
    target.release_status = "active"
    x.status = "active"
    db.add(DeveloperExtensionAudit(
        extension_id=x.id,
        actor_id=ctx.user_id,
        action="rolled_back",
        version=target.version,
        details={"previous_active": [v.version for v in active]},
    ))
    db.commit()
    return {"id": x.id, "version": target.version, "status": target.release_status}

@router.get("/extensions/{extension_id}/manifest")
def extension_manifest(extension_id: str, ctx=Depends(get_context), db=Depends(get_session)):
    developer_guard(ctx)
    x = db.scalar(
        select(DeveloperExtension).where(
            DeveloperExtension.id == extension_id,
            DeveloperExtension.tenant_id == ctx.tenant_id,
        )
    )
    if not x:
        raise HTTPException(status_code=404, detail="extension not found")
    versions = db.scalars(
        select(DeveloperExtensionVersion)
        .where(DeveloperExtensionVersion.extension_id == x.id)
        .order_by(DeveloperExtensionVersion.created_at.desc())
    ).all()
    return {
        "extension": {
            "id": x.id,
            "code": x.code,
            "name": x.name,
            "type": x.extension_type,
            "status": x.status,
            "market_scope": x.market_scope,
            "capabilities": x.capabilities,
            "permissions": x.permissions,
        },
        "versions": [
            {
                "version": v.version,
                "status": v.release_status,
                "test_status": v.test_status,
                "source_hash": v.source_hash,
                "compatibility": v.compatibility,
                "manifest": v.manifest,
            }
            for v in versions
        ],
    }

def _get_version(db, tenant_id: int, extension_id: str, version: str):
    x = db.scalar(
        select(DeveloperExtension).where(
            DeveloperExtension.id == extension_id,
            DeveloperExtension.tenant_id == tenant_id,
        )
    )
    if not x:
        raise HTTPException(status_code=404, detail="extension not found")
    v = db.scalar(
        select(DeveloperExtensionVersion).where(
            DeveloperExtensionVersion.extension_id == x.id,
            DeveloperExtensionVersion.version == version,
        )
    )
    return x, v
