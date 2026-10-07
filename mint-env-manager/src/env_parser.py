"""
Environment File Parser and Serializer for Mint Environment Manager.
Handles /etc/environment and .env files with comment and whitespace preservation,
atomic saves, and automatic safety backups.
"""

import os
import re
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class EnvEntry:
    key: str
    value: str
    is_export: bool = False
    quote_char: str = '"'
    test_status: str = "Not Tested"
    test_details: str = ""


class EnvFile:
    """
    Manages loading, modifying, and saving environment files.
    Preserves comments and blank lines accurately.
    """

    DEFAULT_SYSTEM_PATH = "/etc/environment"

    def __init__(self, file_path: str = DEFAULT_SYSTEM_PATH):
        self.file_path = os.path.abspath(os.path.expanduser(file_path))
        self.raw_lines: List[str] = []
        # List of tokens: ('var', EnvEntry), ('comment', str), ('blank', str), ('raw', str)
        self.tokens: List[Tuple[str, object]] = []
        self.is_dirty: bool = False

    def load(self, path: Optional[str] = None) -> Tuple[bool, str]:
        """Loads and parses the target environment file."""
        if path:
            self.file_path = os.path.abspath(os.path.expanduser(path))

        self.tokens = []
        self.is_dirty = False

        if not os.path.exists(self.file_path):
            # If file does not exist yet (e.g. creating new .env)
            return True, f"New file created at {self.file_path}"

        try:
            with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            return False, f"Failed to read {self.file_path}: {e}"

        var_pattern = re.compile(
            r"^\s*(?:(export)\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$"
        )

        for line in content.splitlines(keepends=False):
            stripped = line.strip()

            if not stripped:
                self.tokens.append(("blank", line))
                continue

            if stripped.startswith("#"):
                self.tokens.append(("comment", line))
                continue

            match = var_pattern.match(line)
            if match:
                is_export = bool(match.group(1))
                key = match.group(2)
                raw_val = match.group(3).strip()

                quote_char = '"'
                val = raw_val

                # Check quotes
                if len(raw_val) >= 2 and raw_val[0] in ('"', "'") and raw_val[-1] == raw_val[0]:
                    quote_char = raw_val[0]
                    val = raw_val[1:-1]
                    # Unescape escaped quotes
                    if quote_char == '"':
                        val = val.replace('\\"', '"').replace("\\\\", "\\")
                    elif quote_char == "'":
                        val = val.replace("\\'", "'")
                elif raw_val.startswith('"') and not raw_val.endswith('"'):
                    quote_char = '"'
                    val = raw_val[1:]
                elif raw_val.startswith("'") and not raw_val.endswith("'"):
                    quote_char = "'"
                    val = raw_val[1:]

                entry = EnvEntry(
                    key=key,
                    value=val,
                    is_export=is_export,
                    quote_char=quote_char,
                )
                self.tokens.append(("var", entry))
            else:
                self.tokens.append(("raw", line))

        return True, f"Loaded {len(self.get_entries())} variables from {self.file_path}"

    def get_entries(self) -> List[EnvEntry]:
        """Returns list of parsed variable entries."""
        return [tok[1] for tok in self.tokens if tok[0] == "var"]

    def get_entry(self, key: str) -> Optional[EnvEntry]:
        """Finds entry by key name."""
        for tok_type, obj in self.tokens:
            if tok_type == "var" and obj.key == key:
                return obj
        return None

    def set_entry(self, key: str, value: str, is_export: bool = False, quote_char: str = '"') -> bool:
        """
        Sets or updates an environment variable.
        Returns True if created or updated.
        """
        key = key.strip()
        # Validate variable name
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            raise ValueError(f"Invalid environment variable name: '{key}'. Must start with a letter/underscore and contain only alphanumeric characters.")

        # Check existing
        for i, (tok_type, obj) in enumerate(self.tokens):
            if tok_type == "var" and obj.key == key:
                if obj.value != value or obj.is_export != is_export:
                    obj.value = value
                    obj.is_export = is_export
                    obj.quote_char = quote_char
                    self.is_dirty = True
                return True

        # Append new variable
        entry = EnvEntry(key=key, value=value, is_export=is_export, quote_char=quote_char)
        self.tokens.append(("var", entry))
        self.is_dirty = True
        return True

    def remove_entry(self, key: str) -> bool:
        """Removes a variable entry by key."""
        initial_len = len(self.tokens)
        self.tokens = [
            tok for tok in self.tokens
            if not (tok[0] == "var" and tok[1].key == key)
        ]
        if len(self.tokens) < initial_len:
            self.is_dirty = True
            return True
        return False

    def serialize(self) -> str:
        """Converts tokens back into full file string."""
        lines = []
        for tok_type, obj in self.tokens:
            if tok_type == "blank":
                lines.append(str(obj))
            elif tok_type == "comment":
                lines.append(str(obj))
            elif tok_type == "raw":
                lines.append(str(obj))
            elif tok_type == "var":
                entry: EnvEntry = obj
                prefix = "export " if entry.is_export else ""
                q = entry.quote_char if entry.quote_char in ('"', "'") else '"'
                # Escape quote inside value
                escaped = entry.value.replace("\\", "\\\\").replace(q, f"\\{q}")
                lines.append(f"{prefix}{entry.key}={q}{escaped}{q}")

        # Ensure trailing newline
        return "\n".join(lines) + "\n"

    def save(self, target_path: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        """
        Saves changes atomically to target_path (defaults to self.file_path).
        Creates a backup before overwriting.
        Returns (success: bool, message: str, backup_path: Optional[str]).
        """
        dest_path = os.path.abspath(os.path.expanduser(target_path or self.file_path))
        dest_dir = os.path.dirname(dest_path) or "."

        backup_path: Optional[str] = None

        # Create backup if destination exists
        if os.path.exists(dest_path):
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_path = f"{dest_path}.bak.{timestamp}"
            try:
                shutil.copy2(dest_path, backup_path)
            except Exception as e:
                return False, f"Failed to create safety backup at {backup_path}: {e}", None

        # Write to temporary file in same directory for atomic replace
        try:
            os.makedirs(dest_dir, exist_ok=True)
            with tempfile.NamedTemporaryFile("w", dir=dest_dir, delete=False, encoding="utf-8") as tf:
                temp_name = tf.name
                tf.write(self.serialize())
                tf.flush()
                os.fsync(tf.fileno())

            # Set standard world-readable permissions (0644) so applications can read it
            os.chmod(temp_name, 0o644)
            # Atomically replace
            os.replace(temp_name, dest_path)
            self.file_path = dest_path
            self.is_dirty = False
            return True, f"Successfully saved to {dest_path}", backup_path
        except Exception as e:
            return False, f"Error writing to {dest_path}: {e}", backup_path


def detect_service(key: str, value: str) -> Tuple[str, str, str]:
    """
    Detects API service provider based on variable name and value characteristics.
    Returns (service_id, display_name, icon_name).
    """
    key_upper = key.upper()
    val = value.strip()

    # 1. Steam Web API Key
    if "STEAM" in key_upper:
        return "steam", "Steam Web API", "applications-games"
    if len(val) == 32 and all(c in "0123456789ABCDEFabcdef" for c in val):
        if "KEY" in key_upper or "API" in key_upper:
            return "steam", "Steam Web API", "applications-games"

    # 2. GitHub Token / Personal Access Token
    if any(k in key_upper for k in ("GITHUB", "GH_TOKEN", "PERSONAL_ACCESS_TOKEN", "GITHUB_PAT")):
        return "github", "GitHub Token", "system-software-update"
    if val.startswith("ghp_") or val.startswith("github_pat_") or val.startswith("gho_"):
        return "github", "GitHub Token", "system-software-update"

    # 3. OpenAI
    if "OPENAI" in key_upper or "CHATGPT" in key_upper:
        return "openai", "OpenAI API", "dialog-information"
    if val.startswith("sk-proj-") or (val.startswith("sk-") and not val.startswith("sk-ant-")):
        return "openai", "OpenAI API", "dialog-information"

    # 4. Google Gemini / Generative Language
    if any(k in key_upper for k in ("GEMINI", "GOOGLE_AI", "GOOGLE_API", "PALM")):
        return "gemini", "Google Gemini", "emblem-favorite"
    if val.startswith("AIzaSy"):
        return "gemini", "Google Gemini", "emblem-favorite"

    # 5. Anthropic Claude
    if "ANTHROPIC" in key_upper or "CLAUDE" in key_upper:
        return "anthropic", "Anthropic Claude", "dialog-information"
    if val.startswith("sk-ant-"):
        return "anthropic", "Anthropic Claude", "dialog-information"

    # 6. Groq
    if "GROQ" in key_upper:
        return "groq", "Groq Cloud", "utilities-terminal"
    if val.startswith("gsk_"):
        return "groq", "Groq Cloud", "utilities-terminal"

    # 7. Real-Debrid
    if "REALDEBRID" in key_upper or "RD_API" in key_upper or "DEBRID" in key_upper:
        return "realdebrid", "Real-Debrid", "folder-download"

    # 8. Hugging Face
    if "HUGGING" in key_upper or "HF_TOKEN" in key_upper or "HF_API" in key_upper:
        return "huggingface", "Hugging Face", "emblem-default"
    if val.startswith("hf_"):
        return "huggingface", "Hugging Face", "emblem-default"

    # 9. Discord Webhook
    if "DISCORD" in key_upper or "discord.com/api/webhooks" in val:
        return "discord", "Discord Webhook", "network-transmit-receive"

    # 10. TMDB (The Movie Database)
    if "TMDB" in key_upper:
        return "tmdb", "The Movie Database (TMDB)", "applications-multimedia"

    # 11. WeatherAPI
    if "WEATHER" in key_upper:
        return "weatherapi", "WeatherAPI", "weather-clear"

    # 12. Mistral AI
    if "MISTRAL" in key_upper:
        return "mistral", "Mistral AI", "dialog-information"

    # 13. Cohere
    if "COHERE" in key_upper:
        return "cohere", "Cohere", "dialog-information"

    # System variables
    if key_upper in ("PATH", "LD_LIBRARY_PATH", "PYTHONPATH", "MANPATH"):
        return "system_path", "System Path", "system-run"

    return "generic", "Generic API Key / Variable", "dialog-password"
