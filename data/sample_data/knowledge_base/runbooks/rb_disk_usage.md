# Runbook: Disk Usage Warning

**ID:** RB-INFRA-001  
**Severity:** LOW  
**Service:** Any pod/node with persistent storage  
**Last updated:** 2025-12-10  
**Owner:** platform-ops-team

---

## Symptoms

- Alert: `DiskUsageWarning` firing
- `node_filesystem_used_percent` > 80% (warning) or > 90% (critical)
- Log rotation may have stopped
- Service may stop writing logs (silently!)

---

## Immediate actions

### Step 1 — Identify what's consuming disk

```bash
# Find the node
kubectl get pods -n <namespace> -o wide | grep <service>

# On the node (via debug pod):
kubectl debug node/<node-name> -it --image=busybox

# Inside debug pod:
df -h
du -sh /var/log/* 2>/dev/null | sort -rh | head -20
find /var/log -name "*.log" -size +500M 2>/dev/null
find /var/log -name "*.log" -mtime +7 2>/dev/null | wc -l
```

### Step 2 — Check log rotation status

```bash
kubectl exec -n <namespace> deploy/<service> -- \
  cat /etc/logback.xml | grep -A10 "rollingPolicy"

# Check when last rotation happened
kubectl exec -n <namespace> deploy/<service> -- \
  ls -lth /var/log/app/ | head -20

# Rotation stopped signs:
# - All files have same date (rotation day)
# - Main log file > 1GB
# - No .gz compressed files when there should be
```

### Step 3 — Manual cleanup: compress old logs

```bash
# Compress logs older than 1 day
kubectl exec -n <namespace> deploy/<service> -- \
  find /var/log/app -name "*.log" -mtime +1 -exec gzip {} \;

# Delete compressed logs older than retention policy (30 days default)
kubectl exec -n <namespace> deploy/<service> -- \
  find /var/log/app -name "*.log.gz" -mtime +30 -delete

# Check space freed
kubectl exec -n <namespace> deploy/<service> -- df -h /var/log
```

### Step 4 — Fix log rotation configuration

Common cause: timezone change breaks cron expression in logback

```xml
<!-- logback.xml — ensure timezone-safe cron or use size-based rotation -->
<rollingPolicy class="ch.qos.logback.core.rolling.SizeAndTimeBasedRollingPolicy">
  <fileNamePattern>/var/log/app/app-%d{yyyy-MM-dd}.%i.log.gz</fileNamePattern>
  <maxFileSize>100MB</maxFileSize>
  <maxHistory>30</maxHistory>
  <totalSizeCap>10GB</totalSizeCap>
</rollingPolicy>
```

After config fix, restart pod to pick up new logback config:
```bash
kubectl rollout restart deployment/<service> -n <namespace>
```

---

## Prevention

1. Add `totalSizeCap` to logback config — hard limit regardless of rotation
2. Add disk usage alert at 80% (warning) AND 90% (critical)
3. Test log rotation in staging after any timezone or cluster config changes
4. Consider shipping logs to external system (ELK/Loki) instead of local disk

---

## Escalation

- Disk > 90% → immediate action required, escalate to platform-ops on-call
- Service stopped writing logs (symptom: log file not growing) → investigate if disk is full
