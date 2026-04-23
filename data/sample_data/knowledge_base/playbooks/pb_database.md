# Playbook: Database Incidents

**ID:** PB-DATABASE-001  
**Covers:** Connection pool exhaustion, slow queries, deadlocks, replication lag  

## Severity classification

| Condition | Severity |
|-----------|----------|
| Connection pool > 95% AND error rate > 10% | CRITICAL |
| Connection pool > 80% OR query p99 > 5s | HIGH |
| Slow queries detected, no user impact yet | LOW |

## Response steps

1. **Triage** — confirm which database (operational, analytics, keycloak, etc.)
2. **Assess blast radius** — which services depend on this DB?
3. **Check recent deployments** — was there a deploy in last 2 hours?
4. **Parallel tracks:**
   - Track A: Mitigate user impact (rollback, circuit breaker, static error page)
   - Track B: Investigate root cause (logs, slow query log, pg_stat_activity)
5. **Fix** — targeted to root cause (see specific runbooks)
6. **Verify** — connection count normalises, error rate drops
7. **Postmortem** — required for any CRITICAL DB incident

## Common patterns and their runbooks

| Pattern | Runbook |
|---------|---------|
| Connection pool exhausted | RB-DB-001 |
| Sessions table bloat (Keycloak) | RB-AUTH-001 |
| Deadlock between batch jobs | RB-DATA-001 |
| Slow queries after migration | RB-DB-002 (TBD) |

---