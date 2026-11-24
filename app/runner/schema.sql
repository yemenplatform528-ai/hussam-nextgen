-- Hussam Runner V1 prototype. Apply ONLY to a disposable PostgreSQL DB after review.
-- Never apply to existing Staging, Production, or YIB resources.
CREATE SCHEMA IF NOT EXISTS hussam_runner_v1;

CREATE TABLE IF NOT EXISTS hussam_runner_v1.tasks (
 id uuid PRIMARY KEY, tenant_id bigint NOT NULL, task_type varchar(120) NOT NULL,
 handler_version varchar(40) NOT NULL DEFAULT '1', payload jsonb NOT NULL,
 idempotency_key varchar(255) NOT NULL,
 state varchar(20) NOT NULL DEFAULT 'pending'
  CHECK (state IN ('pending','running','retry_wait','succeeded','failed','dead_letter','cancelled')),
 priority integer NOT NULL DEFAULT 0, run_after timestamptz NOT NULL DEFAULT now(),
 max_attempts integer NOT NULL DEFAULT 5 CHECK (max_attempts > 0),
 attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
 lease_owner varchar(160), lease_expires_at timestamptz,
 fencing_token bigint NOT NULL DEFAULT 0 CHECK (fencing_token >= 0),
 safe_error_code varchar(100), safe_error_summary varchar(1200),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 started_at timestamptz, completed_at timestamptz,
 UNIQUE (tenant_id,idempotency_key)
);
CREATE INDEX IF NOT EXISTS ix_runner_v1_claim
 ON hussam_runner_v1.tasks (tenant_id,state,run_after,priority DESC,created_at);

CREATE TABLE IF NOT EXISTS hussam_runner_v1.attempts (
 id bigserial PRIMARY KEY, task_id uuid NOT NULL REFERENCES hussam_runner_v1.tasks(id),
 tenant_id bigint NOT NULL, attempt_no integer NOT NULL, worker_id varchar(160) NOT NULL,
 fencing_token bigint NOT NULL, started_at timestamptz NOT NULL DEFAULT now(),
 finished_at timestamptz, outcome varchar(20)
  CHECK (outcome IN ('succeeded','retry','failed','lease_lost')),
 safe_error_code varchar(100), UNIQUE (task_id,attempt_no)
);
CREATE TABLE IF NOT EXISTS hussam_runner_v1.checkpoints (
 id bigserial PRIMARY KEY, task_id uuid NOT NULL REFERENCES hussam_runner_v1.tasks(id),
 tenant_id bigint NOT NULL, sequence_no integer NOT NULL CHECK (sequence_no > 0),
 handler_version varchar(40) NOT NULL, payload jsonb NOT NULL, sha256 char(64) NOT NULL,
 fencing_token bigint NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (task_id,sequence_no)
);
CREATE TABLE IF NOT EXISTS hussam_runner_v1.audit_events (
 id bigserial PRIMARY KEY, task_id uuid, tenant_id bigint NOT NULL,
 event_type varchar(100) NOT NULL, worker_id varchar(160), fencing_token bigint,
 safe_metadata jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_runner_v1_audit_tenant_task
 ON hussam_runner_v1.audit_events (tenant_id,task_id,id);
CREATE TABLE IF NOT EXISTS hussam_runner_v1.workers (
 worker_id varchar(160) PRIMARY KEY, process_instance_id uuid NOT NULL,
 build_version varchar(80) NOT NULL, last_seen_at timestamptz NOT NULL DEFAULT now(),
 safe_metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE IF NOT EXISTS hussam_runner_v1.schedules (
 id uuid PRIMARY KEY, tenant_id bigint NOT NULL, task_type varchar(120) NOT NULL,
 handler_version varchar(40) NOT NULL DEFAULT '1', payload jsonb NOT NULL,
 cron_expression varchar(120) NOT NULL, timezone varchar(80) NOT NULL,
 enabled boolean NOT NULL DEFAULT true, next_run_at timestamptz NOT NULL,
 misfire_policy varchar(20) NOT NULL DEFAULT 'skip'
  CHECK (misfire_policy IN ('skip','run_once','catch_up')),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS hussam_runner_v1.schedule_occurrences (
 id bigserial PRIMARY KEY, schedule_id uuid NOT NULL REFERENCES hussam_runner_v1.schedules(id),
 tenant_id bigint NOT NULL, scheduled_for timestamptz NOT NULL, task_id uuid,
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE (schedule_id,scheduled_for)
);

-- Force tenant scope at the database boundary. Set app.tenant_id transaction-locally.
DO $$
DECLARE tab text;
BEGIN
 FOREACH tab IN ARRAY ARRAY['tasks','attempts','checkpoints','audit_events','schedules','schedule_occurrences']
 LOOP
  EXECUTE format('ALTER TABLE hussam_runner_v1.%I ENABLE ROW LEVEL SECURITY',tab);
  EXECUTE format('ALTER TABLE hussam_runner_v1.%I FORCE ROW LEVEL SECURITY',tab);
  IF NOT EXISTS (
   SELECT 1 FROM pg_policies
   WHERE schemaname='hussam_runner_v1' AND tablename=tab AND policyname='tenant_scope'
  ) THEN
   EXECUTE format(
    'CREATE POLICY tenant_scope ON hussam_runner_v1.%I USING (tenant_id = NULLIF(current_setting(''app.tenant_id'',true),'''')::bigint) WITH CHECK (tenant_id = NULLIF(current_setting(''app.tenant_id'',true),'''')::bigint)',
    tab
   );
  END IF;
 END LOOP;
END $$;

-- Before integration: grant only required table/function privileges to a dedicated role.
-- The application must set app.tenant_id from authenticated server-side context, never user input.
-- This prototype intentionally does not create roles, grant privileges, or touch existing databases.
