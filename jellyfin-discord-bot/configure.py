#!/usr/bin/env python3
"""
Interactive setup & configuration utility for Jellyfin Discord Bot.
"""

import os
import sys
import json
import argparse
import requests

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def read_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {
        "jellyfin_url": "http://localhost:8096",
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
        "notify_new_media": True
    }

def save_config(config):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    print(f"\n[✔] Configuration successfully saved to: {CONFIG_PATH}")

def test_jellyfin(url, api_key):
    print(f"[*] Testing connection to Jellyfin at {url}...")
    try:
        headers = {
            "Authorization": f'MediaBrowser Client="JellyScratch", Device="CLI", Version="1.0.0", Token="{api_key}"',
            "X-Emby-Token": api_key,
            "X-MediaBrowser-Token": api_key
        }
        r = requests.get(f"{url.rstrip('/')}/System/Info", headers=headers, timeout=5)
        if r.status_code == 200:
            info = r.json()
            server_name = info.get("ServerName", "Jellyfin")
            version = info.get("Version", "Unknown")
            print(f"[✔] Connected to Jellyfin! Server: '{server_name}' (v{version})")
            return True
        elif r.status_code == 401:
            print("[x] Error 401: Unauthorized. Please check your Jellyfin API Key.")
            return False
        else:
            print(f"[x] Error {r.status_code}: {r.text}")
            return False
    except Exception as e:
        print(f"[x] Connection failed: {e}")
        return False

def test_discord(webhook_url):
    print("[*] Testing Discord Webhook...")
    try:
        payload = {
            "embeds": [
                {
                    "title": "🎬 Jellyfin Discord Bot Connected",
                    "description": "Discord webhook connection verified successfully! Your bot is ready to track active movies.",
                    "color": 0x00A4DC
                }
            ]
        }
        r = requests.post(webhook_url, json=payload, timeout=5)
        if r.status_code in (200, 204):
            print("[✔] Discord webhook test message sent successfully!")
            return True
        else:
            print(f"[x] Discord webhook failed: {r.status_code} - {r.text}")
            return False
    except Exception as e:
        print(f"[x] Failed to reach Discord: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Configure Jellyfin Discord Bot")
    parser.add_argument("--url", help="Jellyfin server URL (default: http://localhost:8096)")
    parser.add_argument("--api-key", help="Jellyfin API key")
    parser.add_argument("--webhook", help="Live Playback Discord Webhook URL")
    parser.add_argument("--webhook-all", help="All Content Types Upload Webhook URL")
    parser.add_argument("--webhook-movies", help="Movies Upload Webhook URL")
    parser.add_argument("--webhook-series", help="TV Shows/Series Upload Webhook URL")
    parser.add_argument("--webhook-episodes", help="TV Episodes Upload Webhook URL")
    parser.add_argument("--webhook-music", help="Music/Audio Upload Webhook URL")
    parser.add_argument("--webhook-music-videos", help="Music Videos Upload Webhook URL")
    parser.add_argument("--webhook-videos", help="Videos/Clips Upload Webhook URL")
    parser.add_argument("--interval", type=int, help="Update interval in seconds (default: 30)")
    parser.add_argument("--test", action="store_true", help="Test current configuration")
    args = parser.parse_args()

    config = read_config()

    if args.url:
        config["jellyfin_url"] = args.url
    if args.api_key:
        config["jellyfin_api_key"] = args.api_key
    if args.webhook:
        config["discord_webhook_url"] = args.webhook
    if args.webhook_all:
        config["discord_webhook_all"] = args.webhook_all
        config["discord_new_media_webhook_url"] = args.webhook_all
    if args.webhook_movies:
        config["discord_webhook_movies"] = args.webhook_movies
    if args.webhook_series:
        config["discord_webhook_series"] = args.webhook_series
    if args.webhook_episodes:
        config["discord_webhook_episodes"] = args.webhook_episodes
    if args.webhook_music:
        config["discord_webhook_music"] = args.webhook_music
    if args.webhook_music_videos:
        config["discord_webhook_music_videos"] = args.webhook_music_videos
    if args.webhook_videos:
        config["discord_webhook_videos"] = args.webhook_videos
    if args.interval:
        config["update_interval_seconds"] = args.interval

    # If no flags provided and not just testing, run interactive prompt
    has_any_flag = any([
        args.url, args.api_key, args.webhook, args.webhook_all, args.webhook_movies,
        args.webhook_series, args.webhook_episodes, args.webhook_music,
        args.webhook_music_videos, args.webhook_videos, args.interval, args.test
    ])

    if not has_any_flag:
        print("=" * 60)
        print("     Jellyfin Discord Bot Configuration Wizard")
        print("=" * 60)

        current_url = config.get("jellyfin_url", "http://localhost:8096")
        url_input = input(f"Enter Jellyfin URL [{current_url}]: ").strip()
        if url_input:
            config["jellyfin_url"] = url_input

        current_key = config.get("jellyfin_api_key", "")
        key_prompt = f"Enter Jellyfin API Key [{current_key[:8]}...]: " if current_key and current_key != "YOUR_JELLYFIN_API_KEY_HERE" else "Enter Jellyfin API Key: "
        key_input = input(key_prompt).strip()
        if key_input:
            config["jellyfin_api_key"] = key_input

        current_webhook = config.get("discord_webhook_url", "")
        wh_prompt = f"Enter Live Playback Webhook URL [{current_webhook[:25]}...]: " if current_webhook and current_webhook != "YOUR_DISCORD_WEBHOOK_URL_HERE" else "Enter Live Playback Webhook URL: "
        wh_input = input(wh_prompt).strip()
        if wh_input:
            config["discord_webhook_url"] = wh_input

        print("\n--- 7 Upload Content Type Webhooks (Leave blank to skip) ---")
        prompt_types = [
            ("All Content Types", "discord_webhook_all", "discord_new_media_webhook_url"),
            ("Movies", "discord_webhook_movies", None),
            ("TV Shows / Series", "discord_webhook_series", None),
            ("TV Episodes", "discord_webhook_episodes", None),
            ("Music / Songs", "discord_webhook_music", None),
            ("Music Videos", "discord_webhook_music_videos", None),
            ("Videos / Clips", "discord_webhook_videos", None)
        ]
        for name, key, alt_key in prompt_types:
            curr_val = config.get(key) or (config.get(alt_key) if alt_key else "") or ""
            val_display = f"[{curr_val[:25]}...]" if curr_val else "[None]"
            ans = input(f"Enter {name} Webhook URL {val_display}: ").strip()
            if ans:
                config[key] = ans
                if key == "discord_webhook_all":
                    config["discord_new_media_webhook_url"] = ans

        save_config(config)

        if config["jellyfin_api_key"] and config["jellyfin_api_key"] != "YOUR_JELLYFIN_API_KEY_HERE":
            test_jellyfin(config["jellyfin_url"], config["jellyfin_api_key"])
        if config["discord_webhook_url"] and config["discord_webhook_url"] != "YOUR_DISCORD_WEBHOOK_URL_HERE":
            test_discord(config["discord_webhook_url"])
    elif args.test:
        print("[*] Testing configured services...")
        test_jellyfin(config["jellyfin_url"], config.get("jellyfin_api_key", ""))
        test_discord(config.get("discord_webhook_url", ""))
    else:
        save_config(config)

if __name__ == "__main__":
    main()
