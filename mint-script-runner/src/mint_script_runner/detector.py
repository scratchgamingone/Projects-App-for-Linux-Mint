"""
Script inspector and GitHub usage detector for Mint Script Runner.
Analyzes .sh script contents for administrative and GitHub operations.
"""

import os
import re
from pathlib import Path


class ScriptInspector:
    GIT_PATTERNS = [
        re.compile(r"\bgit\s+(push|pull|commit|clone|fetch|remote|add|rebase|merge|init)\b", re.IGNORECASE),
        re.compile(r"github\.com", re.IGNORECASE),
        re.compile(r"\bgh\s+auth\b", re.IGNORECASE),
        re.compile(r"\bGITHUB_TOKEN\b", re.IGNORECASE),
    ]

    ADMIN_PATTERNS = [
        re.compile(r"\bsudo\b"),
        re.compile(r"\bpkexec\b"),
        re.compile(r"\bapt(-get)?\s+(install|update|upgrade|remove)\b"),
        re.compile(r"\bsystemctl\s+(start|stop|restart|enable|disable)\b"),
        re.compile(r"\b(chown|chmod)\s+-(R|r)\s+(root|0)\b"),
        re.compile(r"\bEUID\s*(-ne|!=)\s*0\b"),
    ]

    @staticmethod
    def inspect(file_path):
        path = Path(file_path)
        if not path.is_file():
            return {
                "is_valid": False,
                "error": f"File does not exist: {file_path}",
            }

        stat = path.stat()
        size_bytes = stat.st_size
        size_human = ScriptInspector._format_size(size_bytes)
        is_executable = os.access(path, os.X_OK)

        lines = []
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as e:
            return {
                "is_valid": False,
                "error": f"Failed to read file: {e}",
            }

        detected_git = []
        detected_admin = []

        for line in lines:
            stripped = line.strip()
            # Ignore comments for git detection
            if stripped.startswith("#"):
                continue

            for pat in ScriptInspector.GIT_PATTERNS:
                match = pat.search(stripped)
                if match and match.group(0) not in detected_git:
                    detected_git.append(match.group(0))

            for pat in ScriptInspector.ADMIN_PATTERNS:
                match = pat.search(stripped)
                if match and match.group(0) not in detected_admin:
                    detected_admin.append(match.group(0))

        preview = "".join(lines[:12])

        return {
            "is_valid": True,
            "file_name": path.name,
            "file_path": str(path.resolve()),
            "dir_path": str(path.parent.resolve()),
            "file_size_human": size_human,
            "line_count": len(lines),
            "is_executable": is_executable,
            "uses_github": len(detected_git) > 0,
            "git_matches": detected_git,
            "admin_suggested": len(detected_admin) > 0,
            "admin_matches": detected_admin,
            "preview_snippet": preview,
        }

    @staticmethod
    def make_executable(file_path):
        try:
            current = os.stat(file_path).st_mode
            os.chmod(file_path, current | 0o111)
            return True, "Executable permission granted."
        except Exception as e:
            return False, str(e)

    @staticmethod
    def _format_size(num_bytes):
        for unit in ["B", "KB", "MB", "GB"]:
            if num_bytes < 1024.0:
                return f"{num_bytes:.1f} {unit}" if unit != "B" else f"{num_bytes} {unit}"
            num_bytes /= 1024.0
        return f"{num_bytes:.1f} TB"
