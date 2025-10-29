Camera RTMP Streaming on Raspberry Pi 5

Overview

This project captures video from `/dev/video0` at HD resolution (1280x720) and 30 FPS and streams it to an RTMP server running locally on the Raspberry Pi 5. The Pi also serves a Wi‑Fi hotspot so clients can connect directly and view the RTMP stream.

What you get

- RTMP server on Raspberry Pi via Nginx + RTMP module
- Wi‑Fi hotspot on the Pi (NetworkManager method preferred; hostapd/dnsmasq fallback)
- Python streamer that uses ffmpeg to publish `/dev/video0` to RTMP
- Python client script to test/preview the RTMP stream
- Optional systemd service to autostart the streamer on boot

Prerequisites

- Raspberry Pi 5 running Raspberry Pi OS (Bookworm recommended)
- Initial internet access to install packages
- A USB camera at `/dev/video0` that supports 1280x720 @ 30 FPS (most do)

Quick start

1) Install RTMP server

```bash
sudo bash scripts/install_rtmp_server.sh
```

2) Create Wi‑Fi hotspot (NetworkManager preferred)

Default SSID `PiRTMP` and password `raspberrypi`.

```bash
sudo SSID="PiRTMP" PASSWORD="pitin0701" bash scripts/setup_hotspot.sh
```

Notes:
- If NetworkManager is active (Bookworm default), the script uses `nmcli` and sets up a hotspot with Internet sharing. It will typically assign IP `10.42.0.1` to `wlan0`.
- If NetworkManager is not active, the script falls back to `hostapd` + `dnsmasq` and assigns `192.168.50.1/24` to `wlan0`.

3) Start streaming `/dev/video0` to RTMP

Choose the correct IP based on your hotspot method:
- NetworkManager hotspot: `rtmp://10.42.0.1/live/cam`
- hostapd/dnsmasq hotspot: `rtmp://192.168.50.1/live/cam`

```bash
python3 streamer/stream_to_rtmp.py   --device /dev/video0   --resolution 1280x720   --fps 30   --bitrate 2500k   --server rtmp://192.168.50.1/live   --stream-key cam --low-latency
```

4) Test from a client device (connected to the Pi hotspot)

On the client device, connect to the Pi hotspot, then run:

```bash
python3 client/test_rtmp_client.py --url rtmp://192.168.50.1/live/cam
```

Optional: Autostart streamer on boot (systemd)

```bash
sudo SERVER_URL=rtmp://192.168.50.1/live STREAM_KEY=cam \
  DEVICE=/dev/video0 WIDTH=1280 HEIGHT=720 FPS=30 BITRATE=2500k \
  bash scripts/install_streamer_service.sh
```

After installation:

```bash
sudo systemctl enable --now rtmp-streamer.service
sudo systemctl status rtmp-streamer.service
```

Files and layout

- `scripts/install_rtmp_server.sh`: Installs Nginx + RTMP module and deploys RTMP config
- `scripts/setup_hotspot.sh`: Creates a hotspot using NetworkManager or hostapd/dnsmasq fallback
- `scripts/install_streamer_service.sh`: Installs an optional systemd unit for autostart
- `config/nginx/rtmp.conf`: RTMP server configuration for Nginx
- `streamer/stream_to_rtmp.py`: Captures from `/dev/video0` and streams to RTMP via ffmpeg
- `client/test_rtmp_client.py`: Simple RTMP playback tester (runs ffplay if available; OpenCV fallback)

RTMP details

- Server bind: `rtmp://<pi-ip>:1935`
- Application: `live`
- Stream key: configurable (default `cam`)
- Full URL: `rtmp://<pi-ip>:1935/live/<stream-key>` (e.g., `rtmp://10.42.0.1/live/cam`)

Troubleshooting

- Camera permissions: add your user to the `video` group, then re-login:
  ```bash
  sudo usermod -aG video "$USER"
  ```
- List camera modes to confirm 1280x720@30 and formats:
  ```bash
  v4l2-ctl --list-formats-ext
  ```
- If `h264_v4l2m2m` fails, the streamer will fall back to `libx264`.
- If RTMP doesn’t play, verify Nginx is running:
  ```bash
  sudo nginx -t && systemctl status nginx
  ```
- Firewall: ensure port 1935 is open (default on Raspberry Pi OS).
- Hotspot switched off existing Wi‑Fi: re-run the script to switch modes, or plug in Ethernet for internet if needed.

License

MIT


