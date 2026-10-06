"""
High-performance X11 mouse clicker engine for Linux.
Supports custom intervals, CPS presets, humanized jitter, fixed coordinates,
single/double clicks, and repeat limits.
"""

import random
import subprocess
import threading
import time
from typing import Callable, Optional

import Xlib.display
import Xlib.X
import Xlib.ext.xtest

from .target import (
    find_matching_window,
    focus_window,
    get_window_geometry,
    is_window_active,
)

BUTTON_MAP = {
    "left": 1,
    "middle": 2,
    "right": 3,
}

def play_toggle_sound(is_start: bool) -> None:
    """Subtly play an audio cue in background without blocking."""
    def _play():
        try:
            # Try canberra-gtk-play first (standard on Linux Mint / Ubuntu)
            snd = "bell" if is_start else "dialog-warning"
            proc = subprocess.run(
                ["canberra-gtk-play", "-i", snd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1.0,
            )
            if proc.returncode != 0:
                # Fallback to terminal bell
                print("\a", end="", flush=True)
        except Exception:
            pass

    threading.Thread(target=_play, daemon=True).start()


class ClickerEngine:
    """Manages the background clicking thread with high precision timing and window injection/locking."""

    def __init__(
        self,
        on_click_callback: Optional[Callable[[int], None]] = None,
        on_stop_callback: Optional[Callable[[str], None]] = None,
        on_status_callback: Optional[Callable[[str], None]] = None,
    ):
        self.on_click = on_click_callback
        self.on_stop = on_stop_callback
        self.on_status = on_status_callback

        self._running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Settings
        self.interval_sec = 0.050  # 50ms default (20 CPS)
        self.use_jitter = False
        self.jitter_sec = 0.005    # ±5ms
        self.button = "left"
        self.click_type = "single"
        self.repeat_mode = "infinite"  # "infinite" or "count"
        self.repeat_count = 100
        self.location_mode = "current"  # "current" or "fixed"
        self.fixed_x = 0
        self.fixed_y = 0
        self.sound_enabled = False

        # Target Application Settings (Cheat Engine style injection/locking)
        self.target_mode = "global"  # "global" or "window"
        self.target_wid = 0
        self.target_pid: Optional[int] = None
        self.target_name = ""
        self.target_title = ""
        self.target_class = ""
        self.target_only_when_active = True
        self.target_confine_to_window = True
        self.target_guard_titlebar = True
        self.target_auto_focus = False

        # Stats & State
        self.click_count = 0
        self.start_time = 0.0
        self.target_state = "ready"

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> bool:
        """Start clicking in a dedicated background thread."""
        if self._running:
            return False

        self._running = True
        self._stop_event.clear()
        self.click_count = 0
        self.start_time = time.perf_counter()
        self.target_state = "clicking"

        if self.sound_enabled:
            play_toggle_sound(True)

        self._thread = threading.Thread(target=self._run_loop, name="MintAutoClickerWorker", daemon=True)
        self._thread.start()
        return True

    def stop(self, reason: str = "manual") -> bool:
        """Stop clicking."""
        if not self._running:
            return False

        self._running = False
        self._stop_event.set()
        self.target_state = "ready"

        if self.sound_enabled:
            play_toggle_sound(False)

        if self.on_stop:
            try:
                self.on_stop(reason)
            except Exception as e:
                print(f"Error in on_stop callback: {e}")

        return True

    def _run_loop(self) -> None:
        """Core clicking loop running on a dedicated Xlib connection."""
        disp = None
        try:
            disp = Xlib.display.Display()
            root = disp.screen().root
            btn_code = BUTTON_MAP.get(self.button.lower(), 1)
            is_double = self.click_type.lower() == "double"
            use_fixed = self.location_mode == "fixed"

            # Auto-focus target window if requested
            if self.target_mode == "window" and self.target_auto_focus and self.target_wid:
                focus_window(disp, self.target_wid)
                time.sleep(0.08)

            target_time = time.perf_counter()
            last_reported_state = None

            while not self._stop_event.is_set():
                # Check repeat count limit
                if self.repeat_mode == "count" and self.click_count >= self.repeat_count:
                    # Limit reached
                    self._running = False
                    self._stop_event.set()
                    if self.on_stop:
                        self.on_stop("count_reached")
                    break

                # Target Application Validation & Confinement Checks
                if self.target_mode == "window" and self.target_wid:
                    # 1. Check window validity and get geometry
                    geom = get_window_geometry(disp, root, self.target_wid)
                    if geom is None:
                        # Try to re-find window if process reloaded
                        new_win = find_matching_window(disp, root, self.target_name, self.target_title)
                        if new_win:
                            self.target_wid = new_win["wid"]
                            geom = new_win["rect"]
                        else:
                            # Target window closed - stop cleanly!
                            self._running = False
                            self._stop_event.set()
                            if self.on_stop:
                                self.on_stop("target_closed")
                            break

                    wx, wy, ww, wh = geom

                    # 2. Check if target window is active/focused in foreground
                    if self.target_only_when_active:
                        if not is_window_active(disp, root, self.target_wid, self.target_pid, self.target_class):
                            if last_reported_state != "paused_unfocused":
                                last_reported_state = "paused_unfocused"
                                self.target_state = "paused_unfocused"
                                if self.on_status:
                                    try:
                                        self.on_status("paused_unfocused")
                                    except Exception:
                                        pass
                            time.sleep(0.04)
                            target_time = time.perf_counter()
                            continue

                    # 3. Check cursor location relative to window boundary
                    if use_fixed:
                        cur_x, cur_y = int(self.fixed_x), int(self.fixed_y)
                    else:
                        try:
                            qp = root.query_pointer()
                            cur_x, cur_y = qp.root_x, qp.root_y
                        except Exception:
                            cur_x, cur_y = 0, 0

                    if self.target_confine_to_window:
                        if not (wx <= cur_x < wx + ww and wy <= cur_y < wy + wh):
                            if last_reported_state != "paused_outside":
                                last_reported_state = "paused_outside"
                                self.target_state = "paused_outside"
                                if self.on_status:
                                    try:
                                        self.on_status("paused_outside")
                                    except Exception:
                                        pass
                            time.sleep(0.04)
                            target_time = time.perf_counter()
                            continue

                    # 4. Guard window titlebar / close button against accidental exit
                    if self.target_guard_titlebar:
                        if cur_y < wy + 32:
                            if last_reported_state != "paused_titlebar":
                                last_reported_state = "paused_titlebar"
                                self.target_state = "paused_titlebar"
                                if self.on_status:
                                    try:
                                        self.on_status("paused_titlebar")
                                    except Exception:
                                        pass
                            time.sleep(0.04)
                            target_time = time.perf_counter()
                            continue

                if last_reported_state != "clicking":
                    last_reported_state = "clicking"
                    self.target_state = "clicking"
                    if self.on_status:
                        try:
                            self.on_status("clicking")
                        except Exception:
                            pass

                # Handle coordinate positioning if fixed location
                if use_fixed:
                    Xlib.ext.xtest.fake_input(disp, Xlib.X.MotionNotify, x=int(self.fixed_x), y=int(self.fixed_y))
                    disp.sync()

                # Calculate press down duration (must be long enough for games/simulators to register)
                down_time = min(0.008, max(0.002, self.interval_sec / 3.0))

                # Perform click (single or double)
                Xlib.ext.xtest.fake_input(disp, Xlib.X.ButtonPress, btn_code)
                disp.sync()
                time.sleep(down_time)
                Xlib.ext.xtest.fake_input(disp, Xlib.X.ButtonRelease, btn_code)
                disp.sync()

                if is_double:
                    # Small gap between double clicks
                    time.sleep(0.025)
                    Xlib.ext.xtest.fake_input(disp, Xlib.X.ButtonPress, btn_code)
                    disp.sync()
                    time.sleep(down_time)
                    Xlib.ext.xtest.fake_input(disp, Xlib.X.ButtonRelease, btn_code)
                    disp.sync()

                self.click_count += 1

                # Notify callback
                if self.on_click:
                    try:
                        self.on_click(self.click_count)
                    except Exception:
                        pass

                # Calculate next interval with jitter if enabled
                current_interval = self.interval_sec
                if self.use_jitter and self.jitter_sec > 0:
                    delta = random.uniform(-self.jitter_sec, self.jitter_sec)
                    current_interval = max(0.001, current_interval + delta)

                # High precision timing loop
                target_time += current_interval
                now = time.perf_counter()
                delay = target_time - now

                if delay > 0:
                    # Split sleep into small slices so stop_event is responsive
                    if delay > 0.05:
                        wake_target = now + delay
                        while not self._stop_event.is_set():
                            remaining = wake_target - time.perf_counter()
                            if remaining <= 0:
                                break
                            time.sleep(min(0.02, remaining))
                    else:
                        time.sleep(delay)
                else:
                    # Running behind; reset anchor to avoid burst clicking
                    target_time = time.perf_counter()

        except Exception as e:
            print(f"Error in ClickerEngine worker: {e}")
        finally:
            if disp is not None:
                try:
                    disp.close()
                except Exception:
                    pass
            self._running = False
