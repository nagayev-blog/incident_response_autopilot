# Playbook: Kafka / Message Queue Incidents

**ID:** PB-KAFKA-001  
**Covers:** Consumer lag, partition leadership changes, broker unavailability  

## Severity classification

| Condition | Severity |
|-----------|----------|
| Lag > 300k AND growing AND SLA-bound service | CRITICAL |
| Lag > 100k OR consumer group rebalancing > 3x/hour | HIGH |
| Lag > 10k, stable, not SLA-bound | LOW |

## Key diagnostic questions

1. Is lag growing or stable? (Growing = root problem, stable = already at new equilibrium)
2. Is it one consumer group or multiple? (Multiple → broker issue)
3. What changed recently? (Deploy, config change, external dependency)
4. Is JVM healthy? (High GC → consumer poll timeout → rebalance → worse lag)

## Response steps

1. Check lag trend in Grafana (last 2h)
2. Check consumer logs for exceptions
3. Check external dependencies latency
4. Scale consumers if topic has enough partitions
5. Fix root cause (see RB-KAFKA-001)

---