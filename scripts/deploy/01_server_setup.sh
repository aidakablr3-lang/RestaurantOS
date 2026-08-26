#!/usr/bin/env bash
# RestaurantOS deploy step 1/4 -- initial server hardening + Docker install.
#
# Target: Ubuntu 24.04, single node -- written for the original 2 vCPU /
# 6GB / 150GB plan, actually deployed on a 2 vCPU / 4GB / 80GB Lightsail
# instance. The 2GB swapfile below exists specifically because of that
# smaller-than-planned RAM.
# Run once, as root (or via sudo), on a fresh VPS before anything else in
# scripts/deploy/. Idempotent-ish: safe to re-run (apt/ufw/systemctl
# calls below are all no-ops or reconciling on a system that already has
# them applied), but it is written for a fresh box, not audited against
# every possible prior state.
#
# What this does, in order:
#   1. apt update/upgrade
#   2. 2GB swapfile -- a box with 4GB RAM runs the stack fine at idle,
#      but `docker compose build admin-web` (next build) is memory-
#      hungry enough to risk an OOM kill without headroom
#   3. ufw: deny all incoming by default, allow 22 (ssh) / 80 / 443 only
#   4. fail2ban: install, enable the sshd jail
#   5. unattended-upgrades: install, enable automatic security updates
#   6. Docker Engine + Compose plugin (needed by every later step --
#      not explicitly asked for, but nothing here runs without it)
#   7. AWS CLI v2 -- backup.sh needs it for the S3 off-host copy (see
#      docs/DEPLOYMENT.md's Backup section)
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

echo "==> Configuring 2GB swap"
if swapon --show | grep -q .; then
    echo "Swap already active, skipping."
else
    fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
    # Low swappiness -- swap exists as headroom for the occasional build
    # spike, not as routine memory pressure relief during normal serving.
    echo "vm.swappiness=10" > /etc/sysctl.d/99-swappiness.conf
    sysctl --system >/dev/null
    swapon --show
fi

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

echo "==> Installing AWS CLI v2"
if ! command -v aws >/dev/null 2>&1; then
    apt-get install -y --no-install-recommends unzip
    tmp_dir="$(mktemp -d)"
    curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-$(uname -m).zip" -o "$tmp_dir/awscliv2.zip"
    unzip -q "$tmp_dir/awscliv2.zip" -d "$tmp_dir"
    "$tmp_dir/aws/install"
    rm -rf "$tmp_dir"
else
    echo "AWS CLI already installed, skipping."
fi

echo "==> Server setup complete."
echo "Verify: docker --version && docker compose version && aws --version && ufw status && systemctl is-active fail2ban unattended-upgrades"
echo "Next: scripts/deploy/02_generate_secrets.sh"
