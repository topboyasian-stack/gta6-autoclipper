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

The image worker never generates more than ten images in a single run. It skips existing assets, so rerunning it continues with missing frames, character references, and thumbnails. Repeat only after reviewing the remaining plan. The default image model is configurable through `MYSTERY_IMAGE_MODEL`.

When the image plan is complete, review and correct every starting frame and character reference before production. If you are not authorizing separate Gemini API image charges, use the prompts with a visual-generation workflow already included in your plan/subscription, then save the resulting assets in the paths recorded by the manifest.

## Google AI Pro versus Gemini Developer API

Google AI Pro's Google Flow credits and the Gemini Developer API are separate usage/billing systems. The monthly Pro Flow allowance can be used in Flow, but it does not automatically cover images generated via `google-genai` using an API key. The image API is therefore disabled unless `--allow-paid-images` is explicitly supplied or the separate `ALLOW_PAID_IMAGE_API=true` environment setting is intentionally configured. Google model availability, rate limits, and prices change; check the current [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing) before opting in.

The text planner defaults to `gemini-3.8-flash`, matching the model family already used by the repository's reusable production workflow, and attempts `gemini-3.5-flash-lite` if the primary model fails. Both are configurable with `MYSTERY_PLANNER_MODEL` and `MYSTERY_FALLBACK_MODEL`.

## Google Flow automation and monthly credit plan

The Mystery & Sci-Fi one-click Colab runner now includes a headed Playwright Flow worker. It runs in a visible browser inside the Colab session, stores its authenticated browser profile privately in Google Drive, and reuses that profile on later runs. The account owner signs in normally once and completes any Google security checks; the worker does not handle credentials or bypass Google authentication.

The worker is designed to automate:
1. Generate recurring character-reference images and scene starting frames in Flow.
2. Upload each starting frame and submit the matching motion/camera/continuity instructions.
3. Wait for the new generation result, download it into `flow_clips/scene_NNN.mp4`, and validate the media file.
4. Resume after interruption by skipping completed images and clips.
5. Start FFmpeg assembly automatically once all clips exist.

The Flow website is a consumer UI, not a stable public automation API. The browser selectors must therefore be tested against the live account UI. If a selector or credit-balance reader is not verified, the worker saves screenshots and visible-control diagnostics to `flow_diagnostics/` and stops rather than guessing or spending credits.

### Credit budget

The default production profile uses **Veo 3.1 Lite, 8 seconds, one output per request**. At the currently published Pro rate of 10 credits per scene, a six-scene episode uses about 60 video credits.

| Monthly plan | Video credits | Budget position |
| --- | ---: | --- |
| 10 episodes | 600 | Within 1,000 monthly credits |
| 15 episodes | 900 | Fits while retaining the 100-credit reserve |
| 20 episodes | 1,200 | Stretch target; needs six 50-credit daily refreshes over separate 24-hour windows, while preserving the reserve |

Google AI Pro includes 1,000 monthly Flow credits and a separate 50-credit daily refresh. Daily credits do not roll over. Flow image creation uses a separate daily image-generation allowance; it is not deducted from the monthly video-credit pool. These allowances and model rates can change, so check the live account and official [Flow credit guide](https://support.google.com/googleone/answer/16287445) before changing models.

The worker maintains `flow_credit_ledger.json` in the Drive workspace. It checks the live balance before every video, enforces a 100-credit protected reserve, permits only one output per request, records submitted/unknown jobs as committed spend, and refuses automatic retries after an uncertain Generate click. Only a failure recorded before submission can be retried. It also keeps a daily image-generation ledger. The live balance check is authoritative; the ledger is an additional guard and audit trail.

### Colab usage

Open the one-click runner:
`https://colab.research.google.com/github/topboyasian-stack/gta6-autoclipper/blob/main/notebooks/Mystery_SciFi_One_Click.ipynb`

Run its single code cell. Choose **R** to resume the active/previous episode or **N** to start a new episode and enter its premise. The active project pointer is saved in Drive so a disconnected run can be resumed by default. Each new episode gets its own project folder, while all episodes share the same monthly Flow credit ledger.

On first use, sign in normally in the embedded browser. Keep the Colab cell running while images/videos render. The worker stores the persistent profile at `GTA6_AutoClipper/browser_profiles/google_flow`, credits at `GTA6_AutoClipper/flow_credit_ledger.json`, and scene downloads in the episode's `flow_clips/` folder. If Colab disconnects, run the same notebook again and choose **R**; finished outputs are skipped.

The monthly ledger's `FLOW_CREDIT_CYCLE_ID` must stay unchanged within the same Google Flow monthly credit cycle. At the next monthly allowance reset, archive the previous ledger and set a new cycle ID so the budget never silently resets or double-counts an earlier cycle.

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

Assembly refuses to export if any expected scene clip or narration audio is missing. It normalizes video to 1920×1080 at 24 fps, uses moderate clip speed adjustment where possible, trims or freeze-pads unusual duration mismatches instead of making an extreme speed change, ducks background music under narration, and burns the SRT captions when present. Review `assembly_quality_report.json` and watch the complete master before publishing; a rendered file is not automatically marked approved or published.

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
