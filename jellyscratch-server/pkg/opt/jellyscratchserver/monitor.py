#!/usr/bin/env python3
"""
Jellyfin Discord Now-Playing & Media Library Monitor
Live status updater that reports movie playback information, audio/video stats,
elapsed time, minutes and hours remaining (updated every 30s), AND automatically
detects and announces newly scanned/uploaded media (movies, videos, TV shows, episodes, music)
via Discord webhooks.
"""

import os
import sys
import re
import time
import json
import logging
import signal
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple, Set
import requests

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("JellyfinDiscordBot")

TICKS_PER_SECOND = 10_000_000


def load_config(config_path: str) -> dict:
    if not os.path.exists(config_path):
        logger.error(f"Configuration file not found at: {config_path}")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def ticks_to_seconds(ticks: Optional[int]) -> float:
    if not ticks:
        return 0.0
    return float(ticks) / TICKS_PER_SECOND


def format_duration_clock(seconds: float) -> str:
    """Format seconds into HH:MM:SS or MM:SS."""
    sec = max(0, int(seconds))
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def format_duration_human(seconds: float) -> str:
    """Format seconds into human readable 'Xh Ym' or 'Ym'."""
    sec = max(0, int(seconds))
    h = sec // 3600
    m = (sec % 3600) // 60
    if h > 0 and m > 0:
        return f"{h}h {m}m"
    elif h > 0:
        return f"{h}h"
    elif m > 0:
        return f"{m}m"
    return f"{sec}s"


def format_remaining_detail(remaining_seconds: float) -> str:
    """Returns detailed remaining time string, e.g., '1h 14m left (74 minutes left)'."""
    rem = max(0, int(remaining_seconds))
    total_minutes = rem // 60
    h = rem // 3600
    m = (rem % 3600) // 60

    if h > 0:
        return f"**{h}h {m:02d}m left** ({total_minutes} mins left)"
    elif total_minutes > 0:
        return f"**{total_minutes} mins left**"
    else:
        return f"**{rem}s left** (Finishing up)"


def make_progress_bar(current_sec: float, total_sec: float, length: int = 15) -> Tuple[str, float]:
    """Generate visual ASCII progress bar and percentage."""
    if total_sec <= 0:
        return "`[───────────────]`", 0.0
    ratio = min(max(current_sec / total_sec, 0.0), 1.0)
    filled = int(round(ratio * length))
    empty = length - filled
    bar = "█" * filled + "░" * empty
    percent = ratio * 100.0
    return f"`[{bar}]`", percent


def format_bitrate(bps: Optional[int]) -> str:
    if not bps:
        return "N/A"
    mbps = bps / 1_000_000.0
    if mbps >= 1.0:
        return f"{mbps:.1f} Mbps"
    kbps = bps / 1_000.0
    return f"{int(kbps)} kbps"


def parse_webhook_url(url: str) -> Optional[Tuple[str, str]]:
    """Extract webhook ID and token from URL."""
    match = re.search(r"/webhooks/(\d+)/([a-zA-Z0-9_\-]+)", url)
    if match:
        return match.group(1), match.group(2)
    return None


class JellyfinClient:
    DEFAULT_MEDIA_TYPES = "Movie,Series,Episode,Video,MusicVideo,Audio,Book"

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()
        # Jellyfin 10.9+, 10.10+, and 12.x require Authorization: MediaBrowser Token="..."
        # Legacy Jellyfin / Emby uses X-Emby-Token or X-MediaBrowser-Token
        # Supply all for maximum compatibility across versions
        self.session.headers.update({
            "Authorization": f'MediaBrowser Client="JellyScratch", Device="Server", DeviceId="JellyScratchServer", Version="1.0.0", Token="{self.api_key}"',
            "X-Emby-Token": self.api_key,
            "X-MediaBrowser-Token": self.api_key,
            "Accept": "application/json"
        })

    def get_sessions(self) -> list:
        url = f"{self.base_url}/Sessions"
        resp = self.session.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_image_bytes(self, item_id: str, image_type: str = "Primary", max_width: int = 400) -> Optional[bytes]:
        url = f"{self.base_url}/Items/{item_id}/Images/{image_type}"
        params = {"maxWidth": max_width, "quality": 85}
        try:
            resp = self.session.get(url, params=params, timeout=10)
            if resp.status_code == 200 and resp.content:
                return resp.content
        except Exception as e:
            logger.debug(f"Could not fetch image for {item_id}: {e}")
        return None

    def get_latest_items(self, limit: int = 100, item_types: Optional[str] = None) -> list:
        """Fetch latest items added to the Jellyfin library across media types."""
        url = f"{self.base_url}/Items"
        types = item_types if item_types is not None else self.DEFAULT_MEDIA_TYPES
        params = {
            "sortBy": "DateCreated",
            "sortOrder": "Descending",
            "includeItemTypes": types,
            "recursive": "true",
            "fields": "Overview,Genres,ProductionYear,OfficialRating,CommunityRating,MediaStreams,DateCreated,RunTimeTicks,Container,Type,ParentIndexNumber,IndexNumber,SeriesName,SeasonName,Artists,Album,SeriesId,ParentPrimaryImageItemId,ParentThumbItemId",
            "limit": limit
        }
        try:
            resp = self.session.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("Items", [])
            else:
                logger.warning(f"Jellyfin /Items response: {resp.status_code} - {resp.text[:100]}")
        except Exception as e:
            logger.error(f"Error fetching latest items from Jellyfin: {e}")
        return []

    def get_all_library_item_ids(self) -> Set[str]:
        """Fetch all existing item IDs across all media types in the library."""
        url = f"{self.base_url}/Items"
        params = {
            "recursive": "true",
            "includeItemTypes": self.DEFAULT_MEDIA_TYPES,
            "fields": "Id",
            "limit": 10000
        }
        try:
            resp = self.session.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                return set(it.get("Id") for it in resp.json().get("Items", []) if it.get("Id"))
        except Exception as e:
            logger.error(f"Error fetching all library item IDs: {e}")
        return set()

    def get_library_scan_task(self) -> Optional[dict]:
        """Get the ScheduledTask object for Scan Media Library (RefreshLibrary)."""
        url = f"{self.base_url}/ScheduledTasks"
        try:
            resp = self.session.get(url, timeout=5)
            if resp.status_code == 200:
                for task in resp.json():
                    if task.get("Key") == "RefreshLibrary" or task.get("Name") == "Scan Media Library":
                        return task
        except Exception as e:
            logger.debug(f"Error checking library scan task: {e}")
        return None

    def trigger_library_scan(self) -> bool:
        """Trigger an immediate library scan on the Jellyfin server."""
        url = f"{self.base_url}/Library/Refresh"
        try:
            resp = self.session.post(url, timeout=5)
            return resp.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Failed to trigger library scan: {e}")
            return False


class DiscordWebhookClient:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        parsed = parse_webhook_url(webhook_url)
        if not parsed:
            raise ValueError(f"Invalid Discord Webhook URL: {webhook_url}")
        self.webhook_id, self.webhook_token = parsed
        self.base_api = f"https://discord.com/api/webhooks/{self.webhook_id}/{self.webhook_token}"

    def post_initial(self, embed: dict, image_bytes: Optional[bytes] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Creates the initial Discord message with rate-limiting retry support.
        Returns (message_id, cdn_attachment_url)
        """
        url = f"{self.base_api}?wait=true"
        payload_data = {"embeds": [embed]}

        for attempt in range(3):
            try:
                if image_bytes:
                    files = {
                        "file": ("poster.jpg", image_bytes, "image/jpeg")
                    }
                    resp = requests.post(
                        url,
                        data={"payload_json": json.dumps(payload_data)},
                        files=files,
                        timeout=15
                    )
                else:
                    resp = requests.post(url, json=payload_data, timeout=15)

                if resp.status_code in (200, 201):
                    data = resp.json()
                    msg_id = data.get("id")
                    cdn_url = None
                    attachments = data.get("attachments", [])
                    if attachments and "url" in attachments[0]:
                        cdn_url = attachments[0]["url"]
                    return msg_id, cdn_url
                elif resp.status_code == 429:
                    retry_after = resp.json().get("retry_after", 1.5)
                    logger.warning(f"Discord rate limit hit (429), retrying in {retry_after}s (attempt {attempt + 1}/3)...")
                    time.sleep(float(retry_after) + 0.2)
                    continue
                else:
                    logger.error(f"Failed to post Discord message: {resp.status_code} - {resp.text}")
                    break
            except Exception as e:
                logger.error(f"Exception posting initial message to Discord (attempt {attempt + 1}/3): {e}")
                time.sleep(1)
        return None, None

    def patch_update(self, message_id: str, embed: dict) -> bool:
        """Updates the existing Discord message with fresh embed content with retry support."""
        url = f"{self.base_api}/messages/{message_id}"
        payload = {"embeds": [embed]}
        for attempt in range(3):
            try:
                resp = requests.patch(url, json=payload, timeout=10)
                if resp.status_code == 200:
                    return True
                elif resp.status_code == 429:
                    retry_after = resp.json().get("retry_after", 1.0)
                    logger.warning(f"Discord rate limit hit, retry after {retry_after}s")
                    time.sleep(float(retry_after) + 0.2)
                    continue
                else:
                    logger.warning(f"Failed to update Discord message {message_id}: {resp.status_code} - {resp.text}")
                    break
            except Exception as e:
                logger.error(f"Exception updating Discord message: {e}")
                time.sleep(1)
        return False

    def delete_message(self, message_id: str) -> bool:
        """Deletes a Discord message."""
        url = f"{self.base_api}/messages/{message_id}"
        try:
            resp = requests.delete(url, timeout=10)
            return resp.status_code == 204
        except Exception as e:
            logger.error(f"Failed to delete Discord message {message_id}: {e}")
            return False


def build_media_stats(item: dict, session: dict) -> Tuple[str, str, str]:
    """
    Extracts stream stats: Resolution, Video Codec, Audio Codec, Bitrate, Play Method
    """
    streams = item.get("MediaStreams", [])
    video_stream = next((s for s in streams if s.get("Type") == "Video"), {})
    audio_stream = next((s for s in streams if s.get("Type") == "Audio"), {})

    # Resolution
    width = video_stream.get("Width")
    height = video_stream.get("Height")
    if height:
        if height >= 2160 or (width and width >= 3840):
            res_label = f"4K UHD ({width}x{height})"
        elif height >= 1080 or (width and width >= 1920):
            res_label = f"1080p FHD ({width}x{height})"
        elif height >= 720:
            res_label = f"720p HD ({width}x{height})"
        else:
            res_label = f"{height}p ({width}x{height})"
    else:
        res_label = "Standard Definition"

    # Video details
    v_codec = video_stream.get("Codec", "").upper()
    v_bitrate = format_bitrate(video_stream.get("BitRate"))
    video_summary = f"{v_codec} ({res_label}) @ {v_bitrate}" if v_codec else res_label

    # Audio details
    a_codec = audio_stream.get("Codec", "").upper()
    a_layout = audio_stream.get("ChannelLayout", "") or f"{audio_stream.get('Channels', '')} ch"
    a_bitrate = format_bitrate(audio_stream.get("BitRate"))
    audio_summary = f"{a_codec} {a_layout}".strip()
    if a_bitrate != "N/A":
        audio_summary += f" @ {a_bitrate}"

    # Playback Method
    play_state = session.get("PlayState", {})
    play_method = play_state.get("PlayMethod", "DirectPlay")
    transcode_info = session.get("TranscodingInfo")

    if play_method == "Transcode" and transcode_info:
        v_action = "Direct" if transcode_info.get("IsVideoDirect") else transcode_info.get("VideoCodec", "Transcode")
        a_action = "Direct" if transcode_info.get("IsAudioDirect") else transcode_info.get("AudioCodec", "Transcode")
        reasons = transcode_info.get("TranscodeReasons", [])
        reason_str = f" ({', '.join(reasons)})" if reasons else ""
        method_str = f"🔄 Transcoding [V: {v_action}, A: {a_action}]{reason_str}"
    elif play_method == "DirectStream":
        method_str = "⚡ Direct Stream"
    else:
        method_str = "🚀 Direct Play"

    return video_summary, audio_summary, method_str


def build_discord_embed(
    session: dict,
    jellyfin_url: str,
    status_override: Optional[str] = None,
    cached_cdn_url: Optional[str] = None,
    use_attachment_url: bool = False
) -> dict:
    """
    Builds the rich Discord Embed showing movie/media playback info, specs, elapsed/remaining time,
    progress bar, and viewer details.
    """
    item = session.get("NowPlayingItem", {})
    play_state = session.get("PlayState", {})

    title = item.get("Name", "Unknown Title")
    year = item.get("ProductionYear")
    item_type = item.get("Type", "Movie")
    is_episode = item_type == "Episode"

    if is_episode:
        series_name = item.get("SeriesName", "")
        season_num = item.get("ParentIndexNumber")
        ep_num = item.get("IndexNumber")
        if series_name and season_num is not None and ep_num is not None:
            title_display = f"📺 {series_name} - S{season_num:02d}E{ep_num:02d} - {title}"
        elif series_name:
            title_display = f"📺 {series_name} - {title}"
        else:
            title_display = f"📺 {title}"
    elif year:
        title_display = f"🎬 {title} ({year})"
    else:
        title_display = f"🎬 {title}"

    item_id = item.get("Id", "")
    item_url = f"{jellyfin_url}/web/index.html#!/details?id={item_id}" if item_id else None

    # Overview / Plot
    overview = item.get("Overview", "")
    if overview:
        if len(overview) > 280:
            overview = overview[:277] + "..."
    else:
        overview = "*No plot summary available.*"

    # Timing and Progress calculations
    runtime_ticks = item.get("RunTimeTicks", 0)
    position_ticks = play_state.get("PositionTicks", 0)

    total_sec = ticks_to_seconds(runtime_ticks)
    current_sec = ticks_to_seconds(position_ticks)
    remaining_sec = max(0, total_sec - current_sec)

    is_paused = play_state.get("IsPaused", False)

    # Determine status & color
    if status_override:
        status_text = status_override
        embed_color = 0x95A5A6  # Gray
    elif is_paused:
        status_text = "⏸️ PAUSED"
        embed_color = 0xF1C40F  # Amber / Yellow
    else:
        status_text = "▶️ NOW PLAYING"
        embed_color = 0x00A4DC  # Jellyfin Signature Cyan/Blue

    # Progress bar and percentages
    bar_str, percent = make_progress_bar(current_sec, total_sec, length=14)

    # Time strings
    current_clock = format_duration_clock(current_sec)
    total_clock = format_duration_clock(total_sec)
    current_human = format_duration_human(current_sec)
    total_human = format_duration_human(total_sec)
    current_minutes = int(current_sec // 60)
    total_minutes = int(total_sec // 60)
    remaining_detail = format_remaining_detail(remaining_sec)

    # Estimated Finish Time
    if remaining_sec > 0 and not is_paused and not status_override:
        finish_dt = datetime.now() + timedelta(seconds=remaining_sec)
        finish_str = finish_dt.strftime("%I:%M %p")
        eta_line = f"🏁 **Est. Finish:** {finish_str}\n"
    else:
        eta_line = ""

    progress_field_value = (
        f"{bar_str} **{percent:.1f}%**\n"
        f"⏱️ **Elapsed:** `{current_clock}` / `{total_clock}` ({current_human} / {current_minutes}m)\n"
        f"⏳ **Remaining:** {remaining_detail}\n"
        f"{eta_line}"
    )

    # Movie Stats
    video_summary, audio_summary, method_str = build_media_stats(item, session)
    container = item.get("Container", "").upper()
    total_bitrate = format_bitrate(item.get("Bitrate"))

    stats_field_value = (
        f"• **Playback:** {method_str}\n"
        f"• **Video:** {video_summary}\n"
        f"• **Audio:** {audio_summary}\n"
        f"• **Format:** {container} ({total_bitrate})"
    )

    # Movie Metadata
    genres = ", ".join(item.get("Genres", [])) or "N/A"
    community_rating = item.get("CommunityRating")
    official_rating = item.get("OfficialRating") or "Not Rated"

    rating_parts = [official_rating]
    if community_rating:
        rating_parts.append(f"⭐ {community_rating:.1f}/10")
    rating_str = " | ".join(rating_parts)

    info_field_value = (
        f"• **Genres:** {genres}\n"
        f"• **Rating:** {rating_str}\n"
        f"• **Total Length:** {total_human} ({total_minutes} mins)"
    )

    # Viewer & Client
    user_name = session.get("UserName", "Unknown")
    client_name = session.get("Client", "Jellyfin Client")
    device_name = session.get("DeviceName", "Device")
    viewer_field_value = f"👤 **{user_name}** watching on **{client_name}** ({device_name})"

    # Assemble Embed
    embed = {
        "title": title_display,
        "description": f"**Status:** `{status_text}`\n\n{overview}",
        "color": embed_color,
        "fields": [
            {
                "name": "⏱️ Time & Progress",
                "value": progress_field_value,
                "inline": False
            },
            {
                "name": "📊 Movie Media Stats",
                "value": stats_field_value,
                "inline": False
            },
            {
                "name": "🎬 Movie Info",
                "value": info_field_value,
                "inline": True
            },
            {
                "name": "👤 Viewer",
                "value": viewer_field_value,
                "inline": False
            }
        ],
        "footer": {
            "text": "Jellyfin Live Monitor • Updated every 30 seconds"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    if item_url:
        embed["url"] = item_url

    # Handle Thumbnail
    if use_attachment_url:
        embed["thumbnail"] = {"url": "attachment://poster.jpg"}
    elif cached_cdn_url:
        embed["thumbnail"] = {"url": cached_cdn_url}

    return embed


def build_new_media_embed(
    item: dict,
    jellyfin_url: str,
    use_attachment_url: bool = False,
    cached_cdn_url: Optional[str] = None
) -> dict:
    """
    Builds a rich Discord announcement embed when new media (Movie, TV Series, Episode, Video, Audio)
    is added to Jellyfin.
    """
    item_type = item.get("Type", "Movie")
    name = item.get("Name", "Unknown Title")
    year = item.get("ProductionYear")
    year_str = f" ({year})" if year else ""

    if item_type == "Episode":
        series_name = item.get("SeriesName", "")
        season_num = item.get("ParentIndexNumber")
        ep_num = item.get("IndexNumber")
        if series_name and season_num is not None and ep_num is not None:
            title_display = f"📺 {series_name} - S{season_num:02d}E{ep_num:02d} - {name}"
        elif series_name:
            title_display = f"📺 {series_name} - {name}"
        else:
            title_display = f"📺 {name}"
        type_label = "TV Episode"
        embed_color = 0x2ECC71  # Emerald Green
    elif item_type == "Series":
        title_display = f"📺 {name}{year_str}"
        type_label = "TV Series"
        embed_color = 0x3498DB  # Blue
    elif item_type == "Video":
        title_display = f"📹 {name}{year_str}"
        type_label = "Video"
        embed_color = 0xE67E22  # Orange
    elif item_type == "MusicVideo":
        title_display = f"🎬 {name}{year_str}"
        type_label = "Music Video"
        embed_color = 0xE91E63  # Pink
    elif item_type == "Audio":
        artists = ", ".join(item.get("Artists", []))
        title_display = f"🎵 {artists} - {name}" if artists else f"🎵 {name}"
        type_label = "Music Track"
        embed_color = 0x1ABC9C  # Teal
    elif item_type == "Book":
        title_display = f"📚 {name}{year_str}"
        type_label = "Book / Audiobook"
        embed_color = 0x8E44AD  # Purple
    else:  # Movie or default
        title_display = f"🎬 {name}{year_str}"
        type_label = "Movie"
        embed_color = 0x9B59B6  # Purple

    item_id = item.get("Id", "")
    item_url = f"{jellyfin_url}/web/index.html#!/details?id={item_id}" if item_id else None

    # Overview
    overview = item.get("Overview", "")
    if overview:
        if len(overview) > 350:
            overview = overview[:347] + "..."
    else:
        overview = "*No summary available.*"

    # Runtime
    runtime_ticks = item.get("RunTimeTicks", 0)
    runtime_sec = ticks_to_seconds(runtime_ticks)
    runtime_str = format_duration_human(runtime_sec)
    runtime_mins = int(runtime_sec // 60)
    runtime_display = f"{runtime_str} ({runtime_mins} mins)" if runtime_sec > 0 else "N/A"

    # Rating
    community_rating = item.get("CommunityRating")
    official_rating = item.get("OfficialRating") or "Not Rated"
    rating_parts = [official_rating]
    if community_rating:
        rating_parts.append(f"⭐ {community_rating:.1f}/10")
    rating_str = " | ".join(rating_parts)

    # Genres
    genres = ", ".join(item.get("Genres", [])) or "N/A"

    # Video details
    streams = item.get("MediaStreams", [])
    video_stream = next((s for s in streams if s.get("Type") == "Video"), {})
    width = video_stream.get("Width")
    height = video_stream.get("Height")
    if height:
        if height >= 2160 or (width and width >= 3840):
            res_label = "4K UHD"
        elif height >= 1080 or (width and width >= 1920):
            res_label = "1080p FHD"
        elif height >= 720:
            res_label = "720p HD"
        else:
            res_label = f"{height}p"
    else:
        res_label = "HD" if streams else "Standard"

    codec = video_stream.get("Codec", "").upper()
    container = item.get("Container", "").upper()
    format_parts = [p for p in [res_label, codec, container] if p]
    format_str = " • ".join(format_parts) if format_parts else "Standard"

    fields = [
        {"name": "🎭 Genres", "value": genres, "inline": True},
        {"name": "⏱️ Runtime", "value": runtime_display, "inline": True},
        {"name": "⭐ Rating", "value": rating_str, "inline": True},
        {"name": "🎞️ Format", "value": format_str, "inline": True}
    ]

    if item_type == "Episode" and item.get("SeriesName"):
        season_name = item.get("SeasonName") or (f"Season {item.get('ParentIndexNumber')}" if item.get("ParentIndexNumber") is not None else "")
        series_val = f"**{item.get('SeriesName')}**" + (f" ({season_name})" if season_name else "")
        fields.insert(0, {
            "name": "📺 Series & Season",
            "value": series_val,
            "inline": False
        })

    embed = {
        "title": title_display,
        "description": f"🎉 **New {type_label} Added to Jellyfin!**\n\n{overview}",
        "color": embed_color,
        "fields": fields,
        "footer": {
            "text": "JellyScratch Server • Library Integration"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    if item_url:
        embed["url"] = item_url

    if use_attachment_url:
        embed["thumbnail"] = {"url": "attachment://poster.jpg"}
    elif cached_cdn_url:
        embed["thumbnail"] = {"url": cached_cdn_url}

    return embed


# Backward compatibility alias
build_new_movie_embed = build_new_media_embed


def build_batch_episodes_embed(
    series_name: str,
    episodes: list,
    jellyfin_url: str,
    season_name: Optional[str] = None,
    use_attachment_url: bool = False,
    cached_cdn_url: Optional[str] = None
) -> dict:
    """
    Builds a clean, grouped announcement card when multiple episodes (>5) are added in a single scan.
    Prevents Discord rate-limits and channel flooding.
    """
    ep_count = len(episodes)
    season_display = season_name or (episodes[0].get("SeasonName") if episodes else "")
    title_display = f"📺 {series_name} - {ep_count} New Episodes Added"

    lines = []
    for ep in episodes[:10]:
        s_num = ep.get("ParentIndexNumber")
        e_num = ep.get("IndexNumber")
        ep_name = ep.get("Name", "Episode")
        if s_num is not None and e_num is not None:
            lines.append(f"• **S{s_num:02d}E{e_num:02d}**: {ep_name}")
        else:
            lines.append(f"• {ep_name}")
    if ep_count > 10:
        lines.append(f"*...and {ep_count - 10} more episodes*")

    ep_list_str = "\n".join(lines)
    desc = f"🎉 **{ep_count} New Episodes Added to Jellyfin!**\n\n{ep_list_str}"

    fields = [
        {"name": "📺 Show", "value": series_name, "inline": True},
        {"name": "🔢 Count", "value": f"{ep_count} Episodes", "inline": True}
    ]
    if season_display:
        fields.insert(1, {"name": "📂 Season", "value": season_display, "inline": True})

    embed = {
        "title": title_display,
        "description": desc,
        "color": 0x3498DB,
        "fields": fields,
        "footer": {"text": "JellyScratch Server • Library Integration"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    series_id = episodes[0].get("SeriesId") if episodes else None
    if series_id:
        embed["url"] = f"{jellyfin_url}/web/index.html#!/details?id={series_id}"

    if use_attachment_url:
        embed["thumbnail"] = {"url": "attachment://poster.jpg"}
    elif cached_cdn_url:
        embed["thumbnail"] = {"url": cached_cdn_url}

    return embed


def build_sample_embed_for_type(item_type: str, jellyfin_url: str = "http://localhost:8096") -> dict:
    """Generates a rich sample embed for testing each specific content type webhook."""
    t = (item_type or "").strip()
    base_url = (jellyfin_url or "http://localhost:8096").rstrip("/")
    if t.lower() in ("all", "all_content", "all_media"):
        return {
            "title": "🌐 JellyScratch Server - All Content Types Feed Connected",
            "description": "🎉 **All Content Types Discord Webhook Verified!**\n\nWhenever new movies, TV shows, episodes, music, music videos, or clips are uploaded, announcements will be posted here.",
            "color": 0x00A4DC,
            "fields": [
                {"name": "📡 Channel Role", "value": "All Content Types (Global Feed)", "inline": True},
                {"name": "⚡ Status", "value": "🟢 Connected & Active", "inline": True},
                {"name": "🔔 Automation", "value": "Real-time sync on library scan & file upload", "inline": False}
            ],
            "footer": {"text": "JellyScratch Server • Library Integration"},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    elif t == "Movie":
        sample = {
            "Type": "Movie",
            "Name": "Interstellar",
            "ProductionYear": 2014,
            "Overview": "A team of explorers travel through a wormhole in space in an attempt to ensure humanity's survival.",
            "Genres": ["Adventure", "Drama", "Sci-Fi"],
            "CommunityRating": 8.7,
            "OfficialRating": "PG-13",
            "RunTimeTicks": 101400000000,
            "MediaStreams": [{"Type": "Video", "Width": 3840, "Height": 2160, "Codec": "HEVC"}],
            "Container": "MKV"
        }
        return build_new_media_embed(sample, base_url)
    elif t == "Series":
        sample = {
            "Type": "Series",
            "Name": "The Flash",
            "ProductionYear": 2014,
            "Overview": "After a particle accelerator causes a freak storm, CSI investigator Barry Allen is struck by lightning and awakens with superhuman speed.",
            "Genres": ["Action", "Adventure", "Drama", "Sci-Fi"],
            "CommunityRating": 8.5,
            "OfficialRating": "TV-PG",
            "MediaStreams": [{"Type": "Video", "Width": 1920, "Height": 1080, "Codec": "H264"}],
            "Container": "MKV"
        }
        return build_new_media_embed(sample, base_url)
    elif t == "Episode":
        sample = {
            "Type": "Episode",
            "Name": "Pilot",
            "SeriesName": "The Flash",
            "SeasonName": "Season 1",
            "ParentIndexNumber": 1,
            "IndexNumber": 1,
            "ProductionYear": 2014,
            "Overview": "Barry Allen, a forensic crime scene assistant for Central City Police Department, is struck by lightning during a particle accelerator explosion and gains superhuman speed.",
            "Genres": ["Action", "Sci-Fi"],
            "CommunityRating": 8.5,
            "OfficialRating": "TV-PG",
            "RunTimeTicks": 26400000000,
            "MediaStreams": [{"Type": "Video", "Width": 1280, "Height": 720, "Codec": "HEVC"}],
            "Container": "MKV"
        }
        return build_new_media_embed(sample, base_url)
    elif t in ("Audio", "Music"):
        sample = {
            "Type": "Audio",
            "Name": "Get Lucky",
            "Artists": ["Daft Punk", "Pharrell Williams"],
            "Album": "Random Access Memories",
            "ProductionYear": 2013,
            "Overview": "Lead single from Daft Punk's fourth studio album, Random Access Memories.",
            "Genres": ["Electronic", "Disco", "Funk"],
            "CommunityRating": 9.2,
            "RunTimeTicks": 2480000000,
            "Container": "FLAC"
        }
        return build_new_media_embed(sample, base_url)
    elif t in ("MusicVideo", "Music_Video"):
        sample = {
            "Type": "MusicVideo",
            "Name": "Bohemian Rhapsody",
            "Artists": ["Queen"],
            "ProductionYear": 1975,
            "Overview": "The official promotional music video for Queen's classic masterpiece Bohemian Rhapsody.",
            "Genres": ["Rock", "Opera Rock"],
            "CommunityRating": 9.6,
            "RunTimeTicks": 3550000000,
            "MediaStreams": [{"Type": "Video", "Width": 1920, "Height": 1080, "Codec": "AVC"}],
            "Container": "MP4"
        }
        return build_new_media_embed(sample, base_url)
    elif t in ("Video", "Videos"):
        sample = {
            "Type": "Video",
            "Name": "Summer Road Trip 2026",
            "ProductionYear": 2026,
            "Overview": "Personal 4K UHD video recording from our summer mountain drive.",
            "Genres": ["Home Videos"],
            "RunTimeTicks": 11120000000,
            "MediaStreams": [{"Type": "Video", "Width": 3840, "Height": 2160, "Codec": "HEVC"}],
            "Container": "MP4"
        }
        return build_new_media_embed(sample, base_url)
    elif t == "Book":
        sample = {
            "Type": "Book",
            "Name": "Dune",
            "ProductionYear": 1965,
            "Overview": "Set on the desert planet Arrakis, Dune is the story of Paul Atreides, heir to a noble family tasked with ruling an inhospitable world.",
            "Genres": ["Sci-Fi", "Classic Literature"],
            "CommunityRating": 9.3
        }
        return build_new_media_embed(sample, base_url)
    else:
        sample = {
            "Type": t,
            "Name": f"Sample {t}",
            "Overview": f"Sample announcement embed for {t}.",
            "Genres": ["Media"]
        }
        return build_new_media_embed(sample, base_url)


class MonitorDaemon:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = load_config(config_path)
        self.jellyfin_url = self.config.get("jellyfin_url", "http://localhost:8096").rstrip("/")
        self.api_key = self.config.get("jellyfin_api_key", "")
        self.notify_new_media = self.config.get("notify_new_media", self.config.get("notify_new_movies", True))
        self.notify_new_movies = self.notify_new_media
        self.update_interval = max(5, int(self.config.get("update_interval_seconds", 30)))
        self.user_filter = self.config.get("user_filter")
        self.delete_on_stop = self.config.get("delete_on_stop", False)
        self.include_poster = self.config.get("include_poster", True)

        self.jf = JellyfinClient(self.jellyfin_url, self.api_key)

        # 1. Live playback status webhook (Now-Playing channel)
        self.webhook_url = self.config.get("discord_webhook_url", "").strip()

        # 2. 7 Content Type Upload Webhooks (Whenever new media is uploaded):
        # (1) All Content Types (with backward-compatibility fallback to discord_new_media_webhook_url)
        self.webhook_all = (
            self.config.get("discord_webhook_all")
            or self.config.get("discord_new_media_webhook_url")
            or ""
        ).strip()
        self.new_media_webhook_url = self.webhook_all  # backward compatibility alias

        # (2) Movies Webhook
        self.webhook_movies = self.config.get("discord_webhook_movies", "").strip()
        # (3) TV Shows / Series Webhook
        self.webhook_series = (
            self.config.get("discord_webhook_series")
            or self.config.get("discord_webhook_shows")
            or ""
        ).strip()
        # (4) TV Episodes Webhook
        self.webhook_episodes = self.config.get("discord_webhook_episodes", "").strip()
        # (5) Music / Audio Webhook
        self.webhook_music = (
            self.config.get("discord_webhook_music")
            or self.config.get("discord_webhook_audio")
            or ""
        ).strip()
        # (6) Music Videos Webhook
        self.webhook_music_videos = self.config.get("discord_webhook_music_videos", "").strip()
        # (7) Standalone Videos Webhook
        self.webhook_videos = self.config.get("discord_webhook_videos", "").strip()

        # Cache DiscordWebhookClient instances by URL to reuse connections and avoid duplicates
        self._url_clients: Dict[str, DiscordWebhookClient] = {}

        def get_or_create_client(url: str) -> Optional[DiscordWebhookClient]:
            if not url or not url.startswith("http"):
                return None
            if url not in self._url_clients:
                try:
                    self._url_clients[url] = DiscordWebhookClient(url)
                except Exception as e:
                    logger.error(f"Invalid Webhook URL ({url[:35]}...): {e}")
                    return None
            return self._url_clients[url]

        self.client_playback = get_or_create_client(self.webhook_url)
        self.discord = self.client_playback  # backward compatibility alias

        self.client_all = get_or_create_client(self.webhook_all)
        self.new_media_discord = self.client_all  # backward compatibility alias

        self.client_movies = get_or_create_client(self.webhook_movies)
        self.client_series = get_or_create_client(self.webhook_series)
        self.client_episodes = get_or_create_client(self.webhook_episodes)
        self.client_music = get_or_create_client(self.webhook_music)
        self.client_music_videos = get_or_create_client(self.webhook_music_videos)
        self.client_videos = get_or_create_client(self.webhook_videos)

    def get_webhook_clients_for_type(self, item_type: str) -> list:
        """
        Returns list of DiscordWebhookClient instances that should receive announcements
        for the given item type. Includes both specific type webhook and All Content Types webhook,
        deduplicated so identical URLs are never messaged twice.
        """
        t = (item_type or "").strip()
        targets = []

        type_client = None
        if t == "Movie":
            type_client = self.client_movies
        elif t == "Series":
            type_client = self.client_series
        elif t == "Episode":
            type_client = self.client_episodes or self.client_series
        elif t in ("Audio", "Music"):
            type_client = self.client_music
        elif t in ("MusicVideo", "Music_Video"):
            type_client = self.client_music_videos or self.client_music
        elif t in ("Video", "Videos"):
            type_client = self.client_videos

        if type_client:
            targets.append(type_client)

        if self.client_all:
            targets.append(self.client_all)

        # De-duplicate by webhook URL so identical URLs are never messaged twice
        unique_targets = []
        seen_urls = set()
        for c in targets:
            if c and c.webhook_url and c.webhook_url not in seen_urls:
                seen_urls.add(c.webhook_url)
                unique_targets.append(c)

        return unique_targets

    def has_any_upload_webhook(self) -> bool:
        return bool(
            self.client_all
            or self.client_movies
            or self.client_series
            or self.client_episodes
            or self.client_music
            or self.client_music_videos
            or self.client_videos
        )

        # Track active playback sessions:
        # session_id -> { "message_id", "item_id", "cdn_url", "last_session", "last_update_time" }
        self.active_tracks: Dict[str, dict] = {}
        self.running = True

        # Track seen media items so only newly added items trigger notifications
        config_dir = Path(config_path).parent
        self.seen_media_file = config_dir / "seen_media_ids.json"
        self.seen_media_ids: Set[str] = self._load_seen_media_ids()

        # Track scheduled tasks for instant scan detection
        self.last_scan_end_time = None
        self.last_scan_state = "Idle"

        self._init_seen_media_baseline()

    def _load_seen_media_ids(self) -> Set[str]:
        try:
            if self.seen_media_file.exists():
                with open(self.seen_media_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return set(data.get("seen_ids", []))
        except Exception as e:
            logger.warning(f"Could not load seen media IDs: {e}")
        return set()

    def _save_seen_media_ids(self):
        try:
            with open(self.seen_media_file, "w", encoding="utf-8") as f:
                json.dump({"seen_ids": list(self.seen_media_ids)}, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save seen media IDs: {e}")

    def _init_seen_media_baseline(self):
        """Populate existing library IDs so newly added items trigger announcements."""
        if not self.seen_media_ids and self.api_key:
            try:
                all_ids = self.jf.get_all_library_item_ids()
                if not all_ids:
                    return

                # If seen_media_ids.json did not exist, check how old items are.
                # If library items are older than 24 hours, baseline them.
                # If items are recent uploads (from today), keep them unbaselined so check_new_media announces them!
                recent_items = self.jf.get_latest_items(limit=100)
                now_utc = datetime.now(timezone.utc)
                recent_ids = set()

                for item in recent_items:
                    dc_str = item.get("DateCreated")
                    if dc_str:
                        try:
                            clean_str = dc_str.rstrip("Z")
                            if "." in clean_str:
                                base_part, frac_part = clean_str.split(".", 1)
                                frac_part = (frac_part + "000000")[:6]
                                dt = datetime.fromisoformat(f"{base_part}.{frac_part}").replace(tzinfo=timezone.utc)
                            else:
                                dt = datetime.fromisoformat(clean_str).replace(tzinfo=timezone.utc)

                            if (now_utc - dt).total_seconds() < 86400:
                                recent_ids.add(item.get("Id"))
                        except Exception:
                            pass

                if recent_ids and len(recent_ids) < len(all_ids):
                    self.seen_media_ids = all_ids - recent_ids
                    self._save_seen_media_ids()
                    logger.info(f"Initialized baseline with {len(self.seen_media_ids)} existing items. Found {len(recent_ids)} recent items to announce.")
                elif not recent_ids and len(all_ids) > 0:
                    # All items are older than 24h: baseline all
                    self.seen_media_ids = all_ids
                    self._save_seen_media_ids()
                    logger.info(f"Initialized baseline with {len(self.seen_media_ids)} existing library items.")
                else:
                    # All items were uploaded today: keep seen_media_ids empty so first cycle announces them!
                    logger.info(f"Detected {len(all_ids)} freshly uploaded library items. Ready to announce on first cycle.")
            except Exception as e:
                logger.debug(f"Baseline initialization deferred: {e}")

    def stop(self):
        self.running = False

    def _announce_single_item(self, item: dict):
        item_id = item.get("Id")
        item_name = item.get("Name", "Unknown")
        item_type = item.get("Type", "Media")

        clients = self.get_webhook_clients_for_type(item_type)
        if not clients:
            logger.debug(f"No webhooks configured for {item_type} ('{item_name}'). Skipping.")
            self.seen_media_ids.add(item_id)
            return

        logger.info(f"📢 Detected new {item_type} added: '{item_name}' (ID: {item_id})")

        image_bytes = None
        if self.include_poster and item_id:
            image_bytes = self.jf.get_image_bytes(item_id, max_width=400)
            if not image_bytes and item.get("SeriesId"):
                image_bytes = self.jf.get_image_bytes(item["SeriesId"], max_width=400)
            if not image_bytes and item.get("ParentPrimaryImageItemId"):
                image_bytes = self.jf.get_image_bytes(item["ParentPrimaryImageItemId"], max_width=400)

        embed = build_new_media_embed(
            item=item,
            jellyfin_url=self.jellyfin_url,
            use_attachment_url=bool(image_bytes)
        )

        for client in clients:
            try:
                msg_id, _ = client.post_initial(embed, image_bytes=image_bytes)
                if msg_id:
                    logger.info(f"✔ Successfully posted new {item_type} announcement to Discord: '{item_name}'")
            except Exception as e:
                logger.error(f"Error posting announcement to Discord webhook: {e}")

        self.seen_media_ids.add(item_id)

    def _announce_batch_episodes(self, series_name: str, eps: list):
        clients = self.get_webhook_clients_for_type("Episode")
        if not clients:
            for ep in eps:
                if ep.get("Id"):
                    self.seen_media_ids.add(ep["Id"])
            return

        logger.info(f"📢 Announcing batch of {len(eps)} new episodes for '{series_name}'")
        first_ep = eps[0]
        image_bytes = None
        if self.include_poster:
            series_id = first_ep.get("SeriesId")
            if series_id:
                image_bytes = self.jf.get_image_bytes(series_id, max_width=400)
            if not image_bytes and first_ep.get("Id"):
                image_bytes = self.jf.get_image_bytes(first_ep["Id"], max_width=400)

        embed = build_batch_episodes_embed(
            series_name=series_name,
            episodes=eps,
            jellyfin_url=self.jellyfin_url,
            use_attachment_url=bool(image_bytes)
        )

        for client in clients:
            try:
                msg_id, _ = client.post_initial(embed, image_bytes=image_bytes)
                if msg_id:
                    logger.info(f"✔ Successfully posted batch episode announcement to Discord for '{series_name}' ({len(eps)} episodes)")
            except Exception as e:
                logger.error(f"Error posting batch episodes announcement to Discord: {e}")

        for ep in eps:
            if ep.get("Id"):
                self.seen_media_ids.add(ep["Id"])

    def check_new_media(self):
        """Checks for newly added media (movies, series, episodes, videos, music videos, music) and posts announcements to Discord."""
        if not self.notify_new_media or not self.has_any_upload_webhook() or not self.api_key:
            return

        try:
            items = self.jf.get_latest_items(limit=100)
        except Exception as e:
            logger.debug(f"Error checking new media: {e}")
            return

        if not items:
            return

        new_items = [it for it in items if it.get("Id") and it.get("Id") not in self.seen_media_ids]
        if not new_items:
            return

        logger.info(f"Found {len(new_items)} new media item(s) to announce.")

        series_items = [it for it in new_items if it.get("Type") == "Series"]
        movie_items = [it for it in new_items if it.get("Type") == "Movie"]
        video_items = [it for it in new_items if it.get("Type") == "Video"]
        music_video_items = [it for it in new_items if it.get("Type") == "MusicVideo"]
        audio_items = [it for it in new_items if it.get("Type") == "Audio"]
        episode_items = [it for it in new_items if it.get("Type") == "Episode"]
        other_items = [it for it in new_items if it.get("Type") not in ("Series", "Movie", "Video", "Audio", "MusicVideo", "Episode")]

        # Post Series announcements first
        for item in series_items:
            self._announce_single_item(item)
            time.sleep(1.2)

        # Post Movies
        for item in movie_items:
            self._announce_single_item(item)
            time.sleep(1.2)

        # Post Standalone Videos
        for item in video_items:
            self._announce_single_item(item)
            time.sleep(1.2)

        # Post Music Videos
        for item in music_video_items:
            self._announce_single_item(item)
            time.sleep(1.2)

        # Post Music / Audio
        for item in audio_items:
            self._announce_single_item(item)
            time.sleep(1.2)

        # Group episodes by Series
        episodes_by_series: Dict[str, list] = {}
        for ep in episode_items:
            s_key = ep.get("SeriesId") or ep.get("SeriesName") or "Unknown"
            episodes_by_series.setdefault(s_key, []).append(ep)

        new_series_ids = set(s.get("Id") for s in series_items)

        for s_key, eps in episodes_by_series.items():
            series_name = eps[0].get("SeriesName", "TV Show")
            # If the series itself was just announced above and there are multiple episodes,
            # mark the episodes as seen to avoid sending duplicate/flooding messages.
            if s_key in new_series_ids and len(eps) > 3:
                logger.info(f"Series '{series_name}' was announced; marking {len(eps)} episodes as indexed.")
                for ep in eps:
                    self.seen_media_ids.add(ep.get("Id"))
            elif len(eps) > 5:
                # Announce as a grouped batch card
                self._announce_batch_episodes(series_name, eps)
                time.sleep(1.2)
            else:
                # 1 to 5 episodes -> announce individually
                for ep in eps:
                    self._announce_single_item(ep)
                    time.sleep(1.2)

        for item in other_items:
            self._announce_single_item(item)
            time.sleep(1.2)

        self._save_seen_media_ids()

    def process_playback_sessions(self):
        if not self.discord:
            return

        try:
            sessions = self.jf.get_sessions()
        except Exception as e:
            logger.warning(f"Unable to reach Jellyfin server at {self.jellyfin_url}: {e}")
            return

        current_active_session_ids = set()

        for session in sessions:
            now_playing = session.get("NowPlayingItem")
            if not now_playing:
                continue

            # Check user filter if configured
            user_name = session.get("UserName")
            if self.user_filter and user_name != self.user_filter:
                continue

            session_id = session.get("Id")
            item_id = now_playing.get("Id")
            current_active_session_ids.add(session_id)

            existing = self.active_tracks.get(session_id)

            if existing and existing["item_id"] == item_id:
                # Update existing message
                message_id = existing["message_id"]
                cdn_url = existing.get("cdn_url")

                embed = build_discord_embed(
                    session=session,
                    jellyfin_url=self.jellyfin_url,
                    cached_cdn_url=cdn_url,
                    use_attachment_url=False
                )
                success = self.discord.patch_update(message_id, embed)
                if success:
                    existing["last_session"] = session
                    existing["last_update_time"] = time.time()
                    logger.info(f"Updated live playback stats for '{now_playing.get('Name')}' (Session {session_id[:6]})")
                else:
                    logger.warning(f"Could not patch message {message_id}, will re-create on next cycle if needed.")
            else:
                # If item changed on the same session, end previous first
                if existing:
                    self._end_session_track(session_id, "Switched Media")

                # New Media Playback Detected!
                logger.info(f"New playback detected: '{now_playing.get('Name')}' by {user_name}")

                image_bytes = None
                if self.include_poster and item_id:
                    image_bytes = self.jf.get_image_bytes(item_id)

                embed = build_discord_embed(
                    session=session,
                    jellyfin_url=self.jellyfin_url,
                    use_attachment_url=bool(image_bytes)
                )

                msg_id, cdn_url = self.discord.post_initial(embed, image_bytes=image_bytes)
                if msg_id:
                    self.active_tracks[session_id] = {
                        "message_id": msg_id,
                        "item_id": item_id,
                        "cdn_url": cdn_url,
                        "last_session": session,
                        "last_update_time": time.time()
                    }
                    logger.info(f"Created Discord status card for '{now_playing.get('Name')}' (Message ID: {msg_id})")

        # Check for sessions that have stopped or closed
        ended_session_ids = [sid for sid in self.active_tracks if sid not in current_active_session_ids]
        for sid in ended_session_ids:
            self._end_session_track(sid, "Playback Stopped / Finished")

    def process_cycle(self):
        # 1. Process active playback status updates
        self.process_playback_sessions()
        # 2. Check and announce newly added media (movies, videos, series, episodes)
        self.check_new_media()

    def _end_session_track(self, session_id: str, reason: str):
        track_info = self.active_tracks.pop(session_id, None)
        if not track_info:
            return

        message_id = track_info["message_id"]
        last_session = track_info.get("last_session")
        cdn_url = track_info.get("cdn_url")
        item_name = last_session.get("NowPlayingItem", {}).get("Name", "Media") if last_session else "Media"

        if self.delete_on_stop:
            logger.info(f"Deleting Discord card for ended media: '{item_name}'")
            if self.discord:
                self.discord.delete_message(message_id)
        else:
            logger.info(f"Marking Discord card as stopped for '{item_name}': {reason}")
            if last_session and self.discord:
                embed = build_discord_embed(
                    session=last_session,
                    jellyfin_url=self.jellyfin_url,
                    status_override=f"⏹️ {reason.upper()}",
                    cached_cdn_url=cdn_url,
                    use_attachment_url=False
                )
                self.discord.patch_update(message_id, embed)

    def run(self):
        logger.info(f"Jellyfin Discord Monitor started. Polling every {self.update_interval}s.")
        logger.info(f"Monitoring Jellyfin at: {self.jellyfin_url}")
        if self.client_playback:
            logger.info("Live Playback webhook: ACTIVE")
        if self.client_all and self.notify_new_media:
            logger.info("New Media (All Content Types) webhook: ACTIVE")
        if self.client_movies and self.notify_new_media:
            logger.info("New Media (Movies) webhook: ACTIVE")
        if self.client_series and self.notify_new_media:
            logger.info("New Media (TV Shows / Series) webhook: ACTIVE")
        if self.client_episodes and self.notify_new_media:
            logger.info("New Media (TV Episodes) webhook: ACTIVE")
        if self.client_music and self.notify_new_media:
            logger.info("New Media (Music / Audio) webhook: ACTIVE")
        if self.client_music_videos and self.notify_new_media:
            logger.info("New Media (Music Videos) webhook: ACTIVE")
        if self.client_videos and self.notify_new_media:
            logger.info("New Media (Videos) webhook: ACTIVE")

        # Run initial check immediately
        try:
            self.process_cycle()
        except Exception as e:
            logger.error(f"Error during initial monitor cycle: {e}", exc_info=True)

        elapsed = 0
        while self.running:
            # Check every second if library scan just finished on Jellyfin
            try:
                scan_task = self.jf.get_library_scan_task()
                if scan_task:
                    curr_state = scan_task.get("State", "Idle")
                    curr_end_time = (scan_task.get("LastExecutionResult") or {}).get("EndTimeUtc")
                    if (self.last_scan_state == "Running" and curr_state == "Idle") or (self.last_scan_end_time and curr_end_time and curr_end_time != self.last_scan_end_time):
                        logger.info("🔄 Library scan completed! Immediately checking for newly added media...")
                        self.check_new_media()
                        self.last_scan_end_time = curr_end_time
                    elif not self.last_scan_end_time and curr_end_time:
                        self.last_scan_end_time = curr_end_time
                    self.last_scan_state = curr_state
            except Exception as e:
                logger.debug(f"Scan check error: {e}")

            time.sleep(1)
            elapsed += 1
            if elapsed >= self.update_interval:
                elapsed = 0
                try:
                    self.process_cycle()
                except Exception as e:
                    logger.error(f"Error during monitor loop: {e}", exc_info=True)

        logger.info("Monitor shutting down gracefully.")


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cfg_file = os.path.join(base_dir, "config.json")
    if not os.path.exists(cfg_file):
        cfg_file = str(Path.home() / ".config" / "jellyscratchserver" / "config.json")

    daemon = MonitorDaemon(cfg_file)

    def handle_signal(sig, frame):
        logger.info(f"Received exit signal ({sig})...")
        daemon.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    daemon.run()
