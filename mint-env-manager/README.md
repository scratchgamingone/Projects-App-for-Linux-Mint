# 🛡️ Mint Environment Manager (`mint-env-manager`)

A native GTK 3 desktop application for Linux Mint to view, add, modify, and verify system-wide environment variables (`/etc/environment` and `.env` files) with mandatory administrator privilege elevation and live API key validation.

![Mint Environment Manager](assets/mint-env-manager.png)

---

## 🌟 Key Features

1. **Mandatory Administrator Privilege Elevation**:
   - System-wide environment variables require root/admin permissions to read and edit.
   - When opened normally from the desktop menu or terminal, it automatically prompts for root credentials using native Linux Mint PolicyKit (`pkexec`).
   - If elevation is not granted or user cancels, the application refuses to open and displays an admin required warning.

2. **System-Wide & Custom `.env` File Support**:
   - Defaults directly to Linux Mint's system-wide `/etc/environment` configuration file.
   - Supports opening and editing any `.env` file across the system with a built-in file switcher.
   - Automatically preserves comments (`# ...`) and empty lines so existing configurations are never mangled.
   - Saves files atomically with standard `0644` permissions.
   - **Automatic Safety Backups**: Automatically creates a timestamped backup (e.g. `/etc/environment.bak.20261006_192000`) before modifying files.

3. **Add and Update Variables**:
   - Add both the variable name (e.g., `STEAM_API_KEY`, `Personal_Access_Token`, `OPENAI_API_KEY`) and secret key value.
   - Quick service presets dropdown to autofill common keys.
   - Secret masking (`••••••••`) with one-click eye toggle to reveal/hide keys.
   - Variable name validation against POSIX standards.
   - In-place updating of existing variables and row deletion (with safety confirmation for system `PATH`).

4. **Live API Key Verification Engine**:
   - Dedicated **"🧪 Test API Key"** button to verify that API keys and tokens are currently active and valid.
   - Tests run in asynchronous background threads so the UI never freezes.
   - Instant auto-detection of the provider based on variable name and key format.
   - Displays latency (in ms), HTTP status, authenticated username/account details, and diagnostics.
   - Directly updates the variable's status in the table (e.g. `🟢 Valid (Steam Web API)`, `🐙 Valid (@scratchgamingone)`).

---

## 🔑 Supported API Key Services

| Provider | Variable Name / Prefix | Verification Test |
|---|---|---|
| **Steam Web API** | `STEAM_API_KEY` (32 hex characters) | Tests `ISteamWebAPIUtil/GetServerInfo/v1` |
| **GitHub Token / PAT** | `Personal_Access_Token`, `GITHUB_TOKEN`, `ghp_*`, `github_pat_*` | Verifies `/user` endpoint, scopes & rate limit |
| **OpenAI** | `OPENAI_API_KEY`, `sk-*`, `sk-proj-*` | Queries `/v1/models` |
| **Google Gemini** | `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `AIzaSy*` | Queries `/v1beta/models` |
| **Anthropic Claude** | `ANTHROPIC_API_KEY`, `sk-ant-*` | Queries `/v1/models` |
| **Groq Cloud** | `GROQ_API_KEY`, `gsk_*` | Queries `/openai/v1/models` |
| **Real-Debrid** | `RD_API_KEY`, `REALDEBRID_API_KEY` | Checks `/rest/1.0/user` (user, premium status, expiry) |
| **Hugging Face** | `HF_TOKEN`, `HUGGINGFACE_API_KEY`, `hf_*` | Checks `/api/whoami-v2` |
| **Discord Webhook** | `DISCORD_WEBHOOK` (Webhook URL) | Checks webhook status without spamming channel |
| **TMDB** | `TMDB_API_KEY` | Tests `/3/authentication` |
| **WeatherAPI** | `WEATHERAPI_KEY` | Tests `/v1/current.json` |
| **Mistral AI** | `MISTRAL_API_KEY` | Tests `/v1/models` |
| **Cohere** | `COHERE_API_KEY` | Tests `/v1/check-api-key` |
| **Custom Endpoint** | User-defined URL | Custom HTTP GET/POST with Bearer or query key |

---

## 🚀 Installation & Launching

### Installation

From the project directory:

```bash
cd /home/sam/Documents/Projects-App-for-Linux-Mint-main/mint-env-manager
./install.sh
```

Or update all projects all at once using the unified manager:

```bash
install-or-update-all-projects
```

### Launching

- **Application Menu**: Linux Mint Cinnamon Menu -> **Projects** -> **Mint Environment Manager** (prompts for admin password via pkexec).
- **Terminal (as root)**:
  ```bash
  sudo mint-env-manager
  ```
- **Terminal (with pkexec elevation)**:
  ```bash
  mint-env-manager
  ```
- **Read-Only / Preview Mode**:
  ```bash
  mint-env-manager --preview
  ```

---

## 🔒 Security Architecture

- `main.py` explicitly verifies `os.geteuid() == 0`.
- If standard user, attempts `pkexec` graphical PolicyKit authorization while preserving `DISPLAY` and `XAUTHORITY`.
- All writes create a timestamped backup before touching `/etc/environment`.
- Atomic writes (`NamedTemporaryFile` + `os.replace`) ensure `/etc/environment` is never left in a corrupted or half-written state if interrupted.
