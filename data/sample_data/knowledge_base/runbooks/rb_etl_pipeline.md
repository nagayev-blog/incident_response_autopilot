# Runbook: ETL Pipeline Failure

**ID:** RB-DATA-001  
**Severity:** HIGH  
**Service:** data-sync-service (ETL: operational DB → analytics DWH)  
**Last updated:** 2026-02-28  
**Owner:** data-engineering-team

---

## Symptoms

- Alert: `ETLPipelineFailure` firing
- `etl_last_success_timestamp` older than 2x schedule interval
- `etl_job_duration_seconds` exceeds SLA threshold (1800s)
- Grafana analytics dashboards showing stale data
- Morning reports at risk if incident detected after 06:00

---

## Immediate actions (first 10 minutes)

### Step 1 — Check current job status and logs

```bash
# Find running job pod
kubectl get pods -n data-platform | grep sync

# Check logs for the stuck job
kubectl logs -n data-platform \
  $(kubectl get pods -n data-platform -o name | grep sync | head -1) \
  --tail=200

# Look for:
# - "deadlock detected"
# - "lock wait timeout"
# - "could not obtain lock"
# - "connection refused" (source DB down)
```

### Step 2 — Check for blocking locks on source DB

```bash
kubectl exec -n data-platform deploy/data-sync-service -- \
  psql $SOURCE_DB_URL -c "
    SELECT
      blocked.pid AS blocked_pid,
      blocked.query AS blocked_query,
      blocking.pid AS blocking_pid,
      blocking.query AS blocking_query,
      blocking.application_name
    FROM pg_stat_activity blocked
    JOIN pg_stat_activity blocking
      ON blocking.pid = ANY(pg_blocking_pids(blocked.pid))
    WHERE cardinality(pg_blocking_pids(blocked.pid)) > 0;"

# If result is empty: no locks, check for other root causes (connection, disk)
# If result shows: ETL blocked by batch job → proceed to Step 3
```

### Step 3 — Identify the blocking process

```bash
kubectl exec -n data-platform deploy/data-sync-service -- \
  psql $SOURCE_DB_URL -c "
    SELECT pid, application_name, query_start,
           now() - query_start AS duration, state, query
    FROM pg_stat_activity
    WHERE state != 'idle'
    ORDER BY query_start ASC;"

# Common blockers:
# - monthly risk-score-batch (application_name: risk-score-calculator)
# - ad-hoc analytics queries from data analysts
# - other ETL jobs (reporting-sync, audit-export)
```

### Step 4a — If blocked by expected batch job: wait with monitoring

```bash
# Check when batch job started and estimate completion
kubectl logs -n data-platform \
  $(kubectl get pods -n data-platform | grep risk-score | awk '{print $1}') \
  | grep -E "progress|complete|percent" | tail -20

# ETL job will auto-retry on restart — just monitor
# If batch job will take > 2h more: escalate to data team lead
```

### Step 4b — If blocked by runaway/stuck query: kill and restart ETL

```bash
# Kill the stuck ETL process (not the blocker)
kubectl exec -n data-platform deploy/data-sync-service -- \
  psql $SOURCE_DB_URL -c \
  "SELECT pg_terminate_backend(<blocked_pid>);"

# Delete the failed job
kubectl delete job -n data-platform \
  $(kubectl get jobs -n data-platform | grep sync | awk '{print $1}')

# Manually trigger a new run
kubectl create job --from=cronjob/operational-to-analytics-sync \
  manual-retry-$(date +%s) -n data-platform

# Monitor new job
kubectl logs -n data-platform -f \
  $(kubectl get pods -n data-platform | grep manual-retry | awk '{print $1}')
```

### Step 4c — If source DB is down or unreachable

```bash
# Test connectivity
kubectl exec -n data-platform deploy/data-sync-service -- \
  psql $SOURCE_DB_URL -c "SELECT 1;"

# If down: escalate to DBA on-call, ETL will resume automatically when DB recovers
```

---

## Fix: prevent deadlocks between concurrent batch jobs

Option 1 — Reschedule ETL to avoid overlap:
```yaml
# In CronJob spec: change ETL schedule to after batch window
# risk-score-batch: runs 01:00, takes 3-4h
# ETL schedule: change from "30 1 * * *" to "0 6 * * *"
spec:
  schedule: "0 6 * * *"  # 06:00 — safe after any batch
```

Option 2 — Add deadlock retry in ETL code:
```python
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

class DeadlockDetected(Exception):
    pass

@retry(
    wait=wait_exponential(multiplier=10, min=10, max=120),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(DeadlockDetected)
)
def sync_batch(batch_query: str):
    try:
        execute_batch(batch_query)
    except Exception as e:
        if "deadlock" in str(e).lower():
            raise DeadlockDetected(str(e))
        raise
```

Option 3 — Use advisory locks to coordinate:
```python
# ETL acquires advisory lock before starting
# Batch job checks for lock before acquiring table locks
conn.execute("SELECT pg_advisory_lock(12345)")  # ETL lock key
try:
    run_etl()
finally:
    conn.execute("SELECT pg_advisory_unlock(12345)")
```

---

## Recovery verification

```bash
# Check job completed successfully
kubectl get jobs -n data-platform | grep sync

# Check data freshness
kubectl exec -n data-platform deploy/data-sync-service -- \
  psql $ANALYTICS_DB_URL -c \
  "SELECT max(updated_at) as latest_record FROM fact_transactions;"

# Alert should resolve within 5 min of successful completion
# Check Grafana: "Data Platform" dashboard → "ETL Last Success"
```

---

## Escalation

- Analytics data stale > 8h before 09:00 → notify Head of Analytics
- ETL cannot run due to persistent blocking → DBA on-call
- Source DB unreachable → DBA on-call immediately

## Related

- Postmortem: PM-2025-0915 (deadlock with risk-score-batch)
- Playbook: PB-DATABASE-001
