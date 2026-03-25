# Rollback Guide `v2.1.1`

## When To Roll Back

- CI workflow behavior no longer matches your team policy.
- Manual-dispatch-only test workflow blocks your expected release flow.
- Runtime deployment after `v2.1.1` introduces regressions in core routes.

## Rollback Steps

1. Stop current services (`docker compose down` or service manager stop).
2. Checkout previous stable release tag (recommended: `v2.1.0`) or use prior image.
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

- `v2.1.1` does not introduce destructive schema migration.
- Rolling back to `2.1.0` remains backward-compatible for current SQLite data layout.
