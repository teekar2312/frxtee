# ZeniTrade AI — Next.js dashboard Dockerfile
FROM node:22-slim AS base

WORKDIR /app

# install bun
RUN npm install -g bun

# install deps
COPY package.json bun.lock* ./
RUN bun install --frozen-lockfile

# copy source
COPY . .

# prisma generate + build
RUN bun run db:generate && bun run build

ENV NODE_ENV=production
ENV PORT=3000
EXPOSE 3000

CMD ["bun", "run", "start"]
