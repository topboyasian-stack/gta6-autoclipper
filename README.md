# GTA 6 AutoClipper

A local, rights-aware workflow for turning permitted gaming footage into vertical clips, reviewing each candidate, and uploading approved cuts to YouTube.

## Current features

- Upload local video files and record source/rights details.
- Process a Kick clip downloaded through a platform-provided method or supplied by its creator.
- Capture a creator-authorized RTMP/RTMPS feed in segments while the app is running.
- Rank candidate moments using one-second audio energy (72%) plus FFmpeg scene-change signals (28%) when available; falls back to audio-only if scene detection fails.
- Render 1080×1920 clips using a blurred background while preserving the full gameplay frame.
- Produce research-led engineering Shorts from Google Flow scenes, with original scripts, a reusable licensed narrator, word-timed captions and QA, licensed music and an evidence pack.
- Produce narrator-led mystery/sci-fi episodes from a structured story plan, scene image prompts, Edge-TTS narration, word-timed Whisper captions, bounded Google Flow batches and FFmpeg assembly. Gemini image API billing is opt-in and defaults off.
- Review, approve, or reject each candidate in the browser.
- Connect your YouTube channel with OAuth, upload approved clips as **Private**, and use a separate explicit action to make a private upload public.

## What “any streamer” means

Any platform-independent feed can be clipped when the streamer provides a feed that you are authorized to capture and reuse. The app currently accepts RTMP/RTMPS feed URLs for live capture. It does not auto-discover every creator across Kick, Twitch, or YouTube, extract arbitrary watch-page media, bypass logins, or defeat DRM. Public visibility does not by itself grant reposting rights. Direct automated extraction from Kick watch-page media playlists is disabled; its current terms restrict scraping and access methods not provided or authorized by the platform.

For older videos from your own YouTube channel, download your own source with YouTube Studio or Google Takeout, then upload that file in the app and include the YouTube URL as its source. The YouTube Data API is used for publishing, not for downloading a video file from a watch page.

## Requirements

- Python 3.11+
- FFmpeg and ffprobe installed and available on PATH
- A Google Cloud OAuth client JSON for YouTube publishing (optional until you are ready to connect the channel)

## No Linux on your Chromebook? Use Google Colab

Open the [single maintained Universal Colab Production Studio](https://colab.research.google.com/github/topboyasian-stack/gta6-autoclipper/blob/main/notebooks/GTA6_AutoClipper_Browser_Only.ipynb). It is the only maintained Colab production notebook, with selectable modes for mystery/sci-fi automation, the serialized fiction series, gaming highlights, AI-generated scene assembly, animated engineering explainers, long-form videos and the legacy Puffy test. Open it directly from GitHub in Colab; do not download or upload the notebook file itself. The former GrowthReady notebook is archived and is not a separate workflow. Choose vertical 9:16 or horizontal 16:9 output, review the result, and export a ZIP with video and YouTube metadata. The first run can upload files once or read a Google Drive folder; later sessions can reuse the saved project sources without uploading again.

For a straight-through narrator-led mystery workflow, use the [one-click six-scene Colab runner](https://colab.research.google.com/github/topboyasian-stack/gta6-autoclipper/blob/main/notebooks/Mystery_SciFi_One_Click.ipynb). It performs setup, code sync, preparation, narration, captions, Flow image/video generation through a persistent signed-in browser, downloads scene clips, and runs final assembly. It includes a Drive-based credit ledger, live balance checks, a 100-credit reserve, and resumable generation. The default plan is 15 six-scene episodes per 1,000-credit monthly allowance; 20 is a stretch goal using daily 50-credit refreshes. Gemini Developer API image/video charges stay disabled. The one-click mystery runner is a focused workflow, not a replacement for the Universal Studio.

This is an on-demand Colab workflow, not a 24/7 service. Google Colab runtimes are temporary and may terminate, so the project saves source files, checkpoints, and exports in Google Drive. The notebook does not scrape arbitrary watch pages or publish automatically. See the [THE 2:17 SIGNAL production guide](docs/THE_217_SIGNAL_PRODUCTION.md), [series bible](series/the_217_signal/series_bible.json), [season-one outline](series/the_217_signal/season_01/outline.json), [Colab Production Studio guide](docs/COLAB_PRODUCTION_STUDIO.md), the [Animated Engineering Channel pilot](docs/ENGINEERING_CHANNEL_PILOT.md), and the [fan-clipping and YouTube setup guide](docs/YOUTUBE_AND_LIVE_SOURCES.md), and the [mystery/sci-fi automation guide](docs/MYSTERY_SCIFI_PIPELINE.md).

## Run locally

From this repository folder:

```bash
# ChromeOS Linux (recommended beginner path)
bash run_chromeos.sh

# Or manually:
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open [http://localhost:8000](http://localhost:8000). Media processing happens on this computer; keep it running during live capture.

## Connect YouTube

Follow [docs/YOUTUBE_AND_LIVE_SOURCES.md](docs/YOUTUBE_AND_LIVE_SOURCES.md) for Google Cloud setup. Save the OAuth client JSON as `data/client_secrets.json`. The app requests only the `youtube.upload` scope and saves the OAuth token under `data/youtube-token.json`; both files are excluded from Git.

The publishing sequence is always manual:
1. Review the candidate in AutoClipper.
2. Click **Approve**.
3. Click **Upload privately to YouTube** and inspect that private upload.
4. Click **Publish publicly on YouTube** only after your final review and rights check.

## Important limitations

- Current moment finding is a signal-based first pass, not semantic understanding of the game. It can still miss quiet, funny, or context-dependent moments.
- Live capture needs a feed that the streamer authorizes and a working RTMP/RTMPS endpoint. This is not a 24/7 hosted service.
- YouTube publishing needs your own OAuth setup and is subject to YouTube account/API limitations.
- No clip is published automatically. A rights basis must be recorded for each source, but the user remains responsible for ensuring that it genuinely covers recording, editing, and redistribution.
- Keep `data/` private; it can contain source footage, generated clips, the SQLite database and Google OAuth tokens.

## Configuration

- `MAX_UPLOAD_MB`: upload limit, defaults to 1024.
- `CLIP_SECONDS`: candidate clip duration, defaults to 35 (bounded to 10–90).
- `MAX_CANDIDATES`: candidates per source segment, defaults to 8.
- `YOUTUBE_CLIENT_SECRETS`: optional override for `data/client_secrets.json`.
- `YOUTUBE_REDIRECT_URI`: optional override for `http://localhost:8000/youtube/oauth/callback`.

See [the source and YouTube setup guide](docs/YOUTUBE_AND_LIVE_SOURCES.md).
