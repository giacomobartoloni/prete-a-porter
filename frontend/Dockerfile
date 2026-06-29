# Frontend Dockerfile — Next.js app on port 3000

FROM node:22-slim AS base
RUN apt-get update && apt-get install -y openssl && rm -rf /var/lib/apt/lists/*
WORKDIR /app

# Stage 1: Install dependencies (cached unless package.json changes)
COPY package.json package-lock.json ./
RUN npm install
RUN npm install @next/swc-linux-arm64-gnu @next/swc-linux-x64-gnu --no-save || true

# Stage 2: Generate Prisma client (needs DATABASE_URL for schema validation)
ENV DATABASE_URL="file:./dev.db"
COPY prisma/ ./prisma/
RUN npx prisma generate

# Stage 3: Build (cached unless source code changes)
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
ENV DATABASE_URL="file:./dev.db"
RUN npm run build

# Stage 4: Run
EXPOSE 3000
CMD ["sh", "-c", "npx prisma db push --skip-generate && npm run start"]
