"""
Global X11 hotkey listener and screen coordinate picker for Mint Auto Clicker.
Listens for keyboard shortcuts system-wide (even when unfocused/in games).
"""

import select
import threading
import time
from typing import Callable, Optional, Tuple

import Xlib.display
import Xlib.X
import Xlib.XK

# Standard function keys and gaming-friendly hotkeys
SUPPORTED_HOTKEYS = [
    "F6",
    "F7",
    "F8",
    "F9",
    "F10",
    "F11",
    "F12",
    "F1",
    "F2",
    "F3",
    "F4",
    "F5",
    "Pause",
    "Scroll_Lock",
    "Insert",
    "Home",
    "End",
]

class HotkeyListener:
    """Manages global hotkey listening across X11 desktop and applications."""

    def __init__(self, key_name: str = "F6", on_trigger: Optional[Callable[[], None]] = None):
        self.key_name = key_name
        self.on_trigger = on_trigger
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._disp: Optional[Xlib.display.Display] = None
        self._current_keycode = 0
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start listening in a background thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="MintAutoClickerHotkeyListener", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop listening and clean up grabbed keys."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None

    def set_hotkey(self, new_key_name: str) -> bool:
        """Change the active hotkey dynamically."""
        with self._lock:
            if new_key_name == self.key_name:
                return True
            old_key = self.key_name
            self.key_name = new_key_name

        # Restart listener with the new key
        self.stop()
        self.start()
        return True

    def _run(self) -> None:
        """Background listener loop."""
        try:
            self._disp = Xlib.display.Display()
            root = self._disp.screen().root

            # Resolve keysym & keycode
            keysym = Xlib.XK.string_to_keysym(self.key_name)
            if keysym == 0:
                print(f"Error: Unknown keysym '{self.key_name}'")
                return

            self._current_keycode = self._disp.keysym_to_keycode(keysym)
            if self._current_keycode == 0:
                print(f"Error: Could not resolve keycode for '{self.key_name}'")
                return

            # Grab key with AnyModifier on root window
            root.grab_key(
                self._current_keycode,
                Xlib.X.AnyModifier,
                1,
                Xlib.X.GrabModeAsync,
                Xlib.X.GrabModeAsync,
            )
            self._disp.sync()

            fd = self._disp.fileno()

            while not self._stop_event.is_set():
                # Process any pending events in the queue
                while self._disp.pending_events() > 0:
                    ev = self._disp.next_event()
                    if ev.type == Xlib.X.KeyPress and getattr(ev, "detail", 0) == self._current_keycode:
                        if self.on_trigger:
                            try:
                                self.on_trigger()
                            except Exception as e:
                                print(f"Error in hotkey trigger callback: {e}")

                # Wait for next event or stop signal
                r, _, _ = select.select([fd], [], [], 0.05)
                if r and not self._stop_event.is_set():
                    ev = self._disp.next_event()
                    if ev.type == Xlib.X.KeyPress and getattr(ev, "detail", 0) == self._current_keycode:
                        if self.on_trigger:
                            try:
                                self.on_trigger()
                            except Exception as e:
                                print(f"Error in hotkey trigger callback: {e}")

        except Exception as e:
            print(f"Error in HotkeyListener thread: {e}")
        finally:
            if self._disp is not None:
                try:
                    root = self._disp.screen().root
                    if self._current_keycode:
                        root.ungrab_key(self._current_keycode, Xlib.X.AnyModifier)
                        self._disp.sync()
                    self._disp.close()
                except Exception:
                    pass
                self._disp = None


def pick_screen_coordinates(timeout_sec: float = 15.0) -> Optional[Tuple[int, int]]:
    """
    Grabs the pointer and waits for a single mouse click anywhere on screen.
    Returns (x, y) coordinates or None if timed out/cancelled.
    """
    disp = None
    try:
        disp = Xlib.display.Display()
        root = disp.screen().root

        # Grab pointer
        status = root.grab_pointer(
            True,
            Xlib.X.ButtonPressMask | Xlib.X.ButtonReleaseMask,
            Xlib.X.GrabModeAsync,
            Xlib.X.GrabModeAsync,
            Xlib.X.NONE,
            Xlib.X.NONE,
            Xlib.X.CurrentTime,
        )
        disp.sync()
        if status != 0:
            print("Failed to grab pointer for coordinate picking")
            return None

        fd = disp.fileno()
        start = time.time()
        coords = None

        while time.time() - start < timeout_sec:
            r, _, _ = select.select([fd], [], [], 0.05)
            if r:
                ev = disp.next_event()
                if ev.type == Xlib.X.ButtonPress:
                    coords = (ev.root_x, ev.root_y)
                    break

        disp.ungrab_pointer(Xlib.X.CurrentTime)
        disp.sync()
        return coords

    except Exception as e:
        print(f"Error in pick_screen_coordinates: {e}")
        return None
    finally:
        if disp is not None:
            try:
                disp.close()
            except Exception:
                pass
