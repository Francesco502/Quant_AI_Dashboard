# Rollback Guide `v2.2.0`

## When To Roll Back

- A `v2.2.0` deployment introduces environment-specific regressions.
- Release validation passed locally, but the target environment behaves differently after upgrade.
- You need to return to the previously known-good release while investigating.

## Rollback Steps

1. Stop current services: `docker compose down`
2. Checkout the previous stable tag or pull the prior image
3. Preserve runtime state before rollback:
   - `data/quant.db`
   - `data/user_state.json`
   - `.env`
   - `logs/`
4. Start the previous release configuration
5. Verify:
   - `/api/health`
   - `/login`
   - `/portfolio`
   - `/trading`
   - `/backtest`

## Data Notes

- `v2.2.0` is intended to remain backward-compatible with the current SQLite-based runtime layout.
- If you enable new providers or credentials during upgrade, keep the pre-upgrade `.env` backup so rollback can restore both code and runtime configuration together.
