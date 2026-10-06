# USB Guard Manager (`usbguard-manager`)

A modern Linux desktop security application and GTK frontend for **USBGuard**. Protects your system against rogue USB devices, unauthorized storage drives, and BadUSB attacks by **blocking any newly plugged-in USB device by default**, while allowing you to easily authorize and trust legitimate hardware with a single click.

---

## Key Features

- 🛡️ **Default-Block USB Protection**: Configures USBGuard with `ImplicitPolicyTarget=block` to immediately deauthorize and block any unknown USB device upon insertion.
- ⚡ **1-Click Device Trusting**: Whitelist legitimate USB devices permanently into `/etc/usbguard/rules.conf` or allow them temporarily for the current session.
- 🔔 **Instant Desktop Notifications**: Alerts you immediately via Linux desktop notifications when an untrusted USB device is plugged in and blocked.
- 📋 **Trusted Whitelist Management**: View, add, or delete permanent USB authorization rules by Vendor:Product ID, device name, and serial number.
- ⌨️ **Safe Baseline Protection**: Generates an initial whitelist for your currently connected peripherals (keyboard, mouse, webcam, hubs) upon package installation to prevent accidental lockouts.
- 🔑 **Seamless Permissions**: Configures IPC access for the `plugdev` and `sudo` groups, letting standard desktop users manage USB authorization without entering a root password on every click.
- 🎨 **Modern Native GTK3 Interface**: Beautiful Linux Mint / Ubuntu desktop styling with dark mode support, real-time hardware status, and search filtering.

---

## Installation (`.deb` Package)

The pre-built Debian package is located at:
```bash
/home/sam/usbguard-manager_1.0.0_all.deb
```

To install the `.deb` package with all required dependencies:
```bash
sudo apt install /home/sam/usbguard-manager_1.0.0_all.deb
```
*(Alternatively, you can double-click the `.deb` file in your file manager to install it via GDebi or Linux Mint Software Manager).*

---

## How It Works

1. **Hardware Detection & Blocking**:
   When you plug in a USB flash drive or device, the Linux kernel communicates with the USBGuard daemon. Because `ImplicitPolicyTarget=block` is active, the device is kept in an unauthorized state (`authorized = 0`). The drive will not mount and cannot send data or keystrokes.
2. **Alert**:
   A desktop notification pops up informing you that a device was plugged in and blocked.
3. **Authorization**:
   Open **USB Guard** from your application menu or terminal (`usbguard-manager`):
   - Click on the blocked device (marked with a red **BLOCKED** badge).
   - Click **🛡️ Trust & Allow Device**: Permanently saves the device to your trusted whitelist. It will be allowed automatically whenever plugged in in the future.
   - Or click **⏱️ Allow Temporarily**: Allows the device for the current session only.
   - If you ever want to revoke trust, click **Remove from Trusted** or delete the rule from the **Trusted Whitelist** tab.

---

## Running Directly from Source (Development / Testing)

You can run the app directly without installing the package:
```bash
cd /home/sam/usbguard-app
python3 src/main.py
```

---

## Rebuilding the `.deb` Package

To rebuild the `.deb` package at any time:
```bash
cd /home/sam/usbguard-app
./build_deb.sh
```
The output file will be generated at `/home/sam/usbguard-manager_1.0.0_all.deb`.
