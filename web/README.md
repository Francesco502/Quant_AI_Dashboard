# Quant-AI Dashboard Frontend

Next.js frontend for Quant-AI Dashboard `v2.1.4`.

## Runtime Baseline

- Next.js 16
- React 19
- default local port: `8686`

## Local Development

```bash
cd web
npm install
npm run dev
```

Open [http://localhost:8686](http://localhost:8686).

## Backend Connection

- local API base in development: `http://127.0.0.1:8685/api`
- recommended local override:

```bash
# web/.env.local
NEXT_PUBLIC_API_URL=http://127.0.0.1:8685/api
```

- in the canonical single-image deployment, the frontend talks to `/api` through Nginx in the same container

## Quality Commands

```bash
npm run lint
npm run build
npm run preview
```

## Structure

- `src/app/`: routes
- `src/components/`: UI and workflow components
- `src/lib/api.ts`: API client and request contracts
- `src/lib/workspace-nav.ts`: top-level information architecture

## Canonical Docs

- project index: [../README.md](../README.md)
- current docs: [../docs/current/README.md](../docs/current/README.md)
- quickstart: [../docs/current/quickstart.md](../docs/current/quickstart.md)
- deployment: [../docs/current/deployment.md](../docs/current/deployment.md)
