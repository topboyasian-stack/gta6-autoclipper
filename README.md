# GTA 6 AutoClipper

A rights-aware, approval-first workflow for turning permitted gaming footage into vertical clips.

## MVP status

This first version runs locally: upload footage you own or are licensed to use, detect loud audio moments, render 9:16 candidate clips with FFmpeg, and approve/reject them in a browser dashboard. It does not scrape or download third-party streams and does not publish automatically.

## Requirements
- Python 3.11+
- FFmpeg and ffprobe installed and available on PATH

## Run
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000.

## Workflow
1. Confirm you have the rights to use the footage.
2. Upload an MP4/MOV/WebM file and record its source and rights basis.
3. The worker analyses audio energy for candidate moments and renders vertical previews.
4. Review every candidate; approve or reject it.
5. Approved clips are staged locally. YouTube OAuth/upload is intentionally not enabled in this MVP.

## Important limitations
- Loudness is only a first-pass signal, not semantic understanding. It can miss quiet funny moments and flag explosions/music.
- Processing happens on the machine running this app. Cloudflare Pages alone cannot run FFmpeg or continuously capture streams.
- Never upload footage from another creator unless their permission/licence covers editing and redistribution.
- Keep `data/` private; it contains source footage, generated clips and the SQLite database.

## Configuration
`MAX_UPLOAD_MB` defaults to 1024. Set `CLIP_SECONDS` (default 35) and `MAX_CANDIDATES` (default 8) to tune processing.
