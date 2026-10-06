#!/usr/bin/env python3
"""
Unit tests and simulation verification for Jellyfin Discord Monitor.
"""

import unittest
from datetime import datetime
from monitor import (
    ticks_to_seconds,
    format_duration_clock,
    format_duration_human,
    format_remaining_detail,
    make_progress_bar,
    build_media_stats,
    build_discord_embed,
    build_new_media_embed,
    build_batch_episodes_embed,
    build_sample_embed_for_type,
    MonitorDaemon,
    TICKS_PER_SECOND
)

class TestMonitorFormatting(unittest.TestCase):
    def test_ticks_to_seconds(self):
        # 10,000,000 ticks = 1 second
        self.assertEqual(ticks_to_seconds(10_000_000), 1.0)
        self.assertEqual(ticks_to_seconds(0), 0.0)
        self.assertEqual(ticks_to_seconds(None), 0.0)

    def test_duration_clock(self):
        # 45 minutes = 2700 seconds -> 45:00
        self.assertEqual(format_duration_clock(2700), "45:00")
        # 1 hour 24 minutes 15 seconds -> 01:24:15
        self.assertEqual(format_duration_clock(5055), "01:24:15")

    def test_remaining_detail(self):
        # 1 hour 15 minutes left (75 mins)
        rem_sec = 75 * 60
        result = format_remaining_detail(rem_sec)
        self.assertIn("1h 15m left", result)
        self.assertIn("75 mins left", result)

        # 25 minutes left
        rem_sec_short = 25 * 60
        result_short = format_remaining_detail(rem_sec_short)
        self.assertIn("25 mins left", result_short)

    def test_progress_bar(self):
        bar, pct = make_progress_bar(3600, 7200, length=10)
        self.assertEqual(pct, 50.0)
        self.assertEqual(bar, "`[█████░░░░░]`")

    def test_build_discord_embed_full(self):
        # Mock Session Data
        runtime_sec = 8880  # 2h 28m
        current_sec = 3600  # 1h 00m (50% in, 1h 28m left)

        mock_session = {
            "Id": "sess12345",
            "UserName": "sam",
            "Client": "Jellyfin Web",
            "DeviceName": "Chrome on Linux",
            "NowPlayingItem": {
                "Id": "item999",
                "Name": "Inception",
                "ProductionYear": 2010,
                "Overview": "A thief who steals corporate secrets through the use of dream-sharing technology...",
                "Genres": ["Action", "Sci-Fi", "Adventure"],
                "OfficialRating": "PG-13",
                "CommunityRating": 8.8,
                "RunTimeTicks": runtime_sec * TICKS_PER_SECOND,
                "Container": "mkv",
                "Bitrate": 18_500_000,
                "MediaStreams": [
                    {
                        "Type": "Video",
                        "Codec": "hevc",
                        "Width": 3840,
                        "Height": 2160,
                        "BitRate": 17_000_000
                    },
                    {
                        "Type": "Audio",
                        "Codec": "dts",
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

        embed = build_discord_embed(
            session=mock_session,
            jellyfin_url="http://localhost:8096",
            use_attachment_url=False
        )

        self.assertEqual(embed["title"], "🎬 Inception (2010)")
        self.assertIn("NOW PLAYING", embed["description"])

        # Check fields
        field_names = [f["name"] for f in embed["fields"]]
        self.assertIn("⏱️ Time & Progress", field_names)
        self.assertIn("📊 Movie Media Stats", field_names)
        self.assertIn("🎬 Movie Info", field_names)
        self.assertIn("👤 Viewer", field_names)

        progress_field = next(f for f in embed["fields"] if f["name"] == "⏱️ Time & Progress")
        self.assertIn("Elapsed:", progress_field["value"])
        self.assertIn("Remaining:", progress_field["value"])
        self.assertIn("Est. Finish:", progress_field["value"])

        stats_field = next(f for f in embed["fields"] if f["name"] == "📊 Movie Media Stats")
        self.assertIn("4K UHD", stats_field["value"])
        self.assertIn("HEVC", stats_field["value"])
        self.assertIn("DTS 5.1", stats_field["value"])
        self.assertIn("Direct Play", stats_field["value"])

        viewer_field = next(f for f in embed["fields"] if f["name"] == "👤 Viewer")
        self.assertIn("sam", viewer_field["value"])
        self.assertIn("Chrome on Linux", viewer_field["value"])

        self.assertIn("30 seconds", embed["footer"]["text"])


    def test_build_new_media_embed_movie(self):
        movie_item = {
            "Type": "Movie",
            "Name": "Interstellar",
            "ProductionYear": 2014,
            "Overview": "A team of explorers travel through a wormhole in space in an attempt to ensure humanity's survival.",
            "Genres": ["Adventure", "Drama", "Sci-Fi"],
            "CommunityRating": 8.7,
            "OfficialRating": "PG-13",
            "RunTimeTicks": 101400000000,
            "MediaStreams": [{"Type": "Video", "Width": 3840, "Height": 2160, "Codec": "hevc"}],
            "Container": "mkv"
        }
        embed = build_new_media_embed(movie_item, "http://localhost:8096")
        self.assertEqual(embed["title"], "🎬 Interstellar (2014)")
        self.assertIn("New Movie Added to Jellyfin!", embed["description"])

    def test_build_new_media_embed_episode(self):
        episode_item = {
            "Type": "Episode",
            "Name": "Pilot",
            "SeriesName": "The Flash",
            "SeasonName": "Season 1",
            "ParentIndexNumber": 1,
            "IndexNumber": 1,
            "Overview": "Barry Allen gets struck by lightning.",
            "Genres": ["Action", "Sci-Fi"],
            "CommunityRating": 8.5,
            "OfficialRating": "TV-PG",
            "RunTimeTicks": 26400000000,
            "MediaStreams": [{"Type": "Video", "Width": 1280, "Height": 720, "Codec": "hevc"}],
            "Container": "mkv"
        }
        embed = build_new_media_embed(episode_item, "http://localhost:8096")
        self.assertEqual(embed["title"], "📺 The Flash - S01E01 - Pilot")
        self.assertIn("New TV Episode Added to Jellyfin!", embed["description"])
        field_names = [f["name"] for f in embed["fields"]]
        self.assertIn("📺 Series & Season", field_names)

    def test_build_batch_episodes_embed(self):
        eps = [
            {"Name": f"Episode {i}", "ParentIndexNumber": 1, "IndexNumber": i} for i in range(1, 11)
        ]
        embed = build_batch_episodes_embed("The Flash", eps, "http://localhost:8096", season_name="Season 1")
        self.assertEqual(embed["title"], "📺 The Flash - 10 New Episodes Added")
        self.assertIn("10 New Episodes Added to Jellyfin!", embed["description"])
        self.assertIn("S01E01", embed["description"])

    def test_build_sample_embeds_for_all_7_types(self):
        # 1. All Content Types
        emb_all = build_sample_embed_for_type("all")
        self.assertIn("All Content Types", emb_all["title"])

        # 2. Movie
        emb_movie = build_sample_embed_for_type("Movie")
        self.assertIn("Interstellar", emb_movie["title"])

        # 3. Series
        emb_series = build_sample_embed_for_type("Series")
        self.assertIn("The Flash", emb_series["title"])

        # 4. Episode
        emb_ep = build_sample_embed_for_type("Episode")
        self.assertIn("S01E01", emb_ep["title"])

        # 5. Audio / Music
        emb_audio = build_sample_embed_for_type("Audio")
        self.assertIn("Get Lucky", emb_audio["title"])

        # 6. Music Video
        emb_mv = build_sample_embed_for_type("MusicVideo")
        self.assertIn("Bohemian Rhapsody", emb_mv["title"])

        # 7. Video
        emb_vid = build_sample_embed_for_type("Video")
        self.assertIn("Summer Road Trip", emb_vid["title"])

    def test_build_new_media_embed_book(self):
        book_item = {
            "Type": "Book",
            "Name": "Dune",
            "ProductionYear": 1965,
            "Overview": "Set on the desert planet Arrakis."
        }
        embed = build_new_media_embed(book_item, "http://localhost:8096")
        self.assertEqual(embed["title"], "📚 Dune (1965)")
        self.assertIn("Book / Audiobook", embed["description"])

    def test_daemon_webhook_routing_and_deduplication(self):
        import tempfile
        import json
        with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as tf:
            cfg = {
                "jellyfin_url": "http://localhost:8096",
                "jellyfin_api_key": "testkey",
                "discord_webhook_url": "https://discord.com/api/webhooks/11111/playback",
                "discord_webhook_all": "https://discord.com/api/webhooks/22222/all",
                "discord_webhook_movies": "https://discord.com/api/webhooks/33333/movies",
                "discord_webhook_series": "https://discord.com/api/webhooks/44444/series",
                "discord_webhook_episodes": "https://discord.com/api/webhooks/55555/episodes",
                "discord_webhook_music": "https://discord.com/api/webhooks/66666/music",
                "discord_webhook_music_videos": "https://discord.com/api/webhooks/77777/mvideos",
                "discord_webhook_videos": "https://discord.com/api/webhooks/88888/videos",
            }
            json.dump(cfg, tf)
            tf.flush()
            temp_path = tf.name

        daemon = MonitorDaemon(temp_path)
        # Test routing
        clients_movie = daemon.get_webhook_clients_for_type("Movie")
        # Should contain movies webhook AND all webhook
        urls_movie = [c.webhook_url for c in clients_movie]
        self.assertIn("https://discord.com/api/webhooks/33333/movies", urls_movie)
        self.assertIn("https://discord.com/api/webhooks/22222/all", urls_movie)
        self.assertEqual(len(urls_movie), 2)

        # Test deduplication when same URL used for all and movies
        with open(temp_path, "w") as f:
            cfg["discord_webhook_movies"] = "https://discord.com/api/webhooks/22222/all"
            json.dump(cfg, f)

        daemon_dedup = MonitorDaemon(temp_path)
        clients_dedup = daemon_dedup.get_webhook_clients_for_type("Movie")
        self.assertEqual(len(clients_dedup), 1)
        self.assertEqual(clients_dedup[0].webhook_url, "https://discord.com/api/webhooks/22222/all")


if __name__ == "__main__":
    unittest.main()

