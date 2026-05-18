# Run the Trading Bot with Docker

## Prerequisites

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Mac)
2. Ensure Docker is running (`docker --version`)

## Quick start

### 1. Configure `.env`

If you do not have `.env` yet:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set at minimum:

- `API_KEY` / `API_SECRET` (Binance)
- Alert channel (Telegram, Discord, or ntfy) if you want notifications

For Docker, you do **not** need to change `DASHBOARD_HOST` — `docker-compose.yml` sets `0.0.0.0` automatically.

### 2. Build and run

From the project folder:

```powershell
cd C:\Users\adilk\Desktop\trading
docker compose up -d --build
```

### 3. Open the dashboard

In your browser:

- **Dashboard:** http://localhost:8000
- **API docs:** http://localhost:8000/docs

Click **Start Live Feed** in the UI to begin scanning.

### 4. View logs

```powershell
docker compose logs -f
```

Stop following logs with `Ctrl+C`.

### 5. Stop the bot

```powershell
docker compose down
```

---

## Useful commands

| Command | Description |
|---------|-------------|
| `docker compose up -d --build` | Build image and start in background |
| `docker compose logs -f` | Follow live logs |
| `docker compose restart` | Restart container |
| `docker compose down` | Stop and remove container |
| `docker compose ps` | Show running status |

---

## Change the port

If port `8000` is already in use on your PC, edit `docker-compose.yml`:

```yaml
ports:
  - "8001:8000"
```

Then open http://localhost:8001

---

## Persisted data

These folders on your machine are mounted into the container:

| Host folder | Contents |
|-------------|----------|
| `./logs` | `bot.log` |
| `./data` | `alerts.csv` |

---

## Auto-start scanner on launch

In `.env`:

```env
AUTO_START_BOT=true
```

Then rebuild:

```powershell
docker compose up -d --build
```

---

## Share access with someone outside your PC

Yes — Docker can expose the dashboard to others. Your compose file already publishes port **8000** on all network interfaces (`0.0.0.0`).

**Always set a password first** in `.env`:

```env
DASHBOARD_USERNAME=yourfriend
DASHBOARD_PASSWORD=use_a_strong_password_here
```

Restart:

```powershell
docker compose up -d --build
```

The browser will ask for username/password before showing the dashboard.

### Option A — Same Wi‑Fi / office network (LAN)

1. Find your PC IP: `ipconfig` → IPv4 (e.g. `192.168.1.50`)
2. Allow port 8000 in **Windows Firewall** (Inbound rule → TCP 8000)
3. Share: `http://192.168.1.50:8000`

### Option B — Internet via cloud VPS (recommended for 24/7)

1. Rent a small VPS (DigitalOcean, AWS, Hetzner, etc.)
2. Install Docker on the server
3. Copy project + `.env` to the VPS
4. Open **TCP 8000** in the VPS firewall / security group
5. Share: `http://YOUR_SERVER_IP:8000`

Use **HTTPS** in production (Caddy/Nginx reverse proxy + free SSL).

### Option C — Tunnel without opening router ports (quick test)

Use [ngrok](https://ngrok.com) or [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/):

```powershell
ngrok http 8000
```

Share the `https://....ngrok.io` URL (still use dashboard username/password).

### Option D — Private VPN (safest for one person)

[Tailscale](https://tailscale.com): install on your PC and their device → share `http://100.x.x.x:8000` (only visible on your private network).

### Security warnings

- Do **not** expose the dashboard without `DASHBOARD_USERNAME` / `DASHBOARD_PASSWORD`
- Never commit `.env` (contains Binance API keys)
- Prefer VPN or HTTPS tunnel over raw public HTTP
- Anyone with access can **start/stop** the scanner via the UI

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `port is already allocated` | Change host port in `docker-compose.yml` or stop the other app using 8000 |
| Dashboard not loading | Use http://localhost:8000 (not 127.0.0.1 inside container) |
| No market data | Check API keys in `.env`; try `BINANCE_WS_MARKET=spot` |
| Container exits immediately | Run `docker compose logs` and fix `.env` / API errors |

---

## Run without Compose (optional)

```powershell
docker build -t trading-alert-bot .
docker run -d --name trading-alert-bot -p 8000:8000 --env-file .env -v ${PWD}/logs:/app/logs -v ${PWD}/data:/app/data -e DASHBOARD_HOST=0.0.0.0 trading-alert-bot
```
