"""Shared Whisper hardware selection for Colab and local production runs.

Auto mode prefers a usable CTranslate2 CUDA device (T4/L4 and similar), uses
float16 on GPU, and falls back to int8 CPU when CUDA is unavailable or cannot
initialize. Explicit CPU/CUDA choices remain available for reproducibility.
"""
from __future__ import annotations

import os


def resolve_whisper_runtime(device_preference: str | None = None) -> tuple[str, str]:
    """Return the resolved (device, compute_type) for auto, cpu, or cuda mode."""
    preference = (
        device_preference or os.getenv("WHISPER_DEVICE", "auto") or "auto"
    ).strip().lower()
    if preference not in {"auto", "cpu", "cuda"}:
        raise ValueError("Whisper device preference must be 'auto', 'cpu', or 'cuda'.")
    if preference == "cpu":
        return "cpu", "int8"

    cuda_count = 0
    detection_detail = ""
    try:
        import ctranslate2
        cuda_count = int(ctranslate2.get_cuda_device_count())
    except Exception as exc:
        detection_detail = str(exc).replace("\n", " ")[:220]

    if preference == "cuda" and cuda_count < 1:
        detail = f" Detection detail: {detection_detail}" if detection_detail else ""
        raise RuntimeError(
            "CUDA was explicitly requested, but CTranslate2 did not detect a usable CUDA device. "
            "Select 'auto' to fall back safely or choose CPU." + detail
        )
    if cuda_count > 0:
        return "cuda", "float16"
    return "cpu", "int8"


def load_whisper_model(
    model_class,
    model_name: str,
    device_preference: str | None = None,
):
    """Load Whisper on the resolved device, with CPU fallback only in auto mode."""
    preference = (
        device_preference or os.getenv("WHISPER_DEVICE", "auto") or "auto"
    ).strip().lower()
    device, compute_type = resolve_whisper_runtime(preference)
    try:
        model = model_class(model_name, device=device, compute_type=compute_type)
    except Exception as exc:
        if preference == "auto" and device == "cuda":
            print(
                "WARNING: Whisper detected CUDA but GPU model initialization failed; "
                f"falling back to CPU int8. GPU error: {str(exc)[:300]}",
                flush=True,
            )
            model = model_class(model_name, device="cpu", compute_type="int8")
            return model, "cpu", "int8"
        raise RuntimeError(
            f"Whisper could not initialize on {device} using {compute_type}: {exc}"
        ) from exc
    return model, device, compute_type
