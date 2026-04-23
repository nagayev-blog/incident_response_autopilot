# Runbook: CDN Cache Hit Rate Low

**ID:** RB-CDN-001  
**Severity:** LOW  
**Service:** frontend-cdn, React SPA  
**Last updated:** 2026-01-15  
**Owner:** frontend-platform-team

---

## Symptoms

- Alert: `CDNCacheHitRateLow` firing
- `cdn_cache_hit_ratio` < 0.5 (baseline ~0.94)
- Origin request rate spiked 2-4x
- Users experiencing slower page loads (p95 > 3s instead of ~1s)
- Usually happens immediately after frontend deployment

---

## Root cause patterns

### Pattern A — Post-deploy cache invalidation (most common, ~80% of cases)

Content-hash filenames changed in new deploy, but Cache-Control headers set to `no-cache` or `max-age=0`.
CDN cannot serve old cached assets for new URLs, all requests go to origin.
CDN naturally warms up over 15-60 minutes as users request assets.

### Pattern B — Cache-Control header misconfiguration

CI/CD pipeline injected wrong headers. New deploy accidentally sets `max-age=0` on static assets.

### Pattern C — CDN provider incident

Check CDN status page if patterns A/B don't match.

---

## Immediate actions

### Step 1 — Confirm it's post-deploy (check timing)

```bash
kubectl rollout history deployment/frontend-cdn -n frontend | tail -5
# Deploy time should be within minutes of alert start time
```

### Step 2 — Check current Cache-Control headers

```bash
# Check what headers are being served for static assets
curl -I https://app.internal/static/js/main.abc123.js | grep -i cache

# Expected for hashed assets: Cache-Control: max-age=31536000, immutable
# Problem state: Cache-Control: max-age=0, no-cache
```

### Step 3 — Fix Cache-Control headers

```bash
# Update nginx/CDN config in deployment
kubectl set env deployment/frontend-cdn -n frontend \
  CACHE_CONTROL_HASHED_ASSETS="max-age=31536000, immutable" \
  CACHE_CONTROL_INDEX_HTML="max-age=0, no-cache" \
  CACHE_CONTROL_MANIFEST="max-age=0, no-cache"

kubectl rollout restart deployment/frontend-cdn -n frontend
kubectl rollout status deployment/frontend-cdn -n frontend
```

### Step 4 — Verify fix

```bash
# Check headers after restart
curl -I https://app.internal/static/js/main.abc123.js | grep -i "cache-control"
# Expected: Cache-Control: max-age=31536000, immutable

# Monitor cache hit ratio in Grafana: "CDN" dashboard
# Should return to > 80% within 20-30 minutes as CDN warms up
# Full recovery to ~94% typically takes 30-60 minutes
```

---

## Fix in CI/CD pipeline (prevent recurrence)

```nginx
# nginx.conf — correct caching strategy for React SPA

# index.html — never cache (new deploys must be picked up immediately)
location = /index.html {
    add_header Cache-Control "max-age=0, no-cache, no-store, must-revalidate";
}

# Hashed static assets — cache forever (hash changes on content change)
location /static/ {
    add_header Cache-Control "max-age=31536000, immutable";
    gzip_static on;
}

# manifest.json, robots.txt — short cache
location ~* \.(json|txt)$ {
    add_header Cache-Control "max-age=300";
}
```

---

## Monitoring

CDN cache warmup is normal after every deploy — low hit rate for 15-30 min is expected.
Consider adjusting alert to:
- Suppress for 30 minutes after detected deployment
- Alert only if hit rate < 0.3 (not recovering at all) or not recovering after 60 min
