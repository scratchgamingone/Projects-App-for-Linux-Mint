"""
Settings manager for Mint Script Runner.
Persists GitHub credentials and execution preferences securely in ~/.config/mint-script-runner/config.json.
"""

import json
import os
import urllib.request
import urllib.error
from pathlib import Path


class SettingsManager:
    def __init__(self):
        self.config_dir = Path.home() / ".config" / "mint-script-runner"
        self.config_file = self.config_dir / "config.json"
        self.defaults = {
            "github_username": "scratchgamingone",
            "github_token": "",
            "github_email": "scratchgamingone@users.noreply.github.com",
            "default_remote": "https://github.com/scratchgamingone/Projects-App-for-Linux-Mint.git",
            "always_ask_admin": True,
            "auto_inject_github": True,
            "auto_scroll_output": True,
            "clear_output_on_run": True,
        }
        self.data = self.load()

    def load(self):
        if not self.config_file.is_file():
            # If no config file yet, check if git config already has username/email
            data = dict(self.defaults)
            try:
                import subprocess
                user = subprocess.check_output(["git", "config", "user.name"], text=True, stderr=subprocess.DEVNULL).strip()
                if user:
                    data["github_username"] = user
                email = subprocess.check_output(["git", "config", "user.email"], text=True, stderr=subprocess.DEVNULL).strip()
                if email:
                    data["github_email"] = email
            except Exception:
                pass
            return data

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
                merged = dict(self.defaults)
                merged.update(saved)
                return merged
        except Exception:
            return dict(self.defaults)

    def save(self):
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            # Write with restricted permissions (0600) to protect GitHub token
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
            os.chmod(self.config_file, 0o600)
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False

    def get(self, key, default=None):
        return self.data.get(key, self.defaults.get(key, default))

    def set(self, key, value):
        self.data[key] = value

    def has_github_token(self):
        token = self.get("github_token", "").strip()
        return bool(token and token.startswith("gh"))

    def test_github_token(self):
        """Validates the GitHub token against GitHub's API."""
        token = self.get("github_token", "").strip()
        user = self.get("github_username", "").strip()

        if not token:
            return False, "No GitHub Personal Access Token provided."

        url = "https://api.github.com/user"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Accept", "application/vnd.github.v3+json")
        req.add_header("User-Agent", "Mint-Script-Runner")

        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                if response.status == 200:
                    payload = json.loads(response.read().decode("utf-8"))
                    api_user = payload.get("login", "")
                    name = payload.get("name") or api_user
                    repos = payload.get("public_repos", 0) + payload.get("total_private_repos", 0)
                    return True, f"Verified! Logged in as @{api_user} ({name}) — {repos} repos accessible."
                return False, f"Unexpected HTTP status {response.status}"
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return False, "401 Unauthorized: Invalid or expired GitHub Personal Access Token."
            elif e.code == 403:
                return False, "403 Forbidden: Token lacks required scopes or API rate limit reached."
            return False, f"GitHub API error: {e.code} {e.reason}"
        except urllib.error.URLError as e:
            return False, f"Connection failed: {e.reason}"
        except Exception as e:
            return False, f"Verification failed: {str(e)}"
