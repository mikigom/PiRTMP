#!/usr/bin/env bash
set -euo pipefail

# Installs Nginx with RTMP module and deploys RTMP config

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Please run as root: sudo bash scripts/install_rtmp_server.sh" >&2
  exit 1
fi

echo "[1/4] Updating package lists..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y

echo "[2/4] Installing nginx, libnginx-mod-rtmp, ffmpeg..."
apt-get install -y --no-install-recommends nginx libnginx-mod-rtmp ffmpeg

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "[3/4] Deploying RTMP config at main level and wiring include ..."
install -m 0644 "$REPO_ROOT/config/nginx/rtmp.conf" /etc/nginx/rtmp.conf

# Ensure rtmp.conf is included at top-level (outside 'http' block)
if ! grep -qE '^\s*include\s+/etc/nginx/rtmp.conf;\s*$' /etc/nginx/nginx.conf; then
  cp /etc/nginx/nginx.conf "/etc/nginx/nginx.conf.bak.$(date +%Y%m%d%H%M%S)"
  # Insert include before the first 'http {' block if present; else append at end
  if grep -qE '^[[:space:]]*http[[:space:]]*\{' /etc/nginx/nginx.conf; then
    sed -i '/^[[:space:]]*http[[:space:]]*{/i include /etc/nginx/rtmp.conf;' /etc/nginx/nginx.conf
  else
    echo "include /etc/nginx/rtmp.conf;" >> /etc/nginx/nginx.conf
  fi
fi

# Ensure the RTMP dynamic module is loaded only if not already enabled.
# Debian/Ubuntu often auto-enable it via /etc/nginx/modules-enabled/50-mod-rtmp.conf
RTMP_LOADED=false
if grep -qE '^\s*load_module\s+.*ngx_rtmp_module\.so;' /etc/nginx/nginx.conf 2>/dev/null; then
  RTMP_LOADED=true
fi
if [[ -d /etc/nginx/modules-enabled ]] && \
   grep -RqsE '^\s*load_module\s+.*ngx_rtmp_module\.so;' /etc/nginx/modules-enabled; then
  RTMP_LOADED=true
fi
if [[ "$RTMP_LOADED" != true ]]; then
  MOD_PATH="$(dpkg -L libnginx-mod-rtmp 2>/dev/null | grep -E '/ngx_rtmp_module\.so$' | head -n 1 || true)"
  if [[ -n "${MOD_PATH:-}" ]]; then
    cp /etc/nginx/nginx.conf "/etc/nginx/nginx.conf.bak.$(date +%Y%m%d%H%M%S).rtmp"
    # Prepend a load_module line at the very top (must appear before any blocks)
    sed -i "1iload_module ${MOD_PATH};" /etc/nginx/nginx.conf
  fi
fi

# Remove any misplaced RTMP config under conf.d (invalid context)
if [[ -f /etc/nginx/conf.d/rtmp.conf ]]; then
  rm -f /etc/nginx/conf.d/rtmp.conf
fi

echo "[4/4] Testing and restarting nginx..."
nginx -t
systemctl enable nginx
systemctl restart nginx

echo "Done. RTMP is available at rtmp://<this-pi-ip>:1935/live/<stream-key>"


