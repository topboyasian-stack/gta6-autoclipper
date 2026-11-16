import unittest

from app.kids_story_studio import _story_word_targets


class KidsStoryWordTargetTests(unittest.TestCase):
    def test_valid_story_shorter_than_requested_target_is_accepted(self):
        # Six saved Flow scenes run for about 49.66 seconds. The model returned
        # 81 words, which is enough for a complete slower-paced children's story.
        target_words, minimum_words = _story_word_targets(49.66)
        self.assertEqual(target_words, 111)
        self.assertEqual(minimum_words, 77)
        model_word_count = 81
        self.assertTrue(minimum_words <= model_word_count <= target_words + 25)

    def test_extremely_short_story_is_still_rejected_for_long_footage(self):
        target_words, minimum_words = _story_word_targets(49.66)
        self.assertFalse(minimum_words <= 50 <= target_words + 25)

    def test_word_targets_are_bounded_for_very_short_and_long_footage(self):
        short_target, short_minimum = _story_word_targets(5.0)
        long_target, long_minimum = _story_word_targets(200.0)
        self.assertEqual(short_target, 50)
        self.assertEqual(short_minimum, 45)
        self.assertEqual(long_target, 145)
        self.assertEqual(long_minimum, 101)


if __name__ == "__main__":
    unittest.main()
