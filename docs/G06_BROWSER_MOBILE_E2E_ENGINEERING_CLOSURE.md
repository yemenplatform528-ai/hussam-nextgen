# G06 — Browser / Mobile E2E Engineering Closure

## Status

- Engineering status: `ENGINEERING_READY`
- Production certification status: `PENDING_EXTERNAL`
- Gate: `G06`

## Scope

G06 verifies the customer-facing console and seller workspace as a browser contract at desktop and mobile viewport sizes. The engineering run exercises the real bundled `app/ui/index.html`, `app/ui/styles.css`, and `app/ui/app.js` in Chromium.

The engineering harness uses deterministic in-browser API stubs. This proves browser rendering, navigation, responsive layout, session/account surface behavior, and seller workspace navigation without fabricating a production E2E result.

## Engineering checks

1. Desktop Chromium viewport loads the marketplace home.
2. Public catalog content renders.
3. Account surface exposes the official OIDC login route and HttpOnly-session statement.
4. Legacy engineering session-token entry remains available as a controlled engineering path.
5. Seller Center navigation renders after session verification.
6. Seller product workspace navigation is reachable.
7. The same customer/account/workspace journey is exercised at a 390x844 mobile viewport.

## Commands / results

- `python scripts/browser_e2e.py` → `BROWSER_E2E_OK desktop+mobile`
- `pytest -q` → `191 passed`
- `python -m compileall -q app alembic tests scripts` → passed
- Fresh SQLite `alembic upgrade head` → passed
- `alembic check` → no new upgrade operations
- `python scripts/baseline_audit.py` → 0 failures / 0 warnings

## Production evidence still required

G06 cannot be closed from these engineering checks alone. Production certification requires an external artifact from the real deployed environment covering at least:

- real browser login/session flow;
- real customer journey through the deployed public console;
- real seller workspace authorization;
- desktop and supported mobile/browser matrix;
- checkout and order journey against the deployed APIs;
- screenshots/video or equivalent trace artifact;
- test environment, build/release identifier, timestamps, and reviewer decision;
- SHA-256 of the evidence artifact;
- validation through the production Evidence Protocol.

No production evidence is generated or implied by the engineering harness.
