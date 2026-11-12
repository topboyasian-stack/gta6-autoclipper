import unittest

from fastapi import HTTPException

from app.main import (
    _KickMetaParser,
    combine_moment_scores,
    validate_authorized_rtmp_url,
    validate_kick_clip_url,
    validate_kick_media_url,
)


class KickImportValidationTests(unittest.TestCase):
    def test_accepts_canonical_kick_clip(self):
        page_url, channel, clip_id = validate_kick_clip_url(
            "https://kick.com/3rdcollector/clips/clip_01KD53FXYEWKBZH2WQJC556AXA"
        )
        self.assertEqual(page_url, "https://kick.com/3rdcollector/clips/clip_01KD53FXYEWKBZH2WQJC556AXA")
        self.assertEqual(channel, "3rdcollector")
        self.assertEqual(clip_id, "clip_01KD53FXYEWKBZH2WQJC556AXA")

    def test_rejects_non_kick_hosts(self):
        with self.assertRaises(HTTPException):
            validate_kick_clip_url("https://example.com/3rdcollector/clips/clip_123ABC")

    def test_rejects_channel_and_vod_links(self):
        for url in (
            "https://kick.com/3rdcollector",
            "https://kick.com/3rdcollector/videos",
            "https://kick.com/3rdcollector/videos/abc",
        ):
            with self.subTest(url=url), self.assertRaises(HTTPException):
                validate_kick_clip_url(url)

    def test_accepts_only_matching_kick_media_playlist(self):
        media = "https://clips.kick.com/clips/87/clip_01KD53FXYEWKBZH2WQJC556AXA/playlist.m3u8"
        self.assertEqual(
            validate_kick_media_url(media, "clip_01KD53FXYEWKBZH2WQJC556AXA"),
            media,
        )

    def test_rejects_unrelated_media_hosts_and_clip_ids(self):
        with self.assertRaises(HTTPException):
            validate_kick_media_url(
                "https://example.com/clips/87/clip_01KD53FXYEWKBZH2WQJC556AXA/playlist.m3u8",
                "clip_01KD53FXYEWKBZH2WQJC556AXA",
            )
        with self.assertRaises(HTTPException):
            validate_kick_media_url(
                "https://clips.kick.com/clips/87/clip_ABC123/playlist.m3u8",
                "clip_EXPECTED",
            )

    def test_reads_open_graph_clip_metadata(self):
        parser = _KickMetaParser()
        parser.feed(
            '<meta property="og:title" content="Squad wipe🔥 - 3rdcollector Clip on KICK">'
            '<meta property="og:video" content="https://clips.kick.com/clips/87/'
            'clip_01KD53FXYEWKBZH2WQJC556AXA/playlist.m3u8">'
        )
        self.assertIn("Squad wipe", parser.meta["og:title"])
        self.assertTrue(parser.meta["og:video"].endswith("/playlist.m3u8"))



class AuthorizedLiveFeedTests(unittest.TestCase):
    def test_accepts_rtmp_feed_and_masks_stream_key_in_descriptor(self):
        url, descriptor = validate_authorized_rtmp_url("rtmps://media.example:443/live/private-key")
        self.assertEqual(url, "rtmps://media.example:443/live/private-key")
        self.assertEqual(descriptor, "rtmps://media.example:443")
        self.assertNotIn("private-key", descriptor)

    def test_rejects_watch_pages_and_unsupported_schemes(self):
        for url in (
            "https://www.youtube.com/watch?v=abc",
            "https://kick.com/3rdcollector",
            "rtsp://media.example/live/key",
            "rtmp://user:password@media.example/live/key",
        ):
            with self.subTest(url=url), self.assertRaises(HTTPException):
                validate_authorized_rtmp_url(url)



class HighlightScoringTests(unittest.TestCase):
    def test_visual_scene_change_contributes_to_candidate_score(self):
        scores = combine_moment_scores([10.0, 20.0, 12.0], {0: 0.8, 2: 1.0})
        self.assertEqual(len(scores), 3)
        self.assertGreater(scores[2], 0.0)
        self.assertGreater(scores[1], scores[0])

    def test_audio_only_fallback_is_supported(self):
        scores = combine_moment_scores([1.0, 5.0, 2.0], {})
        self.assertEqual(len(scores), 3)
        self.assertAlmostEqual(scores[0], 0.0)
        self.assertAlmostEqual(scores[1], 0.72)


if __name__ == "__main__":
    unittest.main()
