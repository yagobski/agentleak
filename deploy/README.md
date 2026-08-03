# Deploying AgentLeak Cloud to agentleak.org

This deploys the hosted, free-for-agents service in **public mode** (quotas,
per-IP throttling, BYOK, secure cookies) behind a reverse proxy, coexisting
with anything already running on the box (e.g. ournia.com).

The app **never binds a public port itself** — it listens on `127.0.0.1:8787`
and a reverse proxy terminates TLS for both hostnames. `https://www.agentleak.org`
is canonical; the apex redirects to the same path on `www`.

## 0. Prerequisites

- Docker + Docker Compose v2 on the server.
- DNS: `A` records for `agentleak.org` and `www.agentleak.org` (and `AAAA` if
  you have IPv6) pointing
  at the server's public IP. Verify before requesting TLS:
  ```bash
  dig +short agentleak.org
  ```
- Decide the proxy path:
  - **The server already runs nginx** (likely, if ournia.com is on nginx) →
    use **Path A**.
  - **The server already runs Apache** → use `deploy/APACHE-DEPLOYMENT.md`.
  - **No web server on 80/443 yet** → use **Path B** (bundled Caddy).

## 1. Get the code and configure

```bash
git clone https://github.com/yagobski/agentleak.git
cd agentleak
cp .env.production.example .env
# Review .env — the defaults are production-safe. Do NOT set any platform
# OPENROUTER_API_KEY (BYOK keeps the free tier free).
```

## 2A. Path A — existing nginx (recommended for the ournia box)

Bring the app up (loopback only, no bundled proxy):

```bash
docker compose up -d --build
curl -fsS http://127.0.0.1:8787/readyz    # {"status":"ready", ...}
```

Add the vhost and provision TLS:

```bash
sudo cp deploy/nginx-agentleak.org.conf /etc/nginx/sites-available/agentleak.org
sudo ln -s /etc/nginx/sites-available/agentleak.org /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d agentleak.org -d www.agentleak.org  # obtains + wires the certificate
```

`certbot` edits the vhost to add TLS. Keep the apex as a path-preserving 301 to
`https://www.agentleak.org`; only the `www` TLS vhost should proxy the app.

## 2B. Path B — bundled Caddy (only if 80/443 are free)

```bash
docker compose --profile caddy up -d --build
```

Caddy obtains and renews the `agentleak.org` certificate automatically. Nothing
else to do.

## 3. Verify

```bash
curl -fsS https://www.agentleak.org/api/health     # {"status":"ok","version":"0.7.x"}
curl -fsS https://www.agentleak.org/api/meta | jq .free_tier

# Full agent flow, end to end:
curl -sX POST https://www.agentleak.org/api/agent/onboard \
  -H 'content-type: application/json' \
  -d '{"email":"smoke@fomox.com","agent_name":"SmokeBot"}'
```

The first account created becomes the **admin** — register your own account
first at `https://www.agentleak.org`, then use the admin console at `/admin`.

## 4. Operations

```bash
docker compose logs -f app          # tail logs
docker compose pull && docker compose up -d --build   # update to a new version
docker compose down                 # stop (data survives in the named volume)
```

**Backups.** All state is the SQLite DB in the `agentleak-data` volume:

```bash
docker run --rm -v agentleak_agentleak-data:/data -v "$PWD":/backup alpine \
  tar czf /backup/agentleak-backup-$(date +%F).tgz -C /data .
```

## 5. Tuning the free tier

Edit `.env` and `docker compose up -d` to apply:

| Variable | Meaning | Default (public) |
|---|---|---|
| `AGENTLEAK_FREE_MONTHLY_QUOTA` | metered actions / account / month (0 = ∞) | 1000 |
| `AGENTLEAK_REGISTER_IP_LIMIT` | sign-ups / IP / hour | 10 |
| `AGENTLEAK_IP_RATE_LIMIT` | requests / IP / minute | 240 |
| `AGENTLEAK_FORCE_BYOK` | never use a platform LLM key | 1 |
| `AGENTLEAK_EXTRAS` | `gui` (lean) or `full` (Presidio) | gui |

## 6. Account recovery

There is no emailed password-reset link: AgentLeak ships no mail
infrastructure and keeps state local. Recovery belongs to whoever owns the
database, which on a hosted instance is you, over SSH:

```bash
docker compose exec app agentleak admin list-users
docker compose exec app agentleak admin reset-password someone@example.com
```

Every session for that account is revoked by the reset, so a stolen cookie
stops working at the same moment.

## 7. Known ceilings of this single-node deployment

This deployment is deliberately one container plus SQLite. That is the right
shape at current scale and it has a documented edge:

| Concern | Where it lives | Ceiling |
|---|---|---|
| Quotas + per-IP throttles | in-process memory | **Correct for one replica only.** Two replicas would each enforce half the limit. Scale up (bigger box) rather than out, or move limits to Redis first. |
| Runs, users, sessions | SQLite in a Docker volume | Comfortable into the low millions of rows; back it up (§4) before it matters. |
| Concurrency | one uvicorn process | CPU-bound analysis serializes. Raise workers only after moving rate limits out of memory. |
| Sessions | server-side rows | Survive restarts; wiped by `docker compose down -v`. |

The practical rule: **do not add a second replica** until quotas and rate
limits are shared state. Everything else scales vertically for now.

## Notes on coexistence with ournia.com

- The app only publishes `127.0.0.1:8787`; it cannot collide with ournia's
  ports and is unreachable from the internet except through the proxy.
- Path A adds a **new** nginx server block — it does not touch existing sites.
- Do **not** enable the Caddy profile on a box that already serves 80/443.
- The container runs as an unprivileged user and writes only to its volume.
