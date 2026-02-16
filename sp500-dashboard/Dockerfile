# ============================================================
# SP500 Portfolio Dashboard — Multi-stage Docker Build
# ============================================================
# Stage 1: Install dependencies
# Stage 2: Build the Next.js app (with Excel → JSON generation)
# Stage 3: Minimal production runner
# ============================================================

# --- Stage 1: Build ---
FROM node:20-alpine AS builder
WORKDIR /app

# Install ALL dependencies (dev included — needed for TypeScript, Tailwind, etc.)
COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

# Generate static JSON from Excel (prebuild step)
RUN node scripts/generate-data.mjs

# Build Next.js in standalone mode (prebuild runs again via npm script, harmless)
RUN npm run build

# --- Stage 3: Production Runner ---
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV PORT=8080
ENV HOSTNAME="0.0.0.0"

# Create non-root user for security
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy standalone build output
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

# Set ownership
RUN chown -R nextjs:nodejs /app

USER nextjs

EXPOSE 8080

CMD ["node", "server.js"]
