# Rollback Guide `v2.1.2`

## When To Roll Back

- Optimized single-image deployment after `v2.1.2` introduces runtime regressions in core routes.
- Your deployment depends on a previous image tag while investigating release-image changes.
- CI image validation passes but your environment-specific runtime behavior still regresses.

## Rollback Steps

1. Stop current services (`docker compose down` or service manager stop).
2. Checkout previous stable release tag (recommended: `v2.1.1`) or use the prior image.
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

- `v2.1.2` does not introduce destructive schema migration.
- Rolling back to `2.1.1` remains backward-compatible for the current SQLite data layout.
