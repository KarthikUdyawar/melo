# ── Build stage ─────────────────────────────────────────────────────
FROM node:20-alpine AS build

RUN corepack enable && corepack prepare pnpm@9.0.0 --activate

WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm build
# `pnpm build` with next.config.mjs's output:'export' produces /app/out

# ── Runtime stage ───────────────────────────────────────────────────
FROM nginx:alpine

# Self-signed cert baked into the image (FE7-10) — solo/LAN box, no
# public domain to validate a real cert against. Browser will show a
# one-time self-signed warning; expected, not a bug.
RUN apk add --no-cache openssl \
    && mkdir -p /etc/nginx/ssl \
    && openssl req -x509 -nodes -days 3650 \
       -newkey rsa:2048 \
       -keyout /etc/nginx/ssl/melo-selfsigned.key \
       -out /etc/nginx/ssl/melo-selfsigned.crt \
       -subj "/CN=melo.local" \
    && chown -R nginx:nginx /etc/nginx/ssl

RUN chown -R nginx:nginx /var/cache/nginx \
    && chown -R nginx:nginx /var/log/nginx \
    && chown -R nginx:nginx /etc/nginx/conf.d \
    && touch /var/run/nginx.pid \
    && chown -R nginx:nginx /var/run/nginx.pid \
    && chown -R nginx:nginx /usr/share/nginx/html

COPY --from=build /app/out /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

USER nginx

EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
