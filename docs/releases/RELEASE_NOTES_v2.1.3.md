# Release Notes `v2.1.3`

## Highlights

- Upgraded release line from `v2.1.2` to `v2.1.3`.
- Fixed CI and clean-checkout runtime imports by tracking the `core.data.external` package in Git.
- Preserved the `2.1.2` release artifact while moving the validated source baseline forward.

## Core Changes

- `.gitignore` now ignores only the runtime `/data/` directory instead of hiding the tracked `core/data/` package.
- Added tracked package files under `core/data/` so GitHub Actions and other clean environments can import external-data loaders reliably.
- Kept backend, frontend, deployment metadata, tests, and release docs aligned to `2.1.3`.

## Operational Impact

- Fresh clones and CI runners now match local development for `core.data.external` imports.
- The release line after `2.1.2` is source-consistent with the green CI run on `main`.
- Single-image deployments remain same-origin and continue to expose frontend on `8686` and API on `8685`.
