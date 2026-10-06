import os
import shutil
import subprocess
import glob
from typing import Tuple, List, Optional

def format_size(size_in_bytes: int) -> str:
    """Format bytes into human-readable string (KB, MB, GB)."""
    if size_in_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    size = float(size_in_bytes)
    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1
    return f"{size:.1f} {units[unit_index]}"

def get_dir_size_and_count(path: str) -> Tuple[int, int]:
    """Calculate total byte size and file count in a directory safely."""
    total_size = 0
    count = 0
    if not os.path.exists(path):
        return 0, 0
    try:
        for entry in os.scandir(path):
            try:
                if entry.is_file(follow_symlinks=False):
                    total_size += entry.stat(follow_symlinks=False).st_size
                    count += 1
                elif entry.is_dir(follow_symlinks=False):
                    sub_size, sub_count = get_dir_size_and_count(entry.path)
                    total_size += sub_size
                    count += sub_count
            except (PermissionError, FileNotFoundError):
                continue
    except (PermissionError, FileNotFoundError):
        pass
    return total_size, count

class CleanTarget:
    def __init__(self, target_id: str, name: str, description: str, requires_root: bool = False):
        self.target_id = target_id
        self.name = name
        self.description = description
        self.requires_root = requires_root
        self.size_bytes = 0
        self.item_count = 0
        self.enabled = True

    def scan(self) -> Tuple[int, int]:
        raise NotImplementedError

    def clean(self) -> Tuple[int, Optional[str]]:
        """Returns (freed_bytes, error_message)."""
        raise NotImplementedError

class ThumbnailCleaner(CleanTarget):
    def __init__(self):
        super().__init__(
            target_id="thumbnails",
            name="Thumbnail Cache",
            description="Cached desktop file and image preview thumbnails (~/.cache/thumbnails)",
            requires_root=False
        )
        self.path = os.path.expanduser("~/.cache/thumbnails")

    def scan(self) -> Tuple[int, int]:
        self.size_bytes, self.item_count = get_dir_size_and_count(self.path)
        return self.size_bytes, self.item_count

    def clean(self) -> Tuple[int, Optional[str]]:
        freed = 0
        try:
            if os.path.exists(self.path):
                before_size, _ = get_dir_size_and_count(self.path)
                for item in os.listdir(self.path):
                    item_path = os.path.join(self.path, item)
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path, ignore_errors=True)
                    else:
                        try:
                            os.remove(item_path)
                        except OSError:
                            pass
                after_size, _ = get_dir_size_and_count(self.path)
                freed = max(0, before_size - after_size)
            return freed, None
        except Exception as e:
            return 0, str(e)

class TrashCleaner(CleanTarget):
    def __init__(self):
        super().__init__(
            target_id="trash",
            name="User Trash Bin",
            description="Deleted files still residing in the Trash folder (~/.local/share/Trash)",
            requires_root=False
        )
        self.path = os.path.expanduser("~/.local/share/Trash")

    def scan(self) -> Tuple[int, int]:
        files_dir = os.path.join(self.path, "files")
        info_dir = os.path.join(self.path, "info")
        size_f, count_f = get_dir_size_and_count(files_dir)
        size_i, count_i = get_dir_size_and_count(info_dir)
        self.size_bytes = size_f + size_i
        self.item_count = count_f
        return self.size_bytes, self.item_count

    def clean(self) -> Tuple[int, Optional[str]]:
        freed = 0
        try:
            files_dir = os.path.join(self.path, "files")
            info_dir = os.path.join(self.path, "info")
            before_size, _ = self.scan()
            for d in [files_dir, info_dir]:
                if os.path.exists(d):
                    for item in os.listdir(d):
                        p = os.path.join(d, item)
                        if os.path.isdir(p):
                            shutil.rmtree(p, ignore_errors=True)
                        else:
                            try:
                                os.remove(p)
                            except OSError:
                                pass
            after_size, _ = self.scan()
            freed = max(0, before_size - after_size)
            return freed, None
        except Exception as e:
            return 0, str(e)

class AptCacheCleaner(CleanTarget):
    def __init__(self):
        super().__init__(
            target_id="apt_cache",
            name="APT Package Cache",
            description="Downloaded .deb installer files cached by apt (/var/cache/apt/archives)",
            requires_root=True
        )
        self.path = "/var/cache/apt/archives"

    def scan(self) -> Tuple[int, int]:
        total_size = 0
        count = 0
        if os.path.exists(self.path):
            deb_files = glob.glob(os.path.join(self.path, "*.deb"))
            for f in deb_files:
                try:
                    total_size += os.path.getsize(f)
                    count += 1
                except OSError:
                    continue
        self.size_bytes = total_size
        self.item_count = count
        return self.size_bytes, self.item_count

    def clean(self) -> Tuple[int, Optional[str]]:
        before_size, _ = self.scan()
        if before_size == 0:
            return 0, None
        cmd = ["pkexec", "apt-get", "clean"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if res.returncode == 0:
                after_size, _ = self.scan()
                return max(0, before_size - after_size), None
            else:
                return 0, res.stderr.strip() or "APT clean cancelled or failed."
        except Exception as e:
            return 0, str(e)

class SystemdJournalCleaner(CleanTarget):
    def __init__(self):
        super().__init__(
            target_id="journal_logs",
            name="Systemd Journal Logs (>7 days)",
            description="Vacuum old system journal logs keeping only the last 7 days",
            requires_root=True
        )

    def scan(self) -> Tuple[int, int]:
        journal_path = "/var/log/journal"
        if os.path.exists(journal_path):
            self.size_bytes, self.item_count = get_dir_size_and_count(journal_path)
        else:
            self.size_bytes, self.item_count = 0, 0
        return self.size_bytes, self.item_count

    def clean(self) -> Tuple[int, Optional[str]]:
        before_size, _ = self.scan()
        cmd = ["pkexec", "journalctl", "--vacuum-time=7d"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if res.returncode == 0:
                after_size, _ = self.scan()
                return max(0, before_size - after_size), None
            else:
                return 0, res.stderr.strip() or "Journalctl clean failed."
        except Exception as e:
            return 0, str(e)

class FlatpakUnusedCleaner(CleanTarget):
    def __init__(self):
        super().__init__(
            target_id="flatpak_unused",
            name="Unused Flatpak Runtimes",
            description="Remove unused Flatpak runtimes and dependencies (flatpak uninstall --unused)",
            requires_root=False
        )

    def is_available(self) -> bool:
        return shutil.which("flatpak") is not None

    def scan(self) -> Tuple[int, int]:
        if not self.is_available():
            self.size_bytes = 0
            self.item_count = 0
            return 0, 0
        try:
            res = subprocess.run(
                ["flatpak", "list", "--unused", "--columns=ref"],
                capture_output=True, text=True, timeout=10
            )
            lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
            self.item_count = len(lines)
            # Estimated 150MB per unused runtime if present
            self.size_bytes = self.item_count * 150 * 1024 * 1024
            return self.size_bytes, self.item_count
        except Exception:
            self.size_bytes = 0
            self.item_count = 0
            return 0, 0

    def clean(self) -> Tuple[int, Optional[str]]:
        if not self.is_available() or self.item_count == 0:
            return 0, None
        try:
            res = subprocess.run(
                ["flatpak", "uninstall", "--unused", "-y"],
                capture_output=True, text=True, timeout=120
            )
            if res.returncode == 0:
                cleaned_size = self.size_bytes
                self.size_bytes = 0
                self.item_count = 0
                return cleaned_size, None
            return 0, res.stderr.strip() or "Flatpak clean failed."
        except Exception as e:
            return 0, str(e)

def get_all_cleaners() -> List[CleanTarget]:
    """Returns a list of all available cleaner targets."""
    return [
        ThumbnailCleaner(),
        TrashCleaner(),
        AptCacheCleaner(),
        SystemdJournalCleaner(),
        FlatpakUnusedCleaner()
    ]
