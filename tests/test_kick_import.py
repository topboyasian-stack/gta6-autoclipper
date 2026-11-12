import unittest

from fastapi import HTTPException

from app.main import _KickMetaParser, validate_kick_clip_url, validate_kick_media_url


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


if __name__ == "__main__":
    unittest.main()
