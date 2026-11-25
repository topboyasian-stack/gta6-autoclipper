# Modular Mystery/Sci-Fi Video Pipeline

## Scope and compatibility

This is an additional narrator-led mystery/sci-fi workflow alongside the existing GTA6 AutoClipper modes, THE 2:17 SIGNAL character-dialogue workflow, engineering explainers, scene assembly, long-form editing, gaming highlights, and the legacy Puffy test. It does not replace or rename those modes.

The workflow follows the five production stages in the provided automation blueprint:

1. Structured episode planning to `episode.json`.
2. Frame, character-reference, and three thumbnail prompt planning; optionally generate images through the Gemini Developer API.
3. Scene-by-scene narrator audio plus word-timed Whisper captions.
4. A single master prompt and ordered Flow manifests, split into bounded batches.
5. FFmpeg assembly with narration, optional ducked music, burned captions, and a quality report.

## Run from a local project folder

Install Python requirements, ensure `ffmpeg` and `ffprobe` are available, and configure `GEMINI_API_KEY` through an environment variable or a local `.env` file that is not committed to Git. The key can also be provided by the maintained Colab notebook through its Secrets panel.

Plan an episode and prepare its upstream assets:

```bash
python main.py --topic "An abandoned coastal radio station receives a warning from tomorrow" --output output
```

This runs planning, image prompt preparation, narration generation, Whisper captions, and Flow manifest creation. It does **not** spend Gemini image API money by default. It writes `episode.json`, `episode_brief.md`, `assets_generation_plan.json` and the readable `assets_generation_plan.md`, `audio/`, `captions/subtitles.srt`, `flow_master_prompt.md`, and `flow_upload_manifest.json/.txt`.

Generate one bounded image API batch only after checking the pricing on the actual Google AI Studio API key:

```bash
python main.py --stage assets --output output --allow-paid-images --max-images 10
```

The image worker never generates more than ten images in a single run. It skips existing assets, so rerunning it continues with missing frames, character references, and thumbnails. It requests 9:16 source images for scene frames and 16:9 images for character references and thumbnails, adapts old saved landscape prompts when reusing an existing episode plan, then normalizes the delivery assets to their target sizes. Repeat only after reviewing the remaining plan. The default image model is configurable through `MYSTERY_IMAGE_MODEL`.

When the image plan is complete, review and correct every starting frame and character reference before production. If you are not authorizing separate Gemini API image charges, use the prompts with a visual-generation workflow already included in your plan/subscription, then save the resulting assets in the paths recorded by the manifest.

## Google AI Pro versus Gemini Developer API

Google AI Pro's Google Flow credits and the Gemini Developer API are separate usage/billing systems. The monthly Pro Flow allowance can be used in Flow, but it does not automatically cover images generated via `google-genai` using an API key. The image API is therefore disabled unless `--allow-paid-images` is explicitly supplied or the separate `ALLOW_PAID_IMAGE_API=true` environment setting is intentionally configured. Google model availability, rate limits, and prices change; check the current [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing) before opting in.

The text planner defaults to `gemini-3.8-flash` and falls back to `gemini-3.5-flash-lite`; both are configurable with `MYSTERY_PLANNER_MODEL` and `MYSTERY_FALLBACK_MODEL`. The optional Gemini Developer API image worker defaults to `gemini-nano-banana-2.1` via `MYSTERY_IMAGE_MODEL`. That image API path remains disabled unless explicitly opted into and can incur charges separate from Google AI Pro.

## Google Flow stage

The Flow worker deliberately prepares the prompt pack instead of silently automating the consumer website. It produces:

- `flow_master_prompt.md` — global continuity and style rules plus scene prompts.
- `flow_upload_manifest.json` — ordered scenes, image paths, motion prompts and expected clip paths.
- `flow_upload_manifest.txt` — readable per-scene checklist.
- Batches of no more than eight scenes by default (absolute cap: twelve); the command-line override remains available, to limit accidental credit use.

Use the chosen Flow model's current credit cost in the UI before generating a batch. Save exported video clips as `flow_clips/scene_001.mp4`, `flow_clips/scene_002.mp4`, and so on. The manifest identifies missing starting frames and clips. This leaves control of authentication, credit spend, and final generation clicks with the account owner rather than relying on brittle selectors or a remote Colab browser pretending to be the Chromebook's logged-in Chrome session.

## Assembly

After all expected clips and audio files are present:

```bash
python main.py --stage assemble --output output
```

Input conventions:

- Flow clips: `output/flow_clips/scene_NNN.mp4`
- Narration audio: `output/audio/scene_NNN.wav`
- Word-timed captions: `output/captions/subtitles.srt`
- Optional licensed background music: `output/assets/music.mp3` (or pass `--music /path/to/licensed_music.mp3`)

Assembly refuses to export if any expected scene clip or narration audio is missing. It normalizes video to portrait 1080×1920 at 30 fps, uses moderate clip speed adjustment where possible, trims or freeze-pads unusual duration mismatches instead of making an extreme speed change, ducks background music under narration, and burns the SRT captions when present. Review `assembly_quality_report.json` and watch the complete master before publishing; a rendered file is not automatically marked approved or published.

## Commands

- `python main.py --stage plan --topic "..." --output output`
- `python main.py --stage assets --output output` (creates prompt plan only; no image API calls)
- `python main.py --stage assets --output output --allow-paid-images --max-images 10`
- `python main.py --stage audio --output output`
- `python main.py --stage flow-pack --output output --max-scenes-per-flow-run 10`
- `python main.py --stage assemble --output output`

An existing `episode.json` is reused instead of being silently overwritten. Use `--force-plan` only when you intend to replace it; the previous JSON is saved to a timestamped backup first.

## Voice and captions

The narrator is generated scene by scene through Edge TTS, then converted to mono 44.1 kHz WAV. Faster-Whisper supplies audio-derived word timestamps; captions are grouped into readable short phrases. This is a single narrator voice, not the per-character cast used by THE 2:17 SIGNAL. The network speech service and available voices may change, and caption timing/transcription must be reviewed.

## Human release gate

Before upload, review the story structure and factual claims if applicable, character identity, starting frames, every Flow shot, narration pronunciation and pacing, subtitle correctness, music rights/attribution, the complete 1080p output, and YouTube audience designation. Nothing is uploaded or published automatically. API image generation and Flow video generation use different usage systems; keep a manual record of both.
