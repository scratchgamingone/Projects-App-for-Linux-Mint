# 🚀 Mint Script Runner (`mint-script-runner`)

**Mint Script Runner** is a native Linux desktop application built for Linux Mint and Debian-based systems. It allows you to run any shell script (`.sh`) by **drag-and-drop** or file selection without ever needing to open a terminal.

---

## ✨ Features

- **🎯 Drag & Drop Interface**:
  - Drag and drop any `.sh` or `.bash` script from your file manager (Nemo) directly onto the application.
  - Right-click integration: Right-click any `.sh` file and choose **"Open With Mint Script Runner"**.
  - File picker button to browse files.

- **🛡️ Pre-Flight Permission Guard & Admin Elevation**:
  - Inspects the script before running to detect administrative commands (`sudo`, `apt`, `systemctl`, etc.).
  - Prompts you with an execution confirmation dialog:
    - **🔒 Run as Administrator (Root)**: Uses Linux Mint's native PolicyKit (`pkexec`) graphical authentication dialog.
    - **👤 Run as Standard User**: Executes under your normal user account.
  - Automatically ensures executable permissions (`chmod +x`).

- **🐙 GitHub Credentials & Settings Tab**:
  - Automatically inspects the script for Git/GitHub operations (`git push`, `git pull`, `git clone`, `github.com`).
  - Alerts you if GitHub credentials are required but not yet configured.
  - Dedicated **⚙️ GitHub Settings** tab:
    - GitHub Username (e.g. `scratchgamingone`).
    - GitHub Personal Access Token (PAT) with masked entry and show/hide toggle.
    - Git Author Email.
    - Default Git Remote Repository URL.
    - **Test Connection** button that pings GitHub's API to verify your token instantly.
    - Secure configuration stored in `~/.config/mint-script-runner/config.json` (`chmod 600`).

- **⚡ Silent Non-Interactive Git AskPass Helper**:
  - Injects `GIT_ASKPASS`, `GITHUB_TOKEN`, and `GH_TOKEN` into the script's environment.
  - When Git prompts for a username or password during `git push`, the AskPass helper automatically answers using your saved credentials—no terminal prompts or freezes!

- **🖥️ 100% Offline & Native Desktop (No Localhost / No Browser)**:
  - Built with Python 3 and native GTK3 (PyGObject).
  - Embedded real-time dark terminal console with line-by-line streaming output.
  - Stop/kill process button, output copy, clear console, and execution elapsed timer.

---

## 📦 Installation & Menu Integration

The package is already built as a standard `.deb` package:

```bash
# User-level installation (instant, no password required):
cd /home/sam/Projects/mint-script-runner
./install.sh

# System-wide installation via .deb:
sudo dpkg -i /home/sam/Projects/mint-script-runner/mint-script-runner_1.0.0_all.deb
```

Once installed, it appears in your Linux Mint Cinnamon Application Menu under **Projects** and **Administration**:
- **Application Menu** ➔ **Projects** ➔ **Mint Script Runner**
- Terminal command: `mint-script-runner` (or `script-runner`)

---

## 🛠️ Rebuilding the Package

To rebuild the `.deb` archive after modifications:

```bash
cd /home/sam/Projects/mint-script-runner
./build_deb.sh
```
