# Runbook: PostgreSQL Connection Pool Exhausted

**ID:** RB-DB-001  
**Severity:** CRITICAL  
**Service:** Any Spring Boot service with PostgreSQL  
**Last updated:** 2026-03-10  
**Owner:** platform-dba-team

---

## Symptoms

- Alert: `DBConnectionPoolExhausted` firing
- `pg_connections_active` equals `pg_connections_max`
- HTTP 503 / 504 errors on service endpoints
- Latency p99 > 10s and climbing
- JVM thread pool exhaustion may follow

---

## Immediate actions (first 5 minutes)

### Step 1 — Confirm pool exhaustion

```bash
# Check active connections in PostgreSQL
kubectl exec -n <namespace> deploy/<service> -- \
  psql $DATABASE_URL -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# Expected normal: ~40 active, rest idle
# Incident state: 100 active, 0 idle
```

### Step 2 — Identify connection leak source

```bash
# Find long-running queries holding connections
kubectl exec -n <namespace> deploy/<service> -- \
  psql $DATABASE_URL -c "
    SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state
    FROM pg_stat_activity
    WHERE (now() - pg_stat_activity.query_start) > interval '30 seconds'
    ORDER BY duration DESC;"
```

### Step 3 — Emergency: kill idle connections older than 5 minutes

```bash
# CAUTION: only do this if step 2 shows stuck idle connections
kubectl exec -n <namespace> deploy/<service> -- \
  psql $DATABASE_URL -c "
    SELECT pg_terminate_backend(pid)
    FROM pg_stat_activity
    WHERE state = 'idle'
      AND query_start < now() - interval '5 minutes'
      AND pid <> pg_backend_pid();"
```

### Step 4 — Check for recent deployment

```bash
kubectl rollout history deployment/<service> -n <namespace>
# If last deploy < 2 hours ago, consider rollback
```

### Step 5 — Rollback if deployment caused the issue

```bash
kubectl rollout undo deployment/<service> -n <namespace>
kubectl rollout status deployment/<service> -n <namespace>
```

---

## Investigation (after stabilisation)

### Check HikariCP pool metrics

```bash
# In Grafana: dashboard "JVM / Spring Boot" → "HikariCP" panel
# Look for: hikaricp_connections_timeout_total climbing
# Look for: hikaricp_connections_acquire_nanos_max > 5000ms
```

### Check application logs for connection not closed

```bash
kubectl logs -n <namespace> deploy/<service> --since=1h | \
  grep -E "connection|HikariPool|timeout" | tail -100
```

Common root causes:
- Missing `finally { connection.close() }` after refactor
- New retry logic that opens connections without releasing on exception
- N+1 query in new feature loading large datasets without pagination

---

## Recovery verification

```bash
# Pool should return to normal within 2-3 minutes after fix
watch -n 5 'kubectl exec -n <namespace> deploy/<service> -- \
  psql $DATABASE_URL -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"'
```

Expected recovery: active connections drop below 50, HTTP error rate returns to < 1%.

---

## Escalation

- Not resolved in 15 minutes → page DBA on-call
- Revenue impact confirmed → notify Product Owner + Engineering Director
- Rollback not possible → DBA on-call + incident bridge

---

## Related

- Postmortem: PM-2025-0318 (same root cause, payment service v2.9.0)
- Postmortem: PM-2024-1102 (similar: reporting service connection leak)
- Playbook: PB-DATABASE-001 (general DB incident response)
