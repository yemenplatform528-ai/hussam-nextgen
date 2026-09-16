import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['HUSSAM_RELEASE_PROFILE']='full-development'
from app.api.main import app, RELEASE_PROFILE

paths={r.path for r in app.routes}
required={
    '/health',
    '/api/v1/platform/manifest',
    '/api/v1/platform/release',
}
for p in required:
    assert p in paths, f'missing required path: {p}'
assert RELEASE_PROFILE == 'full-development'
# The unified platform exposes all capability domains from one coherent boundary.
for required_prefix in ('/api/v1/marketplace','/api/v1/retail','/api/v1/ai','/api/v1/purchasing','/api/v1/documents','/api/v1/workflows','/api/v1/finance','/api/v1/inventory','/api/v1/payments','/api/v1/logistics'):
    assert any(p.startswith(required_prefix) for p in paths), f'missing unified surface: {required_prefix}'
assert any(p.startswith('/api/v1/marketplace') for p in paths)
print('Unified Platform 1.0 release-surface audit: PASS')
print(f'public routes: {len(paths)}')
