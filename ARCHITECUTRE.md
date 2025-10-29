
### High-level overview
- **Purpose**: Capture video from a USB camera on a Raspberry Pi and broadcast it over RTMP so clients connected to the Pi (often via a built-in Wi‑Fi hotspot) can view the stream.
- **Core pipeline**: Camera (`/dev/video0`) → FFmpeg (via `streamer/stream_to_rtmp.py`) → Nginx RTMP server → RTMP clients.

Camera → Streamer (FFmpeg) → RTMP server (Nginx+RTMP) → Clients (ffplay/OpenCV)

### Components
- **RTMP server**: Nginx with the RTMP module serves `rtmp://<pi-ip>:1935/live/<stream-key>`. Installed and wired by `scripts/install_rtmp_server.sh`, configured via `config/nginx/rtmp.conf`.
- **Streamer**: `streamer/stream_to_rtmp.py` wraps FFmpeg to read `/dev/video0` and push H.264 video to the RTMP server. Prefers hardware encoder `h264_v4l2m2m`, falls back to `libx264`. Optional low-latency flags.
- **Autostart (optional)**: `scripts/install_streamer_service.sh` creates a `systemd` unit `rtmp-streamer.service` to run the streamer on boot.
- **Hotspot**: `scripts/setup_hotspot.sh` sets up connectivity for viewers. Uses NetworkManager shared hotspot if available; else configures `hostapd` + `dnsmasq`.
- **Client tester**: `client/test_rtmp_client.py` plays the stream using `ffplay` (preferred) with low-latency options, or OpenCV fallback.

### Runtime data flow
1. The streamer process invokes FFmpeg to read from V4L2 (`/dev/video0`) at a chosen resolution/FPS, encodes H.264, and publishes to `rtmp://<pi-ip>:1935/live/<stream-key>`.
2. Nginx (with RTMP module) accepts the publish and serves concurrent players on the LAN/hotspot.
3. Clients connect with `ffplay`/OpenCV using the full RTMP URL.

### Processes and services
- **`nginx`**: Long-running service hosting the RTMP endpoint.
- **`rtmp-streamer.service`** (optional): Long-running user process executing the Python streamer with configured arguments; depends on `network-online.target` and `nginx.service`.
- **Hotspot**: Managed by NetworkManager (preferred) or `hostapd`/`dnsmasq`, giving the Pi a known IP (commonly `10.42.0.1` with NM or `192.168.50.1` with hostapd/dnsmasq).

### Network and endpoints
- **RTMP bind**: `rtmp://<pi-ip>:1935`
- **Application**: `live`
- **Publish/play URL**: `rtmp://<pi-ip>:1935/live/<stream-key>` (default stream key `cam`)
- **Access policy**: Open for publish/play on the LAN/hotspot (no auth).

### Key configs (for reference)
```1:12:/home/pitin/CameraRSTP/config/nginx/rtmp.conf
rtmp {
    server {
        listen 1935;
        chunk_size 8192;

        application live {
            live on;
            record off;
            allow publish all;  # Allow any publisher on LAN/hotspot
            allow play all;     # Allow any player on LAN/hotspot
        }
    }
}
```

```39:47:/home/pitin/CameraRSTP/scripts/install_streamer_service.sh
ExecStart=/usr/bin/python3 /home/pitin/CameraRSTP/streamer/stream_to_rtmp.py \
  --device $DEVICE \
  --resolution ${WIDTH}x${HEIGHT} \
  --fps $FPS \
  --bitrate $BITRATE \
  --server $SERVER_URL \
  --stream-key $STREAM_KEY \
  --input-format $INPUT_FORMAT \
  --encoder $ENCODER
```

### Operational notes
- **Latency**: The streamer and client use flags to minimize latency (no B‑frames, small buffer/GOP aligned to FPS).
- **Resilience**: Hardware encoder preferred; automatic fallback to software encoder if unavailable.
- **Security**: RTMP allows publish/play from anyone on the LAN/hotspot; tighten if needed for production.

- Set up the repo’s main files to understand architecture and read the key configs. 
- The system consists of a streamer (FFmpeg via Python) pushing to an Nginx RTMP server, with an optional systemd service and a hotspot for client connectivity.