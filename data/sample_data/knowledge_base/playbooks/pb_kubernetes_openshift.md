# Playbook: Kubernetes / OpenShift Pod Incidents

**ID:** PB-K8S-001  
**Covers:** OOMKilled, CrashLoopBackOff, ImagePullBackOff, Pending pods  

## Severity classification

| Condition | Severity |
|-----------|----------|
| Critical service pod restarting > 5x/hour | CRITICAL |
| Non-critical service CrashLoopBackOff | HIGH |
| Pod Pending > 10 minutes | HIGH |
| Single replica restart, auto-recovered | LOW |

## Response steps

1. **Identify pod state:**
   ```bash
   kubectl get pods -n <namespace> | grep -v Running
   kubectl describe pod <pod> -n <namespace> | tail -30
   ```

2. **For OOMKilled:**
   - Check previous logs: `kubectl logs <pod> --previous`
   - Identify memory-heavy operation (large query, file processing, in-memory cache)
   - Immediate: increase memory limit
   - Fix: streaming / pagination for large datasets

3. **For CrashLoopBackOff (not OOM):**
   - Check startup logs for configuration errors
   - Check if dependent services are reachable (DB, Kafka, Keycloak)
   - Check if ConfigMap / Secret values are correct

4. **For ImagePullBackOff:**
   - Check image tag exists in registry
   - Check imagePullSecret is configured in namespace

## Escalation

- CRITICAL service (payments, auth) → page on-call immediately
- Multiple pods failing simultaneously → possible node issue, page infra team

---