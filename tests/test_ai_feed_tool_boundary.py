from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

from app.ai.tools import execute_mutation_tool
from app.core.models.core import Tenant
from app.core.models.platform_completion import MarketplaceFeedJob
from app.core.persistence import Base


def test_ai_feed_validation_is_tenant_bound_and_executes_real_validation():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    db = sessionmaker(engine, expire_on_commit=False)()

    db.add_all([
        Tenant(id=1, name="Tenant One", status="active"),
        Tenant(id=2, name="Tenant Two", status="active"),
    ])
    db.flush()
    feed = MarketplaceFeedJob(
        tenant_id=2,
        feed_type="catalog",
        payload_json={},
        status="queued",
        attempts=0,
    )
    db.add(feed)
    db.commit()
    db.refresh(feed)

    with pytest.raises(Exception, match="feed job not found"):
        execute_mutation_tool(
            db,
            1,
            "marketplace.feed.validate",
            {"feed_job_id": feed.id, "rows": [{"row_number": 2, "required_missing": ["sku"]}]},
        )

    result = execute_mutation_tool(
        db,
        2,
        "marketplace.feed.validate",
        {"feed_job_id": feed.id, "rows": [{"row_number": 2, "required_missing": ["sku", "price"]}]},
    )
    assert result["accepted"] is True
    assert result["issue_count"] == 2
    assert {item["field_name"] for item in result["issues"]} == {"sku", "price"}
