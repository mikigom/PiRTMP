#!/usr/bin/env bash
set -euo pipefail

# Installs a systemd service to auto-start the RTMP streamer on boot.

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Please run as root: sudo SERVER_URL=rtmp://10.42.0.1/live STREAM_KEY=cam bash scripts/install_streamer_service.sh" >&2
  exit 1
fi

# Parameters (can be overridden by environment)
SERVER_URL=${SERVER_URL:-rtmp://10.42.0.1/live}
STREAM_KEY=${STREAM_KEY:-cam}
DEVICE=${DEVICE:-/dev/video0}
WIDTH=${WIDTH:-1280}
HEIGHT=${HEIGHT:-720}
FPS=${FPS:-30}
BITRATE=${BITRATE:-2500k}
INPUT_FORMAT=${INPUT_FORMAT:-mjpeg}
ENCODER=${ENCODER:-h264_v4l2m2m}
USER_NAME=${USER_NAME:-${SUDO_USER:-pi}}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

SERVICE_PATH=/etc/systemd/system/rtmp-streamer.service

cat > "$SERVICE_PATH" <<EOF
[Unit]
Description=RTMP Webcam Streamer
After=network-online.target nginx.service
Wants=network-online.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$REPO_ROOT
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 $REPO_ROOT/streamer/stream_to_rtmp.py \
  --device $DEVICE \
  --resolution ${WIDTH}x${HEIGHT} \
  --fps $FPS \
  --bitrate $BITRATE \
  --server $SERVER_URL \
  --stream-key $STREAM_KEY \
  --input-format $INPUT_FORMAT \
  --encoder $ENCODER
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable rtmp-streamer.service

echo "Installed service at $SERVICE_PATH"
echo "Enable and start now: sudo systemctl enable --now rtmp-streamer.service"


