# Runbook: Kafka Consumer Lag Critical

**ID:** RB-KAFKA-001  
**Severity:** CRITICAL / HIGH  
**Last updated:** 2026-02-14  
**Owner:** data-platform-team

---

## Symptoms

- `kafka_consumer_lag` > 100,000 (HIGH) or > 300,000 (CRITICAL)
- Notifications / events delayed for end users
- JVM heap climbing, GC pauses increasing
- Consumer group rebalancing frequently

---

## Immediate actions

### Step 1 — Assess lag growth rate

```bash
# Via Grafana: "Kafka / Consumer Groups" dashboard
# Key metric: is lag growing or stable?
# Growing = producer faster than consumer → need to find bottleneck
# Stable high = consumer caught up to producer speed
```

### Step 2 — Check for external dependency slowdown

```bash
kubectl logs -n <namespace> deploy/<service> --since=30m | \
  grep -E "timeout|connection refused|slow|latency" | tail -50

# Common culprits: SMTP gateway, SMS provider, push notification service
# If external service is slow → consumer naturally slows down
```

### Step 3 — Check JVM heap / GC

```bash
# In Grafana: JVM dashboard → Heap Used, GC Pause Duration
# If heap > 85%: GC pauses cause Kafka poll timeout → partition rebalance → worse lag
kubectl top pod -n <namespace> | grep <service>
```

### Step 4a — If root cause is external service timeout

```bash
# Option 1: Add circuit breaker / timeout to external call (code fix, slower)
# Option 2: Temporarily route notifications to fallback channel
# Option 3: Increase consumer instances to process faster despite slow external
kubectl scale deployment/<service> -n <namespace> --replicas=5
# Note: only works if Kafka topic has >= 5 partitions
```

### Step 4b — If root cause is memory leak / GC pressure

```bash
# Increase heap limit temporarily
kubectl set env deployment/<service> -n <namespace> \
  JAVA_OPTS="-Xmx6g -XX:+UseG1GC -XX:MaxGCPauseMillis=200"
kubectl rollout status deployment/<service> -n <namespace>
```

### Step 5 — Monitor recovery

```bash
# Lag should start decreasing within 5-10 minutes of fix
# Full recovery time = lag_messages / (consume_rate - produce_rate)
# At lag=500k, consume=51/s, produce=12/s → ~3.5h if produce rate stays same
```

---

## Escalation

- Lag not decreasing after 20 minutes → page Kafka admin
- SLA breach confirmed → notify Product Owner
