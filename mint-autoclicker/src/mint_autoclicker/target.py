"""
Target Application and Process Management for Mint Auto Clicker.
Provides Cheat Engine-style application searching, process listing,
window picking, and window-confinement safety checks.
"""

import os
import select
import subprocess
import time
from typing import Dict, List, Optional, Tuple

import Xlib.display
import Xlib.error
import Xlib.protocol.event
import Xlib.X
import Xlib.Xatom


class TargetManager:
    """Manages window discovery, process scanning, and X11 target tracking."""

    @staticmethod
    def get_open_windows(exclude_desktop: bool = True) -> List[Dict]:
        """
        Scan and return all visible top-level application windows.
        Ordered by stacking order (topmost first).
        """
        disp = None
        try:
            disp = Xlib.display.Display()
            root = disp.screen().root

            atom_net_stacking = disp.intern_atom("_NET_CLIENT_LIST_STACKING")
            atom_net_clients = disp.intern_atom("_NET_CLIENT_LIST")
            atom_net_wm_name = disp.intern_atom("_NET_WM_NAME")
            atom_net_wm_pid = disp.intern_atom("_NET_WM_PID")

            prop = root.get_full_property(atom_net_stacking, Xlib.Xatom.WINDOW)
            if not prop or not prop.value:
                prop = root.get_full_property(atom_net_clients, Xlib.Xatom.WINDOW)
            if not prop or not prop.value:
                return []

            windows = []
            # Reversed so frontmost/active windows are listed first
            for wid in reversed(prop.value):
                try:
                    w = disp.create_resource_object("window", wid)
                    attrs = w.get_attributes()
                    if attrs.map_state != Xlib.X.IsViewable:
                        continue

                    # Window Title
                    title = ""
                    name_prop = w.get_full_property(atom_net_wm_name, 0)
                    if name_prop and name_prop.value:
                        try:
                            title = name_prop.value.decode("utf-8", errors="replace")
                        except Exception:
                            title = str(name_prop.value)
                    if not title:
                        title = w.get_wm_name() or ""

                    # WM_CLASS
                    wm_class = w.get_wm_class() or ("", "")
                    res_name, res_class = wm_class if len(wm_class) == 2 else ("", "")

                    # Exclude desktop manager if requested
                    if exclude_desktop and (res_class.lower() == "nemo-desktop" or title == "Desktop"):
                        continue

                    # Skip empty titleless utility windows
                    if not title and not res_name and not res_class:
                        continue

                    # Process ID
                    pid = None
                    pid_prop = w.get_full_property(atom_net_wm_pid, Xlib.Xatom.CARDINAL)
                    if pid_prop and pid_prop.value:
                        pid = pid_prop.value[0]

                    # Executable / Process name from /proc
                    exe = res_name or res_class
                    if pid:
                        try:
                            with open(f"/proc/{pid}/comm", "r", encoding="utf-8", errors="ignore") as f:
                                exe = f.read().strip()
                        except Exception:
                            pass

                    # Geometry in root screen coordinates
                    geom = w.get_geometry()
                    coords = root.translate_coords(w, 0, 0)
                    rect = (coords.x, coords.y, geom.width, geom.height)

                    # Prettified application name
                    display_app = res_class or res_name or exe or "Application"
                    # Clean up common names
                    if display_app.lower() in ("navigator", "firefox-bin"):
                        display_app = "Firefox"
                    elif display_app.lower() == "gnome-terminal-server":
                        display_app = "Terminal"

                    windows.append({
                        "wid": wid,
                        "wid_hex": hex(wid),
                        "pid": pid,
                        "title": title or "(Untitled Window)",
                        "class": res_class or "",
                        "name": res_name or "",
                        "exe": exe or "Unknown",
                        "display_app": display_app,
                        "rect": rect,
                    })
                except Exception:
                    continue

            return windows
        except Exception as e:
            print(f"Error listing open windows: {e}")
            return []
        finally:
            if disp is not None:
                try:
                    disp.close()
                except Exception:
                    pass

    @staticmethod
    def get_all_processes() -> List[Dict]:
        """
        Scan /proc to list all active system and user processes (Cheat Engine style).
        """
        procs = []
        my_uid = os.getuid()
        try:
            for entry in os.scandir("/proc"):
                if entry.is_dir() and entry.name.isdigit():
                    pid = int(entry.name)
                    try:
                        st = entry.stat()
                        is_user = (st.st_uid == my_uid)

                        comm_path = os.path.join(entry.path, "comm")
                        with open(comm_path, "r", encoding="utf-8", errors="ignore") as f:
                            name = f.read().strip()

                        cmdline_path = os.path.join(entry.path, "cmdline")
                        with open(cmdline_path, "r", encoding="utf-8", errors="ignore") as f:
                            raw_cmd = f.read().replace("\x00", " ").strip()
                            cmdline = raw_cmd if raw_cmd else name

                        procs.append({
                            "pid": pid,
                            "name": name,
                            "cmdline": cmdline,
                            "is_user": is_user,
                        })
                    except (FileNotFoundError, PermissionError, ProcessLookupError):
                        continue
        except Exception as e:
            print(f"Error listing processes: {e}")

        # Prioritize user processes, then sort alphabetically by name
        procs.sort(key=lambda p: (not p["is_user"], p["name"].lower()))
        return procs

    @staticmethod
    def pick_window_from_screen(timeout_sec: float = 15.0, ignore_wid: Optional[int] = None) -> Optional[Dict]:
        """
        Crosshair / Window Picker tool (Cheat Engine style).
        Grabs pointer, waits for user to click any window, and returns its metadata.
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
                print("Failed to grab pointer for window picking")
                return None

            fd = disp.fileno()
            start = time.time()
            click_point = None

            while time.time() - start < timeout_sec:
                r, _, _ = select.select([fd], [], [], 0.05)
                if r:
                    ev = disp.next_event()
                    if ev.type == Xlib.X.ButtonPress:
                        click_point = (ev.root_x, ev.root_y)
                        break

            root.ungrab_pointer(Xlib.X.CurrentTime)
            disp.sync()

            if not click_point:
                return None

            click_x, click_y = click_point

            # Find topmost window at (click_x, click_y)
            atom_net_stacking = disp.intern_atom("_NET_CLIENT_LIST_STACKING")
            atom_net_clients = disp.intern_atom("_NET_CLIENT_LIST")
            atom_net_wm_name = disp.intern_atom("_NET_WM_NAME")
            atom_net_wm_pid = disp.intern_atom("_NET_WM_PID")

            prop = root.get_full_property(atom_net_stacking, Xlib.Xatom.WINDOW)
            if not prop or not prop.value:
                prop = root.get_full_property(atom_net_clients, Xlib.Xatom.WINDOW)
            if not prop or not prop.value:
                return None

            for wid in reversed(prop.value):
                if ignore_wid and wid == ignore_wid:
                    continue
                try:
                    w = disp.create_resource_object("window", wid)
                    attrs = w.get_attributes()
                    if attrs.map_state != Xlib.X.IsViewable:
                        continue

                    geom = w.get_geometry()
                    coords = root.translate_coords(w, 0, 0)
                    wx, wy, ww, wh = coords.x, coords.y, geom.width, geom.height

                    if wx <= click_x <= wx + ww and wy <= click_y <= wy + wh:
                        # Found target window!
                        title = ""
                        name_prop = w.get_full_property(atom_net_wm_name, 0)
                        if name_prop and name_prop.value:
                            try:
                                title = name_prop.value.decode("utf-8", errors="replace")
                            except Exception:
                                title = str(name_prop.value)
                        if not title:
                            title = w.get_wm_name() or ""

                        wm_class = w.get_wm_class() or ("", "")
                        res_name, res_class = wm_class if len(wm_class) == 2 else ("", "")

                        pid = None
                        pid_prop = w.get_full_property(atom_net_wm_pid, Xlib.Xatom.CARDINAL)
                        if pid_prop and pid_prop.value:
                            pid = pid_prop.value[0]

                        exe = res_name or res_class
                        if pid:
                            try:
                                with open(f"/proc/{pid}/comm", "r", encoding="utf-8", errors="ignore") as f:
                                    exe = f.read().strip()
                            except Exception:
                                pass

                        display_app = res_class or res_name or exe or "Application"
                        if display_app.lower() in ("navigator", "firefox-bin"):
                            display_app = "Firefox"
                        elif display_app.lower() == "gnome-terminal-server":
                            display_app = "Terminal"

                        return {
                            "wid": wid,
                            "wid_hex": hex(wid),
                            "pid": pid,
                            "title": title or "(Untitled Window)",
                            "class": res_class or "",
                            "name": res_name or "",
                            "exe": exe or "Unknown",
                            "display_app": display_app,
                            "rect": (wx, wy, ww, wh),
                        }
                except Exception:
                    continue

            return None
        except Exception as e:
            print(f"Error picking window: {e}")
            return None
        finally:
            if disp is not None:
                try:
                    disp.close()
                except Exception:
                    pass


def get_window_geometry(disp: Xlib.display.Display, root, wid: int) -> Optional[Tuple[int, int, int, int]]:
    """
    Get screen coordinates and size (x, y, width, height) of a window.
    Returns None if window has been closed/destroyed.
    """
    try:
        w = disp.create_resource_object("window", wid)
        geom = w.get_geometry()
        coords = root.translate_coords(w, 0, 0)
        return (coords.x, coords.y, geom.width, geom.height)
    except Exception:
        return None


def is_window_active(
    disp: Xlib.display.Display,
    root,
    target_wid: int,
    target_pid: Optional[int] = None,
    target_class: Optional[str] = None,
) -> bool:
    """
    Check if the current active/foreground window matches the target.
    Matches by Window ID, PID (handles child dialogs/popups), or WM_CLASS.
    """
    try:
        atom_net_active = disp.intern_atom("_NET_ACTIVE_WINDOW")
        prop = root.get_full_property(atom_net_active, Xlib.Xatom.WINDOW)
        if not prop or not prop.value:
            return False

        active_wid = prop.value[0]
        if target_wid and active_wid == target_wid:
            return True

        # Check PID or class match
        w = disp.create_resource_object("window", active_wid)
        if target_pid:
            atom_net_wm_pid = disp.intern_atom("_NET_WM_PID")
            pid_prop = w.get_full_property(atom_net_wm_pid, Xlib.Xatom.CARDINAL)
            if pid_prop and pid_prop.value and pid_prop.value[0] == target_pid:
                return True

        if target_class:
            wm_class = w.get_wm_class()
            if wm_class and any(c.lower() == target_class.lower() for c in wm_class if c):
                return True

        return False
    except Exception:
        return False


def check_pointer_in_window(
    disp: Xlib.display.Display,
    root,
    target_wid: int,
    guard_titlebar: bool = True,
    titlebar_height: int = 32,
    fixed_coords: Optional[Tuple[int, int]] = None,
) -> Tuple[bool, str]:
    """
    Check if pointer (or fixed coordinate) is safely inside target window.
    Returns:
      (True, "ok")            - Safely inside client content area
      (False, "outside")      - Outside window boundary
      (False, "titlebar")     - In titlebar / close button area (exit protection)
      (False, "invalid")      - Target window no longer exists
    """
    geom = get_window_geometry(disp, root, target_wid)
    if geom is None:
        return False, "invalid"

    wx, wy, ww, wh = geom

    if fixed_coords is not None:
        cur_x, cur_y = fixed_coords
    else:
        try:
            qp = root.query_pointer()
            cur_x, cur_y = qp.root_x, qp.root_y
        except Exception:
            return False, "outside"

    # Confine to window rect
    if not (wx <= cur_x < wx + ww and wy <= cur_y < wy + wh):
        return False, "outside"

    # Titlebar protection against accidental window close/exit
    if guard_titlebar and (cur_y < wy + titlebar_height):
        return False, "titlebar"

    return True, "ok"


def focus_window(disp: Xlib.display.Display, wid: int) -> bool:
    """
    Bring target window to the foreground and set input focus.
    Uses EWMH _NET_ACTIVE_WINDOW with wmctrl fallback.
    """
    try:
        root = disp.screen().root
        atom_net_active = disp.intern_atom("_NET_ACTIVE_WINDOW")
        ev = Xlib.protocol.event.ClientMessage(
            window=wid,
            client_type=atom_net_active,
            data=(32, [1, Xlib.X.CurrentTime, 0, 0, 0]),
        )
        root.send_event(ev, event_mask=Xlib.X.SubstructureRedirectMask | Xlib.X.SubstructureNotifyMask)
        disp.sync()
        return True
    except Exception:
        try:
            subprocess.run(["wmctrl", "-i", "-a", hex(wid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1.0)
            return True
        except Exception:
            return False


def find_matching_window(
    disp: Xlib.display.Display,
    root,
    app_name: str,
    title: str = "",
) -> Optional[Dict]:
    """
    If a target window was closed or restarted, search for a replacement
    matching the same application executable or title.
    """
    try:
        atom_net_stacking = disp.intern_atom("_NET_CLIENT_LIST_STACKING")
        atom_net_clients = disp.intern_atom("_NET_CLIENT_LIST")
        atom_net_wm_name = disp.intern_atom("_NET_WM_NAME")
        atom_net_wm_pid = disp.intern_atom("_NET_WM_PID")

        prop = root.get_full_property(atom_net_stacking, Xlib.Xatom.WINDOW) or root.get_full_property(atom_net_clients, Xlib.Xatom.WINDOW)
        if not prop or not prop.value:
            return None

        app_name_lower = (app_name or "").lower()
        title_lower = (title or "").lower()

        for wid in reversed(prop.value):
            try:
                w = disp.create_resource_object("window", wid)
                attrs = w.get_attributes()
                if attrs.map_state != Xlib.X.IsViewable:
                    continue

                wm_class = w.get_wm_class() or ("", "")
                res_name, res_class = wm_class if len(wm_class) == 2 else ("", "")

                pid = None
                pid_prop = w.get_full_property(atom_net_wm_pid, Xlib.Xatom.CARDINAL)
                if pid_prop and pid_prop.value:
                    pid = pid_prop.value[0]

                exe = res_name or res_class
                if pid:
                    try:
                        with open(f"/proc/{pid}/comm", "r", encoding="utf-8", errors="ignore") as f:
                            exe = f.read().strip()
                    except Exception:
                        pass

                # Check match
                matches = False
                if app_name_lower and (app_name_lower in exe.lower() or app_name_lower in res_name.lower() or app_name_lower in res_class.lower()):
                    matches = True
                elif title_lower:
                    w_title = ""
                    name_prop = w.get_full_property(atom_net_wm_name, 0)
                    if name_prop and name_prop.value:
                        try:
                            w_title = name_prop.value.decode("utf-8", errors="replace")
                        except Exception:
                            w_title = str(name_prop.value)
                    if not w_title:
                        w_title = w.get_wm_name() or ""
                    if title_lower in w_title.lower():
                        matches = True

                if matches:
                    geom = w.get_geometry()
                    coords = root.translate_coords(w, 0, 0)
                    return {
                        "wid": wid,
                        "wid_hex": hex(wid),
                        "pid": pid,
                        "title": title or "(Untitled Window)",
                        "class": res_class or "",
                        "name": res_name or "",
                        "exe": exe or "Unknown",
                        "rect": (coords.x, coords.y, geom.width, geom.height),
                    }
            except Exception:
                continue
    except Exception:
        pass
    return None
