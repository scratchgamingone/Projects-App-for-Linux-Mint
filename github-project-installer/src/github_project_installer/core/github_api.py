"""
GitHub URL parser and REST API client for fetching repository metadata.
"""

import re
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class GitHubRepoInfo:
    owner: str
    repo: str
    branch: Optional[str] = None
    subpath: Optional[str] = None
    clone_url: str = ""
    html_url: str = ""
    zip_url: str = ""
    description: str = ""
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    language: str = ""
    license_name: str = ""
    default_branch: str = "main"
    topics: list = None
    size_kb: int = 0
    updated_at: str = ""
    is_private: bool = False

    def __post_init__(self):
        if self.topics is None:
            self.topics = []
        if not self.clone_url and self.owner and self.repo:
            self.clone_url = f"https://github.com/{self.owner}/{self.repo}.git"
        if not self.html_url and self.owner and self.repo:
            self.html_url = f"https://github.com/{self.owner}/{self.repo}"
        branch_name = self.branch or self.default_branch or "main"
        if not self.zip_url and self.owner and self.repo:
            self.zip_url = f"https://codeload.github.com/{self.owner}/{self.repo}/zip/refs/heads/{branch_name}"


def parse_github_url(raw_input: str) -> Optional[GitHubRepoInfo]:
    """
    Parses any GitHub repository URL or shorthand string into GitHubRepoInfo.
    Supports:
      - https://github.com/owner/repo
      - https://github.com/owner/repo.git
      - https://github.com/owner/repo/tree/branch-name
      - https://github.com/owner/repo/blob/branch-name/path/to/file
      - git@github.com:owner/repo.git
      - owner/repo
    """
    text = raw_input.strip()
    if not text:
        return None

    owner = None
    repo = None
    branch = None
    subpath = None

    # Pattern 1: git@github.com:owner/repo(.git)
    ssh_match = re.match(r"^git@github\.com:([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+?)(?:\.git)?$", text)
    if ssh_match:
        owner = ssh_match.group(1)
        repo = ssh_match.group(2)
        return GitHubRepoInfo(owner=owner, repo=repo)

    # Pattern 2: Shorthand owner/repo
    shorthand_match = re.match(r"^([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)$", text)
    if shorthand_match and "github.com" not in text and not text.startswith("http"):
        owner = shorthand_match.group(1)
        repo = shorthand_match.group(2)
        if repo.endswith(".git"):
            repo = repo[:-4]
        return GitHubRepoInfo(owner=owner, repo=repo)

    # Pattern 3: Standard HTTP / HTTPS URL
    # Examples:
    # https://github.com/owner/repo
    # https://github.com/owner/repo/tree/branch/sub/path
    # https://github.com/owner/repo/blob/branch/file.txt
    url_match = re.match(r"^(?:https?://)?(?:www\.)?github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)(?:/(tree|blob)/([^/]+)(?:/(.*))?)?", text)
    if url_match:
        owner = url_match.group(1)
        repo = url_match.group(2)
        if repo.endswith(".git"):
            repo = repo[:-4]
        branch = url_match.group(4)
        subpath = url_match.group(5)
        return GitHubRepoInfo(owner=owner, repo=repo, branch=branch, subpath=subpath)

    return None


def fetch_repo_metadata(owner: str, repo: str, token: str = "") -> Dict[str, Any]:
    """
    Queries GitHub API to fetch repository details:
    stars, forks, description, license, default_branch, topics, language, etc.
    Gracefully handles rate limiting or private repos.
    """
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {
        "User-Agent": "github-project-installer/1.0 (Linux Mint Desktop App)",
        "Accept": "application/vnd.github.v3+json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(api_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                license_info = data.get("license") or {}
                return {
                    "success": True,
                    "description": data.get("description") or "No description provided.",
                    "stars": data.get("stargazers_count", 0),
                    "forks": data.get("forks_count", 0),
                    "open_issues": data.get("open_issues_count", 0),
                    "language": data.get("language") or "General",
                    "license_name": license_info.get("spdx_id") or license_info.get("name") or "None",
                    "default_branch": data.get("default_branch") or "main",
                    "topics": data.get("topics") or [],
                    "size_kb": data.get("size", 0),
                    "updated_at": data.get("updated_at", ""),
                    "is_private": data.get("private", False),
                    "html_url": data.get("html_url", f"https://github.com/{owner}/{repo}"),
                }
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"success": False, "error": "Repository not found or private."}
        elif e.code == 403:
            return {"success": False, "error": "GitHub API rate limit exceeded (will clone directly)."}
        else:
            return {"success": False, "error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"success": False, "error": f"Network error: {str(e)}"}

    return {"success": False, "error": "Unknown error querying GitHub API."}
