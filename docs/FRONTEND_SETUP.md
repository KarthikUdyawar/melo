# Melo — Frontend Setup (Sprint 7: Next.js/TS/Tailwind)

> Covers local dev, tests, and the Docker build. Backend setup is unchanged — see `INFRA.md`/root `Makefile`.

---

## Prerequisites

| Tool    | Version | Check                                                                            |
| ------- | ------- | -------------------------------------------------------------------------------- |
| Node.js | 20.x    | `node -v`                                                                        |
| pnpm    | 9.x     | `pnpm -v` (install: `corepack enable && corepack prepare pnpm@9.0.0 --activate`) |

No Docker needed for local dev — only for the final `ui` container build.

---

## Install

```bash
cd ui
pnpm install
```

---

## Local Dev Server

```bash
pnpm dev
```

Runs on `http://localhost:3000` by default. **API calls won't work standalone** — `lib/api.ts` calls `/api/*`, which only resolves through nginx's proxy (`INFRA.md`). Two options:

1. Run the full stack (`make up` from repo root) and hit the app through nginx's port instead of `pnpm dev`'s port.
2. Add a Next.js dev-only rewrite so `pnpm dev` proxies `/api/*` straight to `localhost:8000` (the `api` container's exposed port) without touching `next.config.mjs`'s `output: 'export'` for prod. Not wired yet — ask if you want this added, it's a few lines in `next.config.mjs` gated on `NODE_ENV === 'development'`.

---

## Lint

```bash
pnpm lint
```

---

## Tests

```bash
pnpm test              # run once
pnpm test:watch        # watch mode
pnpm test:coverage      # enforce the 80% threshold from jest.config.ts
```

Test files live next to what they test (`lib/api.test.ts`, later `components/SongCard.test.tsx`, etc.) — Jest picks up any `*.test.ts(x)` under `src/`.

`lib/api.ts` tests run against `msw`'s mock server (`src/test/server.ts` + `src/test/handlers.ts`), not a real backend. No `docker compose` needed to run these.

---

## Build (static export)

```bash
pnpm build
```

Produces `ui/out/` — the static HTML/JS/CSS that nginx serves in prod. `output: 'export'` in `next.config.mjs` is what makes this a plain folder of files rather than needing a Node server.

To sanity-check the export locally without Docker:

```bash
npx serve out
```

(`serve` isn't a project dependency — this is just a quick manual check, not part of any script.)

---

## Docker Build (full prod image)

From repo root:

```bash
docker compose build ui
docker compose up ui
```

This runs the multi-stage `ui/Dockerfile`: `pnpm install` + `pnpm build` in a `node:20-alpine` build stage, then copies `out/` into an `nginx:alpine` runtime stage with a self-signed HTTPS cert baked in (FE7-10 — see `DECISIONS.md` Sprint 7).

**First-run browser warning is expected**: the cert is self-signed (`CN=melo.local`), so the browser will show an untrusted-certificate warning on first visit. This is a solo/LAN deployment, not a public domain — click through it or add the cert to your OS/browser trust store if the warning bothers you.

Ports: nginx now listens on 80 (redirects to 443) and 443 (TLS). `docker-compose.yml`'s `ui` service port mapping needs updating to match — **flagged, not yet done**, see `TODO.md`.

---

## Directory Map (what goes where)

```
ui/
  src/
    app/                # Next App Router pages + layout.tsx (PlayerProvider mounts here)
    lib/
      api.ts             # typed fetch wrappers, envelope unwrap (FE7-3, done)
      types.ts           # Song/Playlist/Envelope types, ApiError class (FE7-3, done)
    test/
      server.ts          # msw setupServer, shared across all api.ts tests
      handlers.ts        # baseline msw request handlers
      msw-polyfills.ts   # jsdom fetch/Request/Response polyfills for msw@2
  jest.config.ts
  jest.setup.ts          # msw lifecycle (listen/resetHandlers/close)
  tailwind.config.ts      # DESIGN.md tokens ported to Tailwind theme
  next.config.mjs        # output:'export', images.unoptimized
  Dockerfile              # multi-stage: pnpm build → nginx + self-signed cert
  nginx.conf              # 80→443 redirect, /api proxy, /playlists/[id] rewrite
```

---

## Common Gotchas

| Symptom                                                                                      | Cause                                                            | Fix                                                                                                                                                                            |
| -------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `pnpm dev` loads but every API call 404s                                                     | `/api/*` isn't proxied outside of nginx                          | Run through the full Docker stack, or add the dev-rewrite (see Local Dev Server above)                                                                                         |
| Jest fails with `ReadableStream is not defined` or similar msw@2 errors                      | jsdom's fetch primitives predate msw@2's expectations            | Already handled by `src/test/msw-polyfills.ts`, loaded via `jest.config.ts`'s `setupFiles` — if you see this, check that file wasn't accidentally removed                      |
| `pnpm build` succeeds but `/playlists/<real-id>/` 404s when served via plain `npx serve out` | `serve` doesn't know about the nginx rewrite rule                | Expected outside Docker — the client-resolved dynamic route (`DECISIONS.md` Sprint 7) only works behind the real `nginx.conf`. Use the Docker build to test this path for real |
| Browser cert warning on every container rebuild                                              | Self-signed cert regenerates on each image build (not persisted) | Expected — see Docker Build section above. Not a bug                                                                                                                           |
