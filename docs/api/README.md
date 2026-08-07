# API schema exports

`openapi.json` is generated from `services/api`'s live FastAPI route
definitions -- not hand-written, never edit it directly. Regenerate
after any change to a route's request/response shape:

```bash
cd services/api
JWT_PRIVATE_KEY=dummy JWT_PUBLIC_KEY=dummy python scripts/export_openapi.py
```

Also available live from a running instance at `/openapi.json`
(FastAPI serves this automatically; nothing extra required), and as
interactive docs at `/docs` (Swagger UI) and `/redoc`. The committed
file exists so the schema is diffable in code review and usable by
external tooling (client generators, API documentation sites) without
a server running.

Nothing currently enforces this file staying in sync with the code
automatically (see `docs/RELEASE_CHECKLIST.md`) -- treat "did you
regenerate this?" as a PR review question until CI does.
