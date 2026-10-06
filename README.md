# 🚀 Omni Projects Directory (`~/Projects`)

Welcome to the central development and utilities workspace for Linux Mint. This folder contains native desktop applications, media services, automation tools, and system optimization scripts.

---

## 🛠️ Install or Update All Projects & Dependencies (`install_or_update_all_projects.sh`)

You can install or update all projects, desktop shortcuts, applications, and system dependencies across the entire `~/Projects` folder all at once using the unified manager:

```bash
# Run from ~/Projects:
./install_or_update_all_projects.sh

# Or run from anywhere in your terminal:
install-or-update-all-projects
```

*(Aliases `install-or-update-projects` and `check-dependencies` also work).*

### ✨ How It Works (All-In-One Execution)

1. **Stage 1: Dependencies Resolution & Upgrades**:
   - Scans every project folder for system APT packages, Python requirements (`requirements.txt`, `pyproject.toml`), and Debian package definitions (`control` files).
   - If any required packages are missing, it installs them automatically.
   - If packages are already installed, it checks repositories and upgrades them to the latest versions.

2. **Stage 2: Project Installation & Updates (All Folders at Once)**:
   - **StatDisk**: Installs the GTK3 statistical disk space visualizer into `~/.local/bin/statdisk`, registers desktop shortcuts, and updates icon caches.
   - **Mint Auto Clicker**: Installs the automation clicker into `~/.local/bin/mint-autoclicker` and desktop menu.
   - **Roblox Caffeine**: Links `/dev/uinput` keep-alive daemon into `~/.local/bin/roblox-caffeine` and pulls git updates.
   - **OmniBoot USB**: Installs the bootable USB creator into `~/.local/bin/omniboot-usb` and desktop menu.
   - **USBGuard App**: Installs BadUSB defense manager into `~/.local/bin/usbguard-manager` and desktop menu.
   - **JellyScratch Server**: Installs embedded Jellyfin player & monitor into `~/.local/bin/jellyscratchserver` and desktop menu.
   - **Jellyfin Discord Bot**: Installs playback monitor and configurator into `~/.local/bin/jellyfin-discord-bot`.
   - **Stremio Dashboard**: Installs the Debrid & Discord web dashboard into `~/.local/bin/stremio-dashboard` and desktop menu.
   - **Seerr & Debrid**: Verifies Docker Compose definitions and pulls updated container images.
   - **System Scripts**: Verifies executable permissions and links `fix-speaker` to `~/.local/bin/fix-speaker`.
   - **Any New Custom Folder**: Detects any custom `install.sh` or `.desktop` files in newly created folders and executes/installs them automatically.

3. **Stage 3: Menu & Icon Database Refresh**:
   - Refreshes `update-desktop-database` and `gtk-update-icon-cache` so all applications appear immediately in your Linux Mint Cinnamon Application Menu.
   - Configures a dedicated **Projects** tab in the main Cinnamon Application Menu directly below the **Office** tab, showing all custom AI-built utilities in one central place.

---

## 🖥️ Application Menu: "Projects" Tab

Your custom applications are grouped under a dedicated **Projects** category in the Linux Mint Cinnamon Menu, positioned directly **below the Office tab**:

- 🧪 **CHEM 151 Master Review**: General Chemistry I study guide & 7 offline interactive calculators.
- 📊 **StatDisk**: Disk space analyzer with statistical moments, Pareto, and Gini models.
- 🖱️ **Mint Auto Clicker**: Process-targeted high-speed auto clicker.
- 💾 **OmniBoot USB**: Multi-ISO Ventoy and direct USB flasher.
- 🛡️ **USBGuard Manager**: BadUSB attack defense and device whitelist tool.
- ☕ **Roblox Caffeine**: Linux /dev/uinput anti-AFK keep-alive daemon.
- 🎬 **JellyScratch Server**: Embedded Jellyfin media player and live Discord monitor.
- 🤖 **Jellyfin Discord Bot**: Live playback stats and library updates webhook broadcaster.
- 🌐 **Stremio Dashboard**: Real-Debrid API and Discord webhook web interface.
- 🔄 **Update All Projects**: One-click desktop shortcut to install or update all projects and dependencies.

---

### 📋 Usage & Options

| Command | Action |
|---|---|
| `install-or-update-all-projects` | **Full Mode**: Audits & installs/upgrades system dependencies, then installs/updates all projects and desktop apps all at once. |
| `install-or-update-all-projects -p` | **Projects Only**: Installs/updates all desktop applications, launchers, and menu entries (skips system APT packages, requires no sudo). |
| `install-or-update-all-projects -d` | **Dependencies Only**: Checks, installs, and upgrades system & Python dependencies across all projects. |
| `install-or-update-all-projects -c` | **Audit Check**: Read-only check and status report of both dependencies and project installations. |
| `install-or-update-all-projects -n` | **Dry Run**: Simulates all actions without modifying system state. |

---

## 📁 Projects Overview

| Project | Description | Installed Launcher |
|---|---|---|
| **[CHEM 151 Master Review](./chem151-review)** | General Chemistry Unit 1 & Unit 2 master study guide with 7 offline interactive calculators. | `chem151-master-review` |
| **[StatDisk](./statdisk)** | Modern GTK3 disk space visualizer with Sunburst, Treemap, and statistical inequality models (Gini, Pareto, Tukey). | `statdisk` |
| **[Mint Auto Clicker](./mint-autoclicker)** | Fast desktop auto-clicker for Linux Mint with process selection, window boundary locking, and humanized jitter. | `mint-autoclicker` |
| **[OmniBoot USB](./omniboot-usb)** | Multi-ISO bootable USB creator with Ventoy engine, single-OS direct flashing, and storage capacity verification. | `omniboot-usb` |
| **[USBGuard App](./usbguard-app)** | GTK3 manager for USBGuard that protects against BadUSB attacks with desktop notifications and authorization. | `usbguard-manager` |
| **[Roblox Caffeine](./roblox-caffeine)** | Kernel gamepad emulation via `/dev/uinput` to prevent 20-minute inactivity kicks on Linux. | `roblox-caffeine` |
| **[JellyScratch Server](./jellyscratch-server)** | Embedded WebKit desktop player and manager for Jellyfin Media Server with live Discord playback updates. | `jellyscratchserver` |
| **[Jellyfin Discord Bot](./jellyfin-discord-bot)** | Standalone Discord webhook monitor that announces new media and broadcasts live playback stats. | `jellyfin-discord-bot` |
| **[Stremio Dashboard](./stremio-dashboard)** | Web interface for managing Real-Debrid API keys, Discord webhooks, and stream quality settings. | `stremio-dashboard` |
| **[Seerr (Jellyseerr)](./seerr)** | Docker-based media request and discovery service for Jellyfin. | `seerr` |
| **[Debrid Cloud](./debrid)** | Docker-based Zurg Real-Debrid mount and Rclone caching service for Jellyfin media storage. | `debrid` |
| **[System Scripts](./system-scripts)** | Linux Mint maintenance utilities (audio fixes, face unlock camera configuration, Jellyfin setup). | `fix-speaker` |

---

## 💾 Backups (`copy_to_maxone.sh`)

Sync all project files and source trees to the Maxone External Hard Drive:

```bash
./copy_to_maxone.sh
```

---

## 🚀 GitHub Sync & Upload (`upload_to_github.sh`)

Sync and upload all project files to GitHub ([scratchgamingone/Projects-App-for-Linux-Mint](https://github.com/scratchgamingone/Projects-App-for-Linux-Mint)):

```bash
# Run from ~/Projects:
./upload_to_github.sh

# Or run from anywhere in your terminal:
upload-to-github
```

