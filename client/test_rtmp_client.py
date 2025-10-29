#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys


def parse_args():
    parser = argparse.ArgumentParser(description="Simple RTMP client test (ffplay if available; OpenCV fallback)")
    parser.add_argument("--url", default="rtmp://10.42.0.1/live/cam", help="RTMP URL to play")
    parser.add_argument("--ffplay-path", default=shutil.which("ffplay") or "ffplay", help="Path to ffplay binary")
    parser.add_argument("--use-opencv", action="store_true", help="Force using OpenCV fallback instead of ffplay")
    return parser.parse_args()


def play_with_ffplay(ffplay_path: str, url: str) -> int:
    if shutil.which(ffplay_path) or os.path.isfile(ffplay_path):
        cmd = [
            ffplay_path,
            "-autoexit",
            "-fflags",
            "nobuffer",
            "-flags",
            "low_delay",
            "-probesize",
            "32",
            "-analyzeduration",
            "0",
            "-framedrop",
            "-fast",
            "-rtmp_live",
            "live",
            url,
        ]
        print("Launching ffplay... (close the window to exit)")
        return subprocess.call(cmd)
    return 127


def play_with_opencv(url: str) -> int:
    try:
        import cv2  # type: ignore
    except Exception:
        print("OpenCV not installed. Install opencv-python to use the fallback.")
        return 127

    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        print("Failed to open stream with OpenCV.")
        return 1
    print("Press 'q' to quit.")
    while True:
        ok, frame = cap.read()
        if not ok:
            print("Frame read failed; exiting.")
            break
        cv2.imshow("RTMP Stream", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()
    return 0


def main() -> int:
    args = parse_args()
    if not args.use_opencv:
        rc = play_with_ffplay(args.ffplay_path, args.url)
        if rc == 0:
            return 0
        print("ffplay not available or failed; falling back to OpenCV...")
    return play_with_opencv(args.url)


if __name__ == "__main__":
    sys.exit(main())


