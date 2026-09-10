FROM node:22-alpine AS deps
ARG NPM_REGISTRY=https://registry.npmjs.org/
WORKDIR /app
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml* ./
COPY packages/contracts/package.json ./packages/contracts/package.json
COPY apps/web/package.json ./apps/web/package.json
RUN corepack enable && pnpm config set registry "$NPM_REGISTRY" && pnpm install --frozen-lockfile=false

FROM deps AS build
ARG VITE_API_BASE_URL=
COPY packages/contracts ./packages/contracts
COPY apps/web ./apps/web
RUN pnpm --filter @surgepilot/web build

FROM nginx:1.27-alpine
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/apps/web/dist /usr/share/nginx/html
EXPOSE 80
