#!/usr/bin/env bash
# RestaurantOS deploy step 1/4 -- initial server hardening + Docker install.
#
# Target: Ubuntu 24.04, 2 vCPU / 6GB RAM / 150GB disk, single node.
# Run once, as root (or via sudo), on a fresh VPS before anything else in
# scripts/deploy/. Idempotent-ish: safe to re-run (apt/ufw/systemctl
# calls below are all no-ops or reconciling on a system that already has
# them applied), but it is written for a fresh box, not audited against
# every possible prior state.
#
# What this does, in order:
#   1. apt update/upgrade
#   2. ufw: deny all incoming by default, allow 22 (ssh) / 80 / 443 only
#   3. fail2ban: install, enable the sshd jail
#   4. unattended-upgrades: install, enable automatic security updates
#   5. Docker Engine + Compose plugin (needed by every later step --
#      not explicitly asked for, but nothing here runs without it)
#
# Does NOT touch SSH config itself (key-only auth, disabling root login,
# etc.) -- out of scope for this pass; a reasonable follow-up, but higher
# blast-radius (a mistake here can lock you out) and not something to
# improvise without you present at the console.

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root (or with sudo)." >&2
    exit 1
fi

echo "==> Updating system packages"
apt-get update
apt-get -y upgrade

echo "==> Installing ufw, fail2ban, unattended-upgrades, and Docker prerequisites"
apt-get install -y --no-install-recommends \
    ufw fail2ban unattended-upgrades \
    ca-certificates curl gnupg

echo "==> Configuring firewall (22/80/443 only)"
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
ufw status verbose

echo "==> Enabling fail2ban's sshd jail"
cat > /etc/fail2ban/jail.local <<'EOF'
[sshd]
enabled = true
port = 22
backend = systemd
EOF
systemctl enable --now fail2ban
systemctl restart fail2ban

echo "==> Enabling unattended security upgrades"
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF
systemctl enable --now unattended-upgrades

echo "==> Installing Docker Engine + Compose plugin"
if ! command -v docker >/dev/null 2>&1; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
        $(. /etc/os-release && echo "${VERSION_CODENAME}") stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
else
    echo "Docker already installed, skipping."
fi

echo "==> Server setup complete."
echo "Verify: docker --version && docker compose version && ufw status && systemctl is-active fail2ban unattended-upgrades"
echo "Next: scripts/deploy/02_generate_secrets.sh"
