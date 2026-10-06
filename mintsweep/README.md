# MintSweep 🧹

**MintSweep** is a native GTK3 desktop system cleaner and cache sweeper tailored for **Linux Mint** (and Debian/Ubuntu-based distributions).

It is a 100% native desktop application—**no web servers, no localhost, no browser engines**. It integrates directly with the desktop environment, respects system themes, and packages cleanly as a standard `.deb` file.

---

## Features

- **Safe Scanning:** Analyzes reclaimable space across multiple system locations without modifying files until you approve.
- **APT Package Cache:** Frees cached `.deb` installer archives stored in `/var/cache/apt/archives`.
- **Systemd Journal Cleaner:** Vacuums older system log entries (>7 days) to prevent log bloat.
- **Thumbnail Cache:** Wipes stale image and document thumbnail caches from `~/.cache/thumbnails`.
- **User Trash Bin:** Empties files lingering in the desktop Trash.
- **Flatpak Cleaner:** Detects and removes unused Flatpak runtimes if Flatpak is installed.
- **Desktop Integration:** Installs a `.desktop` launcher under the *Administration / System* category with a custom scalable SVG app icon.

---

## Project Structure

```
mintsweep/
├── bin/
│   └── mintsweep               # Executable launcher script
├── data/
│   ├── mintsweep.desktop       # Linux Mint desktop application shortcut
│   └── icons/
│       └── mintsweep.svg       # Scalable SVG application icon
├── debian/
│   ├── control                 # Debian package metadata & dependencies
│   └── postinst                # Post-install script for desktop/icon caches
├── src/
│   ├── __init__.py
│   ├── cleaner.py              # Scanning and cleaning engine
│   ├── window.py               # GTK3 UI with HeaderBar and async workers
│   └── main.py                 # Application initialization and styling
├── build-deb.sh                # Automated .deb package builder
├── Makefile                    # Make targets (run, deb, clean)
└── README.md
```

---

## Quick Start (Run from Source)

You don't need to install the `.deb` to test or develop the app:

```bash
# Using make:
make run

# Or directly:
./bin/mintsweep
```

---

## Building the `.deb` Package

To compile and build the Debian installer package:

```bash
./build-deb.sh
# or:
make deb
```

This will produce:
```
mintsweep_1.0.0_all.deb
```

---

## Installing on Linux Mint

Install the generated `.deb` package using `apt` (which resolves any dependencies automatically):

```bash
sudo apt install ./mintsweep_1.0.0_all.deb
```

Once installed:
1. Open the Linux Mint menu and search for **MintSweep**.
2. Or run `mintsweep` directly in any terminal.

---

## Uninstalling

```bash
sudo apt remove mintsweep
```
