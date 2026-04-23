# Runbook: Pod OOMKilled / CrashLoopBackOff

**ID:** RB-K8S-001  
**Severity:** HIGH  
**Service:** Any JVM-based service on OpenShift  
**Last updated:** 2026-01-20  
**Owner:** platform-ops-team

---

## Symptoms

- Alert: `PodOOMKilledLoop` firing
- `kubectl get pods` shows `OOMKilled` in REASON column
- `kube_pod_container_status_restarts_total` climbing rapidly
- Pod state: `CrashLoopBackOff`
- Service partially or fully unavailable depending on replica count

---

## Immediate actions (first 5 minutes)

### Step 1 — Confirm OOMKilled as cause

```bash
kubectl describe pod <pod-name> -n <namespace> | grep -A10 "Last State"
# Expected:
#   Last State: Terminated
#     Reason: OOMKilled
#     Exit Code: 137

kubectl get events -n <namespace> --sort-by='.lastTimestamp' | grep OOM
```

### Step 2 — Identify which request triggered OOM

```bash
kubectl logs <pod-name> -n <namespace> --previous | tail -200
# Look for: "Exporting X rows", "Loading X records", "GC overhead limit exceeded"
# Find last HTTP request in access log before OOM
```

### Step 3 — Immediate mitigation: increase memory limit

```bash
kubectl get deployment <service> -n <namespace> -o jsonpath=\
  '{.spec.template.spec.containers[0].resources}'

kubectl set resources deployment/<service> -n <namespace> \
  --limits=memory=1Gi --requests=memory=512Mi

kubectl rollout status deployment/<service> -n <namespace>
```

### Step 4 — Scale up replicas to restore availability

```bash
kubectl scale deployment/<service> -n <namespace> --replicas=3
# Note: won't help if ALL requests trigger OOM
```

---

## Root cause patterns

### Pattern A — Large dataset loaded into memory (most common for report services)

```java
// BEFORE — loads everything into List, causes OOM at 500k+ rows
List<Order> orders = orderRepo.findAll();

// AFTER — streaming with pagination
Pageable page = PageRequest.of(0, 1000);
Page<Order> chunk;
do {
    chunk = orderRepo.findAll(page);
    processChunk(chunk.getContent());
    page = page.next();
} while (chunk.hasNext());
```

Also: use `StreamingResponseBody` for XLSX/CSV exports instead of building in-memory.

### Pattern B — Memory leak (heap grows monotonically)

```bash
# In Grafana: JVM dashboard → "Heap After GC" panel
# Growing after each GC cycle = memory leak
# Enable heap dump on OOM to analyse:
kubectl set env deployment/<service> -n <namespace> \
  JAVA_OPTS="-XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/tmp/heap.hprof"
kubectl cp <namespace>/<pod>:/tmp/heap.hprof ./heap.hprof
# Analyse with Eclipse MAT
```

### Pattern C — Unbounded in-memory cache

```java
// Add size + TTL bounds to any in-memory cache
return Caffeine.newBuilder()
    .maximumSize(10_000)
    .expireAfterWrite(1, HOURS)
    .build();
```

---

## Recovery verification

```bash
watch -n 10 'kubectl get pods -n <namespace> | grep <service>'
kubectl top pod -n <namespace> | grep <service>
kubectl get events -n <namespace> --sort-by='.lastTimestamp' | grep OOM
```

Expected: pod stays Running, memory stays below 80% of new limit, no new OOM events.

---

## Long-term fixes

1. Add streaming/pagination to all bulk endpoints
2. Add request validation: reject report date ranges > 90 days
3. JVM flags: `-XX:+UseG1GC -XX:MaxGCPauseMillis=200`
4. Load test for max expected dataset size in staging pipeline

---

## Escalation

- OOM on payments/auth → bridge call + notify Engineering Director
- Multiple services OOMKilling → node pressure, escalate to infra team

## Related

- Postmortem: PM-2024-1102 (report-generation-service, same root cause)
- Playbook: PB-K8S-001
