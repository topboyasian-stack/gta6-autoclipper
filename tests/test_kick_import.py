import unittest

from fastapi import HTTPException

from app.main import combine_moment_scores, import_kick, validate_authorized_rtmp_url


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



class KickPageImportPolicyTests(unittest.TestCase):
    def test_direct_automated_kick_page_import_is_disabled(self):
        with self.assertRaises(HTTPException) as caught:
            import_kick(
                clip_url="https://kick.com/3rdcollector/clips/clip_example",
                creator="3rdcollector",
                rights_basis="My own channel",
            )
        self.assertEqual(caught.exception.status_code, 501)


if __name__ == "__main__":
    unittest.main()
