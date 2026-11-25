"""Persistent credit ledger and conservative Google Flow production budget."""
from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VIDEO_MODEL_COSTS = {
    "Veo 3.1 Lite": {4: 10, 6: 10, 8: 10},
    "Veo 3.1 - Lite": {4: 10, 6: 10, 8: 10},
    "Veo 3.1 Fast": {4: 20, 6: 20, 8: 20},
    "Veo 3.1 Quality": {8: 100},
}
IMAGE_MODEL_DAILY_LIMITS = {
    "Nano Banana Pro": 100,
    "Nano Banana 2.1": 1000,
    "Nano Banana 2 Lite": 1000,
}
LEDGER_VERSION = 1


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def video_generation_cost(model: str, duration_seconds: int, output_count: int = 1) -> int:
    if model not in VIDEO_MODEL_COSTS or duration_seconds not in VIDEO_MODEL_COSTS[model]:
        raise ValueError(f"No verified Flow price configured for {model!r} at {duration_seconds}s.")
    if output_count != 1:
        raise ValueError("Only one output per request is allowed by the credit controller.")
    return VIDEO_MODEL_COSTS[model][duration_seconds]


def episode_credit_plan(
    *, scene_count: int = 6, monthly_credits: int = 1000, daily_credits: int = 50,
    reserve_percent: int = 10, target_videos: int = 15, stretch_videos: int = 20,
    model: str = "Veo 3.1 Lite", duration_seconds: int = 8,
) -> dict[str, Any]:
    per_scene = video_generation_cost(model, duration_seconds)
    per_episode = per_scene * scene_count
    reserve = math.ceil(monthly_credits * reserve_percent / 100)
    target_cost = target_videos * per_episode
    stretch_cost = stretch_videos * per_episode
    daily_needed = max(0, stretch_cost + reserve - monthly_credits)
    return {
        "video_model": model, "duration_seconds": duration_seconds,
        "credits_per_scene": per_scene, "scenes_per_episode": scene_count,
        "credits_per_episode": per_episode, "monthly_subscription_credits": monthly_credits,
        "daily_refresh_credits": daily_credits, "monthly_reserve_credits": reserve,
        "planned_target_videos": target_videos, "planned_target_credits": target_cost,
        "target_fits_monthly_pool_after_reserve": target_cost <= monthly_credits - reserve,
        "monthly_pool_episodes_after_reserve": max(0, monthly_credits - reserve) // per_episode,
        "stretch_target_videos": stretch_videos, "stretch_target_credits": stretch_cost,
        "stretch_daily_credits_needed_after_reserve": daily_needed,
        "stretch_daily_refreshes_needed": math.ceil(daily_needed / daily_credits) if daily_credits else 0,
        "image_generations_use_monthly_flow_credits": False,
        "image_daily_limits": IMAGE_MODEL_DAILY_LIMITS,
        "assumptions": [
            "One 8-second, 720p Veo 3.1 Lite generation per scene, at 10 credits per scene for Pro.",
            "One output per request; no automatic variants or credit-spending retries.",
            "Pro receives 1,000 monthly credits and 50 daily credits; daily credits do not roll over.",
            "20 six-scene episodes cost 1,200 credits; after a 100-credit reserve, six 50-credit daily refreshes are needed beyond the monthly pool.",
            "The live Flow balance must cover the queued batch plus the protected reserve before videos are submitted.",
            "Flow image generation has a separate daily image quota and does not consume monthly video credits.",
        ],
    }


class FlowCreditLedger:
    """Append-only record of planned spend; unresolved submissions are treated as spent."""

    def __init__(
        self, path: Path, *, cycle_id: str, monthly_credits: int = 1000,
        daily_credits: int = 50, reserve_percent: int = 10,
        image_model: str = "Nano Banana Pro",
    ):
        if not cycle_id.strip():
            raise ValueError("A stable FLOW_CREDIT_CYCLE_ID is required.")
        if image_model not in IMAGE_MODEL_DAILY_LIMITS:
            raise ValueError(f"Unrecognized image model: {image_model}")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            if self.data.get("schema_version") != LEDGER_VERSION:
                raise RuntimeError("Unsupported ledger version; do not overwrite its history.")
            if self.data.get("cycle_id") != cycle_id:
                raise RuntimeError("Billing-cycle ID changed. Archive the old ledger and explicitly initialize a new cycle.")
            expected = {
                "monthly_credits": monthly_credits, "daily_credits": daily_credits,
                "reserve_percent": reserve_percent, "image_model": image_model,
            }
            for key, value in expected.items():
                if self.data.get(key) != value:
                    raise RuntimeError(f"Ledger setting {key} changed; reconcile it before continuing.")
        else:
            self.data = {
                "schema_version": LEDGER_VERSION, "cycle_id": cycle_id, "created_at": utc_iso(),
                "monthly_credits": monthly_credits, "daily_credits": daily_credits,
                "reserve_percent": reserve_percent, "image_model": image_model,
                "events": [], "daily_credit_windows": [], "image_events": [],
                "daily_image_windows": [],
            }
            self._save()

    def _save(self) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    @staticmethod
    def _epoch(value: str | None) -> float:
        return datetime.fromisoformat(value).timestamp() if value else 0.0

    def _window(self, key: str, now: float) -> None:
        windows = self.data.setdefault(key, [])
        if not windows or now - self._epoch(windows[-1].get("earned_at")) >= 86400:
            windows.append({"earned_at": datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds")})

    def _committed(self) -> int:
        return sum(
            int(e.get("expected_credits", 0)) for e in self.data["events"]
            if e.get("status") in {"submitted", "completed", "unknown"}
        )

    def reserve_video_generation(
        self, *, generation_key: str, scene_id: str, model: str,
        duration_seconds: int, current_balance: int, metadata: dict | None = None,
        now: float | None = None,
    ) -> dict:
        old = next((e for e in self.data["events"] if e.get("generation_key") == generation_key), None)
        if old:
            return {"status": "already_recorded", "event": old}
        cost = video_generation_cost(model, int(duration_seconds))
        reserve = math.ceil(self.data["monthly_credits"] * self.data["reserve_percent"] / 100)
        if current_balance < cost + reserve:
            raise RuntimeError(
                f"Flow currently shows {current_balance} credits; {cost} are needed and the controller protects {reserve} credits."
            )
        moment = time.time() if now is None else float(now)
        self._window("daily_credit_windows", moment)
        daily = len(self.data["daily_credit_windows"]) * self.data["daily_credits"]
        budget_left = self.data["monthly_credits"] + daily - reserve - self._committed()
        if budget_left < cost:
            raise RuntimeError(f"Credit budget has {budget_left} credits after reserve; {cost} are required.")
        event = {
            "generation_key": generation_key, "scene_id": scene_id, "model": model,
            "duration_seconds": duration_seconds, "expected_credits": cost,
            "balance_before": current_balance, "status": "submitted",
            "submitted_at": datetime.fromtimestamp(moment, timezone.utc).isoformat(timespec="seconds"),
            "metadata": metadata or {},
        }
        self.data["events"].append(event)
        self._save()
        return {"status": "reserved", "event": event, "remaining_budget_after_reservation": budget_left - cost}

    def finish_video_generation(
        self, generation_key: str, *, status: str, balance_after: int | None = None,
        output_path: str | None = None, error: str | None = None,
    ) -> None:
        if status not in {"completed", "unknown", "failed_no_charge"}:
            raise ValueError("Invalid video generation status.")
        event = next((e for e in self.data["events"] if e.get("generation_key") == generation_key), None)
        if event is None:
            raise KeyError(generation_key)
        event.update({"status": status, "finished_at": utc_iso()})
        if balance_after is not None:
            event["balance_after"] = int(balance_after)
        if output_path:
            event["output_path"] = str(output_path)
        if error:
            event["error"] = str(error)[:1200]
        self._save()

    def reserve_image_generation(
        self, *, image_key: str, output_path: str, model: str | None = None,
        now: float | None = None,
    ) -> dict:
        model = model or self.data["image_model"]
        if model not in IMAGE_MODEL_DAILY_LIMITS:
            raise ValueError(f"No daily Flow image quota is configured for {model!r}.")
        old = next((e for e in self.data["image_events"] if e.get("image_key") == image_key), None)
        if old:
            return {"status": "already_recorded", "event": old}
        moment = time.time() if now is None else float(now)
        self._window("daily_image_windows", moment)
        recent = [
            e for e in self.data["image_events"]
            if self._epoch(e.get("submitted_at")) >= moment - 86400
            and e.get("status") in {"submitted", "completed", "unknown"}
        ]
        limit = IMAGE_MODEL_DAILY_LIMITS[model]
        if len(recent) >= limit:
            raise RuntimeError(f"Image quota guard: {len(recent)}/{limit} {model} generations used in 24 hours.")
        event = {
            "image_key": image_key, "model": model, "output_path": str(output_path),
            "status": "submitted",
            "submitted_at": datetime.fromtimestamp(moment, timezone.utc).isoformat(timespec="seconds"),
        }
        self.data["image_events"].append(event)
        self._save()
        return {"status": "reserved", "event": event}

    def finish_image_generation(self, image_key: str, *, status: str, output_path: str | None = None, error: str | None = None):
        if status not in {"completed", "unknown", "failed_no_quota_charge"}:
            raise ValueError("Invalid image generation status.")
        event = next((e for e in self.data["image_events"] if e.get("image_key") == image_key), None)
        if event is None:
            raise KeyError(image_key)
        event.update({"status": status, "finished_at": utc_iso()})
        if output_path:
            event["output_path"] = str(output_path)
        if error:
            event["error"] = str(error)[:1200]
        self._save()

    def summary(self) -> dict:
        reserve = math.ceil(self.data["monthly_credits"] * self.data["reserve_percent"] / 100)
        daily = len(self.data["daily_credit_windows"]) * self.data["daily_credits"]
        committed = self._committed()
        return {
            "cycle_id": self.data["cycle_id"], "monthly_subscription_credits": self.data["monthly_credits"],
            "daily_credit_windows_earned": len(self.data["daily_credit_windows"]),
            "daily_credits_added_to_budget": daily,
            "gross_estimated_allowance": self.data["monthly_credits"] + daily,
            "estimated_video_credits_committed": committed, "monthly_reserve": reserve,
            "estimated_budget_remaining": self.data["monthly_credits"] + daily - reserve - committed,
            "completed_video_generations": sum(e.get("status") == "completed" for e in self.data["events"]),
            "unresolved_video_generations": sum(e.get("status") in {"submitted", "unknown"} for e in self.data["events"]),
            "completed_image_generations": sum(e.get("status") == "completed" for e in self.data["image_events"]),
            "ledger_path": str(self.path),
        }
