import sys
import types
import unittest
from unittest.mock import patch

from whisper_runtime import load_whisper_model, resolve_whisper_runtime


class WhisperRuntimeTests(unittest.TestCase):
    def _fake_ctranslate2(self, count):
        module = types.ModuleType("ctranslate2")
        module.get_cuda_device_count = lambda: count
        return module

    def test_auto_selects_cuda_float16_when_a_cuda_device_is_available(self):
        with patch.dict(sys.modules, {"ctranslate2": self._fake_ctranslate2(1)}):
            self.assertEqual(resolve_whisper_runtime("auto"), ("cuda", "float16"))

    def test_auto_selects_cpu_int8_when_cuda_is_not_available(self):
        with patch.dict(sys.modules, {"ctranslate2": self._fake_ctranslate2(0)}):
            self.assertEqual(resolve_whisper_runtime("auto"), ("cpu", "int8"))

    def test_explicit_cuda_fails_clearly_when_no_cuda_device_is_detected(self):
        with patch.dict(sys.modules, {"ctranslate2": self._fake_ctranslate2(0)}):
            with self.assertRaisesRegex(RuntimeError, "CUDA was explicitly requested"):
                resolve_whisper_runtime("cuda")

    def test_auto_falls_back_to_cpu_when_gpu_model_initialization_fails(self):
        calls = []

        class FakeWhisperModel:
            def __init__(self, model_name, device, compute_type):
                calls.append((model_name, device, compute_type))
                if device == "cuda":
                    raise RuntimeError("cuDNN could not initialize")

        with patch.dict(sys.modules, {"ctranslate2": self._fake_ctranslate2(1)}):
            model, device, compute_type = load_whisper_model(
                FakeWhisperModel, "base.en", device_preference="auto"
            )

        self.assertIsInstance(model, FakeWhisperModel)
        self.assertEqual(device, "cpu")
        self.assertEqual(compute_type, "int8")
        self.assertEqual(calls, [
            ("base.en", "cuda", "float16"),
            ("base.en", "cpu", "int8"),
        ])

    def test_cpu_mode_does_not_require_cuda_detection(self):
        model, device, compute_type = load_whisper_model(
            lambda name, device, compute_type: (name, device, compute_type),
            "base.en",
            device_preference="cpu",
        )
        self.assertEqual(model, ("base.en", "cpu", "int8"))
        self.assertEqual(device, "cpu")
        self.assertEqual(compute_type, "int8")

    def test_invalid_device_preference_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "auto.*cpu.*cuda"):
            resolve_whisper_runtime("tpu")


if __name__ == "__main__":
    unittest.main()
