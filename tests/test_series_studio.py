import json
import tempfile
import unittest
from pathlib import Path

from app.series_studio import (
    _validate_episode_package,
    approve_series_episode_script,
    _validate_script_approval,
    approve_series_voice_cast,
    initialize_series_workspace,
    mark_series_episode_canonical,
    render_series_flow_prompt_pack,
    validate_series_bible,
    _scene_cache_fingerprint,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SERIES_TEMPLATE = REPO_ROOT / "series" / "the_217_signal"


def make_episode_package(bible, episode=1):
    cast = bible["cast"]
    locations = bible["setting"]["locations"]
    scenes = []
    for index in range(1, 25):
        character = cast[(index - 1) % len(cast)]
        scenes.append({
            "order": index,
            "duration_seconds": 8,
            "scene_title": f"Scene {index}",
            "location_id": locations[(index - 1) % len(locations)]["id"],
            "characters": [character["id"]],
            "visual_action": "The character checks the receiver and compares the signal log with a paper record.",
            "camera": "One slow, motivated push-in at eye level.",
            "continuity_notes": "Keep the character appearance and established location geography unchanged.",
            "flow_prompt": "Show the character in the established location, checking one physical clue.",
            "dialogue_lines": [{
                "speaker_id": character["id"],
                "text": "We need to verify this warning against the official record before anyone acts."
            }],
        })
    return {
        "season_number": 1,
        "episode_number": episode,
        "episode_title": "DEAD AIR",
        "logline": "A radio repairer receives a warning about an event that has not happened.",
        "episode_summary": "A complete immediate problem is resolved while the larger mystery deepens.",
        "continuity_in": "Amara has restored the abandoned receiver.",
        "continuity_out": "The team has verified the warning and found a LANTERN clue.",
        "ending_hook": "A familiar call sign appears in the receiver log.",
        "scenes": scenes,
    }


class SerializedSeriesStudioTests(unittest.TestCase):
    def setUp(self):
        self.bible = json.loads((SERIES_TEMPLATE / "series_bible.json").read_text(encoding="utf-8"))

    def test_default_series_bible_is_complete_and_has_distinct_cast_ids(self):
        validate_series_bible(self.bible)
        self.assertEqual(self.bible["series_id"], "the_217_signal")
        self.assertEqual(len(self.bible["cast"]), 3)
        self.assertEqual(len({item["id"] for item in self.bible["cast"]}), 3)
        self.assertEqual(self.bible["voice_cast"]["status"], "provisional_not_locked")

    def test_episode_validation_enforces_scene_count_runtime_and_dialogue(self):
        package = _validate_episode_package(make_episode_package(self.bible), self.bible, 1)
        self.assertEqual(len(package["scenes"]), 24)
        self.assertEqual(package["scene_runtime_seconds"], 192)
        self.assertEqual(package["dialogue_word_count"], 312)
        self.assertIn("Amara Dike:", package["dialogue_script"])

    def test_episode_rejects_non_canon_character_speaker(self):
        package = make_episode_package(self.bible)
        package["scenes"][0]["characters"] = ["amara"]
        package["scenes"][0]["dialogue_lines"][0]["speaker_id"] = "unknown"
        with self.assertRaisesRegex(ValueError, "speaker not present"):
            _validate_episode_package(package, self.bible, 1)

    def test_episode_rejects_extra_scenes_and_wrong_runtime(self):
        package = make_episode_package(self.bible)
        package["scenes"].pop()
        with self.assertRaisesRegex(ValueError, "exactly 24"):
            _validate_episode_package(package, self.bible, 1)

        package = make_episode_package(self.bible)
        package["scenes"][0]["duration_seconds"] = 15
        with self.assertRaisesRegex(ValueError, "between 6 and 9"):
            _validate_episode_package(package, self.bible, 1)

    def test_episode_allows_up_to_six_deliberate_silent_scenes(self):
        package = make_episode_package(self.bible)
        for scene in package["scenes"][:6]:
            scene["dialogue_lines"] = []
        for scene in package["scenes"][6:12]:
            speaker = scene["characters"][0]
            scene["dialogue_lines"].append({
                "speaker_id": speaker,
                "text": "The record should identify the operator before we decide what to do next."
            })
        validated = _validate_episode_package(package, self.bible, 1)
        self.assertEqual(validated["dialogue_word_count"], 312)

    def test_episode_rejects_too_many_silent_scenes_and_prompt_line_mismatch(self):
        package = make_episode_package(self.bible)
        for scene in package["scenes"][:7]:
            scene["dialogue_lines"] = []
        for scene in package["scenes"][7:14]:
            speaker = scene["characters"][0]
            scene["dialogue_lines"].append({
                "speaker_id": speaker,
                "text": "The record should identify the operator before we decide what to do next."
            })
        with self.assertRaisesRegex(ValueError, "At least 18"):
            _validate_episode_package(package, self.bible, 1)

        package = make_episode_package(self.bible)
        package["scenes"][0]["dialogue_lines"] *= 3
        with self.assertRaisesRegex(ValueError, "zero, one or two"):
            _validate_episode_package(package, self.bible, 1)

    def test_scene_cache_fingerprint_tracks_source_content_and_render_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "scene_001.mp4"
            source.write_bytes(b"first clip bytes")
            original = _scene_cache_fingerprint(source, False, (1920, 1080))
            source.write_bytes(b"other clip bytes")
            changed_source = _scene_cache_fingerprint(source, False, (1920, 1080))
            changed_audio = _scene_cache_fingerprint(source, True, (1920, 1080))
            changed_size = _scene_cache_fingerprint(source, False, (1080, 1920))
        self.assertNotEqual(original, changed_source)
        self.assertNotEqual(changed_source, changed_audio)
        self.assertNotEqual(changed_source, changed_size)

    def test_canon_gate_rechecks_locked_voice_cast_and_script_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            series_dir = initialize_series_workspace(root)
            project_dir = root / "projects" / "pilot"
            project_dir.mkdir(parents=True)
            package = make_episode_package(self.bible)
            package["series_id"] = self.bible["series_id"]
            package["season_number"] = 1
            package["request_fingerprint"] = "approved-test-fingerprint"
            (project_dir / "series_episode_package.json").write_text(json.dumps(package), encoding="utf-8")
            (project_dir / "original_script.md").write_text("# Pilot script\n\nAmara: We must verify the warning.", encoding="utf-8")
            (project_dir / "flow_prompt_pack.md").write_text("# Pilot prompts\n\nScene 1", encoding="utf-8")
            approve_series_episode_script(project_dir, True)
            work_dir = project_dir / "work"
            work_dir.mkdir()
            (work_dir / "series_quality_report.json").write_text(
                json.dumps({"status": "rendered_pending_human_review"}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(PermissionError, "locked, auditioned voice cast"):
                mark_series_episode_canonical(series_dir, project_dir, True)

    def test_flow_prompt_pack_contains_reference_locks_and_silence_rules(self):
        package = _validate_episode_package(make_episode_package(self.bible), self.bible, 1)
        prompt_pack = render_series_flow_prompt_pack(package, self.bible)
        self.assertIn("amara_reference.png", prompt_pack)
        self.assertIn("dami_reference.png", prompt_pack)
        self.assertIn("No audible speech", prompt_pack)
        self.assertIn("scene_024.mp4", prompt_pack)
        self.assertIn("do not reinterpret, redesign", prompt_pack.lower())

    def test_series_workspace_copies_templates_without_overwriting_drive_edits(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            series_dir = initialize_series_workspace(root)
            bible_path = series_dir / "series_bible.json"
            original = bible_path.read_text(encoding="utf-8")
            custom = original.replace("THE 2:17 SIGNAL", "THE 2:17 SIGNAL — user edit", 1)
            bible_path.write_text(custom, encoding="utf-8")
            again = initialize_series_workspace(root)
            self.assertEqual(again, series_dir)
            self.assertEqual(bible_path.read_text(encoding="utf-8"), custom)
            self.assertTrue((series_dir / "continuity" / "season_01.json").exists())

    def test_voice_cast_cannot_lock_duplicate_fallback_models(self):
        with tempfile.TemporaryDirectory() as temp:
            series_dir = initialize_series_workspace(Path(temp))
            characters = {}
            for item in self.bible["cast"]:
                characters[item["id"]] = {
                    "actual_voice_id": "en_US-ljspeech-medium",
                    "audio_path": str(series_dir / "voice_auditions" / f"{item['id']}.wav"),
                }
                (series_dir / "voice_auditions" / f"{item['id']}.wav").write_bytes(b"0" * 2000)
            audition_path = series_dir / "voice_auditions" / "auditions.json"
            audition_path.write_text(json.dumps({"characters": characters}), encoding="utf-8")
            approvals = {item["id"]: True for item in self.bible["cast"]}
            with self.assertRaisesRegex(ValueError, "duplicate models"):
                approve_series_voice_cast(series_dir, approvals)


    def test_script_approval_is_required_and_invalidated_when_files_change(self):
        with tempfile.TemporaryDirectory() as temp:
            project_dir = Path(temp)
            package = make_episode_package(self.bible)
            package["season_number"] = 1
            package["request_fingerprint"] = "test-fingerprint"
            (project_dir / "series_episode_package.json").write_text(json.dumps(package), encoding="utf-8")
            (project_dir / "original_script.md").write_text("# Approved script\n\nAmara: We must verify the warning.", encoding="utf-8")
            (project_dir / "flow_prompt_pack.md").write_text("# Approved prompts\n\nScene 1", encoding="utf-8")
            with self.assertRaises(PermissionError):
                approve_series_episode_script(project_dir, False)
            approval = approve_series_episode_script(project_dir, True)
            self.assertEqual(approval["status"], "approved")
            _validate_script_approval(project_dir, package)
            (project_dir / "original_script.md").write_text("# Changed after approval", encoding="utf-8")
            with self.assertRaisesRegex(PermissionError, "changed after approval"):
                _validate_script_approval(project_dir, package)

    def test_unreviewed_episode_cannot_update_canonical_continuity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            series_dir = initialize_series_workspace(root)
            project_dir = root / "projects" / "pilot"
            project_dir.mkdir(parents=True)
            package = make_episode_package(self.bible)
            package["season_number"] = 1
            package["dialogue_script"] = "Test dialogue"
            (project_dir / "series_episode_package.json").write_text(json.dumps(package), encoding="utf-8")
            (project_dir / "work").mkdir()
            with self.assertRaises(PermissionError):
                mark_series_episode_canonical(series_dir, project_dir, False)


if __name__ == "__main__":
    unittest.main()
