from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.core.observability import metrics


def test_metrics_exposes_runtime_and_readiness_series():
    metrics.set_readiness(True)
    client = TestClient(app)
    response = client.get('/metrics')
    assert response.status_code == 200
    body = response.text
    assert 'hussam_process_start_time_seconds' in body
    assert 'hussam_readiness_ok 1' in body
    assert 'hussam_http_requests_total' in body


def test_g08_alert_rules_cover_availability_readiness_and_5xx():
    rules = Path('config/observability/prometheus-alerts.yml').read_text()
    for token in ('HussamApiDown', 'HussamReadinessFailed', 'HussamHigh5xxRate'):
        assert token in rules
    assert 'rate(hussam_http_requests_failed_total[5m])' in rules


def test_observability_probe_is_secret_free_and_captures_three_probes():
    script = Path('scripts/production_observability_probe.sh').read_text()
    assert 'health' in script and 'ready?deep=true' in script and 'metrics' in script
    assert 'curl' in script
    assert 'Authorization' not in script
    assert 'Cookie' not in script


def test_g08_closure_declares_external_evidence_pending():
    doc = Path('docs/G08_BACKUP_DR_OBSERVABILITY_ENGINEERING_CLOSURE.md').read_text()
    assert 'ENGINEERING_READY' in doc
    assert 'PENDING_EXTERNAL' in doc
    assert 'RPO/RTO' in doc
