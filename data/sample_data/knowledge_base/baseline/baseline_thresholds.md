# Baseline Metrics Reference

**Updated:** 2026-04-01  
**Source:** 30-day P50 from Prometheus  

## Service baselines (production)

| Service | HTTP RPS (peak) | Latency p99 (ms) | Error rate | DB conn (normal) |
|---------|----------------|-----------------|------------|-----------------|
| payment-processing-service | 180 | 220 | 0.2% | 38-45 |
| notification-service | 95 | 180 | 0.3% | n/a (Kafka) |
| report-generation-service | 12 | 4200 | 0.5% | 8-15 |
| keycloak | 340 | 195 | 0.1% | 18-25 |
| data-sync-service | n/a (batch) | n/a | n/a | 5-10 |
| api-gateway | 1200 | 85 | 0.15% | n/a |

## Infrastructure baselines

| Resource | Normal | Warning | Critical |
|----------|--------|---------|----------|
| PostgreSQL connections (per service) | < 50% pool | > 70% pool | > 90% pool |
| JVM heap | < 70% | > 80% | > 90% |
| Kafka consumer lag (SLA services) | < 1000 | > 10000 | > 100000 |
| Pod memory | < 70% limit | > 80% limit | > 90% limit |
| Node disk | < 70% | > 80% | > 90% |
| Keycloak response p99 | < 300ms | > 1000ms | > 3000ms |

## Alert thresholds

| Alert | Threshold | Severity |
|-------|-----------|----------|
| DBConnectionPoolExhausted | connections = max | CRITICAL |
| KafkaConsumerLagCritical | lag > 300k | CRITICAL |
| PodOOMKilledLoop | restarts > 3/hour | HIGH |
| KeycloakAuthDegradation | p99 > 3000ms | HIGH |
| ETLPipelineFailure | lag > 2x schedule | HIGH |
| DiskUsageWarning | used > 80% | LOW |
| CDNCacheHitRateLow | hit_ratio < 0.5 | LOW |