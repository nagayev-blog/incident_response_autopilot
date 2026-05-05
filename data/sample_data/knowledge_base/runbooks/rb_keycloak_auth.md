# Runbook: Keycloak Authentication Performance Degradation

**ID:** RB-AUTH-001  
**Severity:** HIGH / CRITICAL  
**Service:** Keycloak (IAM), affects all authenticated services  
**Last updated:** 2026-03-05  
**Owner:** platform-security-team

---

## Symptoms

- Alert: `KeycloakAuthDegradation` firing
- `keycloak_request_duration_seconds` p99 > 2s (HIGH), > 5s (CRITICAL)
- HTTP 504 errors on auth endpoints (`/realms/*/protocol/openid-connect/*`)
- Users experiencing login failures or token refresh errors
- All downstream services affected (auth is a dependency of everything)

---

## Blast radius warning

Keycloak degradation affects ALL authenticated services simultaneously.
This is a PRIORITY-1 incident even at HIGH severity.
Notify engineering channel immediately upon confirmation.

---

## Immediate actions (first 10 minutes)

### Step 1 — Confirm Keycloak is the bottleneck

```bash
# Check Keycloak pod health
kubectl get pods -n auth | grep keycloak
kubectl top pod -n auth | grep keycloak

# Test auth endpoint directly
curl -w "\n%{time_total}s\n" -o /dev/null -s \
  "https://auth.internal/realms/master/protocol/openid-connect/token" \
  -d "grant_type=client_credentials&client_id=test&client_secret=test"
# > 2s response time confirms Keycloak is degraded
```

### Step 2 — Check DB connections (most common root cause)

```bash
kubectl exec -n auth deploy/keycloak -- \
  psql $KEYCLOAK_DB_URL -c \
  "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# Warning: > 80 active connections
# Critical: > 95 active connections (near pool max of 100)
```

### Step 3 — Check for session table bloat

```bash
kubectl exec -n auth deploy/keycloak -- \
  psql $KEYCLOAK_DB_URL -c \
  "SELECT count(*) as total_sessions FROM USER_SESSION;"

# Also check expired sessions:
kubectl exec -n auth deploy/keycloak -- \
  psql $KEYCLOAK_DB_URL -c \
  "SELECT count(*) as expired FROM USER_SESSION
   WHERE last_session_refresh < extract(epoch from now()) - 86400;"

# > 5M total is a problem
# > 20M expired = critical, session cleanup stopped working
```

### Step 4 — Check for long-running queries

```bash
kubectl exec -n auth deploy/keycloak -- \
  psql $KEYCLOAK_DB_URL -c \
  "SELECT pid, now() - query_start AS duration, query
   FROM pg_stat_activity
   WHERE state = 'active'
     AND query_start < now() - interval '10 seconds'
   ORDER BY duration DESC LIMIT 10;"

# Sequential scan on USER_SESSION with millions of rows = root cause confirmed
```

---

## Fix: Emergency session cleanup

**Requires DBA approval for CRITICAL severity.**

```bash
# Run in batches to avoid lock escalation and DB overload
# Each batch takes ~30-60 seconds on 500k rows
kubectl exec -n auth deploy/keycloak -- \
  psql $KEYCLOAK_DB_URL -c \
  "DELETE FROM USER_SESSION
   WHERE last_session_refresh < extract(epoch from now()) - 86400
   LIMIT 500000;"

# Repeat until count of expired sessions is < 500k
# Monitor p99 latency in Grafana as you delete — should start dropping

# Also clean offline sessions
kubectl exec -n auth deploy/keycloak -- \
  psql $KEYCLOAK_DB_URL -c \
  "DELETE FROM OFFLINE_USER_SESSION
   WHERE created_on < extract(epoch from now()) - 2592000
   LIMIT 500000;"
```

### Verify cleanup progress

```bash
watch -n 30 'kubectl exec -n auth deploy/keycloak -- \
  psql $KEYCLOAK_DB_URL -c \
  "SELECT count(*) FROM USER_SESSION WHERE \
   last_session_refresh < extract(epoch from now()) - 86400;"'
```

---

## Fix: Session cleanup configuration (prevent recurrence)

In Keycloak Admin Console:
1. Go to: **Realm Settings → Tokens**
2. Set: **SSO Session Max** = `8 Hours`
3. Set: **Offline Session Max** = `30 Days`
4. Set: **SSO Session Idle** = `4 Hours`
5. Enable: **Realm Settings → Sessions → Revoke Refresh Token** = ON

Add DB index if missing:
```bash
kubectl exec -n auth deploy/keycloak -- \
  psql $KEYCLOAK_DB_URL -c \
  "CREATE INDEX CONCURRENTLY IF NOT EXISTS \
   idx_user_session_refresh ON USER_SESSION(last_session_refresh);"
```

---

## Recovery verification

```bash
# Latency should return to < 300ms p99
watch -n 15 'curl -w "%{time_total}s\n" -o /dev/null -s \
  https://auth.internal/realms/master/.well-known/openid-configuration'

# Check Grafana: Auth dashboard → "Token Endpoint P99 Latency"
# Expected: drops from 8000ms to < 300ms within 15-30 min of cleanup start
```

---

## Post-incident: add monitoring

```bash
# Alert if session count > 5M
# In Prometheus alerting rules:
- alert: KeycloakSessionTableBloat
  expr: keycloak_user_sessions_total > 5000000
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Keycloak session table growing — cleanup may have stopped"
```

---

## Escalation

- Auth p99 > 5s → bridge call, notify all engineering leads
- Complete auth outage → emergency bypass procedure (requires Security approval)
- Cannot connect to Keycloak DB → escalate to DBA on-call immediately

## Related

- Postmortem: PM-2025-0601 (Keycloak 21 upgrade killed session cleanup)
- Playbook: PB-AUTH-001
