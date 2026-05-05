# Service Baselines — Production Metrics Reference

**Updated:** 2026-04-01  
**Source:** 30-day rolling P50/P95/P99 from Prometheus  
**Environment:** production  

---

## HTTP Service Baselines

| Service | RPS (peak) | RPS (avg) | Latency p50 (ms) | Latency p95 (ms) | Latency p99 (ms) | Error rate (%) |
|---------|-----------|-----------|-----------------|-----------------|-----------------|----------------|
| api-gateway | 1200 | 680 | 45 | 120 | 185 | 0.15 |
| payment-processing-service | 180 | 95 | 85 | 155 | 220 | 0.20 |
| notification-service | 95 | 40 | 140 | 260 | 380 | 0.30 |
| report-generation-service | 12 | 4 | 2100 | 3800 | 4200 | 0.50 |
| keycloak | 340 | 210 | 95 | 155 | 195 | 0.10 |
| data-sync-service | n/a (batch) | n/a | n/a | n/a | n/a | n/a |
| frontend-cdn | 2800 | 1600 | 12 | 35 | 65 | 0.05 |

---

## Database Connection Baselines

| Service | Pool Max | Normal Active | Warning (%) | Critical (%) |
|---------|----------|--------------|-------------|--------------|
| payment-processing-service | 100 | 38–45 | 70 | 90 |
| report-generation-service | 50 | 8–15 | 70 | 90 |
| keycloak | 100 | 18–25 | 70 | 90 |
| data-sync-service | 20 | 5–10 | 70 | 90 |
| notification-service | 30 | 4–8 | 70 | 90 |

---

## JVM / Memory Baselines (Spring Boot services)

| Service | Heap Max | Normal Heap % | GC Pause p99 (ms) | GC Collections/min |
|---------|----------|--------------|------------------|-------------------|
| payment-processing-service | 2048 Mi | 52–62% | 45 | 0.8 |
| notification-service | 4096 Mi | 60–68% | 90 | 1.1 |
| report-generation-service | 512 Mi | 55–70% | 120 | 1.4 |
| data-sync-service | 1024 Mi | 45–60% | 60 | 0.6 |

---

## Kafka Consumer Baselines

| Consumer Group | Topic | Normal Lag | Warning | Critical |
|---------------|-------|------------|---------|----------|
| notification-service-consumer | user-events | 50–300 | 10,000 | 100,000 |
| audit-service-consumer | audit-events | 0–100 | 5,000 | 50,000 |
| analytics-consumer | all-events | 200–1000 | 20,000 | 200,000 |

**Normal consume rates:**
- notification-service: ~51 messages/second
- audit-service: ~120 messages/second

---

## Infrastructure Baselines

| Resource | Service | Normal | Warning Threshold | Critical Threshold |
|----------|---------|--------|------------------|--------------------|
| CPU (cores) | payment-processing-service | 0.8–1.2 | 2.5 | 3.5 |
| CPU (cores) | notification-service | 0.4–0.8 | 1.5 | 2.5 |
| Pod memory | report-generation-service | 280–380 Mi | 450 Mi | 500 Mi |
| Node disk (worker-07) | /var/log | 100–130 GB | 160 GB (80%) | 180 GB (90%) |
| CDN cache hit ratio | frontend-cdn | 0.91–0.96 | 0.60 | 0.40 |

---

## Keycloak-Specific Baselines

| Metric | Normal | Warning | Critical |
|--------|--------|---------|----------|
| Auth endpoint p99 (ms) | 150–250 | 1,000 | 3,000 |
| HTTP 504 rate | 0.0% | 1% | 5% |
| DB connections active | 18–25 | 70 | 90 |
| USER_SESSION table rows | 1M–3M | 5M | 15M |
| Expired session rows | < 500k | > 2M | > 10M |
| Token refresh failures/min | 0–5 | 50 | 200 |

---

## ETL Pipeline Baselines

| Job | Schedule | Normal Duration | Warning | Critical |
|-----|----------|----------------|---------|----------|
| operational-to-analytics-sync | Daily 06:00 | 1,800s (30min) | 3,600s | 7,200s |
| audit-export | Daily 03:00 | 600s (10min) | 1,800s | 3,600s |
| risk-score-batch | 1st of month 01:00 | 10,800s (3h) | 14,400s | 18,000s |

**Data freshness SLA:** Analytics data must not be older than 2 hours at 09:00

---

## Alert Thresholds Summary

| Alert Name | Metric | Threshold | Severity |
|------------|--------|-----------|----------|
| DBConnectionPoolExhausted | pg_connections_active / max | > 90% | CRITICAL |
| DBConnectionPoolHigh | pg_connections_active / max | > 70% | HIGH |
| KafkaConsumerLagCritical | kafka_consumer_lag | > 100,000 | CRITICAL |
| KafkaConsumerLagHigh | kafka_consumer_lag | > 10,000 | HIGH |
| PodOOMKilledLoop | kube_pod_container_status_restarts_total | > 3 in 30min | HIGH |
| KeycloakAuthCritical | keycloak_response_p99_ms | > 5,000 | CRITICAL |
| KeycloakAuthDegradation | keycloak_response_p99_ms | > 2,000 | HIGH |
| KeycloakSessionBloat | keycloak_user_sessions_total | > 5,000,000 | WARNING |
| ETLPipelineFailure | etl_last_success_lag_seconds | > 2× schedule | HIGH |
| DiskUsageWarning | node_filesystem_used_percent | > 80% | LOW |
| DiskUsageCritical | node_filesystem_used_percent | > 90% | HIGH |
| CDNCacheHitRateLow | cdn_cache_hit_ratio | < 0.50 | LOW |
| HighErrorRate | http_requests_5xx_rate | > 5% | HIGH |
| HighErrorRateCritical | http_requests_5xx_rate | > 30% | CRITICAL |
