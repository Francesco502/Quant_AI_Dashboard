# Rollback `v2.0.0`

## When To Roll Back

Roll back if any of the following appear after deployment:

- authentication bootstrap no longer matches your configured environment
- frontend cannot connect to the backend after upgrade
- Docker health checks fail repeatedly
- critical backtest, trading, or portfolio flows regress

## Rollback Steps

1. Stop the current services
2. Restore the previous image tag or previous git tag
3. Restore the previous `.env` and deployment manifests if they were changed
4. Restart services and re-run health/smoke checks

## Minimum Post-Rollback Checks

```bash
curl http://127.0.0.1:8685/api/health
python -m pytest tests/test_v3_smoke.py -q
```

## Important Note

If the issue is related to the new admin bootstrap policy, make sure the rollback target still matches the credentials and auth expectations stored in your current runtime environment.
