from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.flow_credits import FlowCreditLedger, episode_credit_plan, video_generation_cost
from scripts.flow_automator import retry_key


class FlowCreditTests(unittest.TestCase):
    def test_current_lite_cost_and_episode_targets(self):
        self.assertEqual(video_generation_cost("Veo 3.1 Lite", 8), 10)
        self.assertEqual(video_generation_cost("Veo 3.1 - Lite", 8), 10)
        plan = episode_credit_plan(scene_count=6)
        self.assertEqual(plan["credits_per_episode"], 60)
        self.assertEqual(plan["planned_target_credits"], 900)
        self.assertEqual(plan["stretch_target_credits"], 1200)
        self.assertEqual(plan["stretch_daily_refreshes_needed"], 6)
        self.assertEqual(plan["monthly_pool_episodes_after_reserve"], 15)

    def test_unknown_model_or_duration_fails_closed(self):
        with self.assertRaises(ValueError):
            video_generation_cost("Unknown Model", 8)
        with self.assertRaises(ValueError):
            video_generation_cost("Veo 3.1 Lite", 10)

    def test_video_reservation_is_idempotent_and_respects_reserve(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = FlowCreditLedger(
                Path(tmp) / "ledger.json", cycle_id="2026-11-25",
                monthly_credits=1000, daily_credits=50, reserve_percent=10,
            )
            first = ledger.reserve_video_generation(
                generation_key="p:scene_001", scene_id="scene_001", model="Veo 3.1 Lite",
                duration_seconds=8, current_balance=1100, now=1000,
            )
            self.assertEqual(first["status"], "reserved")
            second = ledger.reserve_video_generation(
                generation_key="p:scene_001", scene_id="scene_001", model="Veo 3.1 Lite",
                duration_seconds=8, current_balance=1090, now=1001,
            )
            self.assertEqual(second["status"], "already_recorded")
            self.assertEqual(ledger.summary()["estimated_video_credits_committed"], 10)

    def test_live_balance_must_cover_generation_plus_reserve(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = FlowCreditLedger(
                Path(tmp) / "ledger.json", cycle_id="2026-11-25",
                monthly_credits=1000, daily_credits=50, reserve_percent=10,
            )
            with self.assertRaisesRegex(RuntimeError, "controller protects"):
                ledger.reserve_video_generation(
                    generation_key="p:scene_001", scene_id="scene_001",
                    model="Veo 3.1 Lite", duration_seconds=8, current_balance=109, now=1000,
                )

    def test_credit_guard_blocks_below_reserve_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = FlowCreditLedger(
                Path(tmp) / "ledger.json", cycle_id="2026-11-25",
                monthly_credits=100, daily_credits=0, reserve_percent=10,
            )
            for index in range(9):
                ledger.reserve_video_generation(
                    generation_key=f"p:scene_{index}", scene_id=f"scene_{index}",
                    model="Veo 3.1 Lite", duration_seconds=8, current_balance=100,
                    now=1000 + index,
                )
            with self.assertRaises(RuntimeError):
                ledger.reserve_video_generation(
                    generation_key="p:scene_last", scene_id="scene_last",
                    model="Veo 3.1 Lite", duration_seconds=8, current_balance=100,
                    now=1010,
                )

    def test_new_cycle_cannot_reset_ledger_silently(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            FlowCreditLedger(path, cycle_id="cycle-a")
            with self.assertRaises(RuntimeError):
                FlowCreditLedger(path, cycle_id="cycle-b")

    def test_only_confirmed_no_charge_attempts_are_retryable(self):
        events = [
            {"generation_key": "stable", "status": "failed_no_charge"},
        ]
        self.assertEqual(retry_key(events, "generation_key", "stable", "failed_no_charge"), "stable:retry-2")
        events.append({"generation_key": "stable:retry-2", "status": "unknown"})
        self.assertEqual(retry_key(events, "generation_key", "stable", "failed_no_charge"), "stable")

    def test_image_quota_is_separate_from_video_credits(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = FlowCreditLedger(Path(tmp) / "ledger.json", cycle_id="2026-11-25")
            reservation = ledger.reserve_image_generation(
                image_key="p:frame_001", output_path="frames/scene_001.png", now=1000,
            )
            self.assertEqual(reservation["status"], "reserved")
            self.assertEqual(ledger.summary()["estimated_video_credits_committed"], 0)
            ledger.finish_image_generation("p:frame_001", status="completed")
            self.assertEqual(ledger.summary()["completed_image_generations"], 1)


if __name__ == "__main__":
    unittest.main()
