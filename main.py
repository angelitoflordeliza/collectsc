"""
main.py — Entry point for the Gesture Dataset Collector.

Launch workflow:
  1. Ensure working directory is the project root (so relative paths resolve).
  2. Open the CustomTkinter configuration window (gui.py).
  3. If the user completes configuration, open the camera, show the ready
     screen, then hand off to record_dataset() in collect_data.py.
  4. All errors are surfaced as GUI dialogs — no terminal output required.

Usage:
    python src/main.py
"""

from __future__ import annotations

import os
import sys

# ── Ensure CWD is the project root so all relative paths resolve ──────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
os.chdir(_PROJECT_ROOT)

# ── Add src/ to path so sibling modules import cleanly ───────────────────────
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import cv2
import customtkinter as ctk

from gui import run_config
from collect_data import (
    record_dataset,
    process_frame_with_hands,
    add_black_border,
    draw_overlay,
    _draw_panel,
    _WIN,
    _TOP_H,
    _BOT_H,
    _C_TEXT,
    _C_MUTED,
    _C_DIM,
    _C_ACCENT,
    _toggle_pause,
    _paused,
)
import time


def _show_error_dialog(title: str, message: str) -> None:
    """Display a simple error dialog using CustomTkinter."""
    ctk.set_appearance_mode("dark")
    root = ctk.CTk()
    root.withdraw()

    dialog = ctk.CTkToplevel(root)
    dialog.title(title)
    dialog.geometry("420x160")
    dialog.resizable(False, False)
    dialog.grab_set()

    # Center on screen
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth()  - dialog.winfo_width())  // 2
    y = (dialog.winfo_screenheight() - dialog.winfo_height()) // 2
    dialog.geometry(f"+{x}+{y}")

    ctk.CTkLabel(
        dialog,
        text=title,
        font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
        text_color="#FF4444",
    ).pack(pady=(20, 4))

    ctk.CTkLabel(
        dialog,
        text=message,
        font=ctk.CTkFont(family="Segoe UI", size=12),
        text_color="#8A9196",
        wraplength=380,
    ).pack(pady=(0, 16))

    ctk.CTkButton(
        dialog,
        text="OK",
        width=100,
        fg_color="#00AAFF",
        command=dialog.destroy,
    ).pack()

    dialog.wait_window()
    root.destroy()


def _show_ready_screen(cap: cv2.VideoCapture, n_gestures: int, samples: int) -> bool:
    """Show the camera ready screen and wait for Enter.

    Returns True if the user pressed Enter (proceed), False if ESC.
    This mirrors the original __main__ ready screen exactly.
    """
    global _paused

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        display = cv2.flip(frame, 1)
        display = process_frame_with_hands(display)
        display = add_black_border(display, top=_TOP_H, bottom=_BOT_H)
        fh, fw = display.shape[:2]

        _draw_panel(display, 0, _TOP_H)
        _draw_panel(display, fh - _BOT_H, fh)

        pad = 18
        cv2.putText(display, "Gesture Dataset Collector",
                    (pad, 38), cv2.FONT_HERSHEY_DUPLEX, 0.8, _C_TEXT, 1, cv2.LINE_AA)
        cv2.putText(display, f"  {n_gestures} gesture(s)  ·  {samples} sample(s) each",
                    (pad, 64), cv2.FONT_HERSHEY_DUPLEX, 0.45, _C_MUTED, 1, cv2.LINE_AA)

        pulse = 0.5 + 0.5 * abs(time.time() % 1.0 - 0.5) * 2
        dot_r = int(7 + 4 * pulse)
        cv2.circle(display, (fw - pad - 12, 38), dot_r + 3, _C_DIM,    -1, cv2.LINE_AA)
        cv2.circle(display, (fw - pad - 12, 38), dot_r,     _C_ACCENT, -1, cv2.LINE_AA)

        bot_y0 = fh - _BOT_H
        cv2.putText(display, "Press  Enter  to begin recording",
                    (pad, bot_y0 + 28), cv2.FONT_HERSHEY_DUPLEX, 0.58, _C_ACCENT, 1, cv2.LINE_AA)
        hint = "[P] pause  [ESC] exit"
        (hw2, _), _ = cv2.getTextSize(hint, cv2.FONT_HERSHEY_DUPLEX, 0.38, 1)
        cv2.putText(display, hint,
                    (fw - hw2 - pad, bot_y0 + 54),
                    cv2.FONT_HERSHEY_DUPLEX, 0.38, _C_DIM, 1, cv2.LINE_AA)

        cv2.imshow(_WIN, display)
        key = cv2.waitKey(1)
        if key == 13:    # Enter
            return True
        elif key == 27:  # ESC
            return False
        elif key in (ord('p'), ord('P')):
            _toggle_pause()


def main() -> None:
    # ── 1. Show configuration GUI ─────────────────────────────────────────────
    config = run_config()

    if config is None:
        # User closed the window without starting
        sys.exit(0)

    selected_indices: list[int] = config["selected_indices"]
    samples: int = config["samples"]

    # ── 2. Open camera ────────────────────────────────────────────────────────
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        _show_error_dialog(
            "Camera Not Found",
            "Unable to open the webcam (device index 0).\n\n"
            "Please ensure a camera is connected and not in use by another application.",
        )
        sys.exit(1)

    # ── 3. Create resizable camera window ─────────────────────────────────────
    cv2.namedWindow(_WIN, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(_WIN, 960, 640)

    # ── 4. Ready screen — wait for Enter ──────────────────────────────────────
    proceed = _show_ready_screen(cap, len(selected_indices), samples)
    cv2.destroyAllWindows()

    if not proceed:
        cap.release()
        sys.exit(0)

    # ── 5. Record dataset ─────────────────────────────────────────────────────
    try:
        record_dataset(cap, selected_indices, samples)
    except PermissionError as exc:
        _show_error_dialog(
            "Permission Denied",
            f"Could not create the session folder or write video files.\n\n{exc}",
        )
        sys.exit(1)
    except OSError as exc:
        _show_error_dialog(
            "File System Error",
            f"An error occurred while saving the recording.\n\n{exc}",
        )
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        _show_error_dialog(
            "Recording Error",
            f"An unexpected error occurred during recording.\n\n{exc}",
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
