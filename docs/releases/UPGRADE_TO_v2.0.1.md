# Upgrade To `v2.0.1`

## Audience
Operators upgrading from `v2.0.0` or earlier local hardening builds.

## Required Actions

1. Refresh `.env` from `env.example`.
2. Set a real `SECRET_KEY`.
3. For release deployments, either:
   - set `CORS_ORIGINS` to your frontend origin list, or
   - set `API_EXPECT_SAME_ORIGIN=true` when using a same-origin reverse proxy.
4. If you use AI features, configure a real LLM provider key and verify `/api/llm-analysis/health-check`.
5. If you use SMS alerts, configure the Twilio credentials:
   - `SMS_API_KEY` as Twilio Account SID
   - `SMS_API_SECRET` as Twilio Auth Token
   - `SMS_FROM_NUMBER`
   - `SMS_TO_NUMBERS`

## Recommended Verification

```bash
python -m pytest tests/test_v3_smoke.py -q
python -m pytest tests/unit -q
python -m pytest tests/integration -q
cd web && npm run lint && npm run build
RUN_EXTERNAL_E2E=1 pytest tests/e2e/test_release_validation.py -q
```
