#!/usr/bin/env python3
"""
JellyScratch Server - Desktop Application
Embeds the Jellyfin Media Server web interface into a native desktop window,
automatically starts the Jellyfin server if not running, and runs the live
Discord Now-Playing playback monitor in the background.
"""

import os
import sys
import io
import time
import json
import logging
import socket
import threading
import subprocess
import urllib.parse
from pathlib import Path
from typing import Optional

try:
    import qrcode
except ImportError:
    qrcode = None

import requests
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, Gdk, GLib, WebKit2, Gio, GdkPixbuf

# Import our monitor daemon with comprehensive search paths
search_dirs = [
    Path(__file__).resolve().parent,
    Path("/opt/jellyscratchserver"),
    Path("/home/sam/jellyscratch-server-app"),
    Path("/home/sam/jellyfin-discord-bot"),
    Path.home() / ".local" / "bin"
]
for d in reversed(search_dirs):
    if d.exists() and str(d) not in sys.path:
        sys.path.insert(0, str(d))

from monitor import (
    MonitorDaemon,
    JellyfinClient,
    build_discord_embed,
    build_new_media_embed,
    build_sample_embed_for_type,
    build_new_movie_embed,
    DiscordWebhookClient,
    TICKS_PER_SECOND
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [JellyScratch] %(message)s"
)
logger = logging.getLogger("JellyScratchServer")

DEFAULT_JELLYFIN_URL = "http://localhost:8096"
CONFIG_DIR = Path.home() / ".config" / "jellyscratchserver"
CONFIG_FILE = CONFIG_DIR / "config.json"
COOKIES_FILE = CONFIG_DIR / "cookies.txt"


def ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        default_cfg = {
            "jellyfin_url": DEFAULT_JELLYFIN_URL,
            "jellyfin_api_key": "",
            "discord_webhook_url": "",
            "discord_webhook_all": "",
            "discord_new_media_webhook_url": "",
            "discord_webhook_movies": "",
            "discord_webhook_series": "",
            "discord_webhook_episodes": "",
            "discord_webhook_music": "",
            "discord_webhook_music_videos": "",
            "discord_webhook_videos": "",
            "update_interval_seconds": 30,
            "user_filter": None,
            "delete_on_stop": False,
            "include_poster": True,
            "notify_new_movies": True,
            "notify_new_media": True,
            "seerr_url": "http://localhost:5055",
            "seerr_host": "host.docker.internal",
            "seerr_port": "8096",
            "seerr_email": "",
            "seerr_username": "",
            "seerr_password": "",
            "seerr_autofill_enabled": True,
            "realdebrid_api_key": "",
            "stremio_stream_url": "https://web.stremio.com"
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_cfg, f, indent=2)


def get_config() -> dict:
    ensure_config_dir()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        defaults = {
            "seerr_url": "http://localhost:5055",
            "seerr_host": "host.docker.internal",
            "seerr_port": "8096",
            "seerr_email": "",
            "seerr_username": "",
            "seerr_password": "",
            "seerr_autofill_enabled": True,
            "realdebrid_api_key": "",
            "stremio_stream_url": "https://web.stremio.com"
        }
        changed = False
        for k, v in defaults.items():
            if k not in cfg:
                cfg[k] = v
                changed = True
        if changed:
            save_config(cfg)
        return cfg
    except Exception as e:
        logger.error(f"Error reading config: {e}")
        return {"jellyfin_url": DEFAULT_JELLYFIN_URL, "update_interval_seconds": 30, "seerr_autofill_enabled": True}


def save_config(cfg: dict):
    ensure_config_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def get_jellyfin_admin_username(server_url: str = DEFAULT_JELLYFIN_URL, api_key: str = "") -> str:
    """
    Query Jellyfin's /Users API to detect the administrator username.
    Falls back to 'legostarsets'.
    """
    if not api_key:
        cfg = get_config()
        api_key = cfg.get("jellyfin_api_key", "")
        server_url = cfg.get("jellyfin_url", server_url)

    if api_key:
        try:
            session = requests.Session()
            session.headers.update({
                "Authorization": f'MediaBrowser Client="JellyScratch", Device="Server", DeviceId="JellyScratchServer", Version="1.0.0", Token="{api_key}"',
                "X-Emby-Token": api_key,
                "Accept": "application/json"
            })
            resp = session.get(f"{server_url.rstrip('/')}/Users", timeout=2)
            if resp.status_code == 200:
                users = resp.json()
                for u in users:
                    if u.get("Policy", {}).get("IsAdministrator"):
                        return u.get("Name", "legostarsets")
                if users:
                    return users[0].get("Name", "legostarsets")
        except Exception as e:
            logger.debug(f"Could not query Jellyfin users: {e}")

    return "legostarsets"


def ensure_seerr_running() -> bool:
    """
    Check if Seerr is reachable at http://localhost:5055.
    If not, attempt to start it via docker compose in ~/seerr.
    """
    seerr_url = "http://localhost:5055"
    try:
        r = requests.get(seerr_url, timeout=1.5)
        if r.status_code < 500:
            return True
    except Exception:
        pass

    seerr_dirs = [
        Path("/home/sam/seerr"),
        Path.home() / "seerr"
    ]
    seerr_dir = next((d for d in seerr_dirs if (d / "docker-compose.yml").exists()), None)

    if seerr_dir:
        logger.info("Attempting to auto-start Seerr container via docker compose...")
        started = False
        try:
            res = subprocess.run(
                ["docker", "compose", "up", "-d"],
                cwd=str(seerr_dir),
                capture_output=True,
                text=True,
                timeout=15
            )
            if res.returncode == 0:
                started = True
        except Exception:
            pass

        if not started:
            try:
                res = subprocess.run(
                    ["sg", "docker", "-c", "docker compose up -d"],
                    cwd=str(seerr_dir),
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                if res.returncode == 0:
                    started = True
            except Exception:
                pass

        if started:
            for _ in range(15):
                time.sleep(1)
                try:
                    r = requests.get(seerr_url, timeout=1.0)
                    if r.status_code < 500:
                        logger.info("Seerr started successfully and responding!")
                        return True
                except Exception:
                    pass

    return False


def build_seerr_autofill_script(cfg: dict) -> str:
    """
    Build injected JavaScript that monitors Seerr setup/login forms and
    automatically fills in server host, port, email, username, syncs libraries,
    and focuses the password field for the user.
    """
    api_key = cfg.get("jellyfin_api_key", "")
    username = cfg.get("seerr_username") or get_jellyfin_admin_username(api_key=api_key)
    host = cfg.get("seerr_host") or "host.docker.internal"
    port = str(cfg.get("seerr_port") or "8096")
    email = cfg.get("seerr_email") or f"{username}@local"
    password = cfg.get("seerr_password") or ""

    cfg_json = json.dumps({
        "hostname": host,
        "port": port,
        "email": email,
        "username": username,
        "password": password
    })

    return f"""
(function() {{
    if (window.__jellyscratch_autofill_active) return;
    window.__jellyscratch_autofill_active = true;

    const jCfg = {cfg_json};

    function log(msg) {{
        console.log("[JellyScratch Seerr AutoFill] " + msg);
    }}

    function showBanner(text, autoDismissMs = 6000) {{
        let banner = document.getElementById("jellyscratch-autofill-banner");
        if (!banner) {{
            banner = document.createElement("div");
            banner.id = "jellyscratch-autofill-banner";
            banner.style.position = "fixed";
            banner.style.bottom = "20px";
            banner.style.right = "20px";
            banner.style.zIndex = "9999999";
            banner.style.backgroundColor = "rgba(17, 24, 39, 0.94)";
            banner.style.backdropFilter = "blur(6px)";
            banner.style.border = "1px solid #00a4dc";
            banner.style.borderRadius = "10px";
            banner.style.padding = "12px 18px";
            banner.style.color = "#ffffff";
            banner.style.fontSize = "13px";
            banner.style.boxShadow = "0 6px 20px rgba(0, 164, 220, 0.4)";
            banner.style.display = "flex";
            banner.style.alignItems = "center";
            banner.style.gap = "12px";
            banner.style.fontFamily = "system-ui, -apple-system, sans-serif";
            banner.style.transition = "opacity 0.3s ease, transform 0.3s ease";
            document.body.appendChild(banner);
        }}
        banner.style.opacity = "1";
        banner.style.transform = "translateY(0)";
        banner.innerHTML = `<span style="font-size:20px; line-height:1;">🚀</span> <div>${{text}}</div>`;
        if (window.__jellyscratch_banner_timer) clearTimeout(window.__jellyscratch_banner_timer);
        if (autoDismissMs > 0) {{
            window.__jellyscratch_banner_timer = setTimeout(() => {{
                if (banner) {{
                    banner.style.opacity = "0";
                    banner.style.transform = "translateY(10px)";
                }}
            }}, autoDismissMs);
        }}
    }}

    function setNativeValue(element, value) {{
        if (!element || element.value === value) return;
        const proto = Object.getPrototypeOf(element);
        const set = Object.getOwnPropertyDescriptor(proto, "value")?.set
                 || Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value")?.set;
        if (set) {{
            set.call(element, value);
        }} else {{
            element.value = value;
        }}
        element.dispatchEvent(new Event("input", {{ bubbles: true }}));
        element.dispatchEvent(new Event("change", {{ bubbles: true }}));
        element.dispatchEvent(new Event("blur", {{ bubbles: true }}));
    }}

    function runAutofill() {{
        const url = window.location.href;
        if (!url.includes(":5055")) return;
        const path = window.location.pathname;

        // 1. SETUP WIZARD: Step 1 (Choose Media Server)
        const buttons = Array.from(document.querySelectorAll("button"));
        const jellyfinBtn = buttons.find(b => b.innerText && b.innerText.trim() === "Configure Jellyfin");
        if (jellyfinBtn) {{
            log("Selecting Jellyfin server type on Step 1...");
            showBanner("<b>JellyScratch AutoFill:</b> Selecting Jellyfin Media Server...");
            jellyfinBtn.click();
            return;
        }}

        // 2. SETUP WIZARD: Step 2 (Jellyfin Connection & Sign In)
        const hostInput = document.getElementById("hostname");
        const portInput = document.getElementById("port");
        const emailInput = document.getElementById("email");
        const userInput = document.getElementById("username");
        const passInput = document.getElementById("password");

        if (hostInput || userInput || emailInput) {{
            if (hostInput && !hostInput.value) {{
                log("Autofilling hostname: " + jCfg.hostname);
                setNativeValue(hostInput, jCfg.hostname);
            }}
            if (portInput && (!portInput.value || portInput.value === "8096")) {{
                setNativeValue(portInput, jCfg.port);
            }}
            if (emailInput && !emailInput.value) {{
                log("Autofilling email: " + jCfg.email);
                setNativeValue(emailInput, jCfg.email);
            }}
            if (userInput && !userInput.value) {{
                log("Autofilling username: " + jCfg.username);
                setNativeValue(userInput, jCfg.username);
            }}
            if (passInput) {{
                if (jCfg.password) {{
                    if (!passInput.value) {{
                        setNativeValue(passInput, jCfg.password);
                        showBanner("<b>JellyScratch AutoFill:</b> All credentials filled! Click <b>Sign In</b>.");
                    }}
                }} else {{
                    if (!passInput.getAttribute("data-jellyscratch-autofilled")) {{
                        passInput.setAttribute("data-jellyscratch-autofilled", "true");
                        passInput.focus();
                        passInput.style.outline = "2px solid #00a4dc";
                        passInput.style.boxShadow = "0 0 10px rgba(0, 164, 220, 0.6)";
                        showBanner("<b>JellyScratch AutoFill:</b> Server info &amp; username <b>" + jCfg.username + "</b> filled!<br><small style='color:#38bdf8;'>👉 Enter your password to sign in.</small>");
                    }}
                }}
            }}
        }}

        // 3. SETUP WIZARD: Step 3 (Sync & Enable Libraries)
        const syncBtn = buttons.find(b => b.innerText && b.innerText.includes("Sync Libraries"));
        if (syncBtn && !syncBtn.disabled && !syncBtn.getAttribute("data-jellyscratch-synced")) {{
            syncBtn.setAttribute("data-jellyscratch-synced", "true");
            log("Triggering Sync Libraries...");
            showBanner("<b>JellyScratch AutoFill:</b> Syncing Jellyfin libraries...", 4000);
            syncBtn.click();
        }}

        const libSwitches = Array.from(document.querySelectorAll("button[role='switch']"));
        let enabledAny = false;
        libSwitches.forEach(btn => {{
            if (btn.getAttribute("aria-checked") === "false") {{
                btn.click();
                enabledAny = true;
            }}
        }});
        if (enabledAny) {{
            log("Auto-enabled libraries!");
            showBanner("<b>JellyScratch AutoFill:</b> Enabled all libraries! Ready to continue.", 4000);
        }}

        // 4. SETUP WIZARD: Step 4 (Configure Services -> Finish Setup)
        const finishBtn = buttons.find(b => b.innerText && b.innerText.includes("Finish Setup"));
        if (finishBtn && !finishBtn.disabled && !finishBtn.getAttribute("data-jellyscratch-finished")) {{
            finishBtn.setAttribute("data-jellyscratch-finished", "true");
            log("Clicking Finish Setup...");
            showBanner("<b>JellyScratch AutoFill:</b> Finalizing Seerr setup...", 5000);
            finishBtn.click();
        }}

        // 5. LOGIN PAGE: /login
        if (path === "/login" || path.startsWith("/login")) {{
            const jfLoginBtn = buttons.find(b => b.innerText && b.innerText.includes("Use your Jellyfin account"));
            if (jfLoginBtn && !document.getElementById("username") && !document.getElementById("email")) {{
                jfLoginBtn.click();
                return;
            }}

            const loginUser = document.getElementById("username") || document.getElementById("email") || document.querySelector("input[name='username']") || document.querySelector("input[name='email']");
            const loginPass = document.getElementById("password") || document.querySelector("input[name='password']");

            if (loginUser && !loginUser.value) {{
                setNativeValue(loginUser, jCfg.username);
            }}
            if (loginPass) {{
                if (jCfg.password && !loginPass.value) {{
                    setNativeValue(loginPass, jCfg.password);
                    showBanner("<b>JellyScratch AutoFill:</b> Credentials filled! Click <b>Sign In</b>.");
                }} else if (!loginPass.getAttribute("data-jellyscratch-autofilled")) {{
                    loginPass.setAttribute("data-jellyscratch-autofilled", "true");
                    loginPass.focus();
                    loginPass.style.outline = "2px solid #00a4dc";
                    showBanner("<b>JellyScratch AutoFill:</b> Username <b>" + jCfg.username + "</b> filled!<br><small style='color:#38bdf8;'>👉 Enter your password to sign in.</small>");
                }}
            }}
        }}
    }}

    setInterval(runAutofill, 400);
    runAutofill();
}})();
"""


def is_jellyfin_responding(url: str = DEFAULT_JELLYFIN_URL) -> bool:
    try:
        resp = requests.get(f"{url.rstrip('/')}/System/Info/Public", timeout=1.5)
        return resp.status_code == 200
    except Exception:
        return False


def ensure_jellyfin_ssl_configured() -> bool:
    """
    Ensure a self-signed PKCS12 certificate exists and Jellyfin network.xml
    has HTTPS enabled on port 8920.
    """
    config_dir = Path.home() / ".config" / "jellyfin"
    network_xml = config_dir / "network.xml"
    pfx_path = config_dir / "jellyfin.pfx"
    key_path = config_dir / "jellyfin.key"
    crt_path = config_dir / "jellyfin.crt"

    if not config_dir.exists():
        return False

    updated = False
    if not pfx_path.exists():
        try:
            subprocess.run([
                "openssl", "req", "-x509", "-newkey", "rsa:2048", "-keyout", str(key_path),
                "-out", str(crt_path), "-days", "730", "-nodes",
                "-subj", "/CN=JellyScratchServer",
                "-addext", "subjectAltName=IP:127.0.0.1,DNS:localhost"
            ], check=True, capture_output=True)
            subprocess.run([
                "openssl", "pkcs12", "-export", "-out", str(pfx_path),
                "-inkey", str(key_path), "-in", str(crt_path),
                "-passout", "pass:jellyscratch"
            ], check=True, capture_output=True)
            updated = True
            logger.info(f"Generated SSL certificate for Jellyfin: {pfx_path}")
        except Exception as e:
            logger.warning(f"Could not generate SSL cert: {e}")
            return False

    if network_xml.exists():
        try:
            with open(network_xml, "r", encoding="utf-8") as f:
                content = f.read()
            if "<EnableHttps>false</EnableHttps>" in content or "<CertificatePath />" in content:
                content = content.replace("<EnableHttps>false</EnableHttps>", "<EnableHttps>true</EnableHttps>")
                content = content.replace("<CertificatePath />", f"<CertificatePath>{pfx_path}</CertificatePath>")
                content = content.replace("<CertificatePassword />", "<CertificatePassword>jellyscratch</CertificatePassword>")
                with open(network_xml, "w", encoding="utf-8") as f:
                    f.write(content)
                updated = True
                logger.info("Configured Jellyfin network.xml for HTTPS on port 8920.")
        except Exception as e:
            logger.warning(f"Could not update network.xml: {e}")

    return updated


def get_server_network_addresses(server_url: str = DEFAULT_JELLYFIN_URL, scheme: str = "http") -> dict:
    """
    Detect local network IPs and server connection details for mobile and remote access.
    Uses port 8920 for HTTPS and port 8096 for HTTP.
    """
    parsed = urllib.parse.urlparse(server_url)
    if scheme == "https":
        port = 8920 if (not parsed.port or parsed.port == 8096) else parsed.port
    else:
        port = 8096 if (not parsed.port or parsed.port == 8920) else parsed.port
    base = server_url.rstrip("/")

    # Query public info from Jellyfin if online (always check local 8096 first)
    server_info = {}
    try:
        r = requests.get("http://localhost:8096/System/Info/Public", timeout=1.2)
        if r.status_code == 200:
            server_info = r.json()
    except Exception:
        try:
            r = requests.get(f"{base}/System/Info/Public", timeout=1.2, verify=False)
            if r.status_code == 200:
                server_info = r.json()
        except Exception:
            pass

    is_online = bool(server_info)
    server_name = server_info.get("ServerName", "Jellyfin Server")
    server_version = server_info.get("Version", "")

    # Gather local IP addresses
    discovered_ips = []

    # 1. Check Jellyfin public LocalAddress if non-loopback
    jelly_local = server_info.get("LocalAddress", "")
    if jelly_local:
        try:
            jp = urllib.parse.urlparse(jelly_local)
            if jp.hostname and jp.hostname not in ("localhost", "127.0.0.1", "0.0.0.0") and ":" not in jp.hostname:
                discovered_ips.append(jp.hostname)
        except Exception:
            pass

    # 2. Primary routable outbound IP (most reliable for LAN / Wi-Fi)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        primary = s.getsockname()[0]
        s.close()
        if primary and not primary.startswith("127.") and primary not in discovered_ips:
            discovered_ips.append(primary)
    except Exception:
        pass

    # 3. Hostname -I
    try:
        out = subprocess.check_output(["hostname", "-I"], text=True, timeout=1.5)
        for ip in out.strip().split():
            if ip and not ip.startswith("127.") and ":" not in ip and ip not in discovered_ips:
                discovered_ips.append(ip)
    except Exception:
        pass

    # 4. ip -4 addr
    try:
        out = subprocess.check_output(["ip", "-4", "-o", "addr", "show", "scope", "global"], text=True, timeout=1.5)
        for line in out.strip().splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[2] == "inet":
                ip = parts[3].split("/")[0]
                if ip and not ip.startswith("127.") and ip not in discovered_ips:
                    discovered_ips.append(ip)
    except Exception:
        pass

    # 5. Check if configured server_url uses an explicit host
    config_host = parsed.hostname
    if config_host and config_host not in ("localhost", "127.0.0.1", "0.0.0.0") and config_host not in discovered_ips:
        discovered_ips.insert(0, config_host)

    primary_ip = discovered_ips[0] if discovered_ips else "localhost"
    primary_mobile_url = f"{scheme}://{primary_ip}:{port}"

    addresses = []
    for idx, ip in enumerate(discovered_ips):
        addresses.append({
            "label": f"Local Wi-Fi (HTTP - Port 8096, Recommended)",
            "ip": ip,
            "url": f"http://{ip}:8096",
            "is_primary": (scheme == "http" and idx == 0)
        })
        addresses.append({
            "label": f"Local Wi-Fi (HTTPS - Port 8920, SSL Encrypted)",
            "ip": ip,
            "url": f"https://{ip}:8920",
            "is_primary": (scheme == "https" and idx == 0)
        })

    addresses.append({
        "label": "Localhost (HTTP - Port 8096)",
        "ip": "localhost",
        "url": "http://localhost:8096",
        "is_primary": False
    })
    addresses.append({
        "label": "Localhost (HTTPS - Port 8920)",
        "ip": "localhost",
        "url": "https://localhost:8920",
        "is_primary": False
    })

    return {
        "online": is_online,
        "server_name": server_name,
        "server_version": server_version,
        "port": port,
        "scheme": scheme,
        "primary_ip": primary_ip,
        "primary_mobile_url": primary_mobile_url,
        "addresses": addresses
    }


def is_jellyfin_installed() -> bool:
    import shutil
    return shutil.which("jellyfin") is not None


def install_jellyfin_gui():
    logger.info("Triggering pkexec apt-get install -y jellyfin...")
    try:
        subprocess.Popen(["pkexec", "apt-get", "install", "-y", "jellyfin"])
    except Exception as e:
        logger.error(f"Failed to launch pkexec: {e}")


USER_SERVICE_PATH = Path.home() / ".config" / "systemd" / "user" / "jellyfin.service"


def is_system_config_corrupted() -> bool:
    """Check if /etc/jellyfin/logging.default.json is an empty corrupted file causing crashes."""
    bad_file = Path("/etc/jellyfin/logging.default.json")
    try:
        return bad_file.exists() and bad_file.stat().st_size == 0
    except Exception:
        return False


def repair_system_service_gui(on_done=None):
    """
    Repair corrupted /etc/jellyfin/logging.default.json via pkexec.
    Runs once with explicit user initiation, removing the corrupted 0-byte file
    and restarting the Jellyfin service.
    """
    logger.info("Triggering pkexec repair for corrupted /etc/jellyfin/logging.default.json...")
    try:
        repair_cmd = (
            "rm -f /etc/jellyfin/logging.default.json && "
            "systemctl daemon-reload && "
            "systemctl restart jellyfin"
        )
        proc = subprocess.Popen(["pkexec", "bash", "-c", repair_cmd])
        if on_done:
            def wait_repair():
                proc.wait()
                GLib.idle_add(on_done)
            threading.Thread(target=wait_repair, daemon=True).start()
        return True
    except Exception as e:
        logger.error(f"Failed to launch pkexec repair: {e}")
        return False


def ensure_user_jellyfin_service():
    """Ensure a user-level systemd service exists so Jellyfin can run without root or PIN prompts."""
    try:
        if not USER_SERVICE_PATH.exists():
            USER_SERVICE_PATH.parent.mkdir(parents=True, exist_ok=True)
            unit_content = """[Unit]
Description=Jellyfin Media Server (User Service)
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/jellyfin --datadir %h/.local/share/jellyfin --configdir %h/.config/jellyfin --logdir %h/.local/share/jellyfin/log --cachedir %h/.cache/jellyfin --webdir /usr/share/jellyfin/web --ffmpeg /usr/lib/jellyfin-ffmpeg/ffmpeg
Restart=on-failure
RestartSec=5
TimeoutSec=15

[Install]
WantedBy=default.target
"""
            with open(USER_SERVICE_PATH, "w", encoding="utf-8") as f:
                f.write(unit_content)
            subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True, timeout=5)
            subprocess.run(["systemctl", "--user", "enable", "jellyfin"], capture_output=True, timeout=5)
            logger.info("Created and enabled user systemd service for Jellyfin.")
    except Exception as e:
        logger.warning(f"Could not setup user systemd service: {e}")


def start_user_jellyfin_direct():
    """Launch Jellyfin directly in user mode as background process (zero-auth fallback)."""
    try:
        user_datadir = Path.home() / ".local" / "share" / "jellyfin"
        user_configdir = Path.home() / ".config" / "jellyfin"
        user_cachedir = Path.home() / ".cache" / "jellyfin"
        user_logdir = user_datadir / "log"
        for p in [user_datadir, user_configdir, user_cachedir, user_logdir]:
            p.mkdir(parents=True, exist_ok=True)

        cmd = [
            "jellyfin",
            "--datadir", str(user_datadir),
            "--configdir", str(user_configdir),
            "--logdir", str(user_logdir),
            "--cachedir", str(user_cachedir),
            "--webdir", "/usr/share/jellyfin/web",
            "--ffmpeg", "/usr/lib/jellyfin-ffmpeg/ffmpeg"
        ]
        logger.info("Spawning Jellyfin direct user process...")
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        return True
    except Exception as e:
        logger.error(f"Failed to start direct user Jellyfin process: {e}")
        return False


def try_start_jellyfin_service():
    """
    Attempt to start Jellyfin service without triggering an authentication loop.
    Prioritizes user-level systemd service and direct user process so NO root/PIN is required.
    """
    if is_jellyfin_responding():
        return True

    logger.info("Attempting to start Jellyfin service (zero-auth user mode)...")

    # 1. Ensure user-level systemd service exists and is enabled
    ensure_user_jellyfin_service()

    # 2. Try starting user-level systemd service (Zero auth, zero root, zero PIN)
    try:
        res = subprocess.run(["systemctl", "--user", "start", "jellyfin"], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            logger.info("Jellyfin service started via user systemd service.")
            return True
    except Exception as e:
        logger.debug(f"User systemd service start failed: {e}")

    # 3. Try starting systemctl with --no-ask-password to ensure NO GUI prompt pops up
    try:
        res = subprocess.run(["systemctl", "start", "--no-ask-password", "jellyfin"], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            logger.info("Jellyfin service started via systemctl (non-interactive).")
            return True
    except Exception as e:
        logger.debug(f"Direct systemctl start failed: {e}")

    # 4. Fallback: Launch Jellyfin directly in user mode (guaranteed zero PIN)
    return start_user_jellyfin_direct()


class DiscordSettingsDialog(Gtk.Dialog):
    def __init__(self, parent, on_saved_callback):
        super().__init__(title="Server & Integration Settings", transient_for=parent, flags=0)
        self.set_modal(True)
        self.set_default_size(680, 660)
        self.on_saved_callback = on_saved_callback
        self.config = get_config()

        # Dialog buttons
        self.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        btn_save = self.add_button(Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        btn_save.get_style_context().add_class("suggested-action")

        content_area = self.get_content_area()
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        content_area.pack_start(scrolled, True, True, 0)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        main_box.set_margin_top(14)
        main_box.set_margin_bottom(14)
        main_box.set_margin_left(18)
        main_box.set_margin_right(18)
        scrolled.add(main_box)

        # Header
        header_lbl = Gtk.Label()
        header_lbl.set_markup("<b>JellyScratch Server &amp; Integration Settings</b>\n"
                              "<small>Manage server connection, Discord Webhooks, and Cloud Debrid streaming APIs.</small>")
        header_lbl.set_alignment(0, 0.5)
        main_box.pack_start(header_lbl, False, False, 0)

        # 1. Jellyfin Server Settings
        sec1_lbl = Gtk.Label()
        sec1_lbl.set_markup("<b>🔑 Jellyfin Server Connection</b>")
        sec1_lbl.set_alignment(0, 0.5)
        main_box.pack_start(sec1_lbl, False, False, 0)

        grid1 = Gtk.Grid()
        grid1.set_column_spacing(12)
        grid1.set_row_spacing(8)
        grid1.set_margin_left(10)
        main_box.pack_start(grid1, False, False, 0)

        lbl_key = Gtk.Label(label="Jellyfin API Key:")
        lbl_key.set_alignment(0, 0.5)
        grid1.attach(lbl_key, 0, 0, 1, 1)

        self.entry_key = Gtk.Entry()
        self.entry_key.set_hexpand(True)
        self.entry_key.set_placeholder_text("From Jellyfin: Dashboard -> API Keys -> +")
        self.entry_key.set_text(self.config.get("jellyfin_api_key", ""))
        grid1.attach(self.entry_key, 1, 0, 1, 1)

        lbl_interval = Gtk.Label(label="Check Rate (sec):")
        lbl_interval.set_alignment(0, 0.5)
        grid1.attach(lbl_interval, 0, 1, 1, 1)

        self.spin_interval = Gtk.SpinButton.new_with_range(10, 300, 5)
        self.spin_interval.set_value(float(self.config.get("update_interval_seconds", 30)))
        grid1.attach(self.spin_interval, 1, 1, 1, 1)

        main_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 4)

        # 2. Live Playback Status Webhook (Now Playing)
        sec2_lbl = Gtk.Label()
        sec2_lbl.set_markup("<b>🎬 Live Playback Webhook (Now-Playing Channel)</b>\n"
                              "<small>Updates your Discord channel every 30s with progress bar, specs &amp; time left.</small>")
        sec2_lbl.set_alignment(0, 0.5)
        main_box.pack_start(sec2_lbl, False, False, 0)

        grid2 = Gtk.Grid()
        grid2.set_column_spacing(12)
        grid2.set_row_spacing(8)
        grid2.set_margin_left(10)
        main_box.pack_start(grid2, False, False, 0)

        lbl_wh = Gtk.Label(label="Playback Webhook:")
        lbl_wh.set_alignment(0, 0.5)
        grid2.attach(lbl_wh, 0, 0, 1, 1)

        self.entry_wh = Gtk.Entry()
        self.entry_wh.set_hexpand(True)
        self.entry_wh.set_placeholder_text("https://discord.com/api/webhooks/...")
        self.entry_wh.set_text(self.config.get("discord_webhook_url", ""))
        grid2.attach(self.entry_wh, 1, 0, 1, 1)

        test_box1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        test_box1.set_margin_left(10)
        self.btn_test = Gtk.Button(label="Test Playback Card")
        self.btn_test.connect("clicked", self.on_test_clicked)
        test_box1.pack_start(self.btn_test, False, False, 0)

        self.lbl_test_status = Gtk.Label(label="")
        self.lbl_test_status.set_alignment(0, 0.5)
        test_box1.pack_start(self.lbl_test_status, True, True, 0)
        main_box.pack_start(test_box1, False, False, 0)

        main_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 4)

        # 3. New Media Added Webhooks (7 Dedicated Webhooks for Content Types)
        sec3_lbl = Gtk.Label()
        sec3_lbl.set_markup("<b>📢 New Media Upload Webhooks (7 Channels / Content Types)</b>\n"
                              "<small>Automatically announce newly scanned/uploaded content across dedicated Discord channels.</small>")
        sec3_lbl.set_alignment(0, 0.5)
        main_box.pack_start(sec3_lbl, False, False, 0)

        grid3 = Gtk.Grid()
        grid3.set_column_spacing(10)
        grid3.set_row_spacing(8)
        grid3.set_margin_left(10)
        main_box.pack_start(grid3, False, False, 0)

        self.upload_webhook_defs = [
            ("all", "🌐 All Content Types:", "discord_webhook_all", "discord_new_media_webhook_url"),
            ("Movie", "🎬 Movies:", "discord_webhook_movies", None),
            ("Series", "📺 TV Shows / Series:", "discord_webhook_series", "discord_webhook_shows"),
            ("Episode", "🎞️ TV Episodes:", "discord_webhook_episodes", None),
            ("Audio", "🎵 Music / Songs:", "discord_webhook_music", "discord_webhook_audio"),
            ("MusicVideo", "🎸 Music Videos:", "discord_webhook_music_videos", None),
            ("Video", "📹 Videos (Clips/Home):", "discord_webhook_videos", None),
        ]
        self.upload_entries = {}
        self.upload_test_btns = {}

        for row_idx, (type_key, label_text, cfg_key, alt_key) in enumerate(self.upload_webhook_defs):
            lbl = Gtk.Label(label=label_text)
            lbl.set_alignment(0, 0.5)
            grid3.attach(lbl, 0, row_idx, 1, 1)

            entry = Gtk.Entry()
            entry.set_hexpand(True)
            entry.set_placeholder_text("https://discord.com/api/webhooks/...")
            val = self.config.get(cfg_key, "")
            if not val and alt_key:
                val = self.config.get(alt_key, "")
            entry.set_text(val)
            grid3.attach(entry, 1, row_idx, 1, 1)
            self.upload_entries[cfg_key] = entry

            btn_test = Gtk.Button(label="Test")
            btn_test.connect("clicked", self.on_test_upload_type_clicked, type_key, entry, label_text)
            grid3.attach(btn_test, 2, row_idx, 1, 1)
            self.upload_test_btns[type_key] = btn_test

        # Backward compatibility aliases
        self.entry_new_media_wh = self.upload_entries["discord_webhook_all"]
        self.btn_test_new_media = self.upload_test_btns["all"]

        self.check_notify_new_media = Gtk.CheckButton(label="Announce when new media is uploaded across configured Discord webhooks")
        self.check_notify_new_media.set_active(self.config.get("notify_new_media", self.config.get("notify_new_movies", True)))
        self.check_notify_new_media.set_margin_left(10)
        main_box.pack_start(self.check_notify_new_media, False, False, 0)

        test_box2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        test_box2.set_margin_left(10)
        self.lbl_test_new_media_status = Gtk.Label(label="")
        self.lbl_test_new_media_status.set_alignment(0, 0.5)
        test_box2.pack_start(self.lbl_test_new_media_status, True, True, 0)
        main_box.pack_start(test_box2, False, False, 0)

        main_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 4)

        # 4. Manual Library Scan Trigger
        sec4_lbl = Gtk.Label()
        sec4_lbl.set_markup("<b>🔄 Library Scan &amp; Webhook Sync</b>\n"
                              "<small>Trigger an immediate Jellyfin library scan to index new files and send webhooks.</small>")
        sec4_lbl.set_alignment(0, 0.5)
        main_box.pack_start(sec4_lbl, False, False, 0)

        scan_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        scan_box.set_margin_left(10)
        self.btn_dialog_scan = Gtk.Button(label="Scan All Libraries Now")
        self.btn_dialog_scan.connect("clicked", self.on_dialog_scan_clicked)
        scan_box.pack_start(self.btn_dialog_scan, False, False, 0)

        self.lbl_dialog_scan_status = Gtk.Label(label="")
        self.lbl_dialog_scan_status.set_alignment(0, 0.5)
        scan_box.pack_start(self.lbl_dialog_scan_status, True, True, 0)
        main_box.pack_start(scan_box, False, False, 0)

        main_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 4)

        # 5. Seerr / Media Requests Auto-Fill
        sec5_lbl = Gtk.Label()
        sec5_lbl.set_markup("<b>📥 Seerr / Media Requests Auto-Fill</b>\n"
                              "<small>Automatically fills server details, username and libraries in Seerr Request tab.</small>")
        sec5_lbl.set_alignment(0, 0.5)
        main_box.pack_start(sec5_lbl, False, False, 0)

        grid5 = Gtk.Grid()
        grid5.set_column_spacing(10)
        grid5.set_row_spacing(8)
        grid5.set_margin_left(10)
        main_box.pack_start(grid5, False, False, 0)

        self.check_seerr_autofill = Gtk.CheckButton(label="Enable automatic setup & login fill for Seerr")
        self.check_seerr_autofill.set_active(self.config.get("seerr_autofill_enabled", True))
        grid5.attach(self.check_seerr_autofill, 0, 0, 3, 1)

        lbl_s_user = Gtk.Label(label="Admin Username:")
        lbl_s_user.set_alignment(0, 0.5)
        grid5.attach(lbl_s_user, 0, 1, 1, 1)

        self.entry_seerr_user = Gtk.Entry()
        self.entry_seerr_user.set_hexpand(True)
        detected_user = self.config.get("seerr_username") or get_jellyfin_admin_username(api_key=self.config.get("jellyfin_api_key", ""))
        self.entry_seerr_user.set_text(detected_user)
        grid5.attach(self.entry_seerr_user, 1, 1, 1, 1)

        btn_detect_user = Gtk.Button(label="Auto-Detect")
        btn_detect_user.connect("clicked", lambda b: self.entry_seerr_user.set_text(get_jellyfin_admin_username(api_key=self.entry_key.get_text().strip())))
        grid5.attach(btn_detect_user, 2, 1, 1, 1)

        lbl_s_pass = Gtk.Label(label="Password (Optional):")
        lbl_s_pass.set_alignment(0, 0.5)
        grid5.attach(lbl_s_pass, 0, 2, 1, 1)

        self.entry_seerr_pass = Gtk.Entry()
        self.entry_seerr_pass.set_hexpand(True)
        self.entry_seerr_pass.set_visibility(False)
        self.entry_seerr_pass.set_placeholder_text("Leave blank to enter manually during setup")
        self.entry_seerr_pass.set_text(self.config.get("seerr_password", ""))
        grid5.attach(self.entry_seerr_pass, 1, 2, 2, 1)

        main_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 4)

        # 6. Debrid Cloud & Stremio APIs (Zero Local Storage)
        sec6_lbl = Gtk.Label()
        sec6_lbl.set_markup("<b>☁️ Debrid Cloud &amp; Stremio APIs (Zero Local Storage)</b>\n"
                              "<small>Input your Real-Debrid API key to stream directly from cloud without using hard drive space.</small>")
        sec6_lbl.set_alignment(0, 0.5)
        main_box.pack_start(sec6_lbl, False, False, 0)

        grid6 = Gtk.Grid()
        grid6.set_column_spacing(10)
        grid6.set_row_spacing(8)
        grid6.set_margin_left(10)
        main_box.pack_start(grid6, False, False, 0)

        lbl_rd = Gtk.Label(label="Real-Debrid API Key:")
        lbl_rd.set_alignment(0, 0.5)
        grid6.attach(lbl_rd, 0, 0, 1, 1)

        self.entry_rd = Gtk.Entry()
        self.entry_rd.set_hexpand(True)
        self.entry_rd.set_visibility(False)
        self.entry_rd.set_placeholder_text("From real-debrid.com/apitoken")
        self.entry_rd.set_text(self.config.get("realdebrid_api_key", ""))
        grid6.attach(self.entry_rd, 1, 0, 1, 1)

        self.btn_verify_rd = Gtk.Button(label="Verify Key")
        self.btn_verify_rd.connect("clicked", self.on_verify_rd_clicked)
        grid6.attach(self.btn_verify_rd, 2, 0, 1, 1)

        debrid_action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        debrid_action_box.set_margin_left(10)

        self.btn_test_debrid_discord = Gtk.Button(label="🔔 Send Debrid Test to Discord")
        self.btn_test_debrid_discord.set_tooltip_text("Sends a rich embed test card with your Cloud Debrid status to your Discord Webhook")
        self.btn_test_debrid_discord.connect("clicked", self.on_test_debrid_discord_clicked)
        debrid_action_box.pack_start(self.btn_test_debrid_discord, False, False, 0)

        self.btn_open_torrentio = Gtk.Button(label="🚀 Configure Stremio Add-on")
        self.btn_open_torrentio.set_tooltip_text("Open Torrentio add-on pre-configured with this Real-Debrid key")
        self.btn_open_torrentio.connect("clicked", self.on_open_torrentio_clicked)
        debrid_action_box.pack_start(self.btn_open_torrentio, False, False, 0)

        main_box.pack_start(debrid_action_box, False, False, 0)

        self.lbl_debrid_status = Gtk.Label(label="")
        self.lbl_debrid_status.set_alignment(0, 0.5)
        self.lbl_debrid_status.set_margin_left(10)
        main_box.pack_start(self.lbl_debrid_status, False, False, 0)

        self.show_all()

    def on_dialog_scan_clicked(self, widget):
        api_key = self.entry_key.get_text().strip()
        url = self.config.get("jellyfin_url", DEFAULT_JELLYFIN_URL)
        if not api_key:
            self.lbl_dialog_scan_status.set_markup("<span color='#e74c3c'>Please enter a Jellyfin API Key above first.</span>")
            return

        self.btn_dialog_scan.set_sensitive(False)
        self.lbl_dialog_scan_status.set_markup("<span>Triggering library scan...</span>")

        def run_scan():
            try:
                client = JellyfinClient(url, api_key)
                ok = client.trigger_library_scan()
                if ok:
                    GLib.idle_add(lambda: self.lbl_dialog_scan_status.set_markup("<span color='#2ecc71'>✔ Library scan started! Webhooks will send as items are found.</span>"))
                else:
                    GLib.idle_add(lambda: self.lbl_dialog_scan_status.set_markup("<span color='#e74c3c'>Could not start scan. Check API key.</span>"))
            except Exception as e:
                GLib.idle_add(lambda: self.lbl_dialog_scan_status.set_markup(f"<span color='#e74c3c'>Error: {str(e)[:40]}</span>"))
            finally:
                GLib.idle_add(lambda: self.btn_dialog_scan.set_sensitive(True))

        threading.Thread(target=run_scan, daemon=True).start()

    def on_test_clicked(self, widget):
        webhook_url = self.entry_wh.get_text().strip()
        if not webhook_url or not webhook_url.startswith("http"):
            self.lbl_test_status.set_markup("<span color='#e74c3c'>Please enter a valid Webhook URL.</span>")
            return

        self.lbl_test_status.set_markup("<span>Sending test playback card to Discord...</span>")
        self.btn_test.set_sensitive(False)

        def run_test():
            try:
                client = DiscordWebhookClient(webhook_url)
                test_embed = {
                    "title": "🎬 JellyScratch Server Connected!",
                    "description": "Your Discord webhook is configured and ready to receive live movie stats every 30 seconds!",
                    "color": 0x00A4DC,
                    "fields": [
                        {"name": "Status", "value": "🟢 Playback Webhook Verified", "inline": True},
                        {"name": "Update Rate", "value": "Every 30 seconds", "inline": True}
                    ],
                    "footer": {"text": "JellyScratch Live Monitor"}
                }
                msg_id, _ = client.post_initial(test_embed)
                if msg_id:
                    GLib.idle_add(lambda: self.lbl_test_status.set_markup("<span color='#2ecc71'>✔ Test sent successfully to Discord!</span>"))
                else:
                    GLib.idle_add(lambda: self.lbl_test_status.set_markup("<span color='#e74c3c'>Failed to post. Check URL.</span>"))
            except Exception as e:
                GLib.idle_add(lambda: self.lbl_test_status.set_markup(f"<span color='#e74c3c'>Error: {str(e)[:40]}</span>"))
            finally:
                GLib.idle_add(lambda: self.btn_test.set_sensitive(True))

        threading.Thread(target=run_test, daemon=True).start()

    def on_test_upload_type_clicked(self, widget, type_key: str, entry: Gtk.Entry, label_text: str):
        webhook_url = entry.get_text().strip()
        clean_name = label_text.replace(":", "").strip()
        if not webhook_url or not webhook_url.startswith("http"):
            self.lbl_test_new_media_status.set_markup(f"<span color='#e74c3c'>Please enter a valid Webhook URL for {clean_name}.</span>")
            return

        self.lbl_test_new_media_status.set_markup(f"<span>Sending sample {clean_name} card to Discord...</span>")
        widget.set_sensitive(False)

        def run_test():
            try:
                client = DiscordWebhookClient(webhook_url)
                embed = build_sample_embed_for_type(type_key, self.config.get("jellyfin_url", DEFAULT_JELLYFIN_URL))
                msg_id, _ = client.post_initial(embed)
                if msg_id:
                    GLib.idle_add(lambda: self.lbl_test_new_media_status.set_markup(f"<span color='#2ecc71'>✔ Test {clean_name} announcement sent to Discord!</span>"))
                else:
                    GLib.idle_add(lambda: self.lbl_test_new_media_status.set_markup(f"<span color='#e74c3c'>Failed to post to {clean_name} webhook. Check URL.</span>"))
            except Exception as e:
                GLib.idle_add(lambda: self.lbl_test_new_media_status.set_markup(f"<span color='#e74c3c'>Error ({clean_name}): {str(e)[:40]}</span>"))
            finally:
                GLib.idle_add(lambda: widget.set_sensitive(True))

        threading.Thread(target=run_test, daemon=True).start()

    def on_test_new_media_clicked(self, widget):
        self.on_test_upload_type_clicked(widget, "all", self.upload_entries["discord_webhook_all"], "All Content Types")

    def on_verify_rd_clicked(self, widget):
        key = self.entry_rd.get_text().strip()
        if not key:
            self.lbl_debrid_status.set_markup("<span color='#e74c3c'>Please enter a Real-Debrid API Key first.</span>")
            return

        self.lbl_debrid_status.set_markup("<span>Connecting to Real-Debrid API...</span>")
        widget.set_sensitive(False)

        def run_verify():
            try:
                r = requests.get("https://api.real-debrid.com/rest/1.0/user", headers={"Authorization": f"Bearer {key}"}, timeout=8)
                if r.status_code == 200:
                    data = r.json()
                    user = data.get("username", "Unknown")
                    ptype = data.get("type", "Free")
                    exp = data.get("expiration", "N/A")
                    GLib.idle_add(lambda: self.lbl_debrid_status.set_markup(f"<span color='#2ecc71'>✔ Real-Debrid Account: <b>{user}</b> ({ptype.title()}, expires: {exp})</span>"))
                else:
                    GLib.idle_add(lambda: self.lbl_debrid_status.set_markup(f"<span color='#e74c3c'>Invalid API Key (HTTP {r.status_code})</span>"))
            except Exception as e:
                GLib.idle_add(lambda: self.lbl_debrid_status.set_markup(f"<span color='#e74c3c'>Connection error: {str(e)[:40]}</span>"))
            finally:
                GLib.idle_add(lambda: widget.set_sensitive(True))

        threading.Thread(target=run_verify, daemon=True).start()

    def on_test_debrid_discord_clicked(self, widget):
        webhook_url = self.entry_wh.get_text().strip()
        if not webhook_url and "discord_webhook_all" in self.upload_entries:
            webhook_url = self.upload_entries["discord_webhook_all"].get_text().strip()

        if not webhook_url or not webhook_url.startswith("http"):
            self.lbl_debrid_status.set_markup("<span color='#e74c3c'>Please enter a Discord Webhook URL above first.</span>")
            return

        rd_key = self.entry_rd.get_text().strip()
        self.lbl_debrid_status.set_markup("<span>Sending Cloud Debrid test embed to Discord...</span>")
        widget.set_sensitive(False)

        def run_test():
            try:
                rd_status_text = "⚪ Key not provided"
                if rd_key:
                    try:
                        r = requests.get("https://api.real-debrid.com/rest/1.0/user", headers={"Authorization": f"Bearer {rd_key}"}, timeout=5)
                        if r.status_code == 200:
                            u = r.json()
                            rd_status_text = f"🟢 Connected ({u.get('username')}, {u.get('type')})"
                        else:
                            rd_status_text = f"🔴 Invalid Key (HTTP {r.status_code})"
                    except Exception:
                        rd_status_text = "🟡 Unreachable"

                embed = {
                    "title": "☁️ JellyScratch Cloud Streaming Verified",
                    "description": "Zero-Storage Real-Debrid cloud integration is connected to your Discord Webhook.",
                    "color": 0x38BDF8,
                    "fields": [
                        {"name": "Discord Webhook", "value": "🟢 Active & Responding", "inline": True},
                        {"name": "Real-Debrid API", "value": rd_status_text, "inline": True},
                        {"name": "Streaming Engine", "value": "Stremio + Real-Debrid Cloud (0 GB Storage)", "inline": False}
                    ],
                    "footer": {"text": "JellyScratch Cloud Debrid Manager"}
                }

                client = DiscordWebhookClient(webhook_url)
                msg_id, _ = client.post_initial(embed)
                if msg_id:
                    GLib.idle_add(lambda: self.lbl_debrid_status.set_markup("<span color='#2ecc71'>✔ Test response sent to Discord! Check your Discord channel.</span>"))
                else:
                    GLib.idle_add(lambda: self.lbl_debrid_status.set_markup("<span color='#e74c3c'>Failed to post to Discord. Check webhook URL.</span>"))
            except Exception as e:
                GLib.idle_add(lambda: self.lbl_debrid_status.set_markup(f"<span color='#e74c3c'>Discord error: {str(e)[:40]}</span>"))
            finally:
                GLib.idle_add(lambda: widget.set_sensitive(True))

        threading.Thread(target=run_test, daemon=True).start()

    def on_open_torrentio_clicked(self, widget):
        rd_key = self.entry_rd.get_text().strip()
        url = "https://torrentio.strem.fun/configure"
        if rd_key:
            url += f"#realdebrid={urllib.parse.quote(rd_key)}"
        try:
            Gio.AppInfo.launch_default_for_uri(url, None)
            self.lbl_debrid_status.set_markup("<span color='#2ecc71'>✔ Opened Torrentio add-on configuration in browser!</span>")
        except Exception:
            subprocess.Popen(["xdg-open", url])

    def apply_save(self):
        self.config["discord_webhook_url"] = self.entry_wh.get_text().strip()

        # Save all 7 upload webhooks
        all_wh = self.upload_entries["discord_webhook_all"].get_text().strip()
        self.config["discord_webhook_all"] = all_wh
        self.config["discord_new_media_webhook_url"] = all_wh  # sync alias

        self.config["discord_webhook_movies"] = self.upload_entries["discord_webhook_movies"].get_text().strip()
        self.config["discord_webhook_series"] = self.upload_entries["discord_webhook_series"].get_text().strip()
        self.config["discord_webhook_episodes"] = self.upload_entries["discord_webhook_episodes"].get_text().strip()
        self.config["discord_webhook_music"] = self.upload_entries["discord_webhook_music"].get_text().strip()
        self.config["discord_webhook_music_videos"] = self.upload_entries["discord_webhook_music_videos"].get_text().strip()
        self.config["discord_webhook_videos"] = self.upload_entries["discord_webhook_videos"].get_text().strip()

        self.config["jellyfin_api_key"] = self.entry_key.get_text().strip()
        self.config["update_interval_seconds"] = int(self.spin_interval.get_value())
        self.config["notify_new_movies"] = self.check_notify_new_media.get_active()
        self.config["notify_new_media"] = self.check_notify_new_media.get_active()

        # Save Seerr Auto-Fill settings
        self.config["seerr_autofill_enabled"] = self.check_seerr_autofill.get_active()
        self.config["seerr_username"] = self.entry_seerr_user.get_text().strip()
        self.config["seerr_password"] = self.entry_seerr_pass.get_text()

        # Save Real-Debrid API Key
        rd_key = self.entry_rd.get_text().strip()
        self.config["realdebrid_api_key"] = rd_key

        # Sync ~/.stremio_debrid_config.json
        try:
            stremio_cfg_path = Path.home() / ".stremio_debrid_config.json"
            stremio_data = {"rd_api_key": rd_key, "discord_webhook": self.config.get("discord_webhook_url", "")}
            with open(stremio_cfg_path, "w", encoding="utf-8") as sf:
                json.dump(stremio_data, sf, indent=2)
        except Exception:
            pass

        save_config(self.config)
        if self.on_saved_callback:
            self.on_saved_callback()


class ServerConnectionDialog(Gtk.Dialog):
    """
    Modal dialog displaying the local network server link, QR code,
    and instructions for connecting the Jellyfin Mobile App.
    """
    def __init__(self, parent, server_url: str = DEFAULT_JELLYFIN_URL, on_start_server=None, default_scheme: str = "http"):
        super().__init__(title="Jellyfin Server Connection - Mobile App", transient_for=parent, flags=0)
        self.set_modal(True)
        self.set_default_size(620, 600)
        self.server_url = server_url
        self.on_start_server = on_start_server
        self.scheme = default_scheme
        self.info = get_server_network_addresses(self.server_url, scheme=self.scheme)

        self.add_button("Close", Gtk.ResponseType.CLOSE)

        content_area = self.get_content_area()
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        content_area.pack_start(scrolled, True, True, 0)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.main_box.set_margin_top(16)
        self.main_box.set_margin_bottom(16)
        self.main_box.set_margin_start(20)
        self.main_box.set_margin_end(20)
        scrolled.add(self.main_box)

        # 1. Header & Server Status
        self.header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.lbl_status = Gtk.Label()
        self.lbl_status.set_xalign(0.0)
        self._update_status_header()
        self.header_box.pack_start(self.lbl_status, False, False, 0)

        self.btn_start = Gtk.Button(label="▶ Start Jellyfin Server Now")
        self.btn_start.get_style_context().add_class("suggested-action")
        self.btn_start.connect("clicked", self._on_start_clicked)
        self.btn_start.set_no_show_all(True)
        if not self.info["online"]:
            self.btn_start.show()
        self.header_box.pack_start(self.btn_start, False, False, 6)

        self.main_box.pack_start(self.header_box, False, False, 0)
        self.main_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 2)

        # 2. Primary Mobile App Link Section Header with Protocol Toggle
        sec_header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        sec_title = Gtk.Label()
        sec_title.set_markup(
            "<b>📱 Jellyfin Mobile App Link (Wi-Fi / LAN)</b>\n"
            "<small>Copy and paste this link into the Jellyfin app on your phone, tablet, or smart TV:</small>"
        )
        sec_title.set_xalign(0.0)
        sec_header_box.pack_start(sec_title, True, True, 0)

        # Protocol toggle buttons: HTTP (Port 8096, Recommended) vs HTTPS (Port 8920)
        proto_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        proto_box.set_valign(Gtk.Align.CENTER)
        lbl_proto = Gtk.Label()
        lbl_proto.set_markup("<small>Mode:</small>")
        proto_box.pack_start(lbl_proto, False, False, 0)

        self.btn_proto_http = Gtk.RadioButton.new_with_label(None, "🔓 HTTP (8096)")
        self.btn_proto_http.set_tooltip_text("Standard HTTP port 8096 (Recommended for Jellyfin Mobile App on local Wi-Fi)")
        self.btn_proto_http.set_active(self.scheme == "http")
        self.btn_proto_http.connect("toggled", self._on_proto_toggled)
        proto_box.pack_start(self.btn_proto_http, False, False, 0)

        self.btn_proto_https = Gtk.RadioButton.new_with_label_from_widget(self.btn_proto_http, "🔒 HTTPS (8920)")
        self.btn_proto_https.set_tooltip_text("SSL Encrypted port 8920 (Official Jellyfin HTTPS port)")
        self.btn_proto_https.set_active(self.scheme == "https")
        self.btn_proto_https.connect("toggled", self._on_proto_toggled)
        proto_box.pack_start(self.btn_proto_https, False, False, 0)

        sec_header_box.pack_end(proto_box, False, False, 0)
        self.main_box.pack_start(sec_header_box, False, False, 0)

        entry_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.entry_primary = Gtk.Entry()
        self.entry_primary.set_text(self.info["primary_mobile_url"])
        self.entry_primary.set_editable(True)
        self.entry_primary.set_can_focus(True)
        self.entry_primary.set_hexpand(True)
        self.entry_primary.connect("focus-in-event", lambda w, e: self.entry_primary.select_region(0, -1))
        self.entry_primary.connect("changed", self._on_entry_changed)
        entry_box.pack_start(self.entry_primary, True, True, 0)

        self.btn_copy_primary = Gtk.Button(label="📋 Copy Link")
        self.btn_copy_primary.get_style_context().add_class("suggested-action")
        self.btn_copy_primary.set_tooltip_text("Copy server URL to clipboard for mobile app")
        self.btn_copy_primary.connect("clicked", self._copy_primary_link)
        entry_box.pack_start(self.btn_copy_primary, False, False, 0)

        self.main_box.pack_start(entry_box, False, False, 0)

        self.lbl_feedback = Gtk.Label()
        self.lbl_feedback.set_xalign(0.0)
        self.main_box.pack_start(self.lbl_feedback, False, False, 0)

        # 3. Connection Steps Frame
        steps_frame = Gtk.Frame()
        steps_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        steps_box.set_margin_top(10)
        steps_box.set_margin_bottom(10)
        steps_box.set_margin_start(12)
        steps_box.set_margin_end(12)

        self.lbl_steps = Gtk.Label()
        self._update_steps_markup()
        self.lbl_steps.set_xalign(0.0)
        self.lbl_steps.set_line_wrap(True)
        steps_box.pack_start(self.lbl_steps, False, False, 0)
        steps_frame.add(steps_box)
        self.main_box.pack_start(steps_frame, False, False, 2)

        # 4. QR Code & Actions Row
        self.mid_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)

        self.qr_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.qr_vbox.set_valign(Gtk.Align.CENTER)
        self.qr_img = Gtk.Image()
        self.qr_vbox.pack_start(self.qr_img, False, False, 0)
        lbl_qr_sub = Gtk.Label()
        lbl_qr_sub.set_markup("<small>Scan with phone camera</small>")
        self.qr_vbox.pack_start(lbl_qr_sub, False, False, 0)
        self._update_qr_code()
        self.mid_box.pack_start(self.qr_vbox, False, False, 0)

        action_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        action_vbox.set_valign(Gtk.Align.CENTER)

        btn_open_browser = Gtk.Button(label="🌐 Open in Default Web Browser")
        btn_open_browser.connect("clicked", lambda b: Gio.AppInfo.launch_default_for_uri(self.entry_primary.get_text().strip(), None))
        action_vbox.pack_start(btn_open_browser, False, False, 0)

        btn_refresh = Gtk.Button(label="🔄 Refresh Connection Info")
        btn_refresh.connect("clicked", self._on_refresh_clicked)
        action_vbox.pack_start(btn_refresh, False, False, 0)

        lbl_browser_note = Gtk.Label()
        lbl_browser_note.set_markup("<small>You can also use this address in any web browser (Chrome, Safari, Firefox)\non any phone, tablet, laptop, or smart TV on your local network.</small>")
        lbl_browser_note.set_xalign(0.0)
        lbl_browser_note.set_line_wrap(True)
        action_vbox.pack_start(lbl_browser_note, False, False, 0)

        self.mid_box.pack_start(action_vbox, True, True, 0)
        self.main_box.pack_start(self.mid_box, False, False, 4)

        # 5. All Network Addresses Expander
        self.other_expander = Gtk.Expander(label="All Available Connection Links (Localhost & Network)")
        self.other_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.other_box.set_margin_top(8)
        self.other_box.set_margin_bottom(8)
        self.other_box.set_margin_start(8)
        self.other_box.set_margin_end(8)
        self._populate_addresses()
        self.other_expander.add(self.other_box)
        self.main_box.pack_start(self.other_expander, False, False, 0)

        self.show_all()
        GLib.idle_add(lambda: self.entry_primary.select_region(0, -1))

    def _update_status_header(self):
        s_name = self.info.get("server_name", "Jellyfin Server")
        s_ver = self.info.get("server_version", "")
        s_port = self.info.get("port", 8096)
        if self.info["online"]:
            self.lbl_status.set_markup(
                f"<big><span color='#2ecc71'><b>● Jellyfin Server is Online &amp; Ready</b></span></big>\n"
                f"<small>Server Name: <b>{s_name}</b> • Version: <b>{s_ver}</b> • Port: <b>{s_port}</b></small>"
            )
        else:
            self.lbl_status.set_markup(
                f"<big><span color='#e74c3c'><b>● Server is Offline</b></span></big>\n"
                f"<small>Jellyfin is not currently running or responding on port {s_port}.</small>"
            )

    def _on_proto_toggled(self, widget):
        if not widget.get_active():
            return
        self.scheme = "https" if self.btn_proto_https.get_active() else "http"
        self.info = get_server_network_addresses(self.server_url, scheme=self.scheme)
        self.entry_primary.set_text(self.info["primary_mobile_url"])
        self.lbl_feedback.set_text("")
        self._update_steps_markup()
        self._update_qr_code()
        self._populate_addresses()

    def _on_entry_changed(self, entry):
        url = entry.get_text().strip()
        if url:
            if url.startswith("https://") and ":8096" in url:
                self.lbl_feedback.set_markup(
                    "<span color='#e74c3c'>⚠️ <b>SSL Port Mismatch:</b> Port 8096 is HTTP only!\n"
                    "Using <i>https://</i> on port 8096 causes: <b>SSL received a record that exceeded the maximum permissible length</b>.\n"
                    "To fix: Use <b>port 8920</b> (<tt>https://...:8920</tt>) for HTTPS, or switch to <b>http://</b>.</span>"
                )
            elif url.startswith("http://") and ":8920" in url:
                self.lbl_feedback.set_markup(
                    "<span color='#e67e22'>⚠️ <b>Port Notice:</b> Port 8920 is HTTPS. For plain HTTP, please use <b>port 8096</b>.</span>"
                )
            else:
                self.lbl_feedback.set_text("")
            self._update_steps_markup(url)
            self._update_qr_code(url)

    def _update_steps_markup(self, url: str = None):
        target_url = url or self.entry_primary.get_text().strip() or self.info.get("primary_mobile_url", "")
        self.lbl_steps.set_markup(
            "<b>How to connect on your phone:</b>\n"
            "1. Connect your phone to the <b>same Wi-Fi network</b> as this computer.\n"
            "2. Open the <b>Jellyfin</b> app on your phone (available on App Store &amp; Google Play).\n"
            f"3. In the <b>Server Address</b> prompt, paste: <tt>{target_url}</tt>\n"
            "4. Tap <b>Connect</b>, then log in with your Jellyfin username &amp; password."
        )

    def _update_qr_code(self, url: str = None):
        target_url = url or self.entry_primary.get_text().strip() or self.info.get("primary_mobile_url", "")
        pixbuf = self._generate_qr_pixbuf(target_url)
        if pixbuf:
            self.qr_img.set_from_pixbuf(pixbuf)
            self.qr_vbox.show_all()
        else:
            self.qr_vbox.hide()

    def _populate_addresses(self):
        for child in self.other_box.get_children():
            self.other_box.remove(child)
        for addr in self.info["addresses"]:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            lbl_row = Gtk.Label()
            lbl_label = addr.get("label", "")
            lbl_url = addr.get("url", "")
            lbl_row.set_markup(f"<b>{lbl_label}:</b> <tt>{lbl_url}</tt>")
            lbl_row.set_xalign(0.0)
            row.pack_start(lbl_row, True, True, 0)

            btn_copy = Gtk.Button(label="📋 Copy")
            btn_copy.connect("clicked", lambda b, u=lbl_url: self._copy_to_clipboard(u, b))
            row.pack_start(btn_copy, False, False, 0)
            self.other_box.pack_start(row, False, False, 0)
        self.other_box.show_all()

    def _generate_qr_pixbuf(self, url: str):
        if not qrcode or not url:
            return None
        try:
            qr = qrcode.QRCode(box_size=4, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            data = buf.getvalue()
            loader = GdkPixbuf.PixbufLoader.new_with_type("png")
            loader.write(data)
            loader.close()
            return loader.get_pixbuf()
        except Exception:
            return None

    def _copy_primary_link(self, widget):
        text_to_copy = self.entry_primary.get_text().strip() or self.info["primary_mobile_url"]
        self._copy_to_clipboard(text_to_copy, self.btn_copy_primary)
        self.lbl_feedback.set_markup("<span color='#2ecc71'>✔ <b>Copied to clipboard!</b> Ready to paste into the Jellyfin mobile app.</span>")

    def _copy_to_clipboard(self, text: str, button: Optional[Gtk.Button] = None):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(text, -1)
        clipboard.store()
        if button:
            old_label = button.get_label()
            button.set_label("✔ Copied!")
            GLib.timeout_add(2000, lambda: button.set_label(old_label) or False)

    def _on_start_clicked(self, widget):
        self.btn_start.set_sensitive(False)
        self.btn_start.set_label("⏳ Starting Jellyfin Server...")
        if self.on_start_server:
            self.on_start_server()
        def delayed_refresh():
            time.sleep(3)
            GLib.idle_add(self._on_refresh_clicked)
        threading.Thread(target=delayed_refresh, daemon=True).start()

    def _on_refresh_clicked(self, widget=None):
        self.info = get_server_network_addresses(self.server_url, scheme=self.scheme)
        self._update_status_header()
        self.entry_primary.set_text(self.info["primary_mobile_url"])
        self._update_steps_markup()
        self._update_qr_code()
        self._populate_addresses()
        if self.info["online"]:
            self.btn_start.hide()
            self.lbl_feedback.set_markup("<span color='#2ecc71'>✔ Server is online and responding!</span>")
        else:
            self.btn_start.show()
            self.btn_start.set_sensitive(True)
            self.btn_start.set_label("▶ Start Jellyfin Server Now")
            self.lbl_feedback.set_markup("<span color='#e74c3c'>Server still offline. Try starting it again.</span>")


class JellyScratchApp(Gtk.Window):
    def __init__(self):
        super().__init__(title="JellyScratch Server")
        self.set_default_size(1280, 820)
        self.set_position(Gtk.WindowPosition.CENTER)

        # Set WM Class for desktop environments
        self.set_wmclass("jellyscratchserver", "JellyScratchServer")

        # Set application icon
        icon_path = self._find_icon()
        if icon_path and os.path.exists(icon_path):
            self.set_icon_from_file(icon_path)

        self.server_url = DEFAULT_JELLYFIN_URL
        self.monitor_daemon: Optional[MonitorDaemon] = None
        self.monitor_thread: Optional[threading.Thread] = None
        self.server_ready = False

        # Ensure Jellyfin SSL certificate and HTTPS on port 8920 are configured
        ensure_jellyfin_ssl_configured()

        self._build_ui()
        self.connect("destroy", self.on_window_close)
        self.connect("key-press-event", self.on_key_press)

        # Start server check & background monitor
        self.start_server_check_thread()

    def _find_icon(self) -> Optional[str]:
        candidates = [
            Path(__file__).resolve().parent / "icon.png",
            Path("/opt/jellyscratchserver/icon.png"),
            Path("/usr/share/pixmaps/jellyscratchserver.png"),
        ]
        for p in candidates:
            if p.exists():
                return str(p)
        return None

    def _build_ui(self):
        # 1. HeaderBar
        self.headerbar = Gtk.HeaderBar()
        self.headerbar.set_show_close_button(True)
        self.headerbar.props.title = "JellyScratch Server"
        self.headerbar.props.subtitle = "Media Server & Discord Monitor"
        self.set_titlebar(self.headerbar)

        # Navigation Controls (Left)
        nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        self.btn_back = Gtk.Button.new_from_icon_name("go-previous-symbolic", Gtk.IconSize.BUTTON)
        self.btn_back.set_tooltip_text("Back")
        self.btn_back.connect("clicked", lambda b: self.webview.go_back() if self.webview.can_go_back() else None)
        nav_box.pack_start(self.btn_back, False, False, 0)

        self.btn_forward = Gtk.Button.new_from_icon_name("go-next-symbolic", Gtk.IconSize.BUTTON)
        self.btn_forward.set_tooltip_text("Forward")
        self.btn_forward.connect("clicked", lambda b: self.webview.go_forward() if self.webview.can_go_forward() else None)
        nav_box.pack_start(self.btn_forward, False, False, 0)

        self.btn_reload = Gtk.Button.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        self.btn_reload.set_tooltip_text("Reload")
        self.btn_reload.connect("clicked", lambda b: self.webview.reload())
        nav_box.pack_start(self.btn_reload, False, False, 0)

        self.btn_home = Gtk.Button.new_from_icon_name("go-home-symbolic", Gtk.IconSize.BUTTON)
        self.btn_home.set_tooltip_text("Home")
        self.btn_home.connect("clicked", self.on_home_clicked)
        nav_box.pack_start(self.btn_home, False, False, 0)

        self.headerbar.pack_start(nav_box)

        # Right Controls
        right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        # Server Status Button & Indicator (Click to view mobile app & connection links)
        self.btn_status = Gtk.Button()
        self.lbl_status = Gtk.Label()
        self.lbl_status.set_markup("<span color='#f39c12'>● Starting Server...</span>")
        self.btn_status.add(self.lbl_status)
        self.btn_status.set_tooltip_text("Server Status: Starting... Click to view server address & mobile app link")
        self.btn_status.connect("clicked", self.on_server_status_clicked)
        right_box.pack_start(self.btn_status, False, False, 0)

        # Scan Libraries Button
        self.btn_scan = Gtk.Button(label="🔄 Scan Libraries")
        self.btn_scan.set_tooltip_text("Scan all libraries for newly uploaded media & send Discord announcements")
        self.btn_scan.connect("clicked", self.on_scan_libraries_clicked)
        right_box.pack_start(self.btn_scan, False, False, 0)

        # Restart Server Button
        self.btn_restart_server = Gtk.Button(label="⟲ Restart Server")
        self.btn_restart_server.set_tooltip_text("Restart the Jellyfin Media Server and Discord background monitor")
        self.btn_restart_server.connect("clicked", self.on_restart_server_clicked)
        right_box.pack_start(self.btn_restart_server, False, False, 0)

        # Media Requests Button (Seerr / Jellyseerr)
        self.btn_requests = Gtk.Button(label="📥 Requests")
        self.btn_requests.set_tooltip_text("Browse & request movies and TV shows via Seerr / Jellyseerr (port 5055)")
        self.btn_requests.connect("clicked", self.on_requests_clicked)
        right_box.pack_start(self.btn_requests, False, False, 0)

        # Cloud Stream Button (Stremio & Debrid Zero-Storage)
        self.btn_cloud = Gtk.Button(label="☁️ Cloud Stream")
        self.btn_cloud.get_style_context().add_class("suggested-action")
        self.btn_cloud.set_tooltip_text("Zero-Storage Cloud Streaming (Stremio & Real-Debrid)")
        self.btn_cloud.connect("clicked", self.on_cloud_stream_clicked)
        right_box.pack_start(self.btn_cloud, False, False, 0)
        self.btn_cloud.show()

        # Settings Button (Renamed from Discord Webhook)
        self.btn_discord = Gtk.Button(label="⚙️ Settings")
        self.btn_discord.set_tooltip_text("Server configuration, Discord Webhooks, and Debrid API settings")
        self.btn_discord.connect("clicked", self.on_open_discord_settings)
        right_box.pack_start(self.btn_discord, False, False, 0)

        # Fullscreen Toggle Button
        self.btn_fullscreen = Gtk.Button.new_from_icon_name("view-fullscreen-symbolic", Gtk.IconSize.BUTTON)
        self.btn_fullscreen.set_tooltip_text("Toggle Fullscreen (F11)")
        self.btn_fullscreen.connect("clicked", self.toggle_fullscreen)
        right_box.pack_start(self.btn_fullscreen, False, False, 0)

        self.headerbar.pack_end(right_box)

        # 2. Main Stack
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(300)
        self.add(self.stack)

        # Page A: Loading View
        self.loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.loading_box.set_valign(Gtk.Align.CENTER)
        self.loading_box.set_halign(Gtk.Align.CENTER)

        # App Logo in loading view
        icon_path = self._find_icon()
        if icon_path and os.path.exists(icon_path):
            img = Gtk.Image.new_from_file(icon_path)
            self.loading_box.pack_start(img, False, False, 0)

        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(48, 48)
        self.spinner.start()
        self.loading_box.pack_start(self.spinner, False, False, 0)

        self.lbl_loading_msg = Gtk.Label()
        self.lbl_loading_msg.set_markup("<big><b>Starting JellyScratch Server...</b></big>")
        self.loading_box.pack_start(self.lbl_loading_msg, False, False, 0)

        self.lbl_loading_sub = Gtk.Label()
        self.lbl_loading_sub.set_markup("<small>Checking media engine and Discord monitor...</small>")
        self.loading_box.pack_start(self.lbl_loading_sub, False, False, 0)

        # Action buttons in loading view
        self.btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.btn_box.set_halign(Gtk.Align.CENTER)

        self.btn_manual_start = Gtk.Button(label="Start Server Manually")
        self.btn_manual_start.set_no_show_all(True)
        self.btn_manual_start.connect("clicked", self.on_manual_start_clicked)
        self.btn_box.pack_start(self.btn_manual_start, False, False, 0)

        self.btn_repair = Gtk.Button(label="Repair System Service")
        self.btn_repair.set_tooltip_text("Fixes corrupted /etc/jellyfin config (one-time PIN prompt)")
        self.btn_repair.set_no_show_all(True)
        self.btn_repair.connect("clicked", self.on_repair_clicked)
        self.btn_box.pack_start(self.btn_repair, False, False, 0)

        self.loading_box.pack_start(self.btn_box, False, False, 0)

        self.stack.add_named(self.loading_box, "loading")

        # Page B: WebKit View
        self._init_webkit_view()
        self.stack.add_named(self.webview_container, "browser")

        self.stack.set_visible_child_name("loading")
        self.show_all()

    def _init_webkit_view(self):
        # Configure Web Context & Persistent Cookies
        context = WebKit2.WebContext.get_default()
        cookie_mgr = context.get_cookie_manager()
        cookie_mgr.set_persistent_storage(str(COOKIES_FILE), WebKit2.CookiePersistentStorage.TEXT)

        # Configure WebView Settings
        self.webview = WebKit2.WebView()
        settings = self.webview.get_settings()
        settings.set_enable_media_stream(True)
        settings.set_enable_webaudio(True)
        settings.set_enable_webgl(True)
        settings.set_enable_smooth_scrolling(True)
        settings.set_enable_javascript(True)
        settings.set_enable_fullscreen(True)
        settings.set_media_playback_allows_inline(True)
        settings.set_media_playback_requires_user_gesture(False)

        # Fullscreen video events
        self.webview.connect("enter-fullscreen", self.on_webkit_enter_fullscreen)
        self.webview.connect("leave-fullscreen", self.on_webkit_leave_fullscreen)
        self.webview.connect("load-changed", self.on_webview_load_changed)

        # Scrolled container for WebView
        self.webview_container = Gtk.ScrolledWindow()
        self.webview_container.add(self.webview)

    def on_webkit_enter_fullscreen(self, webview):
        self.fullscreen()
        self.headerbar.hide()
        return True

    def on_webkit_leave_fullscreen(self, webview):
        self.unfullscreen()
        self.headerbar.show()
        return True

    def toggle_fullscreen(self, widget=None):
        if self.get_window().get_state() & Gdk.WindowState.FULLSCREEN:
            self.unfullscreen()
            self.headerbar.show()
        else:
            self.fullscreen()

    def on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_F11:
            self.toggle_fullscreen()
            return True
        return False

    def on_open_discord_settings(self, widget):
        dialog = DiscordSettingsDialog(self, on_saved_callback=self.restart_discord_monitor)
        res = dialog.run()
        if res == Gtk.ResponseType.OK:
            dialog.apply_save()
        dialog.destroy()

    def on_server_status_clicked(self, widget):
        dialog = ServerConnectionDialog(self, server_url=self.server_url, on_start_server=self.start_server_check_thread)
        dialog.run()
        dialog.destroy()

    def on_scan_libraries_clicked(self, widget):
        self.btn_scan.set_sensitive(False)
        self.btn_scan.set_label("⏳ Scanning...")

        def run_scan():
            try:
                cfg = get_config()
                client = JellyfinClient(cfg.get("jellyfin_url", DEFAULT_JELLYFIN_URL), cfg.get("jellyfin_api_key", ""))
                client.trigger_library_scan()
                logger.info("Library scan triggered via HeaderBar.")
                time.sleep(2)
                if self.monitor_daemon:
                    self.monitor_daemon.check_new_media()
            except Exception as e:
                logger.error(f"Error triggering scan: {e}")
            finally:
                GLib.idle_add(lambda: self.btn_scan.set_label("🔄 Scan Libraries"))
                GLib.idle_add(lambda: self.btn_scan.set_sensitive(True))

        threading.Thread(target=run_scan, daemon=True).start()

    def on_restart_server_clicked(self, widget):
        self.btn_restart_server.set_sensitive(False)
        self.btn_restart_server.set_label("⏳ Restarting...")

        def do_restart():
            try:
                logger.info("Restarting Jellyfin server via systemctl --user...")
                subprocess.run(["systemctl", "--user", "restart", "jellyfin"], capture_output=True, timeout=15)
                time.sleep(2)
                GLib.idle_add(self.restart_discord_monitor)
                GLib.idle_add(lambda: self.webview.reload() if ":8096" in (self.webview.get_uri() or "") else None)
                logger.info("Jellyfin server restart cycle complete.")
            except Exception as e:
                logger.error(f"Error restarting server: {e}")
            finally:
                GLib.idle_add(lambda: self.btn_restart_server.set_label("⟲ Restart Server"))
                GLib.idle_add(lambda: self.btn_restart_server.set_sensitive(True))

        threading.Thread(target=do_restart, daemon=True).start()

    def on_home_clicked(self, widget=None):
        current_uri = self.webview.get_uri() or ""
        if ":5055" in current_uri:
            self.webview.load_uri("http://localhost:5055")
        elif "web.stremio.com" in current_uri:
            cfg = get_config()
            self.webview.load_uri(cfg.get("stremio_stream_url", "https://web.stremio.com"))
        else:
            self.webview.load_uri(self.server_url)

    def on_cloud_stream_clicked(self, widget):
        current_uri = self.webview.get_uri() or ""
        cfg = get_config()
        stremio_url = cfg.get("stremio_stream_url", "https://web.stremio.com")

        if "web.stremio.com" in current_uri or "torrentio" in current_uri:
            # Currently viewing Cloud Stream -> Switch back to Jellyfin
            self.webview.load_uri(self.server_url)
            self.btn_cloud.set_label("☁️ Cloud Stream")
            self.btn_cloud.set_tooltip_text("Zero-Storage Cloud Streaming (Stremio & Real-Debrid)")
            self.headerbar.props.subtitle = "Media Server & Discord Monitor"
        else:
            # Switch to Cloud Stream
            if ":5055" in current_uri:
                self.btn_requests.set_label("📥 Requests")
            self.stack.set_visible_child_name("browser")
            self.webview.load_uri(stremio_url)
            self.btn_cloud.set_label("🎬 Jellyfin")
            self.btn_cloud.set_tooltip_text("Switch back to Jellyfin Media Server")
            self.headerbar.props.subtitle = "Cloud Streaming (Stremio Web & Real-Debrid)"

    def on_requests_clicked(self, widget):
        current_uri = self.webview.get_uri() or ""
        seerr_url = "http://localhost:5055"

        if ":5055" in current_uri:
            # Currently viewing Seerr -> Switch back to Jellyfin
            self.webview.load_uri(self.server_url)
            self.btn_requests.set_label("📥 Requests")
            self.btn_requests.set_tooltip_text("Browse & request movies and TV shows via Seerr / Jellyseerr (port 5055)")
            self.headerbar.props.subtitle = "Media Server & Discord Monitor"
        else:
            if "web.stremio.com" in current_uri:
                self.btn_cloud.set_label("☁️ Cloud Stream")
            # Check if Seerr is reachable before switching
            self.btn_requests.set_sensitive(False)
            self.btn_requests.set_label("⏳ Connecting...")

            def check_seerr():
                is_up = False
                try:
                    r = requests.get(seerr_url, timeout=1.5)
                    is_up = (r.status_code < 500)
                except Exception:
                    is_up = False

                if not is_up:
                    GLib.idle_add(lambda: self.btn_requests.set_label("⏳ Starting Seerr..."))
                    is_up = ensure_seerr_running()

                def finish():
                    self.btn_requests.set_sensitive(True)
                    if is_up:
                        self._switch_to_seerr(seerr_url)
                    else:
                        self.btn_requests.set_label("📥 Requests")
                        self._show_seerr_offline_dialog()

                GLib.idle_add(finish)

            threading.Thread(target=check_seerr, daemon=True).start()

    def _switch_to_seerr(self, seerr_url: str):
        self.webview.load_uri(seerr_url)
        self.btn_requests.set_label("🎬 Jellyfin")
        self.btn_requests.set_tooltip_text("Switch back to Jellyfin Media Server")
        self.headerbar.props.subtitle = "Media Requests (Seerr / Jellyseerr)"
        GLib.timeout_add(700, self._inject_seerr_autofill)
        GLib.timeout_add(1800, self._inject_seerr_autofill)

    def on_webview_load_changed(self, webview, event):
        if event == WebKit2.LoadEvent.FINISHED:
            uri = webview.get_uri() or ""
            cfg = get_config()
            seerr_url = cfg.get("seerr_url", "http://localhost:5055")
            if ":5055" in uri or seerr_url in uri:
                self._inject_seerr_autofill()

    def _inject_seerr_autofill(self):
        try:
            cfg = get_config()
            if cfg.get("seerr_autofill_enabled", True):
                uri = self.webview.get_uri() or ""
                seerr_url = cfg.get("seerr_url", "http://localhost:5055")
                if ":5055" in uri or seerr_url in uri:
                    js_code = build_seerr_autofill_script(cfg)
                    self.webview.run_javascript(js_code, None, None, None)
        except Exception as e:
            logger.debug(f"Error injecting Seerr autofill: {e}")

    def _show_seerr_offline_dialog(self):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Seerr / Jellyseerr is Not Running"
        )
        dialog.format_secondary_markup(
            "<b>Seerr is not responding on http://localhost:5055.</b>\n\n"
            "To install & start Seerr, open a terminal and run:\n"
            "  <tt>sudo /home/sam/setup_seerr.sh</tt>\n\n"
            "Or if Docker is already installed:\n"
            "  <tt>cd ~/seerr &amp;&amp; docker compose up -d</tt>"
        )
        dialog.run()
        dialog.destroy()

    def on_manual_start_clicked(self, widget):
        if not is_jellyfin_installed():
            install_jellyfin_gui()
        else:
            self.lbl_loading_sub.set_markup("<span>Starting Jellyfin in user mode (no PIN needed)...</span>")
            try_start_jellyfin_service()

    def on_repair_clicked(self, widget):
        self.lbl_loading_sub.set_markup("<span>Repairing system service config...</span>")
        repair_system_service_gui(on_done=lambda: self.start_server_check_thread())

    def start_server_check_thread(self):
        def check_worker():
            if not is_jellyfin_installed():
                logger.info("Jellyfin is not installed yet.")
                GLib.idle_add(lambda: self.lbl_status.set_markup("<span color='#e74c3c'>● Needs Install</span>"))
                GLib.idle_add(lambda: self.lbl_loading_msg.set_markup("<big><b>Jellyfin Server Not Installed</b></big>"))
                GLib.idle_add(lambda: self.lbl_loading_sub.set_markup(
                    "<span>Please install the Jellyfin package.<br>"
                    "Click below for automatic setup or run:<br>"
                    "<code>sudo apt install -y jellyfin</code></span>"
                ))
                GLib.idle_add(lambda: self.btn_manual_start.set_label("Install Jellyfin (One-Click)"))
                GLib.idle_add(lambda: self.btn_manual_start.show())
                GLib.idle_add(lambda: self.btn_repair.hide())

                # Wait for user to install
                while not is_jellyfin_installed():
                    time.sleep(2)

                GLib.idle_add(lambda: self.lbl_loading_msg.set_markup("<big><b>Starting JellyScratch Server...</b></big>"))
                GLib.idle_add(lambda: self.lbl_loading_sub.set_markup("<span>Initializing media engine...</span>"))
                GLib.idle_add(lambda: self.btn_manual_start.hide())
                GLib.idle_add(lambda: self.btn_repair.hide())

            # Server is installed, ensure it is running
            if not is_jellyfin_responding(self.server_url):
                logger.info("Jellyfin server not detected on port 8096. Attempting auto-start...")
                GLib.idle_add(lambda: self.lbl_loading_sub.set_markup("<span>Starting Jellyfin media service...</span>"))
                try_start_jellyfin_service()

            # Poll for up to 25 seconds
            attempts = 0
            while attempts < 25 and not is_jellyfin_responding(self.server_url):
                attempts += 1
                time.sleep(1)
                if attempts == 5 and not is_jellyfin_responding(self.server_url):
                    start_user_jellyfin_direct()
                if attempts == 8:
                    GLib.idle_add(lambda: self.btn_manual_start.set_label("Start Server Manually"))
                    GLib.idle_add(lambda: self.btn_manual_start.show())
                    if is_system_config_corrupted():
                        GLib.idle_add(lambda: self.btn_repair.show())

            if is_jellyfin_responding(self.server_url):
                logger.info("Jellyfin server is online and responding!")
                self.server_ready = True
                GLib.idle_add(self._on_server_online)
            else:
                logger.warning("Jellyfin server did not respond after 25 seconds.")
                GLib.idle_add(self._on_server_timeout)

        threading.Thread(target=check_worker, daemon=True).start()

    def _on_server_online(self):
        self.lbl_status.set_markup("<span color='#2ecc71'><b>● Server Online</b></span>")
        self.btn_status.set_tooltip_text("Server is Online! Click to view & copy link for Jellyfin Mobile App")
        self.webview.load_uri(self.server_url)
        self.stack.set_visible_child_name("browser")
        self.btn_manual_start.hide()
        self.btn_repair.hide()
        # Start the background Discord monitor
        self.restart_discord_monitor()

    def _on_server_timeout(self):
        self.lbl_status.set_markup("<span color='#e74c3c'><b>● Server Offline</b></span>")
        self.btn_status.set_tooltip_text("Server is Offline. Click to view connection links & options")
        self.lbl_loading_msg.set_markup("<big><span color='#e74c3c'>Could not connect to Jellyfin</span></big>")
        if is_system_config_corrupted():
            self.lbl_loading_sub.set_markup(
                "<span>Detected corrupted system config (<code>/etc/jellyfin/logging.default.json</code>).<br>"
                "Click <b>Repair System Service</b> to fix it (requires one-time PIN),<br>"
                "or click <b>Start Server Manually</b> to run without root.</span>"
            )
            self.btn_repair.show()
        else:
            self.lbl_loading_sub.set_markup(
                "<span>Please make sure Jellyfin is installed and started.<br>"
                "Click 'Start Server Manually' to run Jellyfin in user mode without PIN.</span>"
            )
        self.btn_manual_start.show()

    def restart_discord_monitor(self):
        # Stop existing monitor if running
        if self.monitor_daemon:
            self.monitor_daemon.stop()
            self.monitor_daemon = None

        cfg = get_config()
        wh = cfg.get("discord_webhook_url", "").strip()
        upload_wh_keys = [
            "discord_webhook_all",
            "discord_new_media_webhook_url",
            "discord_webhook_movies",
            "discord_webhook_series",
            "discord_webhook_episodes",
            "discord_webhook_music",
            "discord_webhook_music_videos",
            "discord_webhook_videos"
        ]
        has_wh = wh and wh.startswith("http")
        has_upload_wh = any(cfg.get(k, "").strip().startswith("http") for k in upload_wh_keys)

        if not has_wh and not has_upload_wh:
            logger.info("No Discord Webhook configured yet. Open '⚙️ Discord Webhook' to configure.")
            self.btn_discord.get_style_context().add_class("suggested-action")
            return
        else:
            self.btn_discord.get_style_context().remove_class("suggested-action")

        logger.info("Starting Discord Monitor daemon...")
        try:
            self.monitor_daemon = MonitorDaemon(str(CONFIG_FILE))
            self.monitor_thread = threading.Thread(target=self.monitor_daemon.run, daemon=True)
            self.monitor_thread.start()
        except Exception as e:
            logger.error(f"Failed to start Discord Monitor: {e}")

    def on_window_close(self, widget):
        logger.info("Closing JellyScratch Server desktop app...")
        if self.monitor_daemon:
            self.monitor_daemon.stop()
        if Gtk.main_level() > 0:
            Gtk.main_quit()


def main():
    Gtk.init(sys.argv)
    app = JellyScratchApp()
    Gtk.main()


if __name__ == "__main__":
    main()
