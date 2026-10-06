"""
Configuration and settings manager for GitHub Project Installer.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List

CONFIG_DIR = Path.home() / ".config" / "github-project-installer"
CONFIG_FILE = CONFIG_DIR / "config.json"
CACHE_DIR = Path.home() / ".cache" / "github-project-installer"
DEFAULT_INSTALL_DIR = Path.home() / "Documents" / "github-code-projects"

DEFAULT_CONFIG: Dict[str, Any] = {
    "install_dir": str(DEFAULT_INSTALL_DIR),
    "github_token": "",
    "auto_extract_archives": True,
    "keep_git_history": True,
    "dark_mode": True,
    "recent_repos": [],
    "max_recent": 10,
}


class ConfigManager:
    """Manages application preferences and persistence."""

    def __init__(self):
        self.config: Dict[str, Any] = DEFAULT_CONFIG.copy()
        self._ensure_dirs()
        self.load()

    def _ensure_dirs(self):
        """Create necessary config, cache, and default project directories."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (CACHE_DIR / "repos").mkdir(parents=True, exist_ok=True)
        (CACHE_DIR / "zips").mkdir(parents=True, exist_ok=True)
        DEFAULT_INSTALL_DIR.mkdir(parents=True, exist_ok=True)

        # Create user-friendly symlink ~/Documents/github code project if not exists
        alt_link = Path.home() / "Documents" / "github code project"
        try:
            if not alt_link.exists() and not alt_link.is_symlink():
                alt_link.symlink_to(DEFAULT_INSTALL_DIR)
        except Exception:
            pass

    def load(self):
        """Load configuration from disk."""
        if CONFIG_FILE.is_file():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.config.update(data)
            except Exception as e:
                print(f"Warning: Failed to load config ({e}), using defaults")

    def save(self):
        """Save configuration to disk."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save config: {e}")

    @property
    def install_dir(self) -> str:
        return self.config.get("install_dir", str(DEFAULT_INSTALL_DIR))

    @install_dir.setter
    def install_dir(self, val: str):
        self.config["install_dir"] = val
        self.save()

    @property
    def github_token(self) -> str:
        return self.config.get("github_token", "")

    @github_token.setter
    def github_token(self, val: str):
        self.config["github_token"] = val
        self.save()

    @property
    def auto_extract_archives(self) -> bool:
        return self.config.get("auto_extract_archives", True)

    @auto_extract_archives.setter
    def auto_extract_archives(self, val: bool):
        self.config["auto_extract_archives"] = val
        self.save()

    @property
    def keep_git_history(self) -> bool:
        return self.config.get("keep_git_history", True)

    @keep_git_history.setter
    def keep_git_history(self, val: bool):
        self.config["keep_git_history"] = val
        self.save()

    @property
    def recent_repos(self) -> List[str]:
        return self.config.get("recent_repos", [])

    def add_recent_repo(self, url: str):
        """Add a URL to recent repositories history."""
        if not url:
            return
        recents = [r for r in self.recent_repos if r != url]
        recents.insert(0, url)
        max_rec = self.config.get("max_recent", 10)
        self.config["recent_repos"] = recents[:max_rec]
        self.save()


# Global config instance
config_manager = ConfigManager()
