# Upgrade To `v2.0.0`

## Audience
Operators upgrading from the `v2.0.0-alpha.1` line or older local builds.

## Required Actions

1. Review `env.example` and refresh your local `.env`
2. Set one of the following before first login:
   - `APP_LOGIN_PASSWORD`
   - `APP_LOGIN_PASSWORD_HASH`
3. Optionally set `APP_ADMIN_USERNAME` if you do not want the bootstrap admin username to be `admin`
4. If you run external smoke tests, set:
   - `TEST_LOGIN_USERNAME`
   - `TEST_LOGIN_PASSWORD`
5. Rebuild frontend and Docker images after upgrading

## Behavior Changes

- There is no longer a weak built-in `admin / admin123` bootstrap account
- There is no longer a real-looking default OpenAI-compatible API key in code or examples
- When no LLM key is configured, the system returns a dummy placeholder LLM response instead of assuming a default provider key

## Recommended Verification

```bash
python -m pytest tests/test_v3_smoke.py -q
python -m pytest tests/integration/test_auth_api.py -v
cd web && npm run lint && npm run build
docker compose config
```
