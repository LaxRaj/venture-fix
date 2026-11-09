#!/usr/bin/env bash
# One-shot setup for a fresh Ubuntu server (Oracle Cloud Always Free ARM, or any ~$4 VPS).
# Run as root:  sudo bash deploy/setup.sh https://github.com/<you>/venture-fix.git worktree-agent-fleet
# Untested against a live server; read it before running.
set -euo pipefail
REPO="${1:?usage: setup.sh <git-url> [branch]}"
BRANCH="${2:-main}"

apt-get update
apt-get install -y python3 git curl debian-keyring debian-archive-keyring apt-transport-https gpg

# Caddy from its official apt repo (see caddyserver.com/docs/install if these URLs have moved)
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update && apt-get install -y caddy
fi

id fleet >/dev/null 2>&1 || useradd --system --home /opt/venture-fix --shell /usr/sbin/nologin fleet
if [ ! -d /opt/venture-fix/.git ]; then git clone --branch "$BRANCH" "$REPO" /opt/venture-fix; else git -C /opt/venture-fix pull --ff-only; fi
mkdir -p /opt/venture-fix/runs
chown -R fleet:fleet /opt/venture-fix/runs

if [ ! -f /etc/fleet.env ]; then
  install -m 600 -o root -g root /opt/venture-fix/deploy/env.example /etc/fleet.env
  python3 - <<'PY'
import re, secrets
p = "/etc/fleet.env"
t = open(p).read()
t = re.sub(r"(?m)^FLEET_ADMIN_TOKEN=.*$", "FLEET_ADMIN_TOKEN=" + secrets.token_urlsafe(32), t)
open(p, "w").write(t)
PY
  echo ">> Edit /etc/fleet.env: model key + tiers, SMTP, FLEET_HOST. The admin token was generated for you."
fi

install -m 644 /opt/venture-fix/deploy/fleet.service /etc/systemd/system/fleet.service
install -m 755 /opt/venture-fix/deploy/backup.sh /usr/local/bin/fleet-backup
echo '17 3 * * * fleet /usr/local/bin/fleet-backup' > /etc/cron.d/fleet-backup

# Caddy reads FLEET_HOST from the same env file
mkdir -p /etc/systemd/system/caddy.service.d
printf '[Service]\nEnvironmentFile=/etc/fleet.env\n' > /etc/systemd/system/caddy.service.d/env.conf
install -m 644 /opt/venture-fix/deploy/Caddyfile /etc/caddy/Caddyfile

# Oracle's Ubuntu images ship iptables rules that block 80/443 even after the cloud security list is opened
if command -v iptables >/dev/null; then
  iptables -C INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null || iptables -I INPUT 6 -p tcp --dport 80 -j ACCEPT
  iptables -C INPUT -p tcp --dport 443 -j ACCEPT 2>/dev/null || iptables -I INPUT 6 -p tcp --dport 443 -j ACCEPT
  command -v netfilter-persistent >/dev/null && netfilter-persistent save || true
fi

systemctl daemon-reload
echo ">> After editing /etc/fleet.env:  systemctl enable --now fleet && systemctl restart caddy"
echo ">> Admin token: grep FLEET_ADMIN_TOKEN /etc/fleet.env"
