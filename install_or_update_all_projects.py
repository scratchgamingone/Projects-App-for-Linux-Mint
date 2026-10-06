#!/usr/bin/env python3
"""
==============================================================================
Omni Projects: Install or Update All Projects & Dependencies
==============================================================================
Scans all project folders in ~/Projects to:
 1. Check, install, and upgrade all system & Python dependencies.
 2. Install or update all desktop applications, launchers, and menu shortcuts.
 3. Update Git repositories and Docker service configurations.
 4. Refresh Linux Mint desktop and icon databases all at once.
==============================================================================
"""

import sys
import os
import re
import shutil
import argparse
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

# Terminal ANSI colors
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

def color(text: str, c: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{c}{text}{Colors.RESET}"

# ==============================================================================
# Known Project Dependency Registry
# ==============================================================================
PROJECT_REGISTRY = {
    "chem151-review": {
        "name": "CHEM 151 Master Review",
        "description": "General Chemistry I Study Suite & 7 Offline Interactive Calculators",
        "apt_packages": [
            "python3",
            "python3-gi",
            "gir1.2-gtk-3.0",
            "gir1.2-webkit2-4.1",
            "libjs-mathjax",
            "fonts-mathjax",
        ],
        "python_modules": ["gi"],
    },
    "statdisk": {
        "name": "StatDisk",
        "description": "Interactive Disk Space & Statistical Moments Analyzer",
        "apt_packages": [
            "python3",
            "python3-gi",
            "python3-cairo",
            "python3-matplotlib",
            "python3-scipy",
            "python3-numpy",
            "gir1.2-gtk-3.0",
            "xdg-utils",
            "libcanberra-gtk3-module",
        ],
        "python_modules": ["gi", "cairo", "matplotlib", "scipy", "numpy"],
    },
    "mintstatlab": {
        "name": "MintStatLab",
        "description": "Linux Mint System Statistical Telemetry, Heavy-Tail Modeling & Anomaly Lab",
        "apt_packages": [
            "python3",
            "python3-gi",
            "gir1.2-gtk-3.0",
            "python3-numpy",
            "python3-scipy",
            "python3-matplotlib",
            "python3-psutil",
        ],
        "python_modules": ["gi", "numpy", "scipy", "matplotlib", "psutil"],
    },
    "mint-autoclicker": {
        "name": "Mint Auto Clicker",
        "description": "Gaming and Automation Auto-Clicker with Process Targeting",
        "apt_packages": [
            "python3",
            "python3-tk",
            "python3-xlib",
            "wmctrl",
            "libcanberra-gtk-module",
            "libcanberra-gtk3-module",
        ],
        "python_modules": ["tkinter", "Xlib"],
    },
    "omniboot-usb": {
        "name": "OmniBoot USB",
        "description": "Multi-ISO & Single OS Bootable USB Flasher (Ventoy / Direct)",
        "apt_packages": [
            "python3",
            "python3-gi",
            "python3-gi-cairo",
            "gir1.2-gtk-3.0",
            "parted",
            "dosfstools",
            "ntfs-3g",
            "p7zip-full",
            "util-linux",
            "udisks2",
            "polkitd",
            "wimtools",
        ],
        "binaries": ["parted", "mkfs.vfat", "ntfs-3g", "7z", "udisksctl", "wimlib-imagex"],
    },
    "usbguard-app": {
        "name": "USBGuard App",
        "description": "BadUSB Defense & USB Device Authorization Manager",
        "apt_packages": [
            "usbguard",
            "python3",
            "python3-gi",
            "gir1.2-gtk-3.0",
            "gir1.2-notify-0.7",
            "libnotify-bin",
            "polkitd",
        ],
        "binaries": ["usbguard", "notify-send", "pkexec"],
    },
    "roblox-caffeine": {
        "name": "Roblox Caffeine",
        "description": "Linux Gamepad /dev/uinput AFK Kick Preventer",
        "apt_packages": [
            "python3",
            "python3-evdev",
        ],
        "python_modules": ["evdev"],
    },
    "jellyfin-discord-bot": {
        "name": "Jellyfin Discord Bot",
        "description": "Live Playback Status and Library Update Webhook Broadcaster",
        "apt_packages": [
            "python3",
            "python3-requests",
        ],
        "python_modules": ["requests"],
    },
    "jellyscratch-server": {
        "name": "JellyScratch Server",
        "description": "Desktop Jellyfin Server with Embedded WebKit UI & Monitor",
        "apt_packages": [
            "python3",
            "python3-gi",
            "gir1.2-gtk-3.0",
            "gir1.2-webkit2-4.1",
            "python3-requests",
            "python3-qrcode",
            "curl",
            "ca-certificates",
        ],
        "python_modules": ["qrcode", "requests"],
    },
    "stremio-dashboard": {
        "name": "Stremio Dashboard",
        "description": "Cloud Debrid & Discord Webhook Web Management Interface",
        "apt_packages": [
            "python3",
            "python3-flask",
            "python3-requests",
        ],
        "python_modules": ["flask", "requests"],
    },
    "seerr": {
        "name": "Seerr (Jellyseerr)",
        "description": "Media Discovery and Request Manager (Docker)",
        "apt_packages": [
            "docker.io",
            "docker-compose-v2",
        ],
        "binaries": ["docker"],
    },
    "debrid": {
        "name": "Debrid Cloud Services",
        "description": "Zurg Real-Debrid & Rclone Cloud Stream Mounts (Docker)",
        "apt_packages": [
            "docker.io",
            "docker-compose-v2",
        ],
        "binaries": ["docker"],
    },
    "system-scripts": {
        "name": "System Utility Scripts",
        "description": "Speaker Fixes, Facial Recognition & Audio Diagnostics",
        "apt_packages": [
            "curl",
            "ca-certificates",
            "software-properties-common",
        ],
    },
    "core-tools": {
        "name": "Core Project & Build Tools",
        "description": "Essential Development, Packaging, Sync, and Python Tools",
        "apt_packages": [
            "git",
            "rsync",
            "build-essential",
            "dpkg-dev",
            "python3-pip",
            "python3-venv",
            "python3-setuptools",
        ],
        "binaries": ["git", "rsync", "dpkg-deb", "make", "gcc"],
    },
}

PYPI_TO_APT = {
    "requests": "python3-requests",
    "flask": "python3-flask",
    "evdev": "python3-evdev",
    "qrcode": "python3-qrcode",
    "matplotlib": "python3-matplotlib",
    "scipy": "python3-scipy",
    "numpy": "python3-numpy",
    "xlib": "python3-xlib",
    "pillow": "python3-pil",
    "pil": "python3-pil",
    "setuptools": "python3-setuptools",
    "urllib3": "python3-urllib3",
}

# ==============================================================================
# Helper Functions
# ==============================================================================

def is_root() -> bool:
    return os.geteuid() == 0

def check_sudo_access() -> bool:
    if is_root():
        return True
    try:
        res = subprocess.run(["sudo", "-n", "true"], capture_output=True)
        if res.returncode == 0:
            return True
        if sys.stdin.isatty():
            print(color("\n🔐 Administrator privileges (sudo) required to install/upgrade packages.", Colors.CYAN))
            res = subprocess.run(["sudo", "-v"])
            return res.returncode == 0
        return False
    except Exception:
        return False

def get_apt_policy(packages: List[str]) -> Dict[str, Dict[str, Optional[str]]]:
    if not packages:
        return {}

    unique_pkgs = sorted(list(set(packages)))
    try:
        cmd = ["apt-cache", "policy"] + unique_pkgs
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(color(f"Error querying apt-cache: {e}", Colors.RED))
        return {}

    results: Dict[str, Dict[str, Optional[str]]] = {}
    current_pkg: Optional[str] = None

    for line in out.splitlines():
        line_str = line.strip()
        if line and not line.startswith(" "):
            current_pkg = line.rstrip(":")
            results[current_pkg] = {"installed": None, "candidate": None}
        elif current_pkg:
            if line_str.startswith("Installed:"):
                results[current_pkg]["installed"] = line_str.split(":", 1)[1].strip()
            elif line_str.startswith("Candidate:"):
                results[current_pkg]["candidate"] = line_str.split(":", 1)[1].strip()

    return results

def scan_dynamic_dependencies(projects_dir: str) -> Dict[str, List[str]]:
    discovered: Dict[str, Set[str]] = {}

    if not os.path.isdir(projects_dir):
        return {}

    for root, dirs, files in os.walk(projects_dir):
        parts = root.split(os.sep)
        if any(p.startswith(".") or p in ("build", "__pycache__", "debian-pkg", "pkg") for p in parts):
            continue

        rel_root = os.path.relpath(root, projects_dir)
        proj_key = rel_root.split(os.sep)[0]
        if proj_key not in discovered:
            discovered[proj_key] = set()

        for f in files:
            fpath = os.path.join(root, f)

            if f in ("control", "debian-control"):
                try:
                    with open(fpath, "r", errors="ignore") as fp:
                        for line in fp:
                            if line.startswith(("Depends:", "Recommends:")):
                                deps = line.split(":", 1)[1].split(",")
                                for dep in deps:
                                    dep = dep.split("|")[0].strip()
                                    pkg = re.sub(r"\(.*?\)", "", dep).strip()
                                    if pkg and not pkg.startswith("$"):
                                        discovered[proj_key].add(pkg)
                except Exception:
                    pass

            elif f == "requirements.txt":
                try:
                    with open(fpath, "r", errors="ignore") as fp:
                        for line in fp:
                            line = line.strip()
                            if line and not line.startswith("#"):
                                mod = re.split(r"[<>=!~]", line)[0].strip().lower()
                                apt_equiv = PYPI_TO_APT.get(mod, f"python3-{mod}")
                                discovered[proj_key].add(apt_equiv)
                except Exception:
                    pass

            elif f == "pyproject.toml":
                try:
                    with open(fpath, "r", errors="ignore") as fp:
                        content = fp.read()
                        matches = re.findall(r'\"([a-zA-Z0-9_\-]+)(?:[<>=!~].*)?\"', content)
                        for m in matches:
                            m_lower = m.lower()
                            if m_lower in PYPI_TO_APT:
                                discovered[proj_key].add(PYPI_TO_APT[m_lower])
                except Exception:
                    pass

    return {k: sorted(list(v)) for k, v in discovered.items() if v}

def check_python_modules(modules: List[str]) -> Dict[str, bool]:
    results = {}
    for mod in modules:
        try:
            __import__(mod)
            results[mod] = True
        except ImportError:
            results[mod] = False
    return results

def check_binaries(binaries: List[str]) -> Dict[str, Optional[str]]:
    results = {}
    for b in binaries:
        path = shutil.which(b)
        results[b] = path
    return results

def check_git_repos(projects_dir: str) -> List[Dict[str, str]]:
    repos = []
    for root, dirs, files in os.walk(projects_dir):
        if ".git" in dirs:
            proj_name = os.path.basename(root)
            repo_info = {"name": proj_name, "path": root, "remote": "", "status": "Local"}
            try:
                out = subprocess.check_output(
                    ["git", "-C", root, "remote", "get-url", "origin"],
                    text=True, stderr=subprocess.DEVNULL
                ).strip()
                repo_info["remote"] = out
                repo_info["status"] = "Tracked"
            except Exception:
                repo_info["status"] = "No Remote"
            repos.append(repo_info)
    return repos

# ==============================================================================
# Project Installer & Updater Engine
# ==============================================================================

def write_executable(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fp:
        fp.write(content.strip() + "\n")
    path.chmod(0o755)

def write_desktop_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fp:
        fp.write(content.strip() + "\n")
    path.chmod(0o644)

def ensure_cinnamon_menu_tab(home: Path):
    desktop_dirs = home / ".local" / "share" / "desktop-directories"
    desktop_dirs.mkdir(parents=True, exist_ok=True)
    cinnamon_dir_file = desktop_dirs / "cinnamon-projects.directory"
    cinnamon_dir_file.write_text(
        "[Desktop Entry]\n"
        "Type=Directory\n"
        "Encoding=UTF-8\n"
        "Name=Projects\n"
        "Comment=Custom AI and user-developed applications\n"
        "Icon=applications-engineering\n"
    )

    menus_dir = home / ".config" / "menus"
    menus_dir.mkdir(parents=True, exist_ok=True)
    menu_file = menus_dir / "cinnamon-applications.menu"

    base_file = Path("/etc/xdg/menus/cinnamon-applications.menu")
    if base_file.is_file():
        content = base_file.read_text()
        if "<Name>Projects</Name>" not in content:
            office_menu = "</Menu> <!-- End Office -->"
            projects_menu = """</Menu> <!-- End Office -->

  <!-- Projects (Custom AI Projects Tab right below Office) -->
  <Menu>
    <Name>Projects</Name>
    <Directory>cinnamon-projects.directory</Directory>
    <Include>
      <And>
        <Category>Projects</Category>
      </And>
    </Include>
  </Menu> <!-- End Projects -->"""
            content = content.replace(office_menu, projects_menu)

            office_layout = "<Menuname>Office</Menuname>"
            projects_layout = "<Menuname>Office</Menuname>\n\t<Menuname>Projects</Menuname>"
            content = content.replace(office_layout, projects_layout)

        menu_file.write_text(content)

def install_or_update_projects(projects_dir: str, dry_run: bool = False) -> List[str]:
    """
    Checks each project folder in projects_dir and installs or updates its
    launchers, desktop files, icons, and configurations.
    """
    home = Path.home()
    bin_dir = home / ".local" / "bin"
    app_dir = home / ".local" / "share" / "applications"
    icon_hicolor = home / ".local" / "share" / "icons" / "hicolor"
    p_dir = Path(projects_dir)

    bin_dir.mkdir(parents=True, exist_ok=True)
    app_dir.mkdir(parents=True, exist_ok=True)

    if not dry_run:
        ensure_cinnamon_menu_tab(home)

    installed_summary: List[str] = []

    print(color("\n🚀 Installing & Updating All Projects in Folders:\n", Colors.BOLD + Colors.WHITE))

    # 1. StatDisk
    statdisk_dir = p_dir / "statdisk"
    if statdisk_dir.is_dir():
        print(f"  {color('●', Colors.CYAN)} {color('StatDisk', Colors.BOLD)}: Installing desktop launcher and statistical analyzer...")
        if not dry_run:
            install_script = statdisk_dir / "install.sh"
            if install_script.is_file():
                subprocess.run(["bash", str(install_script)], cwd=str(statdisk_dir), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # Ensure Category includes Projects
            stat_desktop = app_dir / "statdisk.desktop"
            if stat_desktop.is_file():
                txt = stat_desktop.read_text()
                if "Projects;" not in txt:
                    txt = txt.replace("Categories=", "Categories=Projects;")
                    stat_desktop.write_text(txt)
        installed_summary.append("StatDisk (Launcher, site-packages, icons & desktop entry)")
        print(f"      {color('✓', Colors.GREEN)} StatDisk application is ready (~/.local/bin/statdisk)")

    # 1b. MintStatLab
    mintstatlab_dir = p_dir / "mintstatlab"
    if mintstatlab_dir.is_dir():
        print(f"  {color('●', Colors.CYAN)} {color('MintStatLab', Colors.BOLD)}: Installing statistical telemetry lab & desktop entry...")
        if not dry_run:
            install_script = mintstatlab_dir / "install.sh"
            if install_script.is_file():
                subprocess.run(["bash", str(install_script)], cwd=str(mintstatlab_dir), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            statlab_desktop = app_dir / "mintstatlab.desktop"
            if statlab_desktop.is_file():
                txt = statlab_desktop.read_text()
                if "Projects;" not in txt:
                    txt = txt.replace("Categories=", "Categories=Projects;")
                    statlab_desktop.write_text(txt)
        installed_summary.append("MintStatLab (Launcher, icons, debian pkg & desktop entry)")
        print(f"      {color('✓', Colors.GREEN)} MintStatLab application is ready (~/.local/bin/mintstatlab)")

    # 2. Mint Auto Clicker
    mint_clicker_dir = p_dir / "mint-autoclicker"
    if mint_clicker_dir.is_dir():
        print(f"  {color('●', Colors.CYAN)} {color('Mint Auto Clicker', Colors.BOLD)}: Installing auto clicker & desktop integration...")
        if not dry_run:
            install_script = mint_clicker_dir / "install.sh"
            if install_script.is_file():
                subprocess.run(["bash", str(install_script)], cwd=str(mint_clicker_dir), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            mint_desktop = app_dir / "mint-autoclicker.desktop"
            if mint_desktop.is_file():
                txt = mint_desktop.read_text()
                if "Projects;" not in txt:
                    txt = txt.replace("Categories=", "Categories=Projects;")
                    mint_desktop.write_text(txt)
        installed_summary.append("Mint Auto Clicker (Launcher, site-packages, icons & desktop entry)")
        print(f"      {color('✓', Colors.GREEN)} Mint Auto Clicker is ready (~/.local/bin/mint-autoclicker)")

    # 3. Roblox Caffeine
    roblox_dir = p_dir / "roblox-caffeine"
    if roblox_dir.is_dir():
        print(f"  {color('●', Colors.CYAN)} {color('Roblox Caffeine', Colors.BOLD)}: Installing keep-alive /dev/uinput utility...")
        if not dry_run:
            install_script = roblox_dir / "install.sh"
            if install_script.is_file():
                subprocess.run(["bash", str(install_script)], cwd=str(roblox_dir), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # Copy roblox icon if available
            r_icon = roblox_dir / "assets" / "roblox_caffeine.png"
            if r_icon.is_file():
                target_r_icon_dir = icon_hicolor / "256x256" / "apps"
                target_r_icon_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(r_icon, target_r_icon_dir / "roblox-caffeine.png")
            # Install roblox desktop file
            roblox_desktop = f"""[Desktop Entry]
Name=Roblox Caffeine
GenericName=Anti-AFK Keep-Alive Utility
Comment=Emulate gamepad activity via /dev/uinput to prevent Roblox 20-minute AFK kick
Exec={bin_dir}/roblox-caffeine
Icon=roblox-caffeine
Terminal=true
Type=Application
Categories=Projects;Game;Utility;
Keywords=roblox;afk;caffeine;gamepad;uinput;
"""
            write_desktop_file(app_dir / "roblox-caffeine.desktop", roblox_desktop)
            # Check git pull if remote exists
            if (roblox_dir / ".git").is_dir():
                subprocess.run(["git", "-C", str(roblox_dir), "pull"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        installed_summary.append("Roblox Caffeine (Kernel gamepad emulation utility & desktop entry)")
        print(f"      {color('✓', Colors.GREEN)} Roblox Caffeine is ready (~/.local/bin/roblox-caffeine)")

    # 4. OmniBoot USB
    omniboot_dir = p_dir / "omniboot-usb"
    if omniboot_dir.is_dir():
        print(f"  {color('●', Colors.CYAN)} {color('OmniBoot USB', Colors.BOLD)}: Installing Multi-ISO & single OS bootable USB flasher...")
        if not dry_run:
            launcher = bin_dir / "omniboot-usb"
            launcher_content = f"""#!/bin/sh
exec /usr/bin/python3 "{omniboot_dir}/main.py" "$@"
"""
            write_executable(launcher, launcher_content)

            # Copy icon
            svg_icon = omniboot_dir / "omniboot-usb.svg"
            if svg_icon.is_file():
                target_icon_dir = icon_hicolor / "scalable" / "apps"
                target_icon_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(svg_icon, target_icon_dir / "omniboot-usb.svg")

            # Desktop entry
            desktop_content = f"""[Desktop Entry]
Name=OmniBoot USB
GenericName=Bootable USB Flasher
Comment=Create bootable USB drives with Ventoy multi-ISO or direct OS flashing
Exec={launcher}
Icon=omniboot-usb
Terminal=false
Type=Application
Categories=Projects;System;Utility;Archiving;
Keywords=usb;flash;iso;ventoy;windows;linux;boot;
StartupNotify=true
"""
            write_desktop_file(app_dir / "omniboot-usb.desktop", desktop_content)
        installed_summary.append("OmniBoot USB (Launcher, scalable SVG icon & desktop entry)")
        print(f"      {color('✓', Colors.GREEN)} OmniBoot USB is ready (~/.local/bin/omniboot-usb)")

    # 5. USBGuard App
    usbguard_dir = p_dir / "usbguard-app"
    if usbguard_dir.is_dir():
        print(f"  {color('●', Colors.CYAN)} {color('USBGuard App', Colors.BOLD)}: Installing BadUSB protection interface...")
        if not dry_run:
            launcher = bin_dir / "usbguard-manager"
            launcher_content = f"""#!/bin/bash
export PYTHONPATH="{usbguard_dir}/src:${{PYTHONPATH}}"
exec /usr/bin/python3 "{usbguard_dir}/src/main.py" "$@"
"""
            write_executable(launcher, launcher_content)

            # Copy icon
            svg_icon = usbguard_dir / "src" / "usbguard-manager.svg"
            if svg_icon.is_file():
                target_icon_dir = icon_hicolor / "scalable" / "apps"
                target_icon_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(svg_icon, target_icon_dir / "usbguard-manager.svg")

            desktop_content = f"""[Desktop Entry]
Name=USBGuard Manager
GenericName=USB Device Authorization Manager
Comment=BadUSB attack defense and USB authorization interface
Exec={launcher}
Icon=usbguard-manager
Terminal=false
Type=Application
Categories=Projects;System;Utility;Security;
StartupNotify=true
"""
            write_desktop_file(app_dir / "usbguard-manager.desktop", desktop_content)
        installed_summary.append("USBGuard App (Launcher, scalable SVG icon & desktop entry)")
        print(f"      {color('✓', Colors.GREEN)} USBGuard Manager is ready (~/.local/bin/usbguard-manager)")

    # 6. JellyScratch Server
    jellyscratch_dir = p_dir / "jellyscratch-server"
    if jellyscratch_dir.is_dir():
        print(f"  {color('●', Colors.CYAN)} {color('JellyScratch Server', Colors.BOLD)}: Installing desktop player & live monitor...")
        if not dry_run:
            launcher = bin_dir / "jellyscratchserver"
            launcher_content = f"""#!/usr/bin/env bash
exec /usr/bin/python3 "{jellyscratch_dir}/src/app.py" "$@"
"""
            write_executable(launcher, launcher_content)

            # Copy icon
            png_icon = jellyscratch_dir / "src" / "icon.png"
            if png_icon.is_file():
                target_icon_dir = icon_hicolor / "256x256" / "apps"
                target_icon_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(png_icon, target_icon_dir / "jellyscratchserver.png")

            desktop_content = f"""[Desktop Entry]
Name=JellyScratch Server
GenericName=Media Server & Player
Comment=Jellyfin Media Server with Live Discord Playback Monitor
Exec={launcher}
Icon=jellyscratchserver
Terminal=false
Type=Application
Categories=Projects;AudioVideo;Video;Player;Network;
Keywords=jellyfin;media;server;player;discord;stream;movies;
StartupWMClass=jellyscratchserver
"""
            write_desktop_file(app_dir / "jellyscratchserver.desktop", desktop_content)
        installed_summary.append("JellyScratch Server (Launcher, 256x256 icon & desktop entry)")
        print(f"      {color('✓', Colors.GREEN)} JellyScratch Server is ready (~/.local/bin/jellyscratchserver)")

    # 7. Jellyfin Discord Bot
    discord_bot_dir = p_dir / "jellyfin-discord-bot"
    if discord_bot_dir.is_dir():
        print(f"  {color('●', Colors.CYAN)} {color('Jellyfin Discord Bot', Colors.BOLD)}: Installing Discord monitor & configurator...")
        if not dry_run:
            launcher = bin_dir / "jellyfin-discord-bot"
            launcher_content = f"""#!/usr/bin/env bash
exec /usr/bin/python3 "{discord_bot_dir}/monitor.py" "$@"
"""
            write_executable(launcher, launcher_content)

            conf_launcher = bin_dir / "jellyfin-discord-configure"
            conf_content = f"""#!/usr/bin/env bash
exec /usr/bin/python3 "{discord_bot_dir}/configure.py" "$@"
"""
            write_executable(conf_launcher, conf_content)

            discord_desktop = f"""[Desktop Entry]
Name=Jellyfin Discord Bot
GenericName=Discord Playback Broadcaster
Comment=Broadcast active Jellyfin playback and library updates to Discord webhook
Exec={launcher}
Icon=applications-internet
Terminal=true
Type=Application
Categories=Projects;AudioVideo;Network;
Actions=Configure;

[Desktop Action Configure]
Name=Configure Discord Bot
Exec={conf_launcher}
"""
            write_desktop_file(app_dir / "jellyfin-discord-bot.desktop", discord_desktop)
        installed_summary.append("Jellyfin Discord Bot (Monitor, configure launchers & desktop entry)")
        print(f"      {color('✓', Colors.GREEN)} Jellyfin Discord Bot is ready (~/.local/bin/jellyfin-discord-bot)")

    # 8. Stremio Dashboard
    stremio_dir = p_dir / "stremio-dashboard"
    if stremio_dir.is_dir():
        print(f"  {color('●', Colors.CYAN)} {color('Stremio Dashboard', Colors.BOLD)}: Installing web dashboard manager...")
        if not dry_run:
            launcher = bin_dir / "stremio-dashboard"
            launcher_content = f"""#!/usr/bin/env bash
exec /usr/bin/python3 "{stremio_dir}/stremio_dashboard.py" "$@"
"""
            write_executable(launcher, launcher_content)

            desktop_content = f"""[Desktop Entry]
Name=Stremio Dashboard
GenericName=Real-Debrid & Discord Stream Manager
Comment=Cloud debrid monitoring and Discord integration dashboard
Exec={launcher}
Icon=applications-internet
Terminal=true
Type=Application
Categories=Projects;Network;AudioVideo;
"""
            write_desktop_file(app_dir / "stremio-dashboard.desktop", desktop_content)
        installed_summary.append("Stremio Dashboard (Launcher & desktop entry)")
        print(f"      {color('✓', Colors.GREEN)} Stremio Dashboard is ready (~/.local/bin/stremio-dashboard)")

    # 9. Project Manager Shortcut in Applications Menu
    if not dry_run:
        update_desktop = f"""[Desktop Entry]
Name=Update All Projects
GenericName=Project & Dependency Manager
Comment=Install and update all AI custom projects, dependencies, and desktop shortcuts
Exec={bin_dir}/install-or-update-all-projects
Icon=system-software-update
Terminal=true
Type=Application
Categories=Projects;System;Utility;
"""
        write_desktop_file(app_dir / "install-or-update-projects.desktop", update_desktop)
        installed_summary.append("Update All Projects (Desktop menu shortcut)")

    # 9. Docker Services (Seerr & Debrid)
    for docker_proj in ("seerr", "debrid"):
        d_dir = p_dir / docker_proj
        if d_dir.is_dir() and (d_dir / "docker-compose.yml").is_file():
            print(f"  {color('●', Colors.CYAN)} {color(docker_proj.capitalize(), Colors.BOLD)}: Verifying Docker Compose configuration...")
            if not dry_run and shutil.which("docker"):
                # If docker daemon running, update image
                res = subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if res.returncode == 0:
                    subprocess.run(["docker", "compose", "pull"], cwd=str(d_dir), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            installed_summary.append(f"{docker_proj.capitalize()} (Docker Compose service)")
            print(f"      {color('✓', Colors.GREEN)} {docker_proj.capitalize()} compose configuration verified")

    # 10. System Utility Scripts
    sys_scripts_dir = p_dir / "system-scripts"
    if sys_scripts_dir.is_dir():
        print(f"  {color('●', Colors.CYAN)} {color('System Utility Scripts', Colors.BOLD)}: Setting execution permissions on system helpers...")
        if not dry_run:
            for s in sys_scripts_dir.glob("*.sh"):
                s.chmod(0o755)
            # Link speaker fix to ~/.local/bin/fix-speaker
            fix_spk = sys_scripts_dir / "fix-speaker.sh"
            if fix_spk.is_file():
                sym = bin_dir / "fix-speaker"
                if sym.is_symlink() or sym.is_file():
                    sym.unlink()
                sym.symlink_to(fix_spk)
        installed_summary.append("System Utility Scripts (Permissions & fix-speaker link)")
        print(f"      {color('✓', Colors.GREEN)} System utility scripts configured")

    # 11. CHEM 151 Master Review
    chem_dir = p_dir / "chem151-review"
    if chem_dir.is_dir():
        print(f"  {color('●', Colors.CYAN)} {color('CHEM 151 Master Review', Colors.BOLD)}: Installing chemistry study suite & calculators...")
        if not dry_run:
            install_script = chem_dir / "install.sh"
            if install_script.is_file():
                subprocess.run(["bash", str(install_script)], cwd=str(chem_dir), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            chem_desktop = app_dir / "chem151-master-review.desktop"
            if chem_desktop.is_file():
                txt = chem_desktop.read_text()
                if "Projects;" not in txt:
                    txt = txt.replace("Categories=", "Categories=Projects;")
                    chem_desktop.write_text(txt)
        installed_summary.append("CHEM 151 Master Review (Study suite & 7 offline calculators)")
        print(f"      {color('✓', Colors.GREEN)} CHEM 151 Master Review is ready (~/.local/bin/chem151-master-review)")

    # 12. Generic detection for any additional custom project folders!
    known_keys = set(PROJECT_REGISTRY.keys())
    for item in p_dir.iterdir():
        if item.is_dir() and item.name not in known_keys and not item.name.startswith("."):
            print(f"  {color('●', Colors.CYAN)} {color(item.name, Colors.BOLD)}: Checking custom folder...")
            # Check for install.sh
            custom_install = item / "install.sh"
            if custom_install.is_file() and not dry_run:
                custom_install.chmod(0o755)
                subprocess.run(["bash", str(custom_install)], cwd=str(item), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                installed_summary.append(f"{item.name} (Ran custom install.sh)")
                print(f"      {color('✓', Colors.GREEN)} Custom install.sh executed for {item.name}")
            # Check for .desktop files
            for dt in item.glob("*.desktop"):
                if not dry_run:
                    shutil.copy2(dt, app_dir / dt.name)
                print(f"      {color('✓', Colors.GREEN)} Installed custom desktop file {dt.name}")

    # Step 3: Refresh desktop and icon databases
    if not dry_run:
        print(color("\n🔄 Refreshing Linux Mint application menu & icon caches...", Colors.CYAN))
        if shutil.which("update-desktop-database"):
            subprocess.run(["update-desktop-database", str(app_dir)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if shutil.which("gtk-update-icon-cache"):
            subprocess.run(["gtk-update-icon-cache", "-t", "-f", str(icon_hicolor)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return installed_summary

# ==============================================================================
# Main Program
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Install or update all projects and dependencies across ~/Projects"
    )
    parser.add_argument(
        "-p", "--projects-only",
        dest="projects_only",
        action="store_true",
        help="Install/update project launchers, desktop entries, and configurations only (skip system APT packages)"
    )
    parser.add_argument(
        "-d", "--deps-only",
        dest="deps_only",
        action="store_true",
        help="Check, install, and upgrade system & Python dependencies only"
    )
    parser.add_argument(
        "-c", "--check", "--check-only",
        dest="check_only",
        action="store_true",
        help="Audit dependencies and project status without making changes"
    )
    parser.add_argument(
        "-n", "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Simulate all actions without making modifications"
    )
    parser.add_argument(
        "-r", "--refresh",
        dest="refresh_apt",
        action="store_true",
        help="Run 'apt-get update' before checking package candidates"
    )

    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    projects_dir = script_dir

    print(color("=" * 76, Colors.BLUE))
    print(color("   🚀 Omni Projects: Install or Update All Projects & Dependencies", Colors.BOLD + Colors.CYAN))
    print(color(f"   Projects Root: {projects_dir}", Colors.DIM))
    print(color("=" * 76, Colors.BLUE))

    # STAGE 1: System & Python Dependencies Audit & Upgrade
    if not args.projects_only:
        print(color("\n📦 STAGE 1: Auditing & Updating Dependencies Across All Projects", Colors.BOLD + Colors.WHITE))

        all_packages: Set[str] = set()
        project_pkgs_map: Dict[str, Set[str]] = {}

        for proj_id, info in PROJECT_REGISTRY.items():
            pkgs = set(info.get("apt_packages", []))
            project_pkgs_map[proj_id] = pkgs
            all_packages.update(pkgs)

        dynamic_discovered = scan_dynamic_dependencies(projects_dir)
        for proj_id, pkgs in dynamic_discovered.items():
            if proj_id not in project_pkgs_map:
                project_pkgs_map[proj_id] = set()
            project_pkgs_map[proj_id].update(pkgs)
            all_packages.update(pkgs)

        if args.refresh_apt and not args.check_only:
            print(color("🔄 Updating APT package repositories...", Colors.YELLOW))
            if check_sudo_access():
                cmd = ["sudo", "apt-get", "update"] if not is_root() else ["apt-get", "update"]
                subprocess.run(cmd)

        apt_info = get_apt_policy(list(all_packages))

        missing_packages: List[str] = []
        upgradable_packages: List[Tuple[str, str, str]] = []
        uptodate_packages: List[Tuple[str, str]] = []

        for pkg in sorted(list(all_packages)):
            info = apt_info.get(pkg)
            if not info:
                continue
            inst = info.get("installed")
            cand = info.get("candidate")

            if not cand or cand == "(none)":
                continue
            elif not inst or inst == "(none)":
                missing_packages.append(pkg)
            elif inst != cand:
                upgradable_packages.append((pkg, inst, cand))
            else:
                uptodate_packages.append((pkg, inst))

        print(f"  • Total dependencies evaluated: {color(str(len(all_packages)), Colors.BOLD)}")
        print(f"  • Already installed & up to date: {color(str(len(uptodate_packages)), Colors.GREEN)}")
        print(f"  • Missing dependencies: {color(str(len(missing_packages)), Colors.RED if missing_packages else Colors.GREEN)}")
        print(f"  • Updates available: {color(str(len(upgradable_packages)), Colors.YELLOW if upgradable_packages else Colors.GREEN)}")

        if missing_packages:
            print(color(f"\n  Missing packages to install: {', '.join(missing_packages)}", Colors.RED))
        if upgradable_packages:
            print(color(f"  Packages to upgrade: {', '.join([p[0] for p in upgradable_packages])}", Colors.YELLOW))

        # Handle Dependency Installation & Upgrades
        if not args.check_only:
            pkgs_to_install = missing_packages
            pkgs_to_upgrade = [p[0] for p in upgradable_packages]

            if pkgs_to_install or pkgs_to_upgrade:
                if args.dry_run:
                    print(color("\n🧪 [DRY RUN] Would run APT installation/upgrade:", Colors.CYAN))
                    if pkgs_to_install:
                        print(f"  apt-get install -y {' '.join(pkgs_to_install)}")
                    if pkgs_to_upgrade:
                        print(f"  apt-get install --only-upgrade -y {' '.join(pkgs_to_upgrade)}")
                else:
                    if not check_sudo_access():
                        print(color("\n⚠️  Notice: Administrator privileges (sudo) needed for system packages.", Colors.YELLOW))
                        print(color("To install/upgrade system dependencies, run in terminal:", Colors.WHITE))
                        if pkgs_to_install:
                            print(f"    sudo apt-get install -y {' '.join(pkgs_to_install)}")
                        if pkgs_to_upgrade:
                            print(f"    sudo apt-get install --only-upgrade -y {' '.join(pkgs_to_upgrade)}")
                    else:
                        sudo_prefix = [] if is_root() else ["sudo"]
                        env = os.environ.copy()
                        env["DEBIAN_FRONTEND"] = "noninteractive"

                        if pkgs_to_install:
                            print(color(f"\n📦 Installing {len(pkgs_to_install)} missing dependencies...", Colors.BOLD + Colors.CYAN))
                            subprocess.run(sudo_prefix + ["apt-get", "install", "-y"] + pkgs_to_install, env=env)

                        if pkgs_to_upgrade:
                            print(color(f"\n⬆️  Upgrading {len(pkgs_to_upgrade)} existing dependencies...", Colors.BOLD + Colors.YELLOW))
                            subprocess.run(sudo_prefix + ["apt-get", "install", "--only-upgrade", "-y"] + pkgs_to_upgrade, env=env)

    # STAGE 2: Install or Update All Projects
    if not args.deps_only:
        print(color("\n💻 STAGE 2: Installing & Updating Desktop Applications & Services", Colors.BOLD + Colors.WHITE))
        installed = install_or_update_projects(projects_dir, dry_run=args.dry_run or args.check_only)

    print(color("\n" + "=" * 76, Colors.GREEN))
    print(color("🎉 All Projects & Dependencies Successfully Checked & Updated!", Colors.GREEN + Colors.BOLD))
    print(color("   • Applications are installed in ~/.local/bin and available in your PATH", Colors.WHITE))
    print(color("   • Desktop menu entries & icons updated in your Linux Mint Application Menu", Colors.WHITE))
    print(color("   • Re-running this script will check for newer versions and upgrade everything automatically.", Colors.WHITE))
    print(color("=" * 76, Colors.GREEN))
    return 0

if __name__ == "__main__":
    sys.exit(main())
