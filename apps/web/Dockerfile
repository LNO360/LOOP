# ── Stage 1: deps ─────────────────────────────────────────────
FROM node:22-alpine AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

# Install pnpm
RUN corepack enable && corepack prepare pnpm@11.3.0 --activate

COPY package.json pnpm-lock.yaml* ./
# strictDepBuilds=false: don't fail on unreviewed native build scripts
# (sharp/msw/unrs-resolver). sharp's prebuilt musl binary is fetched as a
# regular dependency, so skipping the build script is safe here.
RUN pnpm install --no-frozen-lockfile --config.strictDepBuilds=false

# ── Stage 2: builder ───────────────────────────────────────────
FROM node:22-alpine AS builder
WORKDIR /app

RUN corepack enable && corepack prepare pnpm@11.3.0 --activate

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build args become env vars at build time (public vars embedded in JS bundle)
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_WS_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL

# Disable telemetry
ENV NEXT_TELEMETRY_DISABLED=1

# Invoke next directly instead of `pnpm build` — `pnpm run` performs a pre-run
# deps-status-check that re-runs install and trips ERR_PNPM_IGNORED_BUILDS on
# pnpm 11. Calling the binary skips that wrapper entirely.
RUN node_modules/.bin/next build

# ── Stage 3: runner ────────────────────────────────────────────
FROM node:22-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs \
 && adduser  --system --uid 1001 nextjs

# Copy built artifacts
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD wget -qO- http://127.0.0.1:3000/login || exit 1

CMD ["node", "server.js"]
