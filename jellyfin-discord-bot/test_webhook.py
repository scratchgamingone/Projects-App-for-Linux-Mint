#!/usr/bin/env python3
"""
Test script to send a sample Now-Playing movie card to Discord,
demonstrating the exact format, stats, elapsed/remaining time, and 30-second update.
"""

import sys
import os
import time
from datetime import datetime, timezone
import requests
from monitor import (
    load_config,
    DiscordWebhookClient,
    build_discord_embed,
    TICKS_PER_SECOND
)

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cfg_file = os.path.join(base_dir, "config.json")
    config = load_config(cfg_file)

    webhook_url = config.get("discord_webhook_url", "").strip()
    if not webhook_url or "YOUR_DISCORD_WEBHOOK_URL_HERE" in webhook_url:
        print("[!] Please set your 'discord_webhook_url' in config.json before running this test.")
        print("    Example: https://discord.com/api/webhooks/1234567890/abcdef...")
        sys.exit(1)

    print(f"[*] Initializing Discord Webhook Client...")
    discord = DiscordWebhookClient(webhook_url)

    # Sample movie session (1 hour 15 minutes into a 2h 28m movie)
    runtime_sec = 8880   # 2h 28m (148 mins)
    current_sec = 4500   # 1h 15m (75 mins elapsed, 73 mins remaining)

    sample_session = {
        "Id": "test_session_demo",
        "UserName": "sam",
        "Client": "Jellyfin Web",
        "DeviceName": "Chrome on Linux Mint",
        "NowPlayingItem": {
            "Id": "demo_item_id",
            "Name": "Inception",
            "ProductionYear": 2010,
            "Overview": "Dom Cobb is a skilled thief, the absolute best in the dangerous art of extraction, stealing valuable secrets from deep within the subconscious during the dream state.",
            "Genres": ["Action", "Sci-Fi", "Adventure"],
            "OfficialRating": "PG-13",
            "CommunityRating": 8.8,
            "RunTimeTicks": runtime_sec * TICKS_PER_SECOND,
            "Container": "MKV",
            "Bitrate": 18_500_000,
            "MediaStreams": [
                {
                    "Type": "Video",
                    "Codec": "HEVC",
                    "Width": 3840,
                    "Height": 2160,
                    "BitRate": 17_000_000
                },
                {
                    "Type": "Audio",
                    "Codec": "DTS-HD MA",
                    "ChannelLayout": "5.1",
                    "BitRate": 1_509_000
                }
            ]
        },
        "PlayState": {
            "PositionTicks": current_sec * TICKS_PER_SECOND,
            "IsPaused": False,
            "PlayMethod": "DirectPlay"
        }
    }

    print("[*] Generating sample movie embed...")
    embed = build_discord_embed(
        session=sample_session,
        jellyfin_url="http://localhost:8096"
    )

    print("[*] Sending initial Now-Playing card to Discord...")
    msg_id, cdn_url = discord.post_initial(embed)
    if not msg_id:
        print("[x] Failed to send message to Discord. Please check your Webhook URL.")
        sys.exit(1)

    print(f"[✔] Successfully sent test message! Message ID: {msg_id}")
    print("[*] Waiting 5 seconds to demonstrate the 30-second live update mechanism...")
    time.sleep(5)

    # Simulate 30s elapsed: position moved to 4530 sec
    sample_session["PlayState"]["PositionTicks"] = (current_sec + 30) * TICKS_PER_SECOND
    updated_embed = build_discord_embed(
        session=sample_session,
        jellyfin_url="http://localhost:8096",
        cached_cdn_url=cdn_url
    )

    print("[*] Sending PATCH update to the existing Discord message...")
    ok = discord.patch_update(msg_id, updated_embed)
    if ok:
        print("[✔] Successfully updated existing message without creating duplicate messages!")
        print("\nAll tests passed! Your webhook integration is fully working.")
    else:
        print("[x] Could not update message.")

if __name__ == "__main__":
    main()
