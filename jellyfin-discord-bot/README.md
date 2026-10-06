# Jellyfin Discord Now-Playing Live Monitor

A live status updater that reports movie playback information to Discord via Webhooks.

## Features
- **Full Movie Details**: Title, Release Year, Plot summary, Genres, Official & Community Ratings (`⭐ 8.8/10`, `PG-13`), and direct web link.
- **Audio & Video Media Stats**: Resolution (`4K UHD`, `1080p FHD`), Video Codec (`HEVC`, `H.264`), Audio Codec & Channels (`DTS-HD MA 5.1`, `AAC`), Bitrate, Container format (`MKV`, `MP4`), and Playback Method (`Direct Play`, `Direct Stream`, or `Transcoding` with transcode reasons).
- **Elapsed & Remaining Time**:
  - Live visual progress bar `[████████░░░░░░] 52.4%`
  - Elapsed clock: `01:14:20` / Total: `02:28:45`
  - Minutes and hours elapsed: `1h 14m (74 mins)`
  - Minutes and hours left: `1h 14m left (74 mins left)`
  - Estimated finish time: e.g. `Est. Finish: 04:32 PM`
- **30-Second Live Updates**: Updates the exact same message in Discord via `PATCH` every 30 seconds instead of spamming new messages into the channel.
- **Poster Thumbnail**: Automatically extracts and embeds the movie's primary poster image.
- **Session Management**: Detects when playback pauses (`⏸️ PAUSED`), stops/finishes (`⏹️ STOPPED`), or switches movies.

---

## Quick Setup

### 1. Install Jellyfin (if not already installed)
Run the automated installer script:
```bash
sudo ./install_jellyfin.sh
```
Then open `http://localhost:8096` in your browser and complete the initial account and library setup.

### 2. Get your Jellyfin API Key
1. In the Jellyfin web client, click the **hamburger menu (☰)** or profile in the top-left/top-right.
2. Select **Dashboard** (under Administration).
3. In the sidebar under **Advanced**, click **API Keys**.
4. Click the **+** (Add) button, enter an App Name (e.g. `Discord Bot`), and copy the generated token.

### 3. Get your Discord Webhook URLs
1. In Discord, go to your Server Settings (or right-click the channel you want updates in) -> **Integrations** -> **Webhooks**.
2. Click **New Webhook**, name it (e.g., `Jellyfin Now Playing` or `New Movies`), choose the channel, and click **Copy Webhook URL**.
3. You can set up distinct webhooks for all 7 media categories:
   - **All Content Types** (Global upload feed)
   - **Movies**
   - **TV Shows / Series**
   - **TV Episodes**
   - **Music / Songs**
   - **Music Videos**
   - **Videos (Home Videos / Clips)**

### 4. Configure the Bot
Run the interactive configuration wizard:
```bash
python3 /home/sam/jellyfin-discord-bot/configure.py
```
Or edit `/home/sam/jellyfin-discord-bot/config.json` directly:
```json
{
  "jellyfin_url": "http://localhost:8096",
  "jellyfin_api_key": "YOUR_JELLYFIN_API_KEY_HERE",
  "discord_webhook_url": "https://discord.com/api/webhooks/...",
  "discord_webhook_all": "https://discord.com/api/webhooks/...",
  "discord_webhook_movies": "https://discord.com/api/webhooks/...",
  "discord_webhook_series": "https://discord.com/api/webhooks/...",
  "discord_webhook_episodes": "https://discord.com/api/webhooks/...",
  "discord_webhook_music": "https://discord.com/api/webhooks/...",
  "discord_webhook_music_videos": "https://discord.com/api/webhooks/...",
  "discord_webhook_videos": "https://discord.com/api/webhooks/...",
  "update_interval_seconds": 30,
  "user_filter": null,
  "delete_on_stop": false,
  "include_poster": true,
  "notify_new_movies": true,
  "notify_new_media": true
}
```

### 5. Test Webhook Delivery
To send a sample card to your Discord channel and verify the 30-second live update mechanism:
```bash
python3 /home/sam/jellyfin-discord-bot/test_webhook.py
```

### 6. Enable Background Service (Auto-start on boot)
To keep the monitor running 24/7 in the background:
```bash
systemctl --user enable --now jellyfin-discord.service
```
To check status or logs:
```bash
systemctl --user status jellyfin-discord.service
journalctl --user -u jellyfin-discord.service -f
```
