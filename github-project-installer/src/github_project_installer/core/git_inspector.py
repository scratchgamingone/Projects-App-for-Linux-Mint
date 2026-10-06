"""
Repository Inspector: Clones/downloads GitHub repositories into local cache,
indexes folder hierarchies, extracts README content, and analyzes project structure.
"""

import os
import shutil
import subprocess
import zipfile
import urllib.request
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable

from github_project_installer.core.config import CACHE_DIR
from github_project_installer.core.github_api import GitHubRepoInfo, fetch_repo_metadata
from github_project_installer.core.detector import detect_project


@dataclass
class FileNode:
    name: str
    rel_path: str
    abs_path: str
    is_dir: bool
    size: int = 0
    children: List['FileNode'] = field(default_factory=list)


@dataclass
class RepoSnapshot:
    info: GitHubRepoInfo
    local_path: str
    readme_path: Optional[str] = None
    readme_content: str = ""
    root_node: Optional[FileNode] = None
    file_count: int = 0
    dir_count: int = 0
    total_size: int = 0
    detected: Dict[str, Any] = field(default_factory=dict)

    @property
    def formatted_size(self) -> str:
        sz = self.total_size
        for unit in ["B", "KB", "MB", "GB"]:
            if sz < 1024.0:
                return f"{sz:.1f} {unit}"
            sz /= 1024.0
        return f"{sz:.1f} TB"


def format_bytes(bytes_num: int) -> str:
    """Format bytes into readable string."""
    b = float(bytes_num)
    for unit in ["B", "KB", "MB", "GB"]:
        if b < 1024.0:
            return f"{b:.1f} {unit}"
        b /= 1024.0
    return f"{b:.1f} TB"


def build_file_tree(root_dir: Path) -> Tuple[FileNode, int, int, int]:
    """
    Recursively scans root_dir, building a FileNode tree.
    Filters out .git to keep views clean.
    Returns (root_node, file_count, dir_count, total_size).
    """
    root_node = FileNode(
        name=root_dir.name,
        rel_path="",
        abs_path=str(root_dir),
        is_dir=True,
    )

    file_count = 0
    dir_count = 0
    total_size = 0

    def scan(node: FileNode, current_path: Path):
        nonlocal file_count, dir_count, total_size
        try:
            entries = sorted(list(current_path.iterdir()), key=lambda p: (not p.is_dir(), p.name.lower()))
        except Exception:
            return

        for p in entries:
            # Skip internal .git metadata directory in the view
            if p.name == ".git":
                continue

            rel = str(p.relative_to(root_dir))
            if p.is_dir():
                dir_count += 1
                child = FileNode(name=p.name, rel_path=rel, abs_path=str(p), is_dir=True)
                node.children.append(child)
                scan(child, p)
            else:
                file_count += 1
                try:
                    fsize = p.stat().st_size
                except Exception:
                    fsize = 0
                total_size += fsize
                child = FileNode(name=p.name, rel_path=rel, abs_path=str(p), is_dir=False, size=fsize)
                node.children.append(child)

    scan(root_node, root_dir)
    return root_node, file_count, dir_count, total_size


def find_readme(root_dir: Path) -> Tuple[Optional[str], str]:
    """
    Locates any README file in the repository root and returns (readme_path, content).
    Checks README.md, README.markdown, README.rst, README.txt, README, etc.
    """
    candidates = [
        "README.md", "readme.md", "README.MD",
        "README.markdown", "README.rst", "README.txt",
        "README", "readme",
    ]
    for c in candidates:
        target = root_dir / c
        if target.is_file():
            try:
                with open(target, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                return str(target), content
            except Exception:
                pass

    # Secondary check: any file starting with README
    for p in root_dir.iterdir():
        if p.is_file() and p.name.lower().startswith("readme"):
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                return str(p), content
            except Exception:
                pass

    return None, ""


def inspect_repository(
    info: GitHubRepoInfo,
    progress_cb: Optional[Callable[[str, float], None]] = None,
    token: str = "",
) -> RepoSnapshot:
    """
    Clones or downloads repository into local cache, builds the tree,
    and returns a RepoSnapshot ready for UI display.
    """
    repos_cache = CACHE_DIR / "repos"
    target_cache_dir = repos_cache / f"{info.owner}_{info.repo}"

    if progress_cb:
        progress_cb("Connecting to GitHub and fetching repository details...", 0.1)

    # 1. Fetch metadata in parallel / before cloning
    meta = fetch_repo_metadata(info.owner, info.repo, token=token)
    if meta.get("success"):
        info.description = meta.get("description", info.description)
        info.stars = meta.get("stars", info.stars)
        info.forks = meta.get("forks", info.forks)
        info.open_issues = meta.get("open_issues", info.open_issues)
        info.language = meta.get("language", info.language)
        info.license_name = meta.get("license_name", info.license_name)
        info.default_branch = meta.get("default_branch", info.default_branch)
        info.topics = meta.get("topics", info.topics)
        info.html_url = meta.get("html_url", info.html_url)

    # 2. Clone or update cache
    branch = info.branch or info.default_branch or "main"
    clone_url = f"https://github.com/{info.owner}/{info.repo}.git"

    if target_cache_dir.is_dir() and (target_cache_dir / ".git").is_dir():
        if progress_cb:
            progress_cb("Updating existing local cache...", 0.3)
        try:
            subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=target_cache_dir,
                capture_output=True,
                text=True,
                timeout=20,
            )
        except Exception:
            pass
    else:
        # Clean destination if incomplete
        if target_cache_dir.exists():
            shutil.rmtree(target_cache_dir, ignore_errors=True)
        target_cache_dir.mkdir(parents=True, exist_ok=True)

        if progress_cb:
            progress_cb(f"Cloning {info.owner}/{info.repo} (depth 1)...", 0.4)

        clone_cmd = ["git", "clone", "--depth", "1"]
        if info.branch:
            clone_cmd.extend(["--branch", info.branch])
        clone_cmd.extend([clone_url, str(target_cache_dir)])

        clone_success = False
        try:
            res = subprocess.run(
                clone_cmd,
                capture_output=True,
                text=True,
                timeout=45,
            )
            if res.returncode == 0:
                clone_success = True
            else:
                print(f"Git clone stderr: {res.stderr}")
        except Exception as e:
            print(f"Git clone error: {e}")

        # Fallback: Download ZIP if git clone failed
        if not clone_success:
            if progress_cb:
                progress_cb("Git clone failed, downloading ZIP archive fallback...", 0.5)

            zip_dest = CACHE_DIR / "zips" / f"{info.owner}_{info.repo}.zip"
            zip_dest.parent.mkdir(parents=True, exist_ok=True)

            zip_urls = [
                f"https://codeload.github.com/{info.owner}/{info.repo}/zip/refs/heads/{branch}",
                f"https://github.com/{info.owner}/{info.repo}/archive/refs/heads/{branch}.zip",
                f"https://codeload.github.com/{info.owner}/{info.repo}/zip/refs/heads/master",
                f"https://codeload.github.com/{info.owner}/{info.repo}/zip/refs/heads/main",
            ]

            downloaded = False
            for zurl in zip_urls:
                try:
                    req = urllib.request.Request(zurl, headers={"User-Agent": "github-project-installer/1.0"})
                    with urllib.request.urlopen(req, timeout=30) as resp, open(zip_dest, "wb") as out_f:
                        shutil.copyfileobj(resp, out_f)
                    downloaded = True
                    break
                except Exception:
                    continue

            if downloaded and zipfile.is_zipfile(zip_dest):
                if progress_cb:
                    progress_cb("Extracting ZIP archive into cache...", 0.7)
                temp_extract = CACHE_DIR / "zips" / f"extracted_{info.owner}_{info.repo}"
                if temp_extract.exists():
                    shutil.rmtree(temp_extract, ignore_errors=True)
                temp_extract.mkdir(parents=True, exist_ok=True)

                with zipfile.ZipFile(zip_dest, "r") as zf:
                    zf.extractall(temp_extract)

                # Find root extracted folder
                extracted_subdirs = [d for d in temp_extract.iterdir() if d.is_dir()]
                if extracted_subdirs:
                    source_dir = extracted_subdirs[0]
                    for item in source_dir.iterdir():
                        shutil.move(str(item), str(target_cache_dir))
                else:
                    for item in temp_extract.iterdir():
                        shutil.move(str(item), str(target_cache_dir))
                shutil.rmtree(temp_extract, ignore_errors=True)
            else:
                raise RuntimeError(f"Could not clone or download repository '{info.owner}/{info.repo}'. Check URL and internet connectivity.")

    if progress_cb:
        progress_cb("Indexing repository structure and detecting files...", 0.85)

    # 3. Read README
    readme_path, readme_content = find_readme(target_cache_dir)
    if not readme_content:
        readme_content = f"# {info.repo}\n\n{info.description or 'No README provided in this repository.'}"

    # 4. Build File Tree
    root_node, f_count, d_count, total_sz = build_file_tree(target_cache_dir)

    # 5. Detect dependencies & build systems
    detected = detect_project(str(target_cache_dir))

    if progress_cb:
        progress_cb("Inspection complete!", 1.0)

    return RepoSnapshot(
        info=info,
        local_path=str(target_cache_dir),
        readme_path=readme_path,
        readme_content=readme_content,
        root_node=root_node,
        file_count=f_count,
        dir_count=d_count,
        total_size=total_sz,
        detected=detected,
    )
