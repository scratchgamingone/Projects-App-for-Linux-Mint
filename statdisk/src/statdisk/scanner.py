"""
High performance filesystem scanner for StatDisk.
Runs on a background thread and dispatches progress updates to the GTK main loop.
"""

import os
import time
import threading
from typing import Callable, Optional, Dict, Any, List
from gi.repository import GLib

from statdisk.tree_model import FileNode


class ScanStats:
    """Aggregated dataset collected during scan for fast statistical analysis."""
    def __init__(self):
        self.file_sizes: List[int] = []
        self.file_mtimes: List[float] = []
        self.file_extensions: List[str] = []
        self.file_paths: List[str] = []
        self.total_dirs: int = 0
        self.total_files: int = 0
        self.total_bytes: int = 0
        self.scan_duration: float = 0.0


class DirectoryScanner:
    """Background directory scanner."""

    def __init__(self, root_path: str,
                 on_progress: Optional[Callable[[int, int, int, str], None]] = None,
                 on_finished: Optional[Callable[[FileNode, ScanStats], None]] = None,
                 on_error: Optional[Callable[[str], None]] = None):
        self.root_path = os.path.abspath(root_path)
        self.on_progress = on_progress
        self.on_finished = on_finished
        self.on_error = on_error

        self._cancel_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start scanning in background."""
        self._cancel_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="StatDisk-Scanner")
        self._thread.start()

    def cancel(self) -> None:
        """Signal scanner to cancel."""
        self._cancel_event.set()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        start_time = time.time()
        stats = ScanStats()
        last_update_time = [0.0]

        def report_progress(curr_path: str):
            now = time.time()
            if now - last_update_time[0] >= 0.06:  # Update every 60ms
                last_update_time[0] = now
                if self.on_progress:
                    GLib.idle_add(
                        self.on_progress,
                        stats.total_files,
                        stats.total_dirs,
                        stats.total_bytes,
                        curr_path
                    )

        if not os.path.exists(self.root_path):
            if self.on_error:
                GLib.idle_add(self.on_error, f"Path does not exist: {self.root_path}")
            return

        is_dir = os.path.isdir(self.root_path)
        root_name = os.path.basename(self.root_path) or self.root_path
        root_node = FileNode(self.root_path, root_name, is_dir=is_dir)

        if not is_dir:
            try:
                st = os.stat(self.root_path)
                root_node.size = st.st_size
                root_node.mtime = st.st_mtime
                stats.total_files = 1
                stats.total_bytes = st.st_size
                stats.file_sizes.append(st.st_size)
                stats.file_mtimes.append(st.st_mtime)
                stats.file_extensions.append(root_node.extension)
                stats.file_paths.append(self.root_path)
            except OSError as e:
                if self.on_error:
                    GLib.idle_add(self.on_error, str(e))
                return
        else:
            # Recursive scan
            self._scan_directory(root_node, stats, report_progress)

        stats.scan_duration = time.time() - start_time
        root_node.sort_children(recursive=True)

        if not self._cancel_event.is_set():
            if self.on_finished:
                GLib.idle_add(self.on_finished, root_node, stats)

    def _scan_directory(self, dir_node: FileNode, stats: ScanStats, report_progress: Callable[[str], None]) -> None:
        if self._cancel_event.is_set():
            return

        report_progress(dir_node.path)
        stats.total_dirs += 1

        try:
            with os.scandir(dir_node.path) as it:
                for entry in it:
                    if self._cancel_event.is_set():
                        return

                    try:
                        # Follow symlinks = False to prevent loops and duplicate size
                        is_dir = entry.is_dir(follow_symlinks=False)
                        is_file = entry.is_file(follow_symlinks=False)
                        st = entry.stat(follow_symlinks=False)
                    except (PermissionError, FileNotFoundError, OSError):
                        continue

                    child_node = FileNode(
                        path=entry.path,
                        name=entry.name,
                        is_dir=is_dir,
                        size=st.st_size if is_file else 0,
                        mtime=st.st_mtime
                    )
                    dir_node.add_child(child_node)

                    if is_dir:
                        self._scan_directory(child_node, stats, report_progress)
                        dir_node.size += child_node.size
                        dir_node.file_count += child_node.file_count
                        dir_node.dir_count += child_node.dir_count
                    elif is_file:
                        dir_node.size += child_node.size
                        dir_node.file_count += 1
                        stats.total_files += 1
                        stats.total_bytes += child_node.size
                        stats.file_sizes.append(child_node.size)
                        stats.file_mtimes.append(child_node.mtime)
                        stats.file_extensions.append(child_node.extension)
                        stats.file_paths.append(child_node.path)

        except (PermissionError, FileNotFoundError, OSError):
            pass
