# Development-only JWT keypair

`docker-compose.yml`'s `api` service reads an RS256 keypair from
`private.pem`/`public.pem` in this directory. **These files are not
committed** -- generate your own local copy before your first
`docker compose up`:

```bash
./infrastructure/docker/dev-jwt/generate-dev-keys.sh
```

(or `generate-dev-keys.py` if you don't have `openssl` on your `PATH`
but do have Python -- same output, either one works.)

This is idempotent and safe to re-run: if a keypair already exists it
does nothing and tells you so. Delete `private.pem`/`public.pem` and
re-run to rotate it.

**Never used for anything but a developer's own local Postgres instance
with fake/seeded data.** Not staging, not production. A real deployment
generates and manages its own keypair through a secrets manager (see
`docs/RELEASE_CHECKLIST.md` and Technical Architecture v2.0 §7.4).

`.gitignore` excludes `*.pem` in this directory specifically so a
generated key can never end up committed by accident.
