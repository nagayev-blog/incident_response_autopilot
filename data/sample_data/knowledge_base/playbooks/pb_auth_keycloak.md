# Playbook: Authentication / IAM Incidents

**ID:** PB-AUTH-001  
**Covers:** Keycloak performance, token validation failures, SSO issues  

## Critical: all services depend on auth

Authentication incidents have the highest blast radius. Every authenticated service is affected.

## Severity classification

| Condition | Severity |
|-----------|----------|
| Auth p99 > 5s OR error rate > 5% | CRITICAL |
| Auth p99 > 2s OR intermittent 504s | HIGH |
| Auth p99 > 500ms, no user complaints | LOW |

## Response steps

1. **Check Keycloak cluster health:**
   ```bash
   kubectl get pods -n auth
   curl https://auth.internal/health
   ```

2. **Check DB connections to Keycloak DB** (most common cause)

3. **Check USER_SESSION table size** (see RB-AUTH-001)

4. **If auth is completely down:** enable emergency bypass for internal services (requires Security approval)

5. **Notify:** auth outage → all-hands notification to engineering

---