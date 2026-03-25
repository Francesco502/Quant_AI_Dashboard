# Release Notes `v2.1.1`

## Highlights

- Upgraded release line from `v2.1.0` to `v2.1.1`.
- Stabilized CI workflow execution to avoid environment/plugin mismatch failures.
- Changed CI trigger strategy to manual dispatch only.
- Sanitized SMTP examples in legacy docs to reduce false-positive secret alerts.

## Core Changes

- CI workflow now uses `python -m pip` and `python -m pytest` consistently.
- Coverage generation in CI uses the `coverage` module directly.
- Performance test job uses standard performance tests without benchmark-plugin-only arguments.
- Automatic CI triggers on `push` and `pull_request` were removed; `workflow_dispatch` remains.

## Operational Impact

- GitHub Actions no longer run automatically on every push/PR.
- Release verification should be executed manually from Actions when required.
