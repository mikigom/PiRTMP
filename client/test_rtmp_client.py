#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys
import threading
import queue
from datetime import datetime


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
    print("Press 'q' to quit. Press 's' to start saving, 'd' to stop.")

    cv2.namedWindow("RTMP Stream", cv2.WINDOW_NORMAL)
    try:
        cv2.setWindowProperty("RTMP Stream", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    except Exception:
        pass

    screen_w, screen_h = None, None
    try:
        import tkinter as tk  # stdlib
        root = tk.Tk()
        root.withdraw()
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        root.destroy()
    except Exception:
        screen_w, screen_h = None, None

    datasets_root = os.path.join(os.getcwd(), "datasets")
    os.makedirs(datasets_root, exist_ok=True)

    saving = False
    session_dir = None
    frames_queue: queue.Queue | None = None
    stop_event: threading.Event | None = None
    writer_thread: threading.Thread | None = None
    frame_idx = 0

    def _writer_loop(_q: queue.Queue, base_dir: str, _stop: threading.Event) -> None:
        try:
            import cv2  # type: ignore
        except Exception:
            return
        while not _stop.is_set() or not _q.empty():
            try:
                idx, img = _q.get(timeout=0.1)
            except queue.Empty:
                continue
            out_path = os.path.join(base_dir, f"{idx:06d}.jpg")
            try:
                cv2.imwrite(out_path, img)
            except Exception:
                pass
            finally:
                _q.task_done()

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Frame read failed; exiting.")
            break
        display = frame
        if screen_w and screen_h:
            try:
                display = cv2.resize(display, (screen_w, screen_h))
            except Exception:
                pass

        if saving:
            try:
                # Non-blocking enqueue; drop if queue is full
                if frames_queue is not None:
                    frames_queue.put_nowait((frame_idx, frame.copy()))
                    frame_idx += 1
            except queue.Full:
                pass
            # On-screen indicator
            try:
                cv2.putText(
                    display,
                    "Saving...",
                    (20, 50),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.2,
                    (0, 0, 255),
                    3,
                    lineType=cv2.LINE_AA,
                )
            except Exception:
                pass

        cv2.imshow("RTMP Stream", display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s') and not saving:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_dir = os.path.join(datasets_root, ts)
            try:
                os.makedirs(session_dir, exist_ok=True)
            except Exception:
                session_dir = None
            if session_dir:
                frames_queue = queue.Queue(maxsize=240)
                stop_event = threading.Event()
                writer_thread = threading.Thread(target=_writer_loop, args=(frames_queue, session_dir, stop_event), daemon=True)
                writer_thread.start()
                frame_idx = 0
                saving = True
                print(f"Saving started: {session_dir}")
        elif key == ord('d') and saving:
            if stop_event is not None:
                stop_event.set()
            saving = False
            print("Saving stopped.")

    cap.release()
    cv2.destroyAllWindows()
    # Graceful shutdown of writer
    try:
        if stop_event is not None:
            stop_event.set()
        if frames_queue is not None:
            frames_queue.join()
        if writer_thread is not None:
            writer_thread.join(timeout=5)
    except Exception:
        pass
    return 0


def main() -> int:
    args = parse_args()
    # Prefer OpenCV to enable interactive controls; fallback to ffplay if unavailable
    rc = play_with_opencv(args.url)
    if rc == 0:
        return 0
    print("OpenCV not available or failed; launching ffplay (no save controls)...")
    return play_with_ffplay(args.ffplay_path, args.url)


if __name__ == "__main__":
    sys.exit(main())


