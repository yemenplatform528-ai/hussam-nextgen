-- Hussam Runner V1 prototype.
-- Apply ONLY to a disposable PostgreSQL database after review.
-- Never apply to existing Staging, Production, or YIB resources.
CREATE SCHEMA IF NOT EXISTS hussam_runner_v1;

CREATE TABLE IF NOT EXISTS hussam_runner_v1.tasks (
    id uuid PRIMARY KEY,
    tenant_id bigint NOT NULL,
    task_type varchar(120) NOT NULL,
    handler_version varchar(40) NOT NULL DEFAULT '1',
    payload jsonb NOT NULL,
    idempotency_key varchar(255) NOT NULL,
    state varchar(20) NOT NULL DEFAULT 'pending'
        CHECK (state IN ('pending','running','retry_wait','succeeded','failed','dead_letter','cancelled')),
    priority integer NOT NULL DEFAULT 0,
    run_after timestamptz NOT NULL DEFAULT now(),
    max_attempts integer NOT NULL DEFAULT 5 CHECK (max_attempts > 0),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    lease_owner varchar(160),
    lease_expires_at timestamptz,
    fencing_token bigint NOT NULL DEFAULT 0 CHECK (fencing_token >= 0),
    safe_error_code varchar(100),
    safe_error_summary varchar(1200),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    completed_at timestamptz,
    UNIQUE (tenant_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS ix_runner_v1_claim
    ON hussam_runner_v1.tasks (tenant_id, state, run_after, priority DESC, created_at);

CREATE TABLE IF NOT EXISTS hussam_runner_v1.attempts (
    id bigserial PRIMARY KEY,
    task_id uuid NOT NULL REFERENCES hussam_runner_v1.tasks(id),
    tenant_id bigint NOT NULL,
    attempt_no integer NOT NULL,
    worker_id varchar(160) NOT NULL,
    fencing_token bigint NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    outcome varchar(20) CHECK (outcome IN ('succeeded','retry','failed','lease_lost')),
    safe_error_code varchar(100),
    UNIQUE (task_id, attempt_no)
);

CREATE TABLE IF NOT EXISTS hussam_runner_v1.checkpoints (
    id bigserial PRIMARY KEY,
    task_id uuid NOT NULL REFERENCES hussam_runner_v1.tasks(id),
    tenant_id bigint NOT NULL,
    sequence_no integer NOT NULL CHECK (sequence_no > 0),
    handler_version varchar(40) NOT NULL,
    payload jsonb NOT NULL,
    sha256 char(64) NOT NULL,
    fencing_token bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (task_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS hussam_runner_v1.audit_events (
    id bigserial PRIMARY KEY,
    task_id uuid,
    tenant_id bigint NOT NULL,
    event_type varchar(100) NOT NULL,
    worker_id varchar(160),
    fencing_token bigint,
    safe_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_runner_v1_audit_tenant_task
    ON hussam_runner_v1.audit_events (tenant_id, task_id, id);

CREATE TABLE IF NOT EXISTS hussam_runner_v1.workers (
    worker_id varchar(160) PRIMARY KEY,
    process_instance_id uuid NOT NULL,
    build_version varchar(80) NOT NULL,
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    safe_metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

-- Deliberately not wired to the app's tenant auth yet. Before integration,
-- add and test RLS policies using the platform's authenticated tenant context.
-- The repository must always include tenant_id in every task predicate.
