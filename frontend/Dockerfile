# syntax=docker/dockerfile:1.7

# ---------- deps ----------
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund


# ---------- builder ----------
FROM node:20-alpine AS builder
WORKDIR /app

# `next build` reads NEXT_PUBLIC_* at build time and inlines them.
# In our case the only one is NEXT_PUBLIC_API_URL — pass it via --build-arg
# in compose so SSR + browser both target the right backend.
ARG NEXT_PUBLIC_API_URL=http://api:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN npm run build


# ---------- runtime ----------
FROM node:20-alpine AS runtime
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000

RUN addgroup -S nextjs && adduser -S nextjs -G nextjs

# Standalone output bundles only the files needed at runtime.
COPY --from=builder --chown=nextjs:nextjs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nextjs /app/.next/static ./.next/static
# `public/` may be empty / missing — bundle whatever exists.
COPY --from=builder --chown=nextjs:nextjs /app/public/ ./public/

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD wget -qO- http://127.0.0.1:${PORT}/ >/dev/null 2>&1 || exit 1

CMD ["node", "server.js"]
