#!/usr/bin/env python3
import argparse
import os
import shutil
import signal
import subprocess
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stream /dev/video0 to RTMP using ffmpeg")
    parser.add_argument("--device", default="/dev/video0", help="Video device path")
    parser.add_argument("--resolution", default="1280x720", help="Resolution WIDTHxHEIGHT (e.g., 1280x720)")
    parser.add_argument("--fps", type=int, default=30, help="Frames per second")
    parser.add_argument("--bitrate", default="2500k", help="Video bitrate (e.g., 2500k)")
    parser.add_argument("--server", default="rtmp://127.0.0.1/live", help="RTMP server base URL (without stream key)")
    parser.add_argument("--stream-key", default="cam", help="RTMP stream key")
    parser.add_argument("--input-format", default="mjpeg", choices=["mjpeg", "yuyv422", "yuv420p"], help="V4L2 input pixel format")
    parser.add_argument("--encoder", default="h264_v4l2m2m", help="FFmpeg video encoder (try h264_v4l2m2m, fallback to libx264)")
    parser.add_argument("--ffmpeg-path", default=shutil.which("ffmpeg") or "ffmpeg", help="Path to ffmpeg binary")
    parser.add_argument("--low-latency", action="store_true", help="Reduce end-to-end latency (smaller buffers, no B-frames)")
    return parser.parse_args()


def build_ffmpeg_cmd(ffmpeg: str, device: str, resolution: str, fps: int, bitrate: str, input_fmt: str, encoder: str, rtmp_url: str, low_latency: bool = False) -> list:
    width, height = resolution.split("x")
    vf = f"fps={fps},format=yuv420p"
    cmd: list = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "warning",
    ]

    if low_latency:
        cmd.extend([
            "-fflags", "nobuffer",
            "-flags", "low_delay",
            "-avioflags", "direct",
        ])

    cmd.extend([
        "-f", "v4l2",
        "-framerate", str(fps),
        "-video_size", f"{width}x{height}",
        "-input_format", input_fmt,
        "-i", device,
        "-vf", vf,
        "-c:v", encoder,
        "-pix_fmt", "yuv420p",
        "-b:v", bitrate,
        "-maxrate", bitrate,
        "-bufsize", "1M" if low_latency else "5M",
        "-g", str(fps),
        "-bf", "0",
    ])

    if encoder == "libx264":
        # Extra low-latency tuning for software encoder
        cmd.extend([
            "-preset", "veryfast",
            "-tune", "zerolatency",
            "-profile:v", "baseline",
            "-x264-params", f"keyint={fps}:min-keyint={fps}:scenecut=0:bframes=0:nal-hrd=cbr",
        ])

    cmd.extend([
        "-f", "flv",
    ])

    if low_latency:
        # Output-specific low latency muxer/protocol flags must appear before the output URL
        cmd.extend([
            "-rtmp_live", "live",
            "-flvflags", "no_duration_filesize",
            "-muxdelay", "0",
            "-muxpreload", "0",
        ])

    cmd.append(rtmp_url)
    return cmd


def run_with_fallback(cmd_primary: list, cmd_fallback: list) -> int:
    try:
        print("Starting ffmpeg (hardware encoder if available)...")
        return subprocess.call(cmd_primary)
    except FileNotFoundError:
        print("ffmpeg not found. Install ffmpeg and try again.")
        return 127
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Primary encoder failed: {exc}")
        print("Falling back to software encoder (libx264)...")
        return subprocess.call(cmd_fallback)


def main() -> int:
    args = parse_args()

    if not shutil.which(args.ffmpeg_path):
        # Allow explicit path even if not on PATH
        if not os.path.isfile(args.ffmpeg_path):
            print("ffmpeg not found. Please install ffmpeg.")
            return 127

    if not os.path.exists(args.device):
        print(f"Video device not found: {args.device}")
        return 1

    rtmp_url = f"{args.server.rstrip('/')}/{args.stream_key}"

    primary_cmd = build_ffmpeg_cmd(
        args.ffmpeg_path,
        args.device,
        args.resolution,
        args.fps,
        args.bitrate,
        args.input_format,
        args.encoder,
        rtmp_url,
        args.low_latency,
    )

    fallback_cmd = build_ffmpeg_cmd(
        args.ffmpeg_path,
        args.device,
        args.resolution,
        args.fps,
        args.bitrate,
        args.input_format,
        "libx264",
        rtmp_url,
        args.low_latency,
    )

    # Properly handle Ctrl-C by forwarding to child
    def _forward_sigint(signum, frame):  # noqa: ARG001
        print("Stopping stream...")
        try:
            os.killpg(0, signal.SIGINT)
        except Exception:
            pass

    signal.signal(signal.SIGINT, _forward_sigint)

    # Prefer hardware encoder if present
    retcode = run_with_fallback(primary_cmd, fallback_cmd)
    if retcode != 0 and args.encoder != "libx264":
        print(f"ffmpeg exited with code {retcode}. Trying software encoder as last resort...")
        retcode = subprocess.call(fallback_cmd)

    return retcode


if __name__ == "__main__":
    sys.exit(main())


