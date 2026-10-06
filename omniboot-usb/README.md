# OmniBoot USB — Multi-ISO & Single OS Bootable USB Creator

**OmniBoot USB** is a native Linux desktop application (packaged as a standard `.deb` file) for preparing bootable USB drives. It requires **no localhost** and **no web browser**, integrating with Linux Mint, Ubuntu, and Debian.

---

## ✨ Features

- **No Localhost / Native Desktop Application**: Built with Python 3 and native GTK3, fully themed for Linux Mint (Cinnamon, MATE, XFCE) and GNOME.
- **Ventoy Multi-ISO Support**:
  - Install the Ventoy bootloader on the drive.
  - Automatically copy one or multiple ISOs (Linux and/or Windows).
  - Boot any ISO from a clean graphical boot menu.
  - Add more ISOs in the future simply by dragging and dropping them into the USB drive in your file manager!
- **Dedicated Single-ISO Direct Flash**:
  - **Linux ISOs**: Direct raw block flashing (`dd`-style streaming) with live throughput speed (MB/s), ETA calculation, and cache synchronization (`sync`/`fsync`).
  - **Windows ISOs**: Configures dedicated UEFI bootloader setup with automatic Windows 11 hardware check bypass (TPM / Secure Boot / CPU bypass).
- **Pre-Flight Storage Analysis**:
  - Compares USB drive capacity against ISO file size before flashing.
  - Displays Total Drive Capacity, Required Space, and Remaining Free Space.
  - Includes a visual usage meter and safety guard that blocks flashing if the drive is too small.
- **Drive Safety Guard**:
  - Detects removable USB drives.
  - Protects internal system disks (containing `/`, `/boot`, `/home`, or active swap partitions) to prevent data loss.
- **PolicyKit (pkexec) Elevation**:
  - Runs the GUI as your normal desktop user.
  - Prompts for authorization only when writing to the USB block device.
- **100% Offline**:
  - Bundles the Ventoy engine directly inside the `.deb` package. No internet connection is needed to create bootable drives!

---

## 📦 Installation

To install the built `.deb` package on Linux Mint, Ubuntu, or Debian:

```bash
sudo apt install /home/sam/omniboot-usb/omniboot-usb_1.0.0_amd64.deb
```
*(or via dpkg: `sudo dpkg -i /home/sam/omniboot-usb/omniboot-usb_1.0.0_amd64.deb`)*

Once installed, OmniBoot USB will appear in your application menu under **System** or **Administration**, or can be launched from the terminal by running:
```bash
omniboot-usb
```

---

## 🚀 How to Use

1. **Launch OmniBoot USB** from your application menu or terminal (`omniboot-usb`).
2. **Choose Mode**:
   - **Multiple ISOs on One USB (Ventoy Multi-Boot)**: Select this if you want to store and boot multiple operating systems (e.g. Linux Mint, Ubuntu, Windows 11) on a single flash drive.
   - **Single Operating System (Dedicated Direct Flash)**: Select this to create a single-purpose dedicated installer for one OS.
3. **Select Target USB Drive**:
   - Choose your USB drive from the dropdown. (Internal drives are filtered out for your protection).
4. **Select ISO Image(s)**:
   - In Multi-ISO mode: click **Add ISO File...** to select one or multiple ISOs.
   - In Single-ISO mode: click **Choose ISO Image File...**. OmniBoot will auto-detect the operating system type (Linux vs Windows).
5. **Review Storage Pre-Flight Analysis**:
   - Verify that the drive capacity exceeds the ISO size.
   - The indicator will turn **green** ("Storage Check Passed") if space is sufficient, or **red** if the drive is too small.
6. **Click "Install Ventoy & Copy ISOs" or "Flash Dedicated Single OS Installer"**:
   - Confirm the formatting warning.
   - Enter your password in the PolicyKit authorization prompt.
   - Watch the live progress, write speed, and ETA.
7. **Boot**:
   - Plug the USB into your target computer, power it on, and press **F12**, **F11**, or **Del** to open the boot menu and select your USB drive!

---

## 🛠️ Rebuilding the Package

If you modify any source files in `/home/sam/omniboot-usb`, you can rebuild the `.deb` package at any time by running:

```bash
cd /home/sam/omniboot-usb
./build_deb.sh
```
