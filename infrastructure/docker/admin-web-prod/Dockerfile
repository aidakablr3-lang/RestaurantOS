# apps/admin-web (RestaurantOS staff/admin + guest QR ordering app) --
# production image.
#
# Companion to infrastructure/docker/api-prod/Dockerfile, same shape:
# multi-stage, immutable (source baked in), non-root runtime user, no dev
# tooling in the final image. Containerizing admin-web is a deliberate
# change from the earlier pilot draft (systemd + `next start` directly on
# the host) -- see docs/DEPLOYMENT.md for why this deployment puts it in
# docker-compose.prod.yml instead.
#
# NEXT_PUBLIC_API_BASE_URL is a build ARG, not a runtime environment
# variable -- Next.js inlines every NEXT_PUBLIC_* value into the client
# bundle at `next build` time (see next.config.ts's own comment on
# `output: "standalone"`). Changing it after the image is built requires
# rebuilding the image, not just restarting the container.

# ---- deps ----------------------------------------------------------------
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ---- builder ---------------------------------------------------------------
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
RUN test -n "$NEXT_PUBLIC_API_BASE_URL" || (echo "NEXT_PUBLIC_API_BASE_URL build ARG is required" && exit 1)

RUN npm run build

# ---- runtime -----------------------------------------------------------
FROM node:20-alpine AS runtime

RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 restaurantos

WORKDIR /app
ENV NODE_ENV=production

# `output: "standalone"` produces a self-contained server.js plus only the
# node_modules subset it actually needs -- no full node_modules copy, no
# npm/npx in the runtime image.
COPY --from=builder /app/public ./public
COPY --from=builder --chown=restaurantos:nodejs /app/.next/standalone ./
COPY --from=builder --chown=restaurantos:nodejs /app/.next/static ./.next/static

USER restaurantos
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD node -e "require('http').get('http://127.0.0.1:3000/', r => process.exit(r.statusCode < 500 ? 0 : 1)).on('error', () => process.exit(1))"

CMD ["node", "server.js"]
