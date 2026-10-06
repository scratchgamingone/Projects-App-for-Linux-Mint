"""
Configuration manager for Mint Auto Clicker.
Saves and loads user preferences to ~/.config/mint-autoclicker/config.json.
"""

import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "mint-autoclicker"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "hours": 0,
    "minutes": 0,
    "seconds": 0,
    "milliseconds": 50,
    "use_jitter": False,
    "jitter_ms": 5,
    "mouse_button": "left",
    "click_type": "single",
    "repeat_mode": "infinite",
    "repeat_count": 100,
    "location_mode": "current",
    "fixed_x": 0,
    "fixed_y": 0,
    "hotkey": "F6",
    "always_on_top": True,
    "sound_enabled": False,
    "target_mode": "global",
    "target_wid": 0,
    "target_pid": 0,
    "target_app_name": "",
    "target_window_title": "",
    "target_only_when_active": True,
    "target_confine_to_window": True,
    "target_guard_titlebar": True,
    "target_auto_focus": False,
}

def load_config() -> dict:
    """Load configuration from disk, falling back to defaults for any missing keys."""
    config = dict(DEFAULT_CONFIG)
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    for k, v in saved.items():
                        if k in DEFAULT_CONFIG:
                            # Keep type consistency where possible
                            config[k] = type(DEFAULT_CONFIG[k])(v) if v is not None else DEFAULT_CONFIG[k]
    except Exception as e:
        print(f"Warning: Failed to load config ({e}), using defaults.")
    return config

def save_config(config: dict) -> None:
    """Save configuration dictionary to disk."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Warning: Failed to save config ({e}).")
