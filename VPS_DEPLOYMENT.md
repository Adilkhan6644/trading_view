# VPS Deployment Guide

## Option A: Docker (recommended)

1. Install Docker + Docker Compose
2. Upload project to VPS
3. Create `.env` from `.env.example`
4. Build and run:

```bash
docker compose up -d --build
```

5. Check logs:

```bash
docker logs -f trading-alert-bot
```

## Option B: Native Python + systemd

1. Install Python 3.11
2. Clone project
3. Create venv and install deps
4. Configure `.env`
5. Create service file:

```ini
[Unit]
Description=Crypto Trading Alert Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/trading
ExecStart=/opt/trading/.venv/bin/python /opt/trading/main.py
Restart=always
RestartSec=5
User=ubuntu
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

6. Enable service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable trading-alert-bot
sudo systemctl start trading-alert-bot
sudo systemctl status trading-alert-bot
```

## Hardening Tips

- Store `.env` securely and never commit secrets
- Restrict API key permissions to minimum required
- Use firewall + fail2ban
- Monitor disk usage for log growth
