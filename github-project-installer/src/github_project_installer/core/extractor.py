"""
Source Code Installer & Archive Auto-Extractor.
Installs repository files into ~/Documents/github-code-projects/<repo_name>,
auto-extracts nested archive files, and configures executable permissions.
"""

import os
import shutil
import zipfile
import tarfile
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable

from github_project_installer.core.git_inspector import RepoSnapshot


@dataclass
class InstallResult:
    success: bool
    target_path: str
    file_count: int = 0
    extracted_archives: List[str] = field(default_factory=list)
    executable_scripts: List[str] = field(default_factory=list)
    message: str = ""


def find_unique_destination(base_dir: Path, repo_name: str) -> Path:
    """Finds an available directory name if repo_name already exists."""
    target = base_dir / repo_name
    if not target.exists():
        return target

    counter = 1
    while True:
        candidate = base_dir / f"{repo_name}-{counter}"
        if not candidate.exists():
            return candidate
        counter += 1


def auto_extract_archives_in_dir(target_dir: Path) -> List[str]:
    """
    Finds and auto-extracts any archive files (.zip, .tar.gz, .tgz, .tar.bz2)
    found inside the project directory.
    """
    extracted = []
    archive_exts = (".zip", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")

    for root, _, files in os.walk(target_dir):
        for f in files:
            f_lower = f.lower()
            if any(f_lower.endswith(ext) for ext in archive_exts):
                arch_path = Path(root) / f
                out_folder = arch_path.parent / arch_path.stem
                if f_lower.endswith((".tar.gz", ".tar.bz2", ".tar.xz")):
                    out_folder = arch_path.parent / Path(arch_path.stem).stem

                try:
                    if f_lower.endswith(".zip") and zipfile.is_zipfile(arch_path):
                        out_folder.mkdir(parents=True, exist_ok=True)
                        with zipfile.ZipFile(arch_path, 'r') as zf:
                            zf.extractall(out_folder)
                        extracted.append(f"{arch_path.name} -> {out_folder.name}/")
                    elif tarfile.is_tarfile(arch_path):
                        out_folder.mkdir(parents=True, exist_ok=True)
                        with tarfile.open(arch_path, 'r:*') as tf:
                            tf.extractall(out_folder)
                        extracted.append(f"{arch_path.name} -> {out_folder.name}/")
                except Exception as e:
                    print(f"Warning: Failed to auto-extract archive {arch_path.name}: {e}")

    return extracted


def make_scripts_executable(target_dir: Path) -> List[str]:
    """
    Finds shell scripts and configuration launchers, ensuring they have +x permissions.
    """
    executable_scripts = []
    for root, _, files in os.walk(target_dir):
        # Skip .git internals
        if ".git" in root.split(os.sep):
            continue
        for f in files:
            p = Path(root) / f
            is_script = (
                f.endswith(".sh") or
                f.endswith(".bash") or
                f in ["configure", "install", "setup", "run", "entrypoint.sh"]
            )
            if is_script:
                try:
                    current_mode = p.stat().st_mode
                    p.chmod(current_mode | 0o755)
                    rel = str(p.relative_to(target_dir))
                    executable_scripts.append(rel)
                except Exception:
                    pass

    return executable_scripts


def install_repository_to_documents(
    snapshot: RepoSnapshot,
    base_install_dir: str,
    overwrite: bool = True,
    auto_extract: bool = True,
    keep_git: bool = True,
    progress_cb: Optional[Callable[[str, float], None]] = None,
) -> InstallResult:
    """
    Installs the inspected repository snapshot into base_install_dir/<repo_name>.
    Handles auto-extraction of archives and sets script execution permissions.
    """
    base_dir = Path(base_install_dir).expanduser().resolve()
    base_dir.mkdir(parents=True, exist_ok=True)

    repo_name = snapshot.info.repo
    target_dir = base_dir / repo_name

    if target_dir.exists():
        if overwrite:
            if progress_cb:
                progress_cb(f"Cleaning existing directory {target_dir.name}...", 0.2)
            try:
                shutil.rmtree(target_dir)
            except Exception as e:
                return InstallResult(
                    success=False,
                    target_path=str(target_dir),
                    message=f"Could not remove existing destination folder: {e}",
                )
        else:
            target_dir = find_unique_destination(base_dir, repo_name)

    if progress_cb:
        progress_cb(f"Copying project files into {target_dir}...", 0.4)

    target_dir.mkdir(parents=True, exist_ok=True)
    src_dir = Path(snapshot.local_path)

    # Copy files
    copied_count = 0
    for root, dirs, files in os.walk(src_dir):
        rel_root = Path(root).relative_to(src_dir)
        dest_root = target_dir / rel_root

        # Skip .git if user selected not to keep git history
        if not keep_git and ".git" in rel_root.parts:
            continue

        dest_root.mkdir(parents=True, exist_ok=True)

        for f in files:
            if not keep_git and ".git" in rel_root.parts:
                continue
            src_file = Path(root) / f
            dest_file = dest_root / f
            try:
                shutil.copy2(src_file, dest_file)
                copied_count += 1
            except Exception:
                pass

    # Auto extract archives if requested
    extracted_archives = []
    if auto_extract:
        if progress_cb:
            progress_cb("Auto-extracting archives inside repository...", 0.75)
        extracted_archives = auto_extract_archives_in_dir(target_dir)

    # Set script permissions
    if progress_cb:
        progress_cb("Configuring script permissions...", 0.9)
    executables = make_scripts_executable(target_dir)

    if progress_cb:
        progress_cb("Installation completed successfully!", 1.0)

    msg = f"Successfully installed '{repo_name}' to {target_dir} ({copied_count} files)."
    if extracted_archives:
        msg += f" Auto-extracted {len(extracted_archives)} archives."

    return InstallResult(
        success=True,
        target_path=str(target_dir),
        file_count=copied_count,
        extracted_archives=extracted_archives,
        executable_scripts=executables,
        message=msg,
    )
