# Short SOCHI SHOW URLs — staging only

Goal:
- `https://sochi.hijackpoker.ru/` → projector screen (browser address stays short)
- `https://sochi.hijackpoker.ru/admin` → organizer login (browser address stays short)
- `/sochi/api/*` and `/sochi/static/*` remain internal application paths.

**Do not touch existing JACKSIDE/Timer services, databases, or Nginx vhosts.**

## Preconditions

1. DNS A: `sochi.hijackpoker.ru` → `104.171.137.159` (confirm this is the actual server's public IP).
2. `/opt/sochi-show` exists and `curl -fsS http://127.0.0.1:8092/health` returns OK.
3. Debian/Ubuntu Nginx, Certbot, and `/etc/nginx/proxy_params` are present.
4. Before changing any configuration, inspect existing hostname and port-80 bindings with `sudo nginx -T`; avoid duplicate `server_name`.

## Safe deployment order (DNS first)

1. `git fetch origin main` and inspect changes with `git diff HEAD..origin/main -- deploy/`. Do not update running app until approved.
2. Create `/var/www/sochi-certbot/.well-known/acme-challenge/`; enable the temporary `deploy/sochi-bootstrap.nginx.example` as a *new* Nginx site only if no server_name collision.
3. Run `sudo nginx -t`, then `sudo systemctl reload nginx`. Obtain a certificate with `sudo certbot certonly --webroot -w /var/www/sochi-certbot -d sochi.hijackpoker.ru`.
4. Remove only the temporary Sochi bootstrap site; enable `deploy/nginx.sochi.example` as the new dedicated site. Test Nginx before reloading.
5. Change only `SOCHI_SECURE_COOKIE=true` in `/opt/sochi-show/.env`, then restart only `sochi-show.service`. Do not expose the admin UI over plaintext HTTP.
6. Validate HTTPS on `/`, `/admin`, `/sochi/api/public/state`; verify that public API never reveals draft Secret Jacks. Test login through HTTPS. Confirm existing domains continue to respond normally.
7. Keep separate SOCHI SHOW database backups and a copy of its previous service configuration.

## Rollback

Disable only the newly created Sochi HTTPS vhost, validate and reload Nginx; restore its previous Sochi .env + service settings if needed. Never stop/restart JACKSIDE or Timer. Short aliases are Nginx-only; Python API routes remain unchanged.

> A plain `curl -I` sends HEAD, which can return 405 for a FastAPI route restricted to GET. Use `curl -i -X GET` when checking app pages.
