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
            self.sync_to_git_credential_store()
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False

    def sync_to_git_credential_store(self):
        """Automatically updates git credential store (~/.git-credentials)."""
        user = self.get("github_username", "").strip()
        token = self.get("github_token", "").strip()
        if user and token:
            try:
                import subprocess
                p = subprocess.Popen(
                    ["git", "credential", "approve"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    text=True,
                )
                payload = f"protocol=https\nhost=github.com\nusername={user}\npassword={token}\n"
                p.communicate(input=payload)
            except Exception:
                pass

    def get(self, key, default=None):
        return self.data.get(key, self.defaults.get(key, default))

    def set(self, key, value):
        self.data[key] = value

    def has_github_token(self):
        token = self.get("github_token", "").strip()
        return bool(token and (token.startswith(("gh", "github_pat_")) or len(token) >= 8))

    def test_github_token(self):
        """Validates the GitHub token against GitHub's API and tests write permissions."""
        token = self.get("github_token", "").strip()
        user = self.get("github_username", "").strip()
        remote = self.get("default_remote", "").strip()

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

                    # For fine-grained tokens, test if write permissions are enabled
                    if token.startswith("github_pat_"):
                        target_repo = "Projects-App-for-Linux-Mint"
                        if remote and "github.com/" in remote:
                            target_repo = remote.split("github.com/")[-1].replace(".git", "").strip("/")
                        elif api_user:
                            target_repo = f"{api_user}/{target_repo}"

                        try:
                            probe_url = f"https://api.github.com/repos/{target_repo}/git/refs"
                            probe_payload = json.dumps({"ref": "refs/heads/_probe", "sha": "0" * 40}).encode("utf-8")
                            probe_req = urllib.request.Request(probe_url, data=probe_payload, method="POST")
                            probe_req.add_header("Authorization", f"Bearer {token}")
                            probe_req.add_header("Accept", "application/vnd.github.v3+json")
                            probe_req.add_header("User-Agent", "Mint-Script-Runner")

                            try:
                                with urllib.request.urlopen(probe_req, timeout=6):
                                    pass
                            except urllib.error.HTTPError as pe:
                                pe_body = pe.read().decode("utf-8", errors="replace")
                                if pe.code == 403 and "Resource not accessible" in pe_body:
                                    return False, (
                                        f"Logged in as @{api_user}, BUT token lacks Write (Push) permission!\n"
                                        "Under GitHub Settings -> Developer settings -> Fine-grained tokens,\n"
                                        "edit this token and set 'Repository permissions' -> 'Contents' to 'Read and write'."
                                    )
                        except Exception:
                            pass

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
