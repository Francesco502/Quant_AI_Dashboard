# Quant-AI Dashboard Frontend (v1.0.0)

Frontend application for Quant-AI Dashboard, built with Next.js App Router.

## Runtime Baseline
- Framework: Next.js 16
- React: 19
- Default dev/start port: `8686`

## Local Development
```bash
cd web
npm install
npm run dev
```

Open: [http://localhost:8686](http://localhost:8686)

## Backend API Connection
- Default API base in code: `http://127.0.0.1:8685/api`
- Local development:

```bash
# web/.env.local
NEXT_PUBLIC_API_URL=http://127.0.0.1:8685/api
```

## Quality Commands
```bash
npm run lint
npm run build
npm run start
```

## Structure
- `src/app/`: route pages
- `src/components/`: reusable UI components
- `src/lib/api.ts`: typed API client and request contracts

## Versioned Release Docs
- `../docs/RELEASE_NOTES_v1.0.0.md`
- `../docs/CODE_CHANGES_v1.0.0.md`
