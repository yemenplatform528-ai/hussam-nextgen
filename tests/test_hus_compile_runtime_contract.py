from app.hus.compiler import compile_spec

def test_compile_spec_emits_runtime_execution_plan():
    spec = {
        "spec_version": "1.0",
        "organization": {"code": "acme", "name": "Acme"},
        "domains": [
            {"code": "commerce", "name": "Commerce", "engine": "commerce", "capabilities": ["sales.read"]}
        ],
        "workflows": [
            {
                "code": "w.read",
                "name": "Read",
                "trigger": "manual",
                "steps": [{"code": "s1", "action": "commerce.sales.read", "requires_approval": False}],
            }
        ],
        "policies": {},
        "metadata": {},
    }

    result = compile_spec(spec)
    plan = result["contract"]["execution_plan"]
    step = plan["workflows"][0]["steps"][0]

    assert step == {
        "id": "w.read.s1",
        "action": {"engine": "commerce", "capability": "sales.read"},
        "risk": "read",
        "idempotency_required": False,
    }
