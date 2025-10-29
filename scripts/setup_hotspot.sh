#!/usr/bin/env bash
set -euo pipefail

# Creates a Wi-Fi hotspot on Raspberry Pi 5.
# Preferred path: NetworkManager (Bookworm default). Fallback: hostapd + dnsmasq.

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Please run as root: sudo SSID=PiRTMP PASSWORD=raspberrypi bash scripts/setup_hotspot.sh" >&2
  exit 1
fi

SSID=${SSID:-PiRTMP}
PASSWORD=${PASSWORD:-raspberrypi}
WLAN_IF=${WLAN_IF:-wlan0}
CHANNEL=${CHANNEL:-6}

# Fallback network values when not using NetworkManager shared mode
AP_IP=${AP_IP:-192.168.50.1}
SUBNET_CIDR=${SUBNET_CIDR:-192.168.50.0/24}
DHCP_RANGE=${DHCP_RANGE:-192.168.50.10,192.168.50.200,12h}

is_nm_active() {
  systemctl is-active --quiet NetworkManager 2>/dev/null
}

setup_nm_hotspot() {
  echo "[NM] Setting up hotspot via NetworkManager on $WLAN_IF ..."
  apt-get update -y
  apt-get install -y --no-install-recommends network-manager

  nmcli radio wifi on || true

  # Create or reconfigure the default 'Hotspot' connection
  if nmcli -t -f NAME con show | grep -q "^Hotspot$"; then
    nmcli con delete Hotspot || true
  fi

  nmcli dev wifi hotspot ifname "$WLAN_IF" ssid "$SSID" password "$PASSWORD"
  nmcli con modify Hotspot 802-11-wireless.band bg 802-11-wireless.channel "$CHANNEL"
  # Shared mode provides DHCP/NAT automatically; optionally set a custom IP
  if [[ -n "${AP_IP:-}" ]]; then
    nmcli con modify Hotspot ipv4.addresses "$AP_IP/24" ipv4.method shared
  else
    nmcli con modify Hotspot ipv4.method shared
  fi

  nmcli con up Hotspot
  echo "[NM] Hotspot ready: SSID='$SSID' PASSWORD='$PASSWORD'"
  echo "[NM] IP should be at '$AP_IP' (or 10.42.0.1 if not overridden)."
}

setup_hostapd_dnsmasq() {
  echo "[AP] Setting up hotspot via hostapd + dnsmasq on $WLAN_IF ..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y --no-install-recommends hostapd dnsmasq

  systemctl stop hostapd || true
  systemctl stop dnsmasq || true

  # Configure static IP using dhcpcd (common on Raspberry Pi OS without NetworkManager)
  if command -v dhcpcd >/dev/null 2>&1; then
    if ! grep -q "^interface $WLAN_IF$" /etc/dhcpcd.conf 2>/dev/null; then
      cat >> /etc/dhcpcd.conf <<EOF
interface $WLAN_IF
static ip_address=$AP_IP/24
nohook wpa_supplicant
EOF
    fi
    systemctl restart dhcpcd || true
  else
    ip addr add "$AP_IP/24" dev "$WLAN_IF" || true
    ip link set "$WLAN_IF" up || true
  fi

  # hostapd configuration
  cat > /etc/hostapd/hostapd.conf <<EOF
interface=$WLAN_IF
driver=nl80211
ssid=$SSID
hw_mode=g
channel=$CHANNEL
wmm_enabled=1
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=$PASSWORD
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
EOF

  if grep -q '^#*DAEMON_CONF' /etc/default/hostapd 2>/dev/null; then
    sed -i 's|^#*DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd || true
  else
    echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' >> /etc/default/hostapd
  fi

  # dnsmasq configuration
  mkdir -p /etc/dnsmasq.d
  cat > /etc/dnsmasq.d/wlan0.conf <<EOF
interface=$WLAN_IF
bind-interfaces
dhcp-range=${DHCP_RANGE}
EOF

  systemctl unmask hostapd || true
  systemctl enable hostapd dnsmasq
  systemctl restart hostapd
  systemctl restart dnsmasq

  echo "[AP] Hotspot ready: SSID='$SSID' PASSWORD='$PASSWORD' at $AP_IP"
}

if is_nm_active; then
  setup_nm_hotspot
else
  setup_hostapd_dnsmasq
fi

echo "Done. Connect to the hotspot and use RTMP at rtmp://<pi-ip>:1935/live/cam"


