import pytest
from fastapi import HTTPException

from app.api.routes.developer_platform import validate_capability_configuration


def test_capability_configuration_accepts_declared_shape():
    schema = {
        "type": "object",
        "properties": {
            "modes": {"type": "array", "items": {"type": "string"}},
            "offline": {"type": "boolean"},
        },
        "required": ["modes"],
        "additionalProperties": False,
    }
    validate_capability_configuration(schema, {"modes": ["pickup"], "offline": True})


def test_capability_configuration_rejects_unknown_keys_and_wrong_types():
    schema = {
        "type": "object",
        "properties": {"mode": {"type": "string", "enum": ["pickup", "delivery"]}},
        "required": ["mode"],
        "additionalProperties": False,
    }
    with pytest.raises(HTTPException, match="unknown_configuration"):
        validate_capability_configuration(schema, {"mode": "pickup", "secret": True})
    with pytest.raises(HTTPException, match="invalid configuration type"):
        validate_capability_configuration(schema, {"mode": 1})
    with pytest.raises(HTTPException, match="invalid configuration value"):
        validate_capability_configuration(schema, {"mode": "other"})


def test_empty_capability_configuration_schema_remains_open():
    validate_capability_configuration({}, {"future": "compatible"})
