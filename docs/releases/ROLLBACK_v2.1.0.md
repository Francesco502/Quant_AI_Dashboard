# Rollback Guide `v2.1.0`

## When To Roll Back

- Automatic paper-trading jobs produce unexpected orders after deployment.
- Personal-asset valuation or DCA reconciliation introduces breaking regressions.
- Frontend routing, login gating, or core dashboards fail after cold start.

## Rollback Steps

1. Stop the `v2.1.0` frontend, API service, and daemon.
2. Restore the previous verified release image or checkout the previous release commit.
3. Preserve `data/quant.db`, `data/user_state.json`, and `.env` before replacing code or images.
4. Restart services with the previous release configuration.
5. Verify:
   - `/api/health`
   - login
   - `/portfolio`
   - `/trading`
   - daemon status

## Data Notes

- `v2.1.0` does not require a destructive schema migration for SQLite.
- Personal-asset snapshots, transaction history, and paper-account trades remain backward-compatible with the `2.0.x` database baseline.
- If rollback is caused by bad runtime data, restore `data/quant.db` from the latest backup taken before deployment.
