"""
Cheat Engine-style Target Application and Process Selector Dialog.
Allows user to search open application windows or running processes,
use a screen crosshair/window finder, and inject/attach the clicker.
"""

import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Dict, List, Optional

from .target import TargetManager

# Shared Dark Theme Colors
BG_DARK = "#1a1d21"
CARD_BG = "#22272e"
CARD_BORDER = "#373e47"
INPUT_BG = "#16191d"
INPUT_BORDER = "#373e47"
TEXT_MAIN = "#e6edf3"
TEXT_MUTED = "#8b949e"
MINT_GREEN = "#2ecc71"
MINT_HOVER = "#27ae60"
CHIP_BG = "#2d333b"
CHIP_HOVER = "#373e47"
ACCENT_BLUE = "#58a6ff"


class TargetSelectorDialog:
    """Cheat Engine style process/window selector modal dialog."""

    def __init__(self, parent: tk.Tk, on_select: Callable[[Dict], None]):
        self.parent = parent
        self.on_select = on_select

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Select Target Application")
        self.dialog.configure(bg=BG_DARK)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Geometry & centering
        dlg_w, dlg_h = 600, 520
        p_x = parent.winfo_rootx()
        p_y = parent.winfo_rooty()
        p_w = parent.winfo_width()
        p_h = parent.winfo_height()
        pos_x = max(20, p_x + (p_w - dlg_w) // 2)
        pos_y = max(20, p_y + (p_h - dlg_h) // 2)
        self.dialog.geometry(f"{dlg_w}x{dlg_h}+{pos_x}+{pos_y}")
        self.dialog.minsize(500, 420)

        # State
        self.view_mode = tk.StringVar(value="windows")  # "windows" or "processes"
        self.search_var = tk.StringVar(value="")
        self.hide_desktop = tk.BooleanVar(value=True)

        self.windows_cache: List[Dict] = []
        self.processes_cache: List[Dict] = []

        self._init_styles()
        self._build_ui()
        self._refresh_data()

        # Keyboard shortcuts
        self.dialog.bind("<Escape>", lambda e: self.dialog.destroy())
        self.dialog.bind("<Return>", lambda e: self._on_attach_clicked())

        # Focus search bar
        self.ent_search.focus_set()

    def _init_styles(self):
        style = ttk.Style(self.dialog)
        style.theme_use("clam")
        style.configure(
            "Target.Treeview",
            background=INPUT_BG,
            foreground=TEXT_MAIN,
            fieldbackground=INPUT_BG,
            rowheight=26,
            font=("Noto Sans", 9),
            borderwidth=0,
        )
        style.configure(
            "Target.Treeview.Heading",
            background=CARD_BG,
            foreground=TEXT_MUTED,
            relief="flat",
            font=("Noto Sans", 9, "bold"),
            padding=4,
        )
        style.map(
            "Target.Treeview",
            background=[("selected", "#238636")],
            foreground=[("selected", "#ffffff")],
        )

    def _build_ui(self):
        main_frame = tk.Frame(self.dialog, bg=BG_DARK, padx=14, pady=12)
        main_frame.pack(fill="both", expand=True)

        # 1. Header Banner
        header = tk.Frame(main_frame, bg=CARD_BG, padx=12, pady=10, highlightbackground=CARD_BORDER, highlightthickness=1)
        header.pack(fill="x", pady=(0, 10))

        h_title = tk.Label(
            header,
            text="🖥️ TARGET APPLICATION SELECTOR",
            font=("Noto Sans", 11, "bold"),
            fg=TEXT_MAIN,
            bg=CARD_BG,
        )
        h_title.pack(anchor="w")

        h_sub = tk.Label(
            header,
            text="Search and attach Mint Auto Clicker to a specific window or process (Cheat Engine style)",
            font=("Noto Sans", 8),
            fg=TEXT_MUTED,
            bg=CARD_BG,
        )
        h_sub.pack(anchor="w", pady=(2, 0))

        # 2. Search & Tab Controls Frame
        controls = tk.Frame(main_frame, bg=BG_DARK)
        controls.pack(fill="x", pady=(0, 8))

        # Mode Tabs: Windows vs Processes
        tabs_frame = tk.Frame(controls, bg=BG_DARK)
        tabs_frame.pack(side="left")

        self.btn_tab_wins = tk.Button(
            tabs_frame,
            text="🖥️ Open Windows",
            font=("Noto Sans", 9, "bold"),
            bg="#238636",
            fg="#ffffff",
            relief="flat",
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
            command=lambda: self._set_mode("windows"),
        )
        self.btn_tab_wins.pack(side="left", padx=(0, 4))

        self.btn_tab_procs = tk.Button(
            tabs_frame,
            text="⚙️ All Processes",
            font=("Noto Sans", 9),
            bg=CHIP_BG,
            fg=TEXT_MAIN,
            relief="flat",
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
            command=lambda: self._set_mode("processes"),
        )
        self.btn_tab_procs.pack(side="left")

        # Search Bar
        search_box = tk.Frame(controls, bg=INPUT_BG, highlightbackground=INPUT_BORDER, highlightthickness=1)
        search_box.pack(side="right", fill="x", expand=True, padx=(14, 0))

        lbl_s = tk.Label(search_box, text="🔍", bg=INPUT_BG, fg=TEXT_MUTED, font=("Noto Sans", 9))
        lbl_s.pack(side="left", padx=(6, 2))

        self.ent_search = tk.Entry(
            search_box,
            textvariable=self.search_var,
            bg=INPUT_BG,
            fg=TEXT_MAIN,
            font=("Noto Sans", 9),
            insertbackground=MINT_GREEN,
            relief="flat",
            bd=0,
        )
        self.ent_search.pack(side="left", fill="x", expand=True, ipady=4)
        self.search_var.trace_add("write", lambda *args: self._filter_tree())
        self.ent_search.bind("<Down>", lambda e: self.tree.focus_set())

        btn_clear = tk.Button(
            search_box,
            text="✖",
            bg=INPUT_BG,
            fg=TEXT_MUTED,
            font=("Noto Sans", 8),
            activebackground=INPUT_BG,
            activeforeground=TEXT_MAIN,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=lambda: self.search_var.set(""),
        )
        btn_clear.pack(side="right", padx=(2, 6))

        # 3. Table / Treeview Container
        tree_container = tk.Frame(main_frame, bg=CARD_BORDER, padx=1, pady=1)
        tree_container.pack(fill="both", expand=True, pady=(0, 10))

        self.tree = ttk.Treeview(
            tree_container,
            style="Target.Treeview",
            selectmode="browse",
            show="headings",
        )
        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.bind("<Double-1>", lambda e: self._on_attach_clicked())

        # 4. Bottom Action Bar
        bottom = tk.Frame(main_frame, bg=BG_DARK)
        bottom.pack(fill="x")

        # Left tools: Pick window & Refresh
        left_tools = tk.Frame(bottom, bg=BG_DARK)
        left_tools.pack(side="left")

        self.btn_finder = tk.Button(
            left_tools,
            text="🎯 Pick Window from Screen",
            font=("Noto Sans", 9, "bold"),
            bg=CHIP_BG,
            fg=ACCENT_BLUE,
            activebackground=CHIP_HOVER,
            activeforeground="#79c0ff",
            relief="flat",
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
            command=self._on_pick_window_clicked,
        )
        self.btn_finder.pack(side="left", padx=(0, 6))

        btn_refresh = tk.Button(
            left_tools,
            text="🔄 Refresh",
            font=("Noto Sans", 9),
            bg=CHIP_BG,
            fg=TEXT_MAIN,
            activebackground=CHIP_HOVER,
            relief="flat",
            bd=0,
            padx=8,
            pady=6,
            cursor="hand2",
            command=self._refresh_data,
        )
        btn_refresh.pack(side="left")

        # Right actions: Cancel & Attach
        right_tools = tk.Frame(bottom, bg=BG_DARK)
        right_tools.pack(side="right")

        btn_cancel = tk.Button(
            right_tools,
            text="Cancel",
            font=("Noto Sans", 9),
            bg=CHIP_BG,
            fg=TEXT_MAIN,
            activebackground=CHIP_HOVER,
            relief="flat",
            bd=0,
            padx=12,
            pady=6,
            cursor="hand2",
            command=self.dialog.destroy,
        )
        btn_cancel.pack(side="left", padx=(0, 6))

        self.btn_attach = tk.Button(
            right_tools,
            text="💉 Attach to Application",
            font=("Noto Sans", 9, "bold"),
            bg=MINT_GREEN,
            fg="#ffffff",
            activebackground=MINT_HOVER,
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=self._on_attach_clicked,
        )
        self.btn_attach.pack(side="left")

    def _set_mode(self, mode: str):
        """Toggle between Open Windows and All Processes view."""
        self.view_mode.set(mode)
        if mode == "windows":
            self.btn_tab_wins.configure(bg="#238636", fg="#ffffff", font=("Noto Sans", 9, "bold"))
            self.btn_tab_procs.configure(bg=CHIP_BG, fg=TEXT_MAIN, font=("Noto Sans", 9))
            self.btn_finder.configure(state="normal")
        else:
            self.btn_tab_wins.configure(bg=CHIP_BG, fg=TEXT_MAIN, font=("Noto Sans", 9))
            self.btn_tab_procs.configure(bg="#238636", fg="#ffffff", font=("Noto Sans", 9, "bold"))
            self.btn_finder.configure(state="disabled")

        self._configure_tree_columns()
        self._filter_tree()

    def _configure_tree_columns(self):
        mode = self.view_mode.get()
        if mode == "windows":
            self.tree.configure(columns=("app", "title", "pid", "wid"))
            self.tree.heading("app", text="Application", anchor="w")
            self.tree.heading("title", text="Window Title", anchor="w")
            self.tree.heading("pid", text="PID", anchor="center")
            self.tree.heading("wid", text="Window ID", anchor="center")

            self.tree.column("app", width=120, minwidth=80, stretch=False)
            self.tree.column("title", width=270, minwidth=150, stretch=True)
            self.tree.column("pid", width=70, minwidth=50, stretch=False, anchor="center")
            self.tree.column("wid", width=90, minwidth=70, stretch=False, anchor="center")
        else:
            self.tree.configure(columns=("name", "pid", "cmd"))
            self.tree.heading("name", text="Process Name", anchor="w")
            self.tree.heading("pid", text="PID", anchor="center")
            self.tree.heading("cmd", text="Command / Path", anchor="w")

            self.tree.column("name", width=140, minwidth=100, stretch=False)
            self.tree.column("pid", width=70, minwidth=50, stretch=False, anchor="center")
            self.tree.column("cmd", width=340, minwidth=180, stretch=True)

    def _refresh_data(self):
        """Fetch fresh window and process lists in background without freezing UI."""
        self.tree.delete(*self.tree.get_children())
        self.btn_attach.configure(state="disabled")

        def _worker():
            wins = TargetManager.get_open_windows(exclude_desktop=self.hide_desktop.get())
            procs = TargetManager.get_all_processes()
            self.dialog.after(0, lambda: self._on_data_loaded(wins, procs))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_data_loaded(self, wins: List[Dict], procs: List[Dict]):
        self.windows_cache = wins
        self.processes_cache = procs
        self.btn_attach.configure(state="normal")
        self._configure_tree_columns()
        self._filter_tree()

    def _filter_tree(self):
        """Filter table items based on current search query."""
        self.tree.delete(*self.tree.get_children())
        query = self.search_var.get().strip().lower()
        mode = self.view_mode.get()

        if mode == "windows":
            for item in self.windows_cache:
                app_str = item.get("display_app", "")
                title_str = item.get("title", "")
                pid_str = str(item.get("pid", ""))
                wid_str = item.get("wid_hex", "")

                if not query or (
                    query in app_str.lower()
                    or query in title_str.lower()
                    or query in pid_str
                    or query in wid_str.lower()
                    or query in item.get("exe", "").lower()
                ):
                    iid = f"win_{item['wid']}"
                    self.tree.insert(
                        "",
                        "end",
                        iid=iid,
                        values=(app_str, title_str, pid_str or "-", wid_str),
                    )
        else:
            for item in self.processes_cache:
                name_str = item.get("name", "")
                pid_str = str(item.get("pid", ""))
                cmd_str = item.get("cmdline", "")

                if not query or (
                    query in name_str.lower()
                    or query in pid_str
                    or query in cmd_str.lower()
                ):
                    iid = f"proc_{item['pid']}"
                    self.tree.insert(
                        "",
                        "end",
                        iid=iid,
                        values=(name_str, pid_str, cmd_str),
                    )

        # Select first match by default if available
        children = self.tree.get_children()
        if children:
            self.tree.selection_set(children[0])
            self.tree.focus(children[0])

    def _on_pick_window_clicked(self):
        """Screen crosshair tool: Click any window on screen to pick it."""
        self.dialog.withdraw()  # Hide modal temporarily
        self.parent.update()

        def _pick_worker():
            try:
                # Give user a brief moment to click
                target_info = TargetManager.pick_window_from_screen(timeout_sec=15.0)
            except Exception:
                target_info = None

            self.dialog.after(0, lambda: self._on_picked_from_screen(target_info))

        threading.Thread(target=_pick_worker, daemon=True).start()

    def _on_picked_from_screen(self, target_info: Optional[Dict]):
        self.dialog.deiconify()
        self.dialog.lift()
        self.dialog.focus_force()

        if not target_info:
            messagebox.showinfo(
                "Window Finder",
                "No window was selected or picking timed out.",
                parent=self.dialog,
            )
            return

        # Direct selection from pick
        self._select_and_close(target_info)

    def _on_attach_clicked(self):
        """Handle Attach button or Double Click on row."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning(
                "No Selection",
                "Please select an application or process from the list.",
                parent=self.dialog,
            )
            return

        iid = selected[0]
        mode = self.view_mode.get()

        if mode == "windows" and iid.startswith("win_"):
            wid = int(iid.split("_")[1])
            target_info = next((w for w in self.windows_cache if w["wid"] == wid), None)
            if target_info:
                self._select_and_close(target_info)
        elif mode == "processes" and iid.startswith("proc_"):
            pid = int(iid.split("_")[1])
            proc_info = next((p for p in self.processes_cache if p["pid"] == pid), None)
            if proc_info:
                # Find if any open window matches this PID
                matching_win = next((w for w in self.windows_cache if w.get("pid") == pid), None)
                target_dict = {
                    "wid": matching_win["wid"] if matching_win else 0,
                    "wid_hex": matching_win["wid_hex"] if matching_win else "0x0",
                    "pid": pid,
                    "title": matching_win["title"] if matching_win else proc_info["name"],
                    "class": matching_win["class"] if matching_win else proc_info["name"],
                    "name": proc_info["name"],
                    "exe": proc_info["name"],
                    "display_app": matching_win["display_app"] if matching_win else proc_info["name"],
                    "rect": matching_win["rect"] if matching_win else (0, 0, 0, 0),
                }
                self._select_and_close(target_dict)

    def _select_and_close(self, target_dict: Dict):
        """Invoke callback and close dialog."""
        self.dialog.destroy()
        if self.on_select:
            self.on_select(target_dict)
