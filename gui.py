"""
gui.py — CustomTkinter configuration window for the Gesture Dataset Collector.

Responsibilities:
- Present all gestures as selectable checkboxes.
- Accept sample-per-gesture count with validation.
- Display live session info (next session #, gesture count, total recordings).
- Return the validated configuration to main.py after the user clicks Start.
- Surface all errors as inline labels (never crashes to console).
"""

from __future__ import annotations

import os
import sys
from typing import Optional

import customtkinter as ctk

# ── Resolve project root regardless of where the script is invoked from ──────
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
DATASET_PATH = os.path.join(_PROJECT_ROOT, "data", "raw")

# ── Gesture definitions (mirrors collect_data.py exactly) ─────────────────────
GESTURES: list[tuple[str, str, str]] = [
    # (name, description, type)
    ("Open_Palm",    "Hand fully open, fingers extended and spread",          "static"),
    ("Fist",         "Hand fully closed, fingers curled into palm",           "static"),
    ("Pinch",        "Thumb and index finger pressed together",               "static"),
    ("Point",        "Index finger extended, other fingers curled",           "static"),
    ("Two_Finger_V", "Index and middle fingers extended in a V shape",        "static"),
    ("Thumbs_Up",    "Fist with thumb pointing upward",                       "static"),
    ("Swipe",        "Open hand moving horizontally left or right",           "dynamic"),
    ("Push_Down",    "Open palm facing down, moving downward",                "dynamic"),
    ("Twist_Left",   "Pinch rotated counterclockwise (as if turning left)",   "dynamic"),
    ("Twist_Right",  "Pinch rotated clockwise (as if turning right)",         "dynamic"),
]

# ── Design tokens ─────────────────────────────────────────────────────────────
_FONT_FAMILY  = "Segoe UI"
_CLR_ACCENT   = "#00AAFF"
_CLR_GREEN    = "#3CDC50"
_CLR_AMBER    = "#FF9628"
_CLR_DANGER   = "#FF4444"
_CLR_MUTED    = "#8A9196"
_CLR_STATIC   = "#00AAFF"   # badge color for static gestures
_CLR_DYNAMIC  = "#FF9628"   # badge color for dynamic gestures


def _get_next_session_idx(base_path: str) -> int:
    """Return the next auto-incremented session index."""
    if not os.path.exists(base_path):
        return 1
    max_idx = 0
    for entry in os.listdir(base_path):
        full = os.path.join(base_path, entry)
        if os.path.isdir(full) and entry.startswith("session"):
            suffix = entry[7:]
            if suffix.isdigit():
                max_idx = max(max_idx, int(suffix))
    return max_idx + 1


class ConfigWindow(ctk.CTk):
    """Main configuration window.

    After the user clicks 'Start Recording', the window is destroyed and
    `self.result` holds the validated configuration dict::

        {
            "selected_indices": list[int],   # 1-based gesture indices
            "samples":          int,
        }

    If the user exits without starting, `self.result` is None.
    """

    def __init__(self) -> None:
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Gesture Dataset Collector — Configuration")
        self.geometry("740x700")
        self.minsize(680, 620)
        self.resizable(True, True)

        # Result exposed to caller after window closes
        self.result: Optional[dict] = None

        # Internal state
        self._check_vars: list[ctk.BooleanVar] = []
        self._sample_var = ctk.StringVar(value="10")
        self._next_session = _get_next_session_idx(DATASET_PATH)

        self._build_ui()
        self._update_session_info()

        # Center on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - self.winfo_width())  // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_body()
        self._build_footer()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color=("gray20", "gray15"), corner_radius=0)
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="Gesture Dataset Collector",
            font=ctk.CTkFont(family=_FONT_FAMILY, size=22, weight="bold"),
            text_color=_CLR_ACCENT,
        ).grid(row=0, column=0, sticky="w", padx=24, pady=(18, 2))

        ctk.CTkLabel(
            header,
            text="Configure your recording session below, then click Start Recording.",
            font=ctk.CTkFont(family=_FONT_FAMILY, size=12),
            text_color=_CLR_MUTED,
        ).grid(row=1, column=0, sticky="w", padx=24, pady=(0, 14))

    def _build_body(self) -> None:
        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=20, pady=(12, 0))
        body.grid_columnconfigure(0, weight=1)

        row = 0

        # ── Gesture Selection ─────────────────────────────────────────────────
        row = self._section_label(body, "Gesture Selection", row)
        row = self._build_gesture_panel(body, row)

        # ── Sample Count ──────────────────────────────────────────────────────
        row = self._section_label(body, "Samples per Gesture", row)
        row = self._build_sample_panel(body, row)

        # ── Session Info ──────────────────────────────────────────────────────
        row = self._section_label(body, "Session Information", row)
        row = self._build_info_panel(body, row)

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color=("gray20", "gray15"), corner_radius=0)
        footer.grid(row=2, column=0, sticky="ew", padx=0, pady=0)
        footer.grid_columnconfigure((0, 1, 2), weight=1)

        # Error label (inline, never crashes)
        self._error_label = ctk.CTkLabel(
            footer,
            text="",
            font=ctk.CTkFont(family=_FONT_FAMILY, size=12),
            text_color=_CLR_DANGER,
        )
        self._error_label.grid(row=0, column=0, columnspan=3, pady=(12, 0))

        btn_frame = ctk.CTkFrame(footer, fg_color="transparent")
        btn_frame.grid(row=1, column=0, columnspan=3, pady=14)

        ctk.CTkButton(
            btn_frame,
            text="Exit",
            width=130,
            height=40,
            fg_color="transparent",
            border_width=1,
            border_color=("gray50", "gray40"),
            text_color=_CLR_MUTED,
            hover_color=("gray25", "gray20"),
            font=ctk.CTkFont(family=_FONT_FAMILY, size=13),
            command=self._on_exit,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_frame,
            text="▶  Start Recording",
            width=200,
            height=40,
            fg_color=_CLR_GREEN,
            hover_color="#2BB840",
            text_color="#FFFFFF",
            font=ctk.CTkFont(family=_FONT_FAMILY, size=14, weight="bold"),
            command=self._on_start,
        ).pack(side="left")

    # ── Section helpers ───────────────────────────────────────────────────────

    def _section_label(self, parent: ctk.CTkScrollableFrame, text: str, row: int) -> int:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=0, sticky="ew", pady=(16, 4))
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            frame,
            text=text.upper(),
            font=ctk.CTkFont(family=_FONT_FAMILY, size=10, weight="bold"),
            text_color=_CLR_MUTED,
        ).grid(row=0, column=0, sticky="w")

        sep = ctk.CTkFrame(frame, height=1, fg_color=("gray35", "gray30"))
        sep.grid(row=0, column=1, sticky="ew", padx=(10, 0))

        return row + 1

    def _build_gesture_panel(self, parent: ctk.CTkScrollableFrame, row: int) -> int:
        panel = ctk.CTkFrame(parent, fg_color=("gray22", "gray17"), corner_radius=10)
        panel.grid(row=row, column=0, sticky="ew", pady=(0, 4))
        panel.grid_columnconfigure(0, weight=1)

        # Quick-select buttons
        btn_row = ctk.CTkFrame(panel, fg_color="transparent")
        btn_row.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 8))

        def _qbtn(text: str, cmd, fg=None) -> ctk.CTkButton:
            return ctk.CTkButton(
                btn_row,
                text=text,
                width=110,
                height=28,
                fg_color=fg or ("gray35", "gray30"),
                hover_color=("gray45", "gray38"),
                text_color=("#FFFFFF" if fg else _CLR_MUTED),
                font=ctk.CTkFont(family=_FONT_FAMILY, size=12),
                corner_radius=6,
                command=cmd,
            )

        _qbtn("Select All",       self._select_all).pack(side="left", padx=(0, 6))
        _qbtn("Static Only",      self._select_static,  fg=_CLR_STATIC).pack(side="left", padx=(0, 6))
        _qbtn("Dynamic Only",     self._select_dynamic, fg=_CLR_AMBER).pack(side="left", padx=(0, 6))
        _qbtn("Clear Selection",  self._select_none).pack(side="left")

        # Divider
        ctk.CTkFrame(panel, height=1, fg_color=("gray35", "gray28")).grid(
            row=1, column=0, sticky="ew", padx=14
        )

        # Gesture checkboxes
        for i, (name, desc, gtype) in enumerate(GESTURES):
            var = ctk.BooleanVar(value=True)
            self._check_vars.append(var)
            var.trace_add("write", lambda *_: self._update_session_info())

            row_frame = ctk.CTkFrame(panel, fg_color="transparent")
            row_frame.grid(row=i + 2, column=0, sticky="ew", padx=14, pady=3)
            row_frame.grid_columnconfigure(1, weight=1)

            cb = ctk.CTkCheckBox(
                row_frame,
                text="",
                variable=var,
                width=20,
                checkbox_width=18,
                checkbox_height=18,
                border_width=2,
                checkmark_color="#FFFFFF",
                fg_color=_CLR_ACCENT,
            )
            cb.grid(row=0, column=0, padx=(0, 10))

            # Name
            ctk.CTkLabel(
                row_frame,
                text=name.replace("_", " "),
                font=ctk.CTkFont(family=_FONT_FAMILY, size=13, weight="bold"),
                text_color=("gray90", "gray88"),
                anchor="w",
            ).grid(row=0, column=1, sticky="w")

            # Type badge
            badge_color = _CLR_STATIC if gtype == "static" else _CLR_DYNAMIC
            badge_frame = ctk.CTkFrame(
                row_frame,
                fg_color=badge_color,
                corner_radius=4,
                width=60,
                height=18,
            )
            badge_frame.grid(row=0, column=2, padx=(8, 0))
            badge_frame.grid_propagate(False)
            ctk.CTkLabel(
                badge_frame,
                text=gtype,
                font=ctk.CTkFont(family=_FONT_FAMILY, size=10, weight="bold"),
                text_color="#FFFFFF",
            ).place(relx=0.5, rely=0.5, anchor="center")

            # Description
            ctk.CTkLabel(
                row_frame,
                text=desc,
                font=ctk.CTkFont(family=_FONT_FAMILY, size=11),
                text_color=_CLR_MUTED,
                anchor="w",
            ).grid(row=1, column=1, columnspan=2, sticky="w")

        ctk.CTkFrame(panel, height=8, fg_color="transparent").grid(row=len(GESTURES) + 2, column=0)

        return row + 1

    def _build_sample_panel(self, parent: ctk.CTkScrollableFrame, row: int) -> int:
        panel = ctk.CTkFrame(parent, fg_color=("gray22", "gray17"), corner_radius=10)
        panel.grid(row=row, column=0, sticky="ew", pady=(0, 4))
        panel.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            panel,
            text="Videos per gesture:",
            font=ctk.CTkFont(family=_FONT_FAMILY, size=13),
            text_color=("gray85", "gray80"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=16)

        spinner_frame = ctk.CTkFrame(panel, fg_color="transparent")
        spinner_frame.grid(row=0, column=2, padx=16, pady=16)

        ctk.CTkButton(
            spinner_frame, text="−", width=34, height=34,
            fg_color=("gray35", "gray28"),
            hover_color=("gray45", "gray38"),
            font=ctk.CTkFont(family=_FONT_FAMILY, size=16),
            corner_radius=6,
            command=self._decrement_samples,
        ).pack(side="left", padx=(0, 6))

        self._sample_entry = ctk.CTkEntry(
            spinner_frame,
            textvariable=self._sample_var,
            width=64,
            height=34,
            justify="center",
            font=ctk.CTkFont(family=_FONT_FAMILY, size=14, weight="bold"),
        )
        self._sample_entry.pack(side="left")
        self._sample_var.trace_add("write", lambda *_: self._update_session_info())

        ctk.CTkButton(
            spinner_frame, text="+", width=34, height=34,
            fg_color=("gray35", "gray28"),
            hover_color=("gray45", "gray38"),
            font=ctk.CTkFont(family=_FONT_FAMILY, size=16),
            corner_radius=6,
            command=self._increment_samples,
        ).pack(side="left", padx=(6, 0))

        ctk.CTkLabel(
            panel,
            text="(positive integer, min 1)",
            font=ctk.CTkFont(family=_FONT_FAMILY, size=11),
            text_color=_CLR_MUTED,
        ).grid(row=1, column=0, columnspan=3, sticky="w", padx=16, pady=(0, 14))

        return row + 1

    def _build_info_panel(self, parent: ctk.CTkScrollableFrame, row: int) -> int:
        panel = ctk.CTkFrame(parent, fg_color=("gray22", "gray17"), corner_radius=10)
        panel.grid(row=row, column=0, sticky="ew", pady=(0, 16))
        panel.grid_columnconfigure((0, 1, 2), weight=1)

        def _info_col(col: int, label: str, attr: str) -> ctk.CTkLabel:
            ctk.CTkLabel(
                panel,
                text=label,
                font=ctk.CTkFont(family=_FONT_FAMILY, size=11),
                text_color=_CLR_MUTED,
            ).grid(row=0, column=col, padx=16, pady=(14, 2))

            value_label = ctk.CTkLabel(
                panel,
                text="—",
                font=ctk.CTkFont(family=_FONT_FAMILY, size=22, weight="bold"),
                text_color=_CLR_ACCENT,
            )
            value_label.grid(row=1, column=col, padx=16, pady=(0, 14))
            return value_label

        self._lbl_session  = _info_col(0, "Next Session #",       "session")
        self._lbl_gestures = _info_col(1, "Gestures Selected",    "gestures")
        self._lbl_total    = _info_col(2, "Total Recordings",     "total")

        # Vertical separators
        for col in (1, 2):
            ctk.CTkFrame(panel, width=1, fg_color=("gray35", "gray28")).grid(
                row=0, column=col, rowspan=2, sticky="ns", pady=10,
                padx=(0, 0), ipadx=0,
            )

        return row + 1

    # ── Quick-select callbacks ────────────────────────────────────────────────

    def _select_all(self) -> None:
        for v in self._check_vars:
            v.set(True)

    def _select_none(self) -> None:
        for v in self._check_vars:
            v.set(False)

    def _select_static(self) -> None:
        for i, v in enumerate(self._check_vars):
            v.set(GESTURES[i][2] == "static")

    def _select_dynamic(self) -> None:
        for i, v in enumerate(self._check_vars):
            v.set(GESTURES[i][2] == "dynamic")

    # ── Spinner callbacks ─────────────────────────────────────────────────────

    def _increment_samples(self) -> None:
        try:
            self._sample_var.set(str(max(1, int(self._sample_var.get()) + 1)))
        except ValueError:
            self._sample_var.set("1")

    def _decrement_samples(self) -> None:
        try:
            self._sample_var.set(str(max(1, int(self._sample_var.get()) - 1)))
        except ValueError:
            self._sample_var.set("1")

    # ── Live session info update ──────────────────────────────────────────────

    def _update_session_info(self) -> None:
        n_gestures = sum(v.get() for v in self._check_vars)
        try:
            samples = int(self._sample_var.get())
            if samples < 1:
                raise ValueError
            total = n_gestures * samples
        except ValueError:
            total = 0

        self._lbl_session.configure(text=f"{self._next_session:03d}")
        self._lbl_gestures.configure(text=str(n_gestures))
        self._lbl_total.configure(
            text=str(total),
            text_color=_CLR_GREEN if total > 0 else _CLR_DANGER,
        )

    # ── Validation ────────────────────────────────────────────────────────────

    def _validate(self) -> Optional[dict]:
        """Validate inputs; return config dict on success, None on failure."""
        selected_indices = [
            i + 1
            for i, v in enumerate(self._check_vars)
            if v.get()
        ]
        if not selected_indices:
            self._show_error("Please select at least one gesture before starting.")
            return None

        raw = self._sample_var.get().strip()
        if not raw.isdigit() or int(raw) < 1:
            self._show_error("Sample count must be a positive integer (e.g. 10).")
            return None

        self._show_error("")
        return {"selected_indices": selected_indices, "samples": int(raw)}

    def _show_error(self, msg: str) -> None:
        self._error_label.configure(text=msg)

    # ── Action callbacks ──────────────────────────────────────────────────────

    def _on_start(self) -> None:
        config = self._validate()
        if config is None:
            return
        self.result = config
        self.destroy()

    def _on_exit(self) -> None:
        self.result = None
        self.destroy()


def run_config() -> Optional[dict]:
    """Launch the configuration window and return the user's choices.

    Returns:
        dict with keys ``selected_indices`` and ``samples``, or
        ``None`` if the user closed the window without starting.
    """
    app = ConfigWindow()
    app.mainloop()
    return app.result
