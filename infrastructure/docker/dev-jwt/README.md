# Development-only JWT keypair

`private.pem` / `public.pem` in this directory are a fixed RS256 keypair
used **only** by `docker-compose.yml` for local development, so
`docker compose up` works out of the box with zero setup.

**Never used for anything but a developer's own local Postgres instance
with fake/seeded data.** Not staging, not production. A real deployment
generates and manages its own keypair through a secrets manager (see
`docs/RELEASE_CHECKLIST.md` and Technical Architecture v2.0 §7.4) --
this pair is deliberately committed to the repo precisely because it
must never protect anything real.

Regenerate anytime with:

```bash
openssl genrsa -out private.pem 2048
openssl rsa -in private.pem -pubout -out public.pem
```
