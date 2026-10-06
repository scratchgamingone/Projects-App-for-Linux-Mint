"""
Modern Graphical User Interface for Mint Auto Clicker.
Designed specifically for Linux Mint and gaming/clicking simulators.
"""

import math
import os
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Optional

from .clicker import ClickerEngine
from .config import load_config, save_config
from .dialogs import TargetSelectorDialog
from .hotkey import HotkeyListener, SUPPORTED_HOTKEYS, pick_screen_coordinates
from .target import TargetManager

# Color Palette (Mint Dark Gaming Aesthetic)
BG_DARK = "#1a1d21"
CARD_BG = "#22272e"
CARD_BORDER = "#373e47"
INPUT_BG = "#16191d"
INPUT_BORDER = "#373e47"
TEXT_MAIN = "#e6edf3"
TEXT_MUTED = "#8b949e"
MINT_GREEN = "#2ecc71"
MINT_HOVER = "#27ae60"
RED_STOP = "#e06c75"
RED_HOVER = "#be5046"
ACCENT_BLUE = "#58a6ff"
CHIP_BG = "#2d333b"
CHIP_HOVER = "#373e47"


class ModernCard(tk.Frame):
    """Bordered card container for grouping settings."""

    def __init__(self, parent, title: str = "", **kwargs):
        super().__init__(parent, bg=CARD_BG, highlightbackground=CARD_BORDER, highlightthickness=1, padx=12, pady=10, **kwargs)
        if title:
            header_frame = tk.Frame(self, bg=CARD_BG)
            header_frame.pack(fill="x", pady=(0, 8))
            
            # Subtle accent indicator bar
            bar = tk.Frame(header_frame, bg=MINT_GREEN, width=3, height=14)
            bar.pack(side="left", padx=(0, 6))
            bar.pack_propagate(False)

            lbl = tk.Label(header_frame, text=title.upper(), font=("Noto Sans", 9, "bold"), fg=TEXT_MUTED, bg=CARD_BG)
            lbl.pack(side="left")


class MintAutoClickerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Mint Auto Clicker")
        
        # Center window nicely on screen (support scrolling on smaller displays)
        win_w, win_h = 520, 770
        scr_w = self.root.winfo_screenwidth()
        scr_h = self.root.winfo_screenheight()
        pos_x = max(0, (scr_w - win_w) // 2)
        pos_y = max(0, (scr_h - win_h) // 2)
        self.root.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
        self.root.minsize(480, 620)
        self.root.configure(bg=BG_DARK)

        # Load user configuration
        self.config = load_config()

        # Engine & Hotkey
        self.engine = ClickerEngine(
            on_stop_callback=self._on_engine_stopped,
            on_status_callback=self._on_engine_status,
        )
        self.hotkey_listener = HotkeyListener(
            key_name=self.config.get("hotkey", "F6"),
            on_trigger=self._on_hotkey_pressed,
        )

        # UI State Variables
        self.var_hours = tk.StringVar(value=str(self.config.get("hours", 0)))
        self.var_mins = tk.StringVar(value=str(self.config.get("minutes", 0)))
        self.var_secs = tk.StringVar(value=str(self.config.get("seconds", 0)))
        self.var_ms = tk.StringVar(value=str(self.config.get("milliseconds", 50)))

        self.var_use_jitter = tk.BooleanVar(value=self.config.get("use_jitter", False))
        self.var_jitter_ms = tk.StringVar(value=str(self.config.get("jitter_ms", 5)))

        self.var_button = tk.StringVar(value=self.config.get("mouse_button", "left"))
        self.var_click_type = tk.StringVar(value=self.config.get("click_type", "single"))

        self.var_repeat_mode = tk.StringVar(value=self.config.get("repeat_mode", "infinite"))
        self.var_repeat_count = tk.StringVar(value=str(self.config.get("repeat_count", 100)))

        self.var_location_mode = tk.StringVar(value=self.config.get("location_mode", "current"))
        self.var_fixed_x = tk.StringVar(value=str(self.config.get("fixed_x", 0)))
        self.var_fixed_y = tk.StringVar(value=str(self.config.get("fixed_y", 0)))

        self.var_hotkey = tk.StringVar(value=self.config.get("hotkey", "F6"))
        self.var_topmost = tk.BooleanVar(value=self.config.get("always_on_top", True))
        self.var_sound = tk.BooleanVar(value=self.config.get("sound_enabled", False))

        # Target Application & Injection State (Cheat Engine style)
        self.var_target_mode = tk.StringVar(value=self.config.get("target_mode", "global"))
        self.var_target_wid = tk.IntVar(value=self.config.get("target_wid", 0))
        self.var_target_pid = tk.IntVar(value=self.config.get("target_pid", 0))
        self.var_target_app_name = tk.StringVar(value=self.config.get("target_app_name", ""))
        self.var_target_window_title = tk.StringVar(value=self.config.get("target_window_title", ""))
        self.var_target_active_only = tk.BooleanVar(value=self.config.get("target_only_when_active", True))
        self.var_target_confine = tk.BooleanVar(value=self.config.get("target_confine_to_window", True))
        self.var_target_guard_exit = tk.BooleanVar(value=self.config.get("target_guard_titlebar", True))
        self.var_target_autofocus = tk.BooleanVar(value=self.config.get("target_auto_focus", False))

        # Runtime Stats
        self._last_clicks = 0
        self._last_time = time.perf_counter()
        self._engine_status_state = "ready"

        self._set_window_icon()
        self._apply_topmost()
        self._build_ui()

        # Start hotkey listener
        self.hotkey_listener.start()

        # Polling loop for live stats & status sync
        self.root.after(100, self._periodic_update)

        # Graceful shutdown handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _set_window_icon(self):
        """Set application window icon from installed or bundled assets."""
        try:
            asset_dir = Path(__file__).parent / "assets"
            icon_path = asset_dir / "icon-64.png"
            if not icon_path.exists():
                icon_path = Path("/usr/share/icons/hicolor/64x64/apps/mint-autoclicker.png")

            if icon_path.exists():
                img = tk.PhotoImage(file=str(icon_path))
                self.root.iconphoto(True, img)
                self._icon_ref = img  # Keep reference
        except Exception as e:
            print(f"Notice: Window icon could not be set ({e})")

    def _apply_topmost(self):
        """Toggle stay on top window property."""
        self.root.attributes("-topmost", self.var_topmost.get())

    def _build_ui(self):
        """Build the complete user interface layout with smooth scrolling."""
        # Scrollable canvas setup for responsive fit on any screen size
        self.canvas = tk.Canvas(self.root, bg=BG_DARK, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=BG_DARK, padx=14, pady=10)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas_win = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.canvas_win, width=e.width),
        )
        self._bind_mousewheel(self.root)

        container = self.scrollable_frame

        # 1. Header Card with Live Status & Stats
        self._build_header_card(container)

        # 2. Target Application Card (Cheat Engine style)
        self._build_target_card(container)

        # 3. Click Interval Card
        self._build_interval_card(container)

        # 4. Mouse Options Card
        self._build_options_card(container)

        # 5. Repeat & Cursor Location Card
        self._build_repeat_and_location_card(container)

        # 6. Bottom Action & Hotkey Controls
        self._build_action_controls(container)

    def _bind_mousewheel(self, widget):
        """Enable mousewheel scrolling across all child widgets."""
        def _on_wheel(event):
            if event.num == 4:
                self.canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.canvas.yview_scroll(1, "units")
            elif event.delta:
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        widget.bind_all("<Button-4>", _on_wheel)
        widget.bind_all("<Button-5>", _on_wheel)
        widget.bind_all("<MouseWheel>", _on_wheel)

    def _build_header_card(self, parent):
        card = tk.Frame(parent, bg=CARD_BG, highlightbackground=CARD_BORDER, highlightthickness=1, padx=14, pady=12)
        card.pack(fill="x", pady=(0, 10))

        # Top line: Title & Badge
        top_row = tk.Frame(card, bg=CARD_BG)
        top_row.pack(fill="x")

        title_lbl = tk.Label(
            top_row,
            text="⚡ MINT AUTO CLICKER",
            font=("Noto Sans", 12, "bold"),
            fg=TEXT_MAIN,
            bg=CARD_BG,
        )
        title_lbl.pack(side="left")

        # Status Pill Badge
        self.status_badge = tk.Label(
            top_row,
            text="● READY",
            font=("Noto Sans", 9, "bold"),
            fg="#95a5a6",
            bg="#2c3e50",
            padx=10,
            pady=3,
        )
        self.status_badge.pack(side="right")

        # Stats Bar
        stats_frame = tk.Frame(card, bg="#1a1e24", padx=10, pady=8, highlightbackground=CARD_BORDER, highlightthickness=1)
        stats_frame.pack(fill="x", pady=(10, 0))

        self.lbl_clicks = tk.Label(stats_frame, text="Clicks: 0", font=("Noto Sans", 9, "bold"), fg=MINT_GREEN, bg="#1a1e24")
        self.lbl_clicks.pack(side="left", expand=True)

        sep1 = tk.Label(stats_frame, text="|", fg=TEXT_MUTED, bg="#1a1e24")
        sep1.pack(side="left")

        self.lbl_cps = tk.Label(stats_frame, text="Speed: 0.0 CPS", font=("Noto Sans", 9), fg=TEXT_MAIN, bg="#1a1e24")
        self.lbl_cps.pack(side="left", expand=True)

        sep2 = tk.Label(stats_frame, text="|", fg=TEXT_MUTED, bg="#1a1e24")
        sep2.pack(side="left")

        self.lbl_time = tk.Label(stats_frame, text="Time: 00:00:00", font=("Noto Sans", 9), fg=TEXT_MUTED, bg="#1a1e24")
        self.lbl_time.pack(side="left", expand=True)

    def _build_target_card(self, parent):
        card = ModernCard(parent, title="Target Application (Cheat Engine Mode)")
        card.pack(fill="x", pady=(0, 10))

        # Mode Selection Row
        mode_row = tk.Frame(card, bg=CARD_BG)
        mode_row.pack(fill="x", pady=(0, 6))

        rb_global = tk.Radiobutton(
            mode_row,
            text="🌐 Global (All Windows)",
            value="global",
            variable=self.var_target_mode,
            command=self._on_target_mode_changed,
            font=("Noto Sans", 9),
            fg=TEXT_MAIN,
            bg=CARD_BG,
            selectcolor=INPUT_BG,
            activebackground=CARD_BG,
            activeforeground=MINT_GREEN,
            highlightthickness=0,
            bd=0,
        )
        rb_global.pack(side="left")

        rb_window = tk.Radiobutton(
            mode_row,
            text="🎯 Target App (Cheat Engine)",
            value="window",
            variable=self.var_target_mode,
            command=self._on_target_mode_changed,
            font=("Noto Sans", 9, "bold"),
            fg=MINT_GREEN,
            bg=CARD_BG,
            selectcolor=INPUT_BG,
            activebackground=CARD_BG,
            activeforeground=MINT_GREEN,
            highlightthickness=0,
            bd=0,
        )
        rb_window.pack(side="left", padx=(14, 0))

        # Dynamic Content Container
        self.target_details_frame = tk.Frame(card, bg=CARD_BG)
        self.target_details_frame.pack(fill="x", pady=(2, 0))

        self._refresh_target_ui()

    def _refresh_target_ui(self):
        """Render target details and protection guards based on current mode."""
        for child in self.target_details_frame.winfo_children():
            child.destroy()

        mode = self.var_target_mode.get()
        if mode == "global":
            info_lbl = tk.Label(
                self.target_details_frame,
                text="Clicks anywhere on your desktop and all applications (Standard Mode).",
                font=("Noto Sans", 8),
                fg=TEXT_MUTED,
                bg=CARD_BG,
            )
            info_lbl.pack(anchor="w", pady=(2, 2))
            return

        # Target Window Mode (Cheat Engine style)
        has_target = bool(self.var_target_wid.get() or self.var_target_app_name.get())

        box = tk.Frame(self.target_details_frame, bg=INPUT_BG, padx=10, pady=8, highlightbackground=INPUT_BORDER, highlightthickness=1)
        box.pack(fill="x", pady=(0, 6))

        if not has_target:
            lbl_hint = tk.Label(
                box,
                text="No application attached yet. Select an opened window to lock clicks inside it:",
                font=("Noto Sans", 8, "italic"),
                fg=TEXT_MUTED,
                bg=INPUT_BG,
            )
            lbl_hint.pack(anchor="w", pady=(0, 6))

            btn_row = tk.Frame(box, bg=INPUT_BG)
            btn_row.pack(fill="x")

            btn_search = tk.Button(
                btn_row,
                text="🔍 Search & Select Application (Cheat Engine)",
                font=("Noto Sans", 8, "bold"),
                bg=MINT_GREEN,
                fg="#ffffff",
                activebackground=MINT_HOVER,
                relief="flat",
                bd=0,
                padx=10,
                pady=4,
                cursor="hand2",
                command=self._open_target_selector,
            )
            btn_search.pack(side="left", padx=(0, 6))

            btn_pick_win = tk.Button(
                btn_row,
                text="🎯 Pick Window",
                font=("Noto Sans", 8, "bold"),
                bg=CHIP_BG,
                fg=ACCENT_BLUE,
                activebackground=CHIP_HOVER,
                relief="flat",
                bd=0,
                padx=8,
                pady=4,
                cursor="hand2",
                command=self._on_pick_target_window,
            )
            btn_pick_win.pack(side="left")
        else:
            top_line = tk.Frame(box, bg=INPUT_BG)
            top_line.pack(fill="x")

            badge = tk.Label(
                top_line,
                text="● ATTACHED",
                font=("Noto Sans", 8, "bold"),
                fg="#ffffff",
                bg="#238636",
                padx=6,
                pady=1,
            )
            badge.pack(side="left", padx=(0, 8))

            app_title_text = f"{self.var_target_app_name.get()}"
            if self.var_target_window_title.get():
                app_title_text += f" - {self.var_target_window_title.get()[:32]}"

            name_lbl = tk.Label(
                top_line,
                text=app_title_text,
                font=("Noto Sans", 9, "bold"),
                fg=TEXT_MAIN,
                bg=INPUT_BG,
            )
            name_lbl.pack(side="left")

            pid_wid_text = f"PID: {self.var_target_pid.get() or 'N/A'}"
            if self.var_target_wid.get():
                pid_wid_text += f"  |  Window ID: {hex(self.var_target_wid.get())}"

            sub_lbl = tk.Label(
                box,
                text=pid_wid_text,
                font=("Noto Sans", 8),
                fg=TEXT_MUTED,
                bg=INPUT_BG,
            )
            sub_lbl.pack(anchor="w", pady=(2, 6))

            actions = tk.Frame(box, bg=INPUT_BG)
            actions.pack(fill="x")

            btn_change = tk.Button(
                actions,
                text="🔍 Change App...",
                font=("Noto Sans", 8),
                bg=CHIP_BG,
                fg=TEXT_MAIN,
                activebackground=CHIP_HOVER,
                relief="flat",
                bd=0,
                padx=8,
                pady=3,
                cursor="hand2",
                command=self._open_target_selector,
            )
            btn_change.pack(side="left", padx=(0, 6))

            btn_repick = tk.Button(
                actions,
                text="🎯 Re-pick",
                font=("Noto Sans", 8),
                bg=CHIP_BG,
                fg=ACCENT_BLUE,
                activebackground=CHIP_HOVER,
                relief="flat",
                bd=0,
                padx=8,
                pady=3,
                cursor="hand2",
                command=self._on_pick_target_window,
            )
            btn_repick.pack(side="left", padx=(0, 6))

            btn_detach = tk.Button(
                actions,
                text="✖ Detach / Global",
                font=("Noto Sans", 8),
                bg=CHIP_BG,
                fg="#e06c75",
                activebackground=CHIP_HOVER,
                relief="flat",
                bd=0,
                padx=8,
                pady=3,
                cursor="hand2",
                command=self._on_detach_target,
            )
            btn_detach.pack(side="left")

        # Confinement & Protection Safety Options
        guards_frame = tk.Frame(self.target_details_frame, bg=CARD_BG)
        guards_frame.pack(fill="x", pady=(2, 0))

        # Guard 1: Active Window Only
        chk_focus = tk.Checkbutton(
            guards_frame,
            text="Only click when target window is focused / active",
            variable=self.var_target_active_only,
            font=("Noto Sans", 8),
            fg=TEXT_MAIN,
            bg=CARD_BG,
            selectcolor=INPUT_BG,
            activebackground=CARD_BG,
            activeforeground=MINT_GREEN,
            highlightthickness=0,
            bd=0,
        )
        chk_focus.pack(anchor="w", pady=(1, 1))

        # Guard 2: Confine within window boundaries
        chk_confine = tk.Checkbutton(
            guards_frame,
            text="Confine clicks inside window boundary (Screen Lock)",
            variable=self.var_target_confine,
            font=("Noto Sans", 8),
            fg=TEXT_MAIN,
            bg=CARD_BG,
            selectcolor=INPUT_BG,
            activebackground=CARD_BG,
            activeforeground=MINT_GREEN,
            highlightthickness=0,
            bd=0,
        )
        chk_confine.pack(anchor="w", pady=(1, 1))

        # Guard 3: Titlebar & Exit Guard
        chk_exit = tk.Checkbutton(
            guards_frame,
            text="Titlebar & Exit Guard (protects close button from accidental exit)",
            variable=self.var_target_guard_exit,
            font=("Noto Sans", 8),
            fg=TEXT_MAIN,
            bg=CARD_BG,
            selectcolor=INPUT_BG,
            activebackground=CARD_BG,
            activeforeground=MINT_GREEN,
            highlightthickness=0,
            bd=0,
        )
        chk_exit.pack(anchor="w", pady=(1, 1))

        # Guard 4: Auto-focus
        chk_autofocus = tk.Checkbutton(
            guards_frame,
            text="Auto-focus target window when clicking starts",
            variable=self.var_target_autofocus,
            font=("Noto Sans", 8),
            fg=TEXT_MUTED,
            bg=CARD_BG,
            selectcolor=INPUT_BG,
            activebackground=CARD_BG,
            activeforeground=MINT_GREEN,
            highlightthickness=0,
            bd=0,
        )
        chk_autofocus.pack(anchor="w", pady=(1, 2))

    def _build_interval_card(self, parent):
        card = ModernCard(parent, title="Click Interval")
        card.pack(fill="x", pady=(0, 10))

        # Time inputs grid
        grid = tk.Frame(card, bg=CARD_BG)
        grid.pack(fill="x", pady=(0, 8))

        fields = [
            ("Hours", self.var_hours),
            ("Mins", self.var_mins),
            ("Secs", self.var_secs),
            ("Millisecs", self.var_ms),
        ]

        for idx, (label_text, var) in enumerate(fields):
            col = tk.Frame(grid, bg=CARD_BG)
            col.grid(row=0, column=idx, sticky="ew", padx=4)
            grid.grid_columnconfigure(idx, weight=1)

            entry = tk.Entry(
                col,
                textvariable=var,
                font=("Noto Sans", 11, "bold"),
                justify="center",
                bg=INPUT_BG,
                fg=TEXT_MAIN,
                insertbackground=MINT_GREEN,
                relief="flat",
                highlightbackground=INPUT_BORDER,
                highlightcolor=MINT_GREEN,
                highlightthickness=1,
            )
            entry.pack(fill="x", ipady=4)

            lbl = tk.Label(col, text=label_text, font=("Noto Sans", 8), fg=TEXT_MUTED, bg=CARD_BG)
            lbl.pack(pady=(3, 0))

        # Preset Quick Chips Row
        presets_frame = tk.Frame(card, bg=CARD_BG)
        presets_frame.pack(fill="x", pady=(4, 8))

        presets = [
            ("10 CPS (100ms)", 0, 0, 0, 100),
            ("20 CPS (50ms)", 0, 0, 0, 50),
            ("50 CPS (20ms)", 0, 0, 0, 20),
            ("100 CPS (10ms)", 0, 0, 0, 10),
            ("Max (1ms)", 0, 0, 0, 1),
        ]

        lbl_quick = tk.Label(presets_frame, text="Quick Presets:", font=("Noto Sans", 8), fg=TEXT_MUTED, bg=CARD_BG)
        lbl_quick.pack(side="left", padx=(0, 6))

        for text, h, m, s, ms in presets:
            btn = tk.Button(
                presets_frame,
                text=text.split(" ")[0],
                font=("Noto Sans", 8),
                bg=CHIP_BG,
                fg=TEXT_MAIN,
                activebackground=CHIP_HOVER,
                activeforeground=MINT_GREEN,
                relief="flat",
                bd=0,
                padx=6,
                pady=2,
                cursor="hand2",
                command=lambda h=h, m=m, s=s, ms=ms: self._apply_preset(h, m, s, ms),
            )
            btn.pack(side="left", padx=2)

        # Humanizer Jitter Checkbox & Entry (For anti-cheat bypass in simulators)
        jitter_row = tk.Frame(card, bg=CARD_BG)
        jitter_row.pack(fill="x", pady=(2, 0))

        chk_jitter = tk.Checkbutton(
            jitter_row,
            text="Humanize Jitter (± ms):",
            variable=self.var_use_jitter,
            font=("Noto Sans", 9),
            fg=TEXT_MAIN,
            bg=CARD_BG,
            selectcolor=INPUT_BG,
            activebackground=CARD_BG,
            activeforeground=MINT_GREEN,
            highlightthickness=0,
            bd=0,
        )
        chk_jitter.pack(side="left")

        ent_jitter = tk.Entry(
            jitter_row,
            textvariable=self.var_jitter_ms,
            font=("Noto Sans", 9),
            width=5,
            justify="center",
            bg=INPUT_BG,
            fg=TEXT_MAIN,
            insertbackground=MINT_GREEN,
            relief="flat",
            highlightbackground=INPUT_BORDER,
            highlightcolor=MINT_GREEN,
            highlightthickness=1,
        )
        ent_jitter.pack(side="left", padx=6, ipady=2)

        lbl_hint = tk.Label(
            jitter_row,
            text="(avoids anti-bot detection)",
            font=("Noto Sans", 8, "italic"),
            fg=TEXT_MUTED,
            bg=CARD_BG,
        )
        lbl_hint.pack(side="left")

    def _apply_preset(self, h: int, m: int, s: int, ms: int):
        """Quickly assign standard CPS intervals."""
        self.var_hours.set(str(h))
        self.var_mins.set(str(m))
        self.var_secs.set(str(s))
        self.var_ms.set(str(ms))

    def _build_options_card(self, parent):
        card = ModernCard(parent, title="Click Options")
        card.pack(fill="x", pady=(0, 10))

        row = tk.Frame(card, bg=CARD_BG)
        row.pack(fill="x")

        # Mouse Button
        btn_box = tk.Frame(row, bg=CARD_BG)
        btn_box.pack(side="left", fill="x", expand=True)

        lbl_b = tk.Label(btn_box, text="Mouse Button:", font=("Noto Sans", 8, "bold"), fg=TEXT_MUTED, bg=CARD_BG)
        lbl_b.pack(anchor="w", pady=(0, 4))

        buttons_frame = tk.Frame(btn_box, bg=CARD_BG)
        buttons_frame.pack(anchor="w")

        for val, label in [("left", "Left"), ("right", "Right"), ("middle", "Middle")]:
            rb = tk.Radiobutton(
                buttons_frame,
                text=label,
                value=val,
                variable=self.var_button,
                font=("Noto Sans", 9),
                fg=TEXT_MAIN,
                bg=CARD_BG,
                selectcolor=INPUT_BG,
                activebackground=CARD_BG,
                activeforeground=MINT_GREEN,
                highlightthickness=0,
                bd=0,
            )
            rb.pack(side="left", padx=(0, 10))

        # Click Type
        type_box = tk.Frame(row, bg=CARD_BG)
        type_box.pack(side="right", fill="x", expand=True)

        lbl_t = tk.Label(type_box, text="Click Type:", font=("Noto Sans", 8, "bold"), fg=TEXT_MUTED, bg=CARD_BG)
        lbl_t.pack(anchor="w", pady=(0, 4))

        types_frame = tk.Frame(type_box, bg=CARD_BG)
        types_frame.pack(anchor="w")

        for val, label in [("single", "Single"), ("double", "Double")]:
            rb = tk.Radiobutton(
                types_frame,
                text=label,
                value=val,
                variable=self.var_click_type,
                font=("Noto Sans", 9),
                fg=TEXT_MAIN,
                bg=CARD_BG,
                selectcolor=INPUT_BG,
                activebackground=CARD_BG,
                activeforeground=MINT_GREEN,
                highlightthickness=0,
                bd=0,
            )
            rb.pack(side="left", padx=(0, 10))

    def _build_repeat_and_location_card(self, parent):
        # Card contains both Repeat and Cursor Location to keep height balanced
        card = ModernCard(parent, title="Repeat & Location")
        card.pack(fill="x", pady=(0, 10))

        # Repeat section
        r_row = tk.Frame(card, bg=CARD_BG)
        r_row.pack(fill="x", pady=(0, 8))

        rb_inf = tk.Radiobutton(
            r_row,
            text="Repeat until stopped",
            value="infinite",
            variable=self.var_repeat_mode,
            font=("Noto Sans", 9),
            fg=TEXT_MAIN,
            bg=CARD_BG,
            selectcolor=INPUT_BG,
            activebackground=CARD_BG,
            activeforeground=MINT_GREEN,
            highlightthickness=0,
            bd=0,
        )
        rb_inf.pack(side="left")

        rb_count = tk.Radiobutton(
            r_row,
            text="Repeat:",
            value="count",
            variable=self.var_repeat_mode,
            font=("Noto Sans", 9),
            fg=TEXT_MAIN,
            bg=CARD_BG,
            selectcolor=INPUT_BG,
            activebackground=CARD_BG,
            activeforeground=MINT_GREEN,
            highlightthickness=0,
            bd=0,
        )
        rb_count.pack(side="left", padx=(14, 4))

        ent_count = tk.Entry(
            r_row,
            textvariable=self.var_repeat_count,
            font=("Noto Sans", 9),
            width=6,
            justify="center",
            bg=INPUT_BG,
            fg=TEXT_MAIN,
            insertbackground=MINT_GREEN,
            relief="flat",
            highlightbackground=INPUT_BORDER,
            highlightcolor=MINT_GREEN,
            highlightthickness=1,
        )
        ent_count.pack(side="left", ipady=2)

        lbl_times = tk.Label(r_row, text="times", font=("Noto Sans", 9), fg=TEXT_MUTED, bg=CARD_BG)
        lbl_times.pack(side="left", padx=(4, 0))

        # Divider
        sep = tk.Frame(card, bg=CARD_BORDER, height=1)
        sep.pack(fill="x", pady=6)

        # Location section
        loc_row = tk.Frame(card, bg=CARD_BG)
        loc_row.pack(fill="x")

        rb_cur = tk.Radiobutton(
            loc_row,
            text="Current cursor location",
            value="current",
            variable=self.var_location_mode,
            font=("Noto Sans", 9),
            fg=TEXT_MAIN,
            bg=CARD_BG,
            selectcolor=INPUT_BG,
            activebackground=CARD_BG,
            activeforeground=MINT_GREEN,
            highlightthickness=0,
            bd=0,
        )
        rb_cur.pack(side="left")

        rb_fix = tk.Radiobutton(
            loc_row,
            text="Fixed:",
            value="fixed",
            variable=self.var_location_mode,
            font=("Noto Sans", 9),
            fg=TEXT_MAIN,
            bg=CARD_BG,
            selectcolor=INPUT_BG,
            activebackground=CARD_BG,
            activeforeground=MINT_GREEN,
            highlightthickness=0,
            bd=0,
        )
        rb_fix.pack(side="left", padx=(14, 4))

        lbl_x = tk.Label(loc_row, text="X:", font=("Noto Sans", 8), fg=TEXT_MUTED, bg=CARD_BG)
        lbl_x.pack(side="left")

        ent_x = tk.Entry(
            loc_row,
            textvariable=self.var_fixed_x,
            font=("Noto Sans", 9),
            width=5,
            justify="center",
            bg=INPUT_BG,
            fg=TEXT_MAIN,
            insertbackground=MINT_GREEN,
            relief="flat",
            highlightbackground=INPUT_BORDER,
            highlightcolor=MINT_GREEN,
            highlightthickness=1,
        )
        ent_x.pack(side="left", padx=(2, 6), ipady=2)

        lbl_y = tk.Label(loc_row, text="Y:", font=("Noto Sans", 8), fg=TEXT_MUTED, bg=CARD_BG)
        lbl_y.pack(side="left")

        ent_y = tk.Entry(
            loc_row,
            textvariable=self.var_fixed_y,
            font=("Noto Sans", 9),
            width=5,
            justify="center",
            bg=INPUT_BG,
            fg=TEXT_MAIN,
            insertbackground=MINT_GREEN,
            relief="flat",
            highlightbackground=INPUT_BORDER,
            highlightcolor=MINT_GREEN,
            highlightthickness=1,
        )
        ent_y.pack(side="left", padx=(2, 6), ipady=2)

        self.btn_pick = tk.Button(
            loc_row,
            text="📍 Pick",
            font=("Noto Sans", 8, "bold"),
            bg=CHIP_BG,
            fg=ACCENT_BLUE,
            activebackground=CHIP_HOVER,
            activeforeground="#79c0ff",
            relief="flat",
            bd=0,
            padx=6,
            pady=3,
            cursor="hand2",
            command=self._on_pick_location_clicked,
        )
        self.btn_pick.pack(side="left")

    def _build_action_controls(self, parent):
        # Big Giant Action Button (Start / Stop)
        self.btn_toggle = tk.Button(
            parent,
            text=f"▶ START ({self.var_hotkey.get()})",
            font=("Noto Sans", 13, "bold"),
            bg=MINT_GREEN,
            fg="#ffffff",
            activebackground=MINT_HOVER,
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            cursor="hand2",
            pady=12,
            command=self.toggle_clicking,
        )
        self.btn_toggle.pack(fill="x", pady=(4, 10))

        # Bottom Bar: Hotkey selection + Topmost + Sound
        bottom_bar = tk.Frame(parent, bg=BG_DARK)
        bottom_bar.pack(fill="x")

        # Hotkey Dropdown
        hk_box = tk.Frame(bottom_bar, bg=BG_DARK)
        hk_box.pack(side="left")

        lbl_hk = tk.Label(hk_box, text="Hotkey:", font=("Noto Sans", 9), fg=TEXT_MAIN, bg=BG_DARK)
        lbl_hk.pack(side="left", padx=(0, 6))

        # OptionMenu styled
        self.opt_hotkey = ttk.Combobox(
            hk_box,
            textvariable=self.var_hotkey,
            values=SUPPORTED_HOTKEYS,
            state="readonly",
            width=6,
            font=("Noto Sans", 9, "bold"),
        )
        self.opt_hotkey.pack(side="left")
        self.opt_hotkey.bind("<<ComboboxSelected>>", self._on_hotkey_changed)

        # Quick options (Always on top + Sound)
        opts_box = tk.Frame(bottom_bar, bg=BG_DARK)
        opts_box.pack(side="right")

        chk_top = tk.Checkbutton(
            opts_box,
            text="Always on Top",
            variable=self.var_topmost,
            command=self._apply_topmost,
            font=("Noto Sans", 8),
            fg=TEXT_MAIN,
            bg=BG_DARK,
            selectcolor=INPUT_BG,
            activebackground=BG_DARK,
            activeforeground=MINT_GREEN,
            highlightthickness=0,
            bd=0,
        )
        chk_top.pack(side="left", padx=(0, 10))

        chk_snd = tk.Checkbutton(
            opts_box,
            text="Sound Chime",
            variable=self.var_sound,
            font=("Noto Sans", 8),
            fg=TEXT_MAIN,
            bg=BG_DARK,
            selectcolor=INPUT_BG,
            activebackground=BG_DARK,
            activeforeground=MINT_GREEN,
            highlightthickness=0,
            bd=0,
        )
        chk_snd.pack(side="left")

    def _on_hotkey_changed(self, event=None):
        """Update hotkey binding dynamically when user changes dropdown."""
        new_key = self.var_hotkey.get()
        self.hotkey_listener.set_hotkey(new_key)
        self._update_button_label()

    def _update_button_label(self):
        """Refresh Start/Stop button label with current hotkey."""
        key = self.var_hotkey.get()
        if self.engine.is_running:
            self.btn_toggle.configure(
                text=f"⏹ STOP ({key})",
                bg=RED_STOP,
                activebackground=RED_HOVER,
            )
        else:
            self.btn_toggle.configure(
                text=f"▶ START ({key})",
                bg=MINT_GREEN,
                activebackground=MINT_HOVER,
            )

    def _on_target_mode_changed(self):
        """Handle toggle between Global and Target Application mode."""
        if self.var_target_mode.get() == "window":
            if not self.var_target_wid.get() and not self.var_target_app_name.get():
                self._open_target_selector()
        self._refresh_target_ui()
        self.save_current_config()

    def _open_target_selector(self):
        """Open the Cheat Engine-style Target Application Selector modal."""
        TargetSelectorDialog(self.root, self._on_target_selected)

    def _on_target_selected(self, target_info: dict):
        """Callback when an application or window is attached."""
        self.var_target_mode.set("window")
        self.var_target_wid.set(target_info.get("wid", 0))
        self.var_target_pid.set(target_info.get("pid") or 0)
        self.var_target_app_name.set(target_info.get("display_app") or target_info.get("exe") or "Application")
        self.var_target_window_title.set(target_info.get("title", ""))
        self._refresh_target_ui()
        self.save_current_config()

    def _on_detach_target(self):
        """Detach from specific target window and revert to Global mode."""
        self.var_target_mode.set("global")
        self.var_target_wid.set(0)
        self.var_target_pid.set(0)
        self.var_target_app_name.set("")
        self.var_target_window_title.set("")
        self._refresh_target_ui()
        self.save_current_config()

    def _on_pick_target_window(self):
        """One-click crosshair screen window finder."""
        self.root.withdraw()
        self.root.update()

        def _worker():
            target_info = TargetManager.pick_window_from_screen(timeout_sec=15.0, ignore_wid=self.root.winfo_id())
            self.root.after(0, lambda: self._on_target_picked_from_screen(target_info))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_target_picked_from_screen(self, target_info: Optional[dict]):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        if target_info:
            self._on_target_selected(target_info)
        else:
            messagebox.showinfo("Window Finder", "No window was selected or picking timed out.", parent=self.root)

    def _on_engine_status(self, status: str):
        """Invoked by ClickerEngine when active/confinement state changes."""
        self._engine_status_state = status
        self.root.after(0, lambda: self._apply_engine_status(status))

    def _apply_engine_status(self, status: str):
        if not self.engine.is_running:
            return
        if status == "clicking":
            self.status_badge.configure(text="● CLICKING", fg="#ffffff", bg=MINT_GREEN)
        elif status == "paused_unfocused":
            self.status_badge.configure(text="⏸ NOT FOCUSED", fg="#ffffff", bg="#d35400")
        elif status == "paused_outside":
            self.status_badge.configure(text="⏸ OUTSIDE APP", fg="#ffffff", bg="#e67e22")
        elif status == "paused_titlebar":
            self.status_badge.configure(text="🛡️ EXIT GUARD", fg="#ffffff", bg="#c0392b")

    def _sync_engine_settings(self) -> bool:
        """Read UI fields and push into the clicker engine."""
        try:
            h = max(0, int(self.var_hours.get() or 0))
            m = max(0, int(self.var_mins.get() or 0))
            s = max(0, int(self.var_secs.get() or 0))
            ms = max(0, int(self.var_ms.get() or 0))
        except ValueError:
            messagebox.showerror("Invalid Interval", "Please enter valid numbers for the click interval.")
            return False

        total_sec = (h * 3600) + (m * 60) + s + (ms / 1000.0)
        if total_sec <= 0.0005:
            total_sec = 0.001  # Minimum 1ms

        self.engine.interval_sec = total_sec
        self.engine.use_jitter = self.var_use_jitter.get()

        try:
            jitter_ms = max(0, int(self.var_jitter_ms.get() or 0))
        except ValueError:
            jitter_ms = 0
        self.engine.jitter_sec = jitter_ms / 1000.0

        self.engine.button = self.var_button.get()
        self.engine.click_type = self.var_click_type.get()
        self.engine.repeat_mode = self.var_repeat_mode.get()

        try:
            count = max(1, int(self.var_repeat_count.get() or 1))
        except ValueError:
            count = 100
        self.engine.repeat_count = count

        self.engine.location_mode = self.var_location_mode.get()
        try:
            self.engine.fixed_x = int(self.var_fixed_x.get() or 0)
            self.engine.fixed_y = int(self.var_fixed_y.get() or 0)
        except ValueError:
            self.engine.fixed_x = 0
            self.engine.fixed_y = 0

        self.engine.sound_enabled = self.var_sound.get()

        # Target Application & Injection Settings
        self.engine.target_mode = self.var_target_mode.get()
        self.engine.target_wid = int(self.var_target_wid.get() or 0)
        self.engine.target_pid = int(self.var_target_pid.get() or 0) if self.var_target_pid.get() else None
        self.engine.target_name = self.var_target_app_name.get()
        self.engine.target_title = self.var_target_window_title.get()
        self.engine.target_only_when_active = self.var_target_active_only.get()
        self.engine.target_confine_to_window = self.var_target_confine.get()
        self.engine.target_guard_titlebar = self.var_target_guard_exit.get()
        self.engine.target_auto_focus = self.var_target_autofocus.get()

        return True

    def toggle_clicking(self):
        """Toggle between start and stop."""
        if self.engine.is_running:
            self.engine.stop(reason="user_toggle")
            self._set_ui_stopped()
        else:
            # Check if Target App mode is chosen but no application is attached yet
            if self.var_target_mode.get() == "window" and not self.var_target_wid.get() and not self.var_target_app_name.get():
                ans = messagebox.askyesno(
                    "Target Application Required",
                    "Cheat Engine target mode is enabled, but no application is attached yet.\n\n"
                    "Would you like to search and select an opened application now?",
                    parent=self.root,
                )
                if ans:
                    self._open_target_selector()
                return

            if not self._sync_engine_settings():
                return
            if self.engine.start():
                self._last_clicks = 0
                self._last_time = time.perf_counter()
                self._set_ui_running()

    def _on_hotkey_pressed(self):
        """Invoked when global hotkey is pressed from background thread."""
        self.root.after(0, self.toggle_clicking)

    def _on_engine_stopped(self, reason: str):
        """Invoked when clicking finishes or target application is closed."""
        def _ui_stopped():
            self._set_ui_stopped()
            if reason == "target_closed":
                messagebox.showwarning(
                    "Target Application Closed",
                    "The target application was closed. Mint Auto Clicker has safely stopped to prevent clicks outside.",
                    parent=self.root,
                )
        self.root.after(0, _ui_stopped)

    def _set_ui_running(self):
        """Update visual badge and buttons to RUNNING state."""
        self.status_badge.configure(text="● CLICKING", fg="#ffffff", bg=MINT_GREEN)
        self._update_button_label()

    def _set_ui_stopped(self):
        """Update visual badge and buttons to STOPPED state."""
        self.status_badge.configure(text="● READY", fg="#95a5a6", bg="#2c3e50")
        self._update_button_label()

    def _periodic_update(self):
        """Periodic UI updater for stats, elapsed time, CPS calculation, and target status."""
        if self.engine.is_running:
            now = time.perf_counter()
            total_clicks = self.engine.click_count
            elapsed = max(0.001, now - self.engine.start_time)

            # CPS over elapsed session
            cps = total_clicks / elapsed

            # Format HH:MM:SS
            secs_int = int(elapsed)
            hours = secs_int // 3600
            mins = (secs_int % 3600) // 60
            secs = secs_int % 60
            time_str = f"{hours:02d}:{mins:02d}:{secs:02d}"

            self.lbl_clicks.configure(text=f"Clicks: {total_clicks:,}")

            # Show paused reason if clicking is temporarily halted
            if self._engine_status_state == "paused_unfocused":
                self.lbl_cps.configure(text="Speed: Paused (Window not active)")
            elif self._engine_status_state == "paused_outside":
                self.lbl_cps.configure(text="Speed: Paused (Outside window)")
            elif self._engine_status_state == "paused_titlebar":
                self.lbl_cps.configure(text="Speed: Protected (Close button)")
            else:
                self.lbl_cps.configure(text=f"Speed: {cps:.1f} CPS")

            self.lbl_time.configure(text=f"Time: {time_str}")

        self.root.after(100, self._periodic_update)

    def _on_pick_location_clicked(self):
        """Handle user clicking 'Pick Location'."""
        self.btn_pick.configure(text="Click target...", fg=MINT_GREEN)
        self.status_badge.configure(text="● PICK COORDS", fg="#ffffff", bg="#e67e22")

        def _worker():
            coords = pick_screen_coordinates(timeout_sec=15.0)
            self.root.after(0, lambda: self._on_coords_picked(coords))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_coords_picked(self, coords: Optional[tuple]):
        self.btn_pick.configure(text="📍 Pick", fg=ACCENT_BLUE)
        if coords:
            x, y = coords
            self.var_fixed_x.set(str(x))
            self.var_fixed_y.set(str(y))
            self.var_location_mode.set("fixed")
        if not self.engine.is_running:
            self._set_ui_stopped()

    def save_current_config(self):
        """Save form state to disk."""
        try:
            cfg = {
                "hours": int(self.var_hours.get() or 0),
                "minutes": int(self.var_mins.get() or 0),
                "seconds": int(self.var_secs.get() or 0),
                "milliseconds": int(self.var_ms.get() or 50),
                "use_jitter": self.var_use_jitter.get(),
                "jitter_ms": int(self.var_jitter_ms.get() or 5),
                "mouse_button": self.var_button.get(),
                "click_type": self.var_click_type.get(),
                "repeat_mode": self.var_repeat_mode.get(),
                "repeat_count": int(self.var_repeat_count.get() or 100),
                "location_mode": self.var_location_mode.get(),
                "fixed_x": int(self.var_fixed_x.get() or 0),
                "fixed_y": int(self.var_fixed_y.get() or 0),
                "hotkey": self.var_hotkey.get(),
                "always_on_top": self.var_topmost.get(),
                "sound_enabled": self.var_sound.get(),
                "target_mode": self.var_target_mode.get(),
                "target_wid": int(self.var_target_wid.get() or 0),
                "target_pid": int(self.var_target_pid.get() or 0),
                "target_app_name": self.var_target_app_name.get(),
                "target_window_title": self.var_target_window_title.get(),
                "target_only_when_active": self.var_target_active_only.get(),
                "target_confine_to_window": self.var_target_confine.get(),
                "target_guard_titlebar": self.var_target_guard_exit.get(),
                "target_auto_focus": self.var_target_autofocus.get(),
            }
            save_config(cfg)
        except Exception as e:
            print(f"Notice: Failed to persist config ({e})")

    def on_close(self):
        """Clean application shutdown."""
        self.engine.stop()
        self.hotkey_listener.stop()
        self.save_current_config()
        self.root.destroy()


def run_gui():
    """Main application entry point."""
    root = tk.Tk()
    app = MintAutoClickerApp(root)
    root.mainloop()
