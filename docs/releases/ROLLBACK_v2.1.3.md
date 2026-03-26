# Rollback Guide `v2.1.3`

## When To Roll Back

- `v2.1.3` introduces environment-specific regressions after the CI parity fix.
- Your deployment must temporarily stay on the previously published `v2.1.2` line.
- You need to revert the tracked external-data package while investigating unrelated production issues.

## Rollback Steps

1. Stop current services (`docker compose down` or service manager stop).
2. Checkout previous stable release tag (recommended: `v2.1.2`) or use the prior image.
3. Keep persistent data before rollback:
   - `data/quant.db`
   - `data/user_state.json`
   - `.env`
4. Start previous release configuration.
5. Verify:
   - `/api/health`
   - login
   - `/portfolio`
   - `/trading`
   - `/backtest`

## Data Notes

- `v2.1.3` does not introduce destructive schema migration.
- Rolling back to `2.1.2` remains backward-compatible for the current SQLite data layout.
