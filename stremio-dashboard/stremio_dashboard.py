import json
import os
import requests
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)
CONFIG_FILE = os.path.expanduser("~/.stremio_debrid_config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"rd_api_key": "", "discord_webhook": "", "stream_quality": "all"}

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stremio Cloud Debrid & Discord Manager</title>
    <style>
        * { box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; 
            background: #0b0f19; 
            color: #f1f5f9; 
            padding: 40px 20px; 
            margin: 0; 
        }
        .container { 
            max-width: 680px; 
            margin: 0 auto; 
            background: #111827; 
            border: 1px solid #1f2937;
            border-radius: 14px; 
            padding: 30px; 
            box-shadow: 0 20px 40px rgba(0,0,0,0.6); 
        }
        h1 { 
            margin-top: 0; 
            font-size: 24px; 
            color: #38bdf8; 
            display: flex; 
            align-items: center; 
            gap: 12px; 
        }
        .subtitle {
            color: #94a3b8;
            font-size: 14px;
            margin-bottom: 24px;
        }
        .tabs { 
            display: flex; 
            border-bottom: 2px solid #1f2937; 
            margin-bottom: 25px; 
            gap: 10px;
        }
        .tab { 
            padding: 12px 20px; 
            cursor: pointer; 
            border: none; 
            background: none; 
            color: #94a3b8; 
            font-weight: 600; 
            font-size: 15px; 
            border-radius: 8px 8px 0 0;
            transition: all 0.2s ease;
        }
        .tab:hover { color: #f8fafc; }
        .tab.active { 
            color: #38bdf8; 
            border-bottom: 2px solid #38bdf8; 
            background: #1e293b;
        }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        label { 
            display: block; 
            margin: 18px 0 6px; 
            color: #cbd5e1; 
            font-size: 14px; 
            font-weight: 500; 
        }
        input[type="text"], input[type="password"] { 
            width: 100%; 
            padding: 12px 14px; 
            border-radius: 8px; 
            border: 1px solid #374151; 
            background: #030712; 
            color: white; 
            font-size: 14px;
            outline: none;
            transition: border-color 0.2s;
        }
        input[type="text"]:focus, input[type="password"]:focus {
            border-color: #38bdf8;
        }
        .btn-group {
            display: flex;
            gap: 10px;
            margin-top: 20px;
            flex-wrap: wrap;
        }
        button { 
            background: #0284c7; 
            color: white; 
            border: none; 
            padding: 12px 20px; 
            border-radius: 8px; 
            font-weight: 600; 
            cursor: pointer; 
            font-size: 14px;
            transition: background 0.2s ease;
        }
        button:hover { background: #0369a1; }
        .btn-test { background: #5865F2; }
        .btn-test:hover { background: #4752c4; }
        .btn-green { background: #16a34a; }
        .btn-green:hover { background: #15803d; }
        .status { 
            margin-top: 18px; 
            padding: 14px; 
            border-radius: 8px; 
            font-size: 14px; 
            display: none; 
            line-height: 1.5;
        }
        .status.success { background: rgba(6, 78, 59, 0.6); color: #6ee7b7; border: 1px solid #059669; display: block; }
        .status.error { background: rgba(76, 5, 25, 0.6); color: #fda4af; border: 1px solid #e11d48; display: block; }
        .card {
            background: #1e293b;
            padding: 18px;
            border-radius: 8px;
            border: 1px solid #334155;
            margin-top: 15px;
        }
        .card h4 { margin: 0 0 8px 0; color: #38bdf8; }
        .card p { margin: 0; font-size: 13px; color: #94a3b8; }
    </style>
</head>
<body>
<div class="container">
    <h1>🚀 Stremio Cloud Manager</h1>
    <div class="subtitle">Zero-Storage Streaming & Discord Webhook Testing Portal</div>

    <div class="tabs">
        <button class="tab active" onclick="openTab(event, 'tab-apis')">🔑 Debrid & APIs</button>
        <button class="tab" onclick="openTab(event, 'tab-discord')">💬 Discord Webhook</button>
        <button class="tab" onclick="openTab(event, 'tab-stremio')">📺 Stremio Setup</button>
    </div>

    <!-- APIs Tab -->
    <div id="tab-apis" class="tab-content active">
        <label>Real-Debrid API Key:</label>
        <input type="password" id="rd_api_key" value="{{ config.rd_api_key }}" placeholder="Paste your Real-Debrid API token here">
        <p style="font-size:12px; color:#94a3b8; margin-top: 6px;">
            Get your key from: <a href="https://real-debrid.com/apitoken" target="_blank" style="color:#38bdf8; text-decoration:none;">real-debrid.com/apitoken</a>
        </p>
        
        <div class="btn-group">
            <button onclick="saveSettings()">💾 Save API Keys</button>
            <button class="btn-green" onclick="testRD()">⚡ Verify Debrid Account</button>
        </div>
        <div id="rd-status" class="status"></div>
    </div>

    <!-- Discord Tab -->
    <div id="tab-discord" class="tab-content">
        <label>Discord Webhook URL:</label>
        <input type="text" id="discord_webhook" value="{{ config.discord_webhook }}" placeholder="https://discord.com/api/webhooks/...">
        
        <label>Custom Test Message (Optional):</label>
        <input type="text" id="discord_custom_msg" placeholder="e.g. Stremio Debrid Server ping test">

        <div class="btn-group">
            <button onclick="saveSettings()">💾 Save Webhook</button>
            <button class="btn-test" onclick="testDiscord()">🔔 Send Test Response to Discord</button>
        </div>
        <div id="discord-status" class="status"></div>
    </div>

    <!-- Stremio Tab -->
    <div id="tab-stremio" class="tab-content">
        <div class="card">
            <h4>Instant Zero-Storage Streaming</h4>
            <p>Stremio connects to Real-Debrid's high speed CDN directly through Torrentio. You do not need to host or download files locally.</p>
        </div>

        <div class="btn-group" style="margin-top:20px;">
            <button class="btn-green" onclick="openTorrentio()">🚀 Launch Torrentio Add-on Config</button>
            <button onclick="window.open('https://web.stremio.com', '_blank')">🌐 Open Stremio Web</button>
        </div>
    </div>
</div>

<script>
function openTab(evt, tabName) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    evt.currentTarget.classList.add('active');
    document.getElementById(tabName).classList.add('active');
}

async function saveSettings() {
    const rd_key = document.getElementById('rd_api_key').value;
    const webhook = document.getElementById('discord_webhook').value;
    const res = await fetch('/api/save', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({rd_api_key: rd_key, discord_webhook: webhook})
    });
    const data = await res.json();
    alert(data.message);
}

async function testDiscord() {
    const statusBox = document.getElementById('discord-status');
    statusBox.className = 'status';
    statusBox.innerText = 'Sending test payload to Discord...';
    statusBox.style.display = 'block';

    const customMsg = document.getElementById('discord_custom_msg').value;
    const webhookUrl = document.getElementById('discord_webhook').value;

    const res = await fetch('/api/test-discord', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({discord_webhook: webhookUrl, custom_message: customMsg})
    });
    const data = await res.json();
    statusBox.className = 'status ' + (data.success ? 'success' : 'error');
    statusBox.innerText = data.message;
}

async function testRD() {
    const statusBox = document.getElementById('rd-status');
    statusBox.className = 'status';
    statusBox.innerText = 'Connecting to Real-Debrid API...';
    statusBox.style.display = 'block';

    const res = await fetch('/api/test-rd', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({rd_api_key: document.getElementById('rd_api_key').value})
    });
    const data = await res.json();
    statusBox.className = 'status ' + (data.success ? 'success' : 'error');
    statusBox.innerText = data.message;
}

function openTorrentio() {
    const rd_key = document.getElementById('rd_api_key').value.trim();
    if (!rd_key) {
        alert('Please save your Real-Debrid API key first in the APIs tab!');
        return;
    }
    const url = "https://torrentio.strem.fun/configure#realdebrid=" + encodeURIComponent(rd_key);
    window.open(url, '_blank');
}
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE, config=load_config())

@app.route("/api/save", methods=["POST"])
def save():
    data = request.json or {}
    cfg = load_config()
    cfg["rd_api_key"] = data.get("rd_api_key", "").strip()
    cfg["discord_webhook"] = data.get("discord_webhook", "").strip()
    save_config(cfg)
    return jsonify({"success": True, "message": "Settings saved successfully to ~/.stremio_debrid_config.json!"})

@app.route("/api/test-discord", methods=["POST"])
def test_discord():
    data = request.json or {}
    webhook_url = data.get("discord_webhook", "").strip()
    custom_msg = data.get("custom_message", "").strip() or "Webhook test response successfully verified."

    if not webhook_url:
        return jsonify({"success": False, "message": "Please enter a Discord Webhook URL."})
    
    cfg = load_config()
    has_rd = bool(cfg.get("rd_api_key"))

    payload = {
        "username": "Stremio Debrid Server",
        "avatar_url": "https://www.stremio.com/website/stremio-logo-small.png",
        "embeds": [{
            "title": "✅ Discord Webhook Connected",
            "description": custom_msg,
            "color": 3814143,
            "fields": [
                {"name": "Status", "value": "🟢 Active & Ready", "inline": True},
                {"name": "Debrid API Configured", "value": "Yes" if has_rd else "No (Add in APIs tab)", "inline": True},
                {"name": "Storage Mode", "value": "0 GB Cloud Streaming", "inline": False}
            ],
            "footer": {"text": "Stremio Cloud Manager"}
        }]
    }
    
    try:
        r = requests.post(webhook_url, json=payload, timeout=8)
        if r.status_code in [200, 204]:
            return jsonify({"success": True, "message": "Discord message received successfully! Check your Discord channel."})
        return jsonify({"success": False, "message": f"Discord error (HTTP {r.status_code}): {r.text}"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Connection error: {str(e)}"})

@app.route("/api/test-rd", methods=["POST"])
def test_rd():
    data = request.json or {}
    key = data.get("rd_api_key", "").strip()
    if not key:
        return jsonify({"success": False, "message": "Please enter a Real-Debrid API Key."})
    try:
        r = requests.get("https://api.real-debrid.com/rest/1.0/user", headers={"Authorization": f"Bearer {key}"}, timeout=8)
        if r.status_code == 200:
            user = r.json()
            return jsonify({
                "success": True, 
                "message": f"Real-Debrid Connected! Account: {user.get('username')} | Premium Status: {user.get('type')} (Expires: {user.get('expiration', 'N/A')})"
            })
        return jsonify({"success": False, "message": f"Invalid Key or Unauthorized (HTTP {r.status_code})"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error connecting to Real-Debrid: {str(e)}"})

if __name__ == "__main__":
    print("Starting Stremio Cloud Manager on http://localhost:7890")
    app.run(host="0.0.0.0", port=7890)
