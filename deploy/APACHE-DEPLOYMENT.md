# Deploying AgentLeak Cloud behind Apache (instead of nginx/Caddy)

`deploy/README.md` covers the nginx and bundled-Caddy paths. Use this guide
instead if your server's reverse proxy is **Apache** — the deployment shape is
identical (a loopback-only Docker container behind a TLS-terminating vhost),
only the vhost syntax and commands differ.

This is written from real-world experience deploying AgentLeak on a shared
Apache box alongside several unrelated existing sites — the naming gotcha in
§3 is a genuine trap, not a hypothetical.

---

## 0. Prerequisites

- Docker + Docker Compose v2 on the server.
- Apache 2.4 with `proxy`, `proxy_http`, `proxy_wstunnel`, `headers`, `rewrite`,
  and `ssl` modules enabled:
  ```bash
  sudo a2enmod proxy proxy_http proxy_wstunnel headers rewrite ssl
  ```
- `certbot` with the Apache plugin (`sudo apt install certbot python3-certbot-apache`).
- DNS: `A` records for `agentleak.org` and `www.agentleak.org` pointing at the
  server's public IP. The canonical public host is `www`; the apex is redirect-only.
  Verify both before requesting TLS:
  ```bash
  dig +short agentleak.org
  ```
- **If the server already hosts other sites**, confirm your target port and
  subdomain are actually free before touching anything:
  ```bash
  sudo ss -tlnp | grep ':8787 '                 # the port you're about to use
  sudo apache2ctl -S | grep agentleak.org     # no existing vhost for it
  ```

## 1. Get the code and configure

```bash
git clone https://github.com/yagobski/agentleak-oss.git
cd agentleak-oss
cp .env.production.example .env
# Review .env — defaults are production-safe. Do NOT set a platform
# OPENROUTER_API_KEY (BYOK is what keeps the free tier free).
```

## 2. Build and start the container (loopback only)

```bash
docker compose build
docker compose up -d
curl -fsS http://127.0.0.1:8787/readyz    # {"status":"ready", ...}
```

The container publishes `127.0.0.1:8787` **only** — it is never reachable from
the internet except through the reverse proxy you configure next.

## 3. Apache vhost — mind the alphabetical-ordering trap

Debian/Ubuntu Apache loads `sites-enabled/*.conf` in **alphabetical order**,
and the *first* vhost defined for a given `IP:port` silently becomes that
port's *default* server — used for any TLS connection whose SNI doesn't match
a real vhost. On a box with existing sites, a plainly-named new vhost file can
accidentally become the server-wide default and intercept unrelated traffic.

**Always prefix a new vhost file so it sorts last**, e.g. `zzz-<name>.conf`:

```bash
sudo tee /etc/apache2/sites-available/zzz-agentleak.conf >/dev/null << 'CONF'
<VirtualHost *:80>
    ServerName agentleak.org
    ServerAdmin admin@fomox.com

    Redirect permanent / https://www.agentleak.org/

    ErrorLog ${APACHE_LOG_DIR}/agentleak-error.log
    CustomLog ${APACHE_LOG_DIR}/agentleak-access.log combined
</VirtualHost>

<VirtualHost *:80>
    ServerName www.agentleak.org
    ServerAdmin admin@fomox.com

    ProxyPreserveHost On
    ProxyRequests Off
    ProxyTimeout 300

    # Serve ACME http-01 challenges from disk; proxy everything else until
    # Certbot creates the canonical HTTPS vhost and HTTP redirect.
    DocumentRoot /var/www/html
    ProxyPass /.well-known/acme-challenge/ !
    ProxyPass / http://127.0.0.1:8787/
    ProxyPassReverse / http://127.0.0.1:8787/
    RequestHeader set X-Forwarded-Proto "http"

    ErrorLog ${APACHE_LOG_DIR}/agentleak-error.log
    CustomLog ${APACHE_LOG_DIR}/agentleak-access.log combined
</VirtualHost>
CONF

sudo a2ensite zzz-agentleak
sudo apache2ctl configtest        # MUST print "Syntax OK" before reloading
sudo systemctl reload apache2     # graceful — doesn't drop other sites' connections
```

If the server has other sites, verify they're unaffected before moving on:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://<some-other-site-you-host>/
```

## 4. TLS via certbot's Apache plugin

```bash
sudo certbot --apache -d agentleak.org -d www.agentleak.org --non-interactive --agree-tos \
  -m admin@fomox.com --redirect
```

Keep two Certbot-generated `*:443` vhosts. The apex vhost contains only a
path-preserving redirect; the `www` vhost proxies the application and sets the
external scheme explicitly:

```apache
RequestHeader set X-Forwarded-Proto "https"
```

Use `Redirect permanent / https://www.agentleak.org/` in the apex TLS vhost.
Apache appends the unmatched path and preserves the query string.

This obtains the certificate, writes a new
`sites-available/zzz-agentleak-le-ssl.conf`-style vhost (certbot names it after
your original file, so it inherits the `zzz-` prefix automatically), and adds
the HTTP→HTTPS redirect. If certbot ever produces a file *without* your prefix
(e.g. after re-running with a different base name), rename it and re-enable
the same way as in §3 — the ordering trap applies to the `:443` vhost too.

Certbot's renewal config does not hardcode the vhost file path — it re-parses
the live Apache config by `ServerName` on every renewal — so renaming vhost
files after the fact is safe. Confirm auto-renewal is active:

```bash
systemctl is-active certbot.timer
```

## 5. Verify

```bash
curl -s https://www.agentleak.org/api/health
curl -s https://www.agentleak.org/api/meta | jq .free_tier

curl -sX POST https://www.agentleak.org/api/agent/onboard \
  -H 'content-type: application/json' \
  -d '{"email":"you@example.com","agent_name":"SmokeTest"}'
```

Sign in at `https://www.agentleak.org` with your own account **first** — the
first account created on a fresh instance becomes the platform admin.

---

## Updating to new code

```bash
cd agentleak-oss
git pull
docker compose up -d --build
sleep 6
curl -fsS http://127.0.0.1:8787/readyz
```

The SQLite database lives in the named Docker volume, so it survives rebuilds
— only `docker compose down -v` (or `docker volume rm`) destroys it.

## Operations

See `deploy/README.md` §4–5 for logs, backups, and free-tier tuning — those
are proxy-agnostic and apply here unchanged.
