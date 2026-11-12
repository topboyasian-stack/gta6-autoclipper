# GTA 6 AutoClipper

A local, rights-aware workflow for turning permitted gaming footage into vertical clips, reviewing each candidate, and uploading approved cuts to YouTube.

## Current features

- Upload local video files and record source/rights details.
- Import an eligible public Kick clip by URL.
- Capture a creator-authorized RTMP/RTMPS feed in segments while the app is running.
- Rank candidate moments using one-second audio energy (72%) plus FFmpeg scene-change signals (28%) when available; falls back to audio-only if scene detection fails.
- Render 1080×1920 clips using a blurred background while preserving the full gameplay frame.
- Review, approve, or reject each candidate in the browser.
- Connect your YouTube channel with OAuth, upload approved clips as **Private**, and use a separate explicit action to make a private upload public.

## What “any streamer” means

Any platform-independent feed can be clipped when the streamer provides a feed that you are authorized to capture and reuse. The app currently accepts RTMP/RTMPS feed URLs for live capture. It does not auto-discover every creator across Kick, Twitch, or YouTube, extract arbitrary watch-page media, bypass logins, or defeat DRM. Public visibility does not by itself grant reposting rights.

For older videos from your own YouTube channel, download your own source with YouTube Studio or Google Takeout, then upload that file in the app and include the YouTube URL as its source. The YouTube Data API is used for publishing, not for downloading a video file from a watch page.

## Requirements

- Python 3.11+
- FFmpeg and ffprobe installed and available on PATH
- A Google Cloud OAuth client JSON for YouTube publishing (optional until you are ready to connect the channel)

## Run locally

From this repository folder:

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux/ChromeOS Linux: source .venv/bin/activate
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
