"""Structured episode schema shared by planning, assets, audio, and Flow stages."""
from __future__ import annotations

from typing import List
from pydantic import BaseModel, ConfigDict, Field, model_validator


class CharacterSheet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    character_id: str = Field(min_length=1, max_length=48)
    name: str = Field(min_length=1, max_length=100)
    visual_description: str = Field(min_length=30, max_length=1600)
    continuity_anchors: List[str] = Field(min_length=2, max_length=8)
    reference_image_prompt: str = Field(min_length=40, max_length=3000)


class ScenePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scene_number: int = Field(ge=1, le=99)
    duration_seconds: int = Field(default=8, ge=4, le=10)
    scene_title: str = Field(min_length=3, max_length=120)
    narration: str = Field(min_length=1, max_length=1200)
    start_frame_prompt: str = Field(min_length=40, max_length=3000)
    motion_prompt: str = Field(min_length=30, max_length=1800)
    camera_motion: str = Field(min_length=5, max_length=400)
    sound_effects: List[str] = Field(default_factory=list, max_length=8)
    character_ids: List[str] = Field(default_factory=list, max_length=8)
    continuity_notes: str = Field(min_length=5, max_length=600)


class ThumbnailPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    variant: str = Field(pattern="^(A|B|C)$")
    concept: str = Field(min_length=10, max_length=300)
    image_prompt: str = Field(min_length=40, max_length=2500)
    title_text: str = Field(min_length=3, max_length=60)


class EpisodePackage(BaseModel):
    """Canonical machine-readable episode plan saved as output/episode.json."""

    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=160)
    logline: str = Field(min_length=20, max_length=600)
    topic: str = Field(min_length=3, max_length=500)
    target_audience: str = Field(default="teen and adult general audience", max_length=120)
    synopsis: str = Field(min_length=50, max_length=2400)
    visual_style: str = Field(min_length=30, max_length=1200)
    narration_script: str = Field(min_length=100, max_length=20000)
    characters: List[CharacterSheet] = Field(min_length=1, max_length=12)
    scenes: List[ScenePlan] = Field(min_length=6, max_length=48)
    thumbnail_prompts: List[ThumbnailPrompt] = Field(min_length=3, max_length=3)
    content_notes: List[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def validate_episode(self):
        numbers = [scene.scene_number for scene in self.scenes]
        if numbers != list(range(1, len(self.scenes) + 1)):
            raise ValueError("Scene numbers must be continuous and ordered from 1.")
        ids = [character.character_id for character in self.characters]
        if len(ids) != len(set(ids)):
            raise ValueError("Character IDs must be unique.")
        allowed = set(ids)
        for scene in self.scenes:
            unknown = set(scene.character_ids) - allowed
            if unknown:
                raise ValueError(
                    f"Scene {scene.scene_number} references unknown character IDs: {sorted(unknown)}"
                )
        variants = [item.variant for item in self.thumbnail_prompts]
        if sorted(variants) != ["A", "B", "C"]:
            raise ValueError("Exactly three thumbnail prompts are required: variants A, B, and C.")
        composed_script = " ".join(scene.narration.strip() for scene in self.scenes).strip()
        if len(composed_script.split()) < 80:
            raise ValueError("The episode needs at least 80 spoken words to support a complete story.")
        return self
