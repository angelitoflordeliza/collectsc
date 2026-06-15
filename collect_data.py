"""
collect_data.py — Recording engine for the Gesture Dataset Collector.

This module provides the camera HUD, overlay rendering, and the core
record_dataset() function.  All terminal-prompt logic has been moved to
gui.py / main.py.  Import this module; do not run it directly.
"""

import cv2
import numpy as np
import os
import time
from datetime import datetime
import mediapipe as mp

# Initialize MediaPipe Hands
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(min_detection_confidence=0.5, min_tracking_confidence=0.5)

# ── UI Design Tokens (BGR color format) ──────────────────────────────────────
_C_BG      = (22,  17,  15)   # #0F1116  deep navy background
_C_PANEL   = (30,  26,  22)   # #161A1E  HUD panel fill
_C_ACCENT  = (255, 170,   0)  # #00AAFF  electric blue
_C_REC     = ( 80, 220,  60)  # #3CDC50  recording green
_C_WAIT    = ( 40, 150, 255)  # #FF9628  standby amber
_C_TEXT    = (245, 242, 240)  # #F0F2F5  primary text
_C_MUTED   = (150, 145, 138)  # #8A9196  secondary text
_C_DIM     = ( 60,  58,  55)  # #373A3C  separator / dim

_TOP_H  = 110   # top HUD panel height (px, at native camera res)
_BOT_H  =  72   # bottom HUD panel height
_WIN    = "Dataset Collection"
_paused    = False   # global pause flag (toggled by P key)


def _toggle_pause():
    """Toggle the global pause state."""
    global _paused
    _paused = not _paused


def _draw_panel(canvas, y0, y1, alpha=0.82):
    """Paint a semi-transparent dark panel over canvas rows [y0, y1)."""
    roi = canvas[y0:y1]
    overlay = np.full_like(roi, _C_PANEL)
    cv2.addWeighted(overlay, alpha, roi, 1 - alpha, 0, roi)
    canvas[y0:y1] = roi

DATASET_PATH = "data/raw"
VIDEO_DURATION = 1
FPS = 30
FRAME_COUNT = VIDEO_DURATION * FPS
BREAK_TIME = 2  # seconds before each recording
REST_TIME = 2   # seconds between different gestures

GESTURES = [
    ("Open_Palm", "hand fully open, fingers extended and spread"),
    ("Fist", "hand fully closed, fingers curled into palm"),
    ("Pinch", "thumb and index finger pressed together"),
    ("Point", "index finger extended, other fingers curled"),
    ("Two_Finger_V", "index and middle fingers extended in a V shape"),
    ("Thumbs_Up", "fist with thumb pointing upward"),
    ("Swipe", "open hand moving horizontally left or right"),
    ("Push_Down", "open palm facing down, moving downward"),
    ("Twist_Left", "pinch rotated counterclockwise (as if turning left)"),
    ("Twist_Right", "pinch rotated clockwise (as if turning right)")
]


def get_next_session_idx(base_path):
    """Scans base_path for directories starting with 'session',

    parses their indices, and returns the next auto-incremented index.
    """
    if not os.path.exists(base_path):
        return 1
        
    max_idx = 0
    for entry in os.listdir(base_path):
        full_path = os.path.join(base_path, entry)
        if os.path.isdir(full_path) and entry.startswith("session"):
            idx_str = entry[7:] # Extract string after "session"
            if idx_str.isdigit():
                idx = int(idx_str)
                if idx > max_idx:
                    max_idx = idx
    return max_idx + 1


def process_frame_with_hands(frame):
    """Process frame with MediaPipe Hands and draw landmarks."""
    # Convert BGR to RGB
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    # Process the frame
    results = hands.process(rgb_frame)
    # Draw landmarks if hands are detected
    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
    return frame


def add_black_border(frame, top=_TOP_H, bottom=_BOT_H, left=0, right=0, inner_color=(0, 0, 0)):
    """Extend frame with styled dark HUD panels (top and bottom)."""
    h, w = frame.shape[:2]
    canvas = np.empty((h + top + bottom, w + left + right, 3), dtype=np.uint8)
    canvas[:] = _C_BG
    canvas[top:top + h, left:left + w] = frame

    # Thin accent line between video and panels
    border_color = inner_color if inner_color != (0, 0, 0) else _C_DIM
    cv2.line(canvas, (left, top),         (left + w - 1, top),         border_color, 2)
    cv2.line(canvas, (left, top + h - 1), (left + w - 1, top + h - 1), border_color, 2)

    return canvas


def draw_overlay(frame, gesture, description, status, countdown=None, paused=False, sample_info=None):
    """Render a modern, minimal HUD overlay on the camera frame."""
    is_recording = status == "RECORDING"
    is_waiting   = status == "WAITING"

    # Pick accent color per state
    accent = _C_REC if is_recording else (_C_WAIT if is_waiting else _C_ACCENT)
    line_color = accent if is_recording else (0, 0, 0)   # colored edge only when recording

    frame = add_black_border(frame, top=_TOP_H, bottom=_BOT_H, left=0, right=0,
                             inner_color=line_color)
    h, w = frame.shape[:2]

    # ── Semi-transparent HUD panels ──────────────────────────────────────────
    _draw_panel(frame, 0, _TOP_H)
    _draw_panel(frame, h - _BOT_H, h)

    pad = 18   # horizontal padding inside panels

    # ── TOP PANEL ────────────────────────────────────────────────────────────
    # Gesture name (large)
    cv2.putText(frame, gesture.replace("_", " "),
                (pad, 38), cv2.FONT_HERSHEY_DUPLEX, 0.85, _C_TEXT, 1, cv2.LINE_AA)
    # Description (muted, smaller)
    cv2.putText(frame, description,
                (pad, 64), cv2.FONT_HERSHEY_DUPLEX, 0.45, _C_MUTED, 1, cv2.LINE_AA)

    # Sample counter (top-right, e.g. "3 / 10")
    if sample_info is not None:
        si_label = f"{sample_info}"
        (si_w, si_h), _ = cv2.getTextSize(si_label, cv2.FONT_HERSHEY_DUPLEX, 0.72, 1)
        si_x = w - pad - si_w
        cv2.putText(frame, si_label,
                    (si_x, 36), cv2.FONT_HERSHEY_DUPLEX, 0.72, _C_TEXT, 1, cv2.LINE_AA)
        cv2.putText(frame, "sample",
                    (si_x, 62), cv2.FONT_HERSHEY_DUPLEX, 0.38, _C_MUTED, 1, cv2.LINE_AA)

    # Animated pulsing dot (radius oscillates with time)
    pulse = 0.5 + 0.5 * abs(time.time() % 1.0 - 0.5) * 2   # 0..1 sawtooth
    dot_r = int(7 + 4 * pulse) if is_recording else 7
    # shift dot left of sample counter when sample_info is shown
    dot_cx = (w - pad - si_w - 12 - 90) if sample_info is not None else (w - pad - 90)
    dot_cy = 38
    cv2.circle(frame, (dot_cx, dot_cy), dot_r + 3, (*_C_DIM, ), -1, cv2.LINE_AA)
    cv2.circle(frame, (dot_cx, dot_cy), dot_r,     accent,      -1, cv2.LINE_AA)

    # Status label next to dot
    status_label = "REC" if is_recording else ("READY" if is_waiting else "STANDBY")
    cv2.putText(frame, status_label,
                (dot_cx + dot_r + 6, dot_cy + 6),
                cv2.FONT_HERSHEY_DUPLEX, 0.5, accent, 1, cv2.LINE_AA)

    # Countdown timer (only when no sample_info shown, or below the counter)
    if countdown is not None:
        timer_str = f"{countdown}s"
        (tw, _), _ = cv2.getTextSize(timer_str, cv2.FONT_HERSHEY_DUPLEX, 1.1, 2)
        cv2.putText(frame, timer_str,
                    (w - pad - tw, 68),
                    cv2.FONT_HERSHEY_DUPLEX, 1.1, accent, 2, cv2.LINE_AA)

    # ── BOTTOM PANEL ─────────────────────────────────────────────────────────
    bot_y0 = h - _BOT_H

    if is_recording:
        line1 = "Recording in progress"
        line2 = "Vary pose — keep the gesture shape"
    elif is_waiting:
        line1 = "Get ready"
        line2 = "Position your hand for the gesture"
    else:
        line1 = "Standby"
        line2 = status if len(status) < 52 else "Prepare for the next recording"

    cv2.putText(frame, line1,
                (pad, bot_y0 + 26),
                cv2.FONT_HERSHEY_DUPLEX, 0.55, _C_TEXT,  1, cv2.LINE_AA)
    cv2.putText(frame, line2,
                (pad, bot_y0 + 52),
                cv2.FONT_HERSHEY_DUPLEX, 0.45, _C_MUTED, 1, cv2.LINE_AA)

    # Bottom-right hint (includes pause shortcut)
    hint = "[P] pause  [ESC] quit"
    (hw, _), _ = cv2.getTextSize(hint, cv2.FONT_HERSHEY_DUPLEX, 0.38, 1)
    cv2.putText(frame, hint,
                (w - hw - pad, bot_y0 + 52),
                cv2.FONT_HERSHEY_DUPLEX, 0.38, _C_DIM, 1, cv2.LINE_AA)

    # ── PAUSED badge (centered, drawn last so it sits on top) ────────────────
    if paused:
        badge_text = "  PAUSED  "
        badge_scale = 1.0
        (bw, bh), bl = cv2.getTextSize(badge_text, cv2.FONT_HERSHEY_DUPLEX, badge_scale, 2)
        bx = (w - bw) // 2
        by = h // 2 + bh // 2
        # dark pill background
        cv2.rectangle(frame, (bx - 12, by - bh - bl - 8),
                      (bx + bw + 12, by + 8), (20, 18, 16), -1, cv2.LINE_AA)
        cv2.rectangle(frame, (bx - 12, by - bh - bl - 8),
                      (bx + bw + 12, by + 8), _C_ACCENT, 2, cv2.LINE_AA)
        cv2.putText(frame, badge_text,
                    (bx, by), cv2.FONT_HERSHEY_DUPLEX, badge_scale, _C_ACCENT, 2, cv2.LINE_AA)
        # sub-label
        sub = "Press P to resume"
        (sw, _), _ = cv2.getTextSize(sub, cv2.FONT_HERSHEY_DUPLEX, 0.42, 1)
        cv2.putText(frame, sub,
                    ((w - sw) // 2, by + 32),
                    cv2.FONT_HERSHEY_DUPLEX, 0.42, _C_MUTED, 1, cv2.LINE_AA)

    return frame


# Terminal-prompt functions (parse_gestures, ask_gesture_selection,
# ask_samples, ask_confirmation) have been replaced by the CustomTkinter GUI
# in gui.py.  They are intentionally omitted here.


def countdown_sleep(seconds, message, cap=None, gesture=None, description=None, next_gesture=None, next_description=None):
    """Sleep with a visible countdown. If cap/gesture/description are given,

    also renders the countdown on the live camera feed.
    
    next_gesture/next_description can be used to display upcoming gesture info during breaks.
    Honors the global _paused flag — countdown freezes while paused.
    """
    for s in range(seconds, 0, -1):
        print(f"{message}: {s}s   ", end="\r", flush=True)
        if cap is not None:
            deadline = time.time() + 1
            while time.time() < deadline:
                # Freeze countdown while paused
                if _paused:
                    deadline += 0.03   # keep extending deadline so timer doesn't advance
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.03)
                    continue
                display_frame = cv2.flip(frame, 1)
                # Use next gesture if available (for breaks between gestures)
                display_gesture = next_gesture if next_gesture else gesture
                display_description = next_description if next_description else description
                display_frame = process_frame_with_hands(display_frame)
                display_frame = draw_overlay(display_frame, display_gesture, display_description,
                             f"{message} — {s}s remaining", paused=_paused)
                cv2.imshow(_WIN, display_frame)
                key = cv2.waitKey(1)
                if key == 27:
                    return True   # signal early exit

                if key in (ord('p'), ord('P')):
                    _toggle_pause()
        else:
            time.sleep(1)
    print(" " * 80, end="\r")
    return False


def wait_for_enter(cap, gesture, description, next_gesture=None, next_description=None):
    """Wait for user to press Enter key, showing next gesture info if available."""
    print("Press Enter to continue to next gesture...")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        
        display_frame = cv2.flip(frame, 1)
        # Show next gesture if available, otherwise current gesture
        display_gesture = next_gesture if next_gesture else gesture
        display_description = next_description if next_description else description
        display_frame = process_frame_with_hands(display_frame)
        status_msg = f"Press Enter to start {display_gesture}" if next_gesture else "Gesture completed - Press Enter to continue"
        display_frame = draw_overlay(display_frame, display_gesture, display_description,
                                     status_msg, paused=_paused)
        cv2.imshow(_WIN, display_frame)

        key = cv2.waitKey(1)
        if key == 13:   # Enter
            break
        elif key == 27:  # ESC
            return True

        elif key in (ord('p'), ord('P')):
            _toggle_pause()
    
    return False


def record_dataset(cap, selected_indices, samples_per_gesture):
    session_files = []
    stats = {}
    session_start = datetime.now()
    terminated = False

    # 1. Detect and create the active session path
    session_idx = get_next_session_idx(DATASET_PATH)
    session_folder_name = f"session{session_idx:03d}"
    session_path = os.path.join(DATASET_PATH, session_folder_name)
    os.makedirs(session_path, exist_ok=True)

    try:
        for gesture_idx in selected_indices:
            gesture, description = GESTURES[gesture_idx - 1]
            print(f"\nCollecting gesture {gesture_idx}: {gesture}")

            # 2. Create nested gesture directories under the current session path
            gesture_folder = os.path.join(session_path, gesture)
            os.makedirs(gesture_folder, exist_ok=True)

            stats[gesture] = {"count": 0, "files": []}

            for sample in range(samples_per_gesture):
                sample_label = f"{sample + 1} / {samples_per_gesture}"

                # ── PRE-RECORDING WAIT (WAITING phase) ───────────────────────
                start = time.time()
                while True:
                    # Freeze countdown while paused — slide start forward so
                    # elapsed doesn't grow, and never allow the break while paused.
                    if _paused:
                        start = time.time()   # keep resetting start so elapsed stays ~0

                    ret, frame = cap.read()
                    if not ret:
                        continue

                    elapsed = time.time() - start
                    remaining = int(BREAK_TIME - elapsed) + 1

                    # Only exit the wait when NOT paused and time is up
                    if remaining <= 0 and not _paused:
                        break

                    display_frame = cv2.flip(frame, 1)
                    display_frame = process_frame_with_hands(display_frame)
                    display_frame = draw_overlay(
                        display_frame, gesture, description, "WAITING",
                        countdown=remaining, paused=_paused, sample_info=sample_label)
                    cv2.imshow(_WIN, display_frame)

                    key = cv2.waitKey(1)
                    if key == 27:
                        print("\nProgram was terminated prematurely by the user")
                        terminated = True
                        break
                    if key in (ord('p'), ord('P')):
                        _toggle_pause()


                if terminated:
                    break

                # ── RECORDING phase ──────────────────────────────────────────
                # Pause is NOT allowed mid-recording; frames collected = FRAME_COUNT.
                frames = []
                collected = 0
                while collected < FRAME_COUNT:
                    ret, frame = cap.read()
                    if not ret:
                        continue

                    frames.append(frame.copy())
                    collected += 1

                    preview_frame = cv2.flip(frame.copy(), 1)
                    preview_frame = process_frame_with_hands(preview_frame)
                    preview_frame = draw_overlay(
                        preview_frame, gesture, description, "RECORDING",
                        sample_info=sample_label)
                    cv2.imshow(_WIN, preview_frame)

                    key = cv2.waitKey(1)
                    if key == 27:
                        print("\nProgram was terminated prematurely by the user")
                        terminated = True
                        break


                if terminated:
                    break

                # 3. Format self-documenting filename
                timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
                filename = f"session{session_idx:03d}_{gesture}_vid{sample+1:03d}_{timestamp}.mp4"
                video_path = os.path.join(gesture_folder, filename)

                height, width, _ = frames[0].shape
                writer = cv2.VideoWriter(video_path, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (width, height))
                for f in frames:
                    writer.write(f)
                writer.release()

                stats[gesture]["count"] += 1
                stats[gesture]["files"].append(video_path)
                session_files.append(video_path)

                print(f"{gesture} sample {sample+1}/{samples_per_gesture} saved -> {filename}")

            if terminated:
                break

            # Only rest if there are more gestures to collect
            if gesture_idx != selected_indices[-1]:
                # Get next gesture info
                next_gesture_idx = selected_indices[selected_indices.index(gesture_idx) + 1]
                next_gesture, next_description = GESTURES[next_gesture_idx - 1]
                
                # Wait for user to press Enter before starting rest countdown
                print(f"\nGesture {gesture} completed! Prepare for next gesture: {next_gesture}")
                quit_early = wait_for_enter(cap, gesture, description, next_gesture, next_description)
                if quit_early:
                    print("\nProgram was terminated prematurely by the user")
                    terminated = True
                    break
                
                print(f"Resting {REST_TIME}s before next gesture")
                quit_early = countdown_sleep(
                    REST_TIME, "Rest before next gesture",
                    cap=cap, gesture=gesture, description=description,
                    next_gesture=next_gesture, next_description=next_description
                )
                if quit_early:
                    print("\nProgram was terminated prematurely by the user")
                    terminated = True
                    break

        session_end = datetime.now()

    finally:
        cap.release()
        cv2.destroyAllWindows()
        hands.close()

    if terminated:
        print("\nSession was terminated prematurely by the user. Partial data has been saved.")

    log_text = [f"Session started: {session_start}", f"Session ended:   {session_end}", ""]
    for gesture, details in stats.items():
        log_text.append(f"Gesture {gesture} - count: {details['count']}")
        for path in details['files']:
            log_text.append(f"  {path}")
    log_text.append("")
    log_text.append(f"Total files: {len(session_files)}")

    # 4. Save the log file inside the current active session directory
    log_name = datetime.now().strftime("session_log_%y%m%d_%H%M%S.txt")
    log_path = os.path.join(session_path, log_name)
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_text))

    print("\n=== Session Summary ===")
    for line in log_text:
        print(line)
    print(f"Log saved to: {log_path}")

    return stats, session_files, log_path


# The __main__ block has been moved to main.py.
# Run the application with:  python src/main.py
