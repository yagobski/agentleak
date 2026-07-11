# Deploying AgentLeak Cloud to agents.fomox.com

This deploys the hosted, free-for-agents service in **public mode** (quotas,
per-IP throttling, BYOK, secure cookies) behind a reverse proxy, coexisting
with anything already running on the box (e.g. ournia.com).

The app **never binds a public port itself** — it listens on `127.0.0.1:8787`
and a reverse proxy terminates TLS for `agents.fomox.com`.

## 0. Prerequisites

- Docker + Docker Compose v2 on the server.
- DNS: an `A` (and `AAAA` if you have IPv6) record for `agents.fomox.com` pointing
  at the server's public IP. Verify before requesting TLS:
  ```bash
  dig +short agents.fomox.com
  ```
- Decide the proxy path:
  - **The server already runs nginx** (likely, if ournia.com is on nginx) →
    use **Path A**.
  - **The server already runs Apache** → use `deploy/APACHE-DEPLOYMENT.md`.
  - **No web server on 80/443 yet** → use **Path B** (bundled Caddy).

## 1. Get the code and configure

```bash
git clone https://github.com/yagobski/agentleak-oss.git
cd agentleak-oss
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
sudo cp deploy/nginx-agents.fomox.com.conf /etc/nginx/sites-available/agents.fomox.com
sudo ln -s /etc/nginx/sites-available/agents.fomox.com /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d agents.fomox.com     # obtains + wires the certificate
```

`certbot` edits the vhost to add the TLS block and the 80→443 redirect. Done.

## 2B. Path B — bundled Caddy (only if 80/443 are free)

```bash
docker compose --profile caddy up -d --build
```

Caddy obtains and renews the `agents.fomox.com` certificate automatically. Nothing
else to do.

## 3. Verify

```bash
curl -fsS https://agents.fomox.com/api/health     # {"status":"ok","version":"0.7.x"}
curl -fsS https://agents.fomox.com/api/meta | jq .free_tier

# Full agent flow, end to end:
curl -sX POST https://agents.fomox.com/api/agent/onboard \
  -H 'content-type: application/json' \
  -d '{"email":"smoke@fomox.com","agent_name":"SmokeBot"}'
```

The first account created becomes the **admin** — register your own account
first at `https://agents.fomox.com`, then use the admin console at `/admin`.

## 4. Operations

```bash
docker compose logs -f app          # tail logs
docker compose pull && docker compose up -d --build   # update to a new version
docker compose down                 # stop (data survives in the named volume)
```

**Backups.** All state is the SQLite DB in the `agentleak-data` volume:

```bash
docker run --rm -v agentleak-oss_agentleak-data:/data -v "$PWD":/backup alpine \
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

## Notes on coexistence with ournia.com

- The app only publishes `127.0.0.1:8787`; it cannot collide with ournia's
  ports and is unreachable from the internet except through the proxy.
- Path A adds a **new** nginx server block — it does not touch existing sites.
- Do **not** enable the Caddy profile on a box that already serves 80/443.
- The container runs as an unprivileged user and writes only to its volume.
