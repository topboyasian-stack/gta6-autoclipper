from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import threading
import time
import uuid
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.getenv("DATA_DIR", ROOT / "data"))
UPLOADS = DATA / "uploads"
CLIPS = DATA / "clips"
for folder in (DATA, UPLOADS, CLIPS):
    folder.mkdir(parents=True, exist_ok=True)
DB = DATA / "clipper.sqlite3"
YOUTUBE_CLIENT_SECRETS = Path(os.getenv("YOUTUBE_CLIENT_SECRETS", str(DATA / "client_secrets.json")))
YOUTUBE_TOKEN_FILE = DATA / "youtube-token.json"
YOUTUBE_REDIRECT_URI = os.getenv("YOUTUBE_REDIRECT_URI", "http://localhost:8000/youtube/oauth/callback")
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
LIVE_DIR = DATA / "live"
LIVE_DIR.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "1024"))
CLIP_SECONDS = max(10, min(90, int(os.getenv("CLIP_SECONDS", "35"))))
MAX_CANDIDATES = max(1, min(20, int(os.getenv("MAX_CANDIDATES", "8"))))
ALLOWED = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
KICK_PAGE_HOSTS = {"kick.com", "www.kick.com"}
KICK_MEDIA_HOST = "clips.kick.com"

app = FastAPI(title="GTA 6 AutoClipper", version="0.2.0")
app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS sources (
            id TEXT PRIMARY KEY, filename TEXT NOT NULL, path TEXT NOT NULL,
            creator TEXT, source_url TEXT, rights_basis TEXT NOT NULL,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        con.execute("""CREATE TABLE IF NOT EXISTS clips (
            id TEXT PRIMARY KEY, source_id TEXT NOT NULL, start REAL NOT NULL,
            duration REAL NOT NULL, score REAL NOT NULL, path TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            youtube_video_id TEXT,
            FOREIGN KEY(source_id) REFERENCES sources(id))""")
        columns = {row["name"] for row in con.execute("PRAGMA table_info(clips)")}
        if "youtube_video_id" not in columns:
            con.execute("ALTER TABLE clips ADD COLUMN youtube_video_id TEXT")
        con.execute("""CREATE TABLE IF NOT EXISTS live_sessions (
            id TEXT PRIMARY KEY, source_id TEXT NOT NULL, creator TEXT NOT NULL,
            source_descriptor TEXT NOT NULL, segment_seconds INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'recording', error TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP, stopped_at TEXT,
            FOREIGN KEY(source_id) REFERENCES sources(id))""")
        con.execute("UPDATE live_sessions SET status='interrupted', stopped_at=CURRENT_TIMESTAMP WHERE status='recording'")


init_db()


def run(args: list[str], timeout: int = 1800) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=True)
    except FileNotFoundError:
        raise HTTPException(500, "FFmpeg/ffprobe was not found. Install FFmpeg and ensure ffmpeg and ffprobe are on PATH.")
    except subprocess.CalledProcessError as exc:
        raise HTTPException(422, f"Media processing failed: {(exc.stderr or '')[-1200:]}")
    except subprocess.TimeoutExpired:
        raise HTTPException(408, "Media processing timed out.")


def probe(path: Path) -> float:
    result = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                  "-of", "default=noprint_wrappers=1:nokey=1", str(path)])
    try:
        return float(result.stdout.strip())
    except ValueError:
        raise HTTPException(422, "Could not read video duration.")


def detect_moments(path: Path, duration: float) -> list[tuple[float, float]]:
    # Decode mono audio to 8 kHz PCM; calculate one-second RMS windows.
    try:
        proc = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1",
                               "-ar", "8000", "-f", "s16le", "pipe:1"],
                              capture_output=True, timeout=3600, check=True)
    except FileNotFoundError:
        raise HTTPException(500, "FFmpeg was not found. Install FFmpeg and ensure it is on PATH.")
    except subprocess.CalledProcessError as exc:
        raise HTTPException(422, f"Audio analysis failed: {(exc.stderr or b'')[-1200:].decode('utf-8', 'replace')}")
    except subprocess.TimeoutExpired:
        raise HTTPException(408, "Audio analysis timed out.")
    import array
    samples = array.array("h")
    samples.frombytes(proc.stdout)
    rate = 8000
    window = rate
    energies = []
    for i in range(0, len(samples) - window, window):
        chunk = samples[i:i + window]
        rms = (sum(x*x for x in chunk) / len(chunk)) ** 0.5
        energies.append(rms)
    if not energies:
        return [(max(0, duration / 2 - CLIP_SECONDS / 2), min(CLIP_SECONDS, duration))]
    # Rank energetic windows, spread candidates apart, and centre clips around peaks.
    ranked = sorted(range(len(energies)), key=lambda i: energies[i], reverse=True)
    chosen = []
    for idx in ranked:
        centre = float(idx)
        if all(abs(centre - old) >= CLIP_SECONDS * 0.75 for old in chosen):
            chosen.append(centre)
        if len(chosen) >= MAX_CANDIDATES:
            break
    moments = []
    for centre in sorted(chosen):
        start = max(0.0, min(max(0.0, duration - CLIP_SECONDS), centre - CLIP_SECONDS / 2))
        moments.append((start, min(CLIP_SECONDS, duration - start)))
    return moments


def render_clip(source: Path, target: Path, start: float, length: float):
    run(["ffmpeg", "-y", "-ss", f"{start:.2f}", "-i", str(source), "-t", f"{length:.2f}",
         "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
         "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(target)], timeout=3600)


class _KickMetaParser(HTMLParser):
    """Read only the public Open Graph metadata needed to resolve a Kick clip."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "meta":
            return
        values = {str(k).lower(): str(v) for k, v in attrs if k and v is not None}
        key = (values.get("property") or values.get("name") or "").lower()
        value = values.get("content", "").strip()
        if key and value:
            self.meta[key] = value


def validate_kick_clip_url(clip_url: str) -> tuple[str, str, str]:
    """Allow only canonical public Kick clip pages, not arbitrary URLs or VODs."""
    try:
        parsed = urlsplit(clip_url.strip())
        port = parsed.port
    except ValueError:
        raise HTTPException(400, "Enter a valid Kick clip URL.")
    if (parsed.scheme.lower() != "https" or parsed.hostname not in KICK_PAGE_HOSTS
            or parsed.username or parsed.password or port not in (None, 443)):
        raise HTTPException(400, "Use an HTTPS clip page from kick.com.")
    match = re.fullmatch(r"/([A-Za-z0-9_]+)/clips/(clip_[A-Za-z0-9]+)", parsed.path.rstrip("/"))
    if not match:
        raise HTTPException(400, "Paste a public Kick clip URL, not a channel page or full VOD link.")
    channel, clip_id = match.groups()
    canonical = f"https://kick.com/{channel}/clips/{clip_id}"
    return canonical, channel, clip_id


def validate_kick_media_url(media_url: str, clip_id: str) -> str:
    """Prevent a clip page from redirecting FFmpeg to an unrelated host."""
    try:
        parsed = urlsplit(media_url)
        port = parsed.port
    except ValueError:
        raise HTTPException(422, "Kick did not provide a valid media URL.")
    if (parsed.scheme.lower() != "https" or parsed.hostname != KICK_MEDIA_HOST
            or parsed.username or parsed.password or port not in (None, 443)):
        raise HTTPException(422, "Kick returned an unexpected media host; import stopped for safety.")
    match = re.fullmatch(r"/clips/[A-Za-z0-9]{2}/(clip_[A-Za-z0-9]+)/playlist\.m3u8", parsed.path)
    if not match or match.group(1) != clip_id:
        raise HTTPException(422, "Kick's playlist did not match the requested clip.")
    return media_url


def resolve_kick_clip(clip_page_url: str, clip_id: str) -> tuple[str, str]:
    """Get a public clip's HLS URL from Kick's page metadata without login or cookies."""
    request = Request(clip_page_url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; GTA6AutoClipper/0.2; public-clip-import)",
        "Accept": "text/html,application/xhtml+xml",
    })
    try:
        with urlopen(request, timeout=20) as response:
            final_url = urlsplit(response.geturl())
            if final_url.scheme != "https" or final_url.hostname not in KICK_PAGE_HOSTS:
                raise HTTPException(422, "Kick redirected outside its public site; import stopped for safety.")
            html = response.read(3 * 1024 * 1024 + 1)
    except HTTPException:
        raise
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise HTTPException(422, f"Could not read that public Kick clip page: {exc}") from exc
    if len(html) > 3 * 1024 * 1024:
        raise HTTPException(422, "Kick clip page was unexpectedly large; import stopped.")
    parser = _KickMetaParser()
    parser.feed(html.decode("utf-8", "replace"))
    media_url = parser.meta.get("og:video", "")
    title = parser.meta.get("og:title", clip_id)
    if not media_url:
        raise HTTPException(422, "No public video playlist was found. Check the clip is available without signing in.")
    return validate_kick_media_url(media_url, clip_id), title


def create_candidates(source_id: str, source_path: Path) -> dict:
    duration = probe(source_path)
    if duration <= 0:
        raise HTTPException(422, "The source video has no readable duration.")
    moments = detect_moments(source_path, duration)
    made = 0
    for start, length in moments:
        if length <= 0:
            continue
        clip_id = uuid.uuid4().hex
        clip_path = CLIPS / f"{clip_id}.mp4"
        render_clip(source_path, clip_path, start, length)
        with db() as con:
            con.execute("INSERT INTO clips(id,source_id,start,duration,score,path) VALUES(?,?,?,?,?,?)",
                        (clip_id, source_id, start, length, 0.0, str(clip_path)))
        made += 1
    return {"source_id": source_id, "filename": source_path.name, "duration": duration, "candidates_created": made}


def rights_text(value: str):
    if len(value.strip()) < 8:
        raise HTTPException(400, "Describe why you have permission to use this footage.")
    return value.strip()


@app.get("/", response_class=HTMLResponse)
def home():
    return (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/health")
def health():
    return {"ok": True, "ffmpeg": shutil.which("ffmpeg") is not None,
            "ffprobe": shutil.which("ffprobe") is not None, "publishing": "disabled"}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...), creator: str = Form(""),
                 source_url: str = Form(""), rights_basis: str = Form(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(415, "Upload MP4, MOV, MKV, WebM or M4V footage.")
    basis = rights_text(rights_basis)
    source_id = uuid.uuid4().hex
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(file.filename or "footage").name)[:100]
    target = UPLOADS / f"{source_id}_{safe_name}"
    size = 0
    try:
        with target.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_MB * 1024 * 1024:
                    raise HTTPException(413, f"File exceeds {MAX_UPLOAD_MB} MB limit.")
                out.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    with db() as con:
        con.execute("INSERT INTO sources(id,filename,path,creator,source_url,rights_basis) VALUES(?,?,?,?,?,?)",
                    (source_id, safe_name, str(target), creator.strip(), source_url.strip(), basis))
    return create_candidates(source_id, target)


@app.post("/api/import-kick")
def import_kick(clip_url: str = Form(...), creator: str = Form("3rdcollector"),
                rights_basis: str = Form(...)):
    """Import one public Kick clip directly; no account cookies or login are used."""
    basis = rights_text(rights_basis)
    clip_page_url, channel, clip_id = validate_kick_clip_url(clip_url)
    media_url, title = resolve_kick_clip(clip_page_url, clip_id)
    source_id = uuid.uuid4().hex
    base_name = re.sub(r"[^A-Za-z0-9._-]", "_", title).strip("._-")[:80] or clip_id
    safe_name = f"{base_name}_{clip_id}.mp4"
    target = UPLOADS / f"{source_id}_{safe_name}"
    try:
        # Kick clips are at most three minutes. Remux first; transcode only if needed.
        try:
            run(["ffmpeg", "-y", "-i", media_url, "-t", "180", "-c", "copy",
                 "-movflags", "+faststart", str(target)], timeout=600)
        except HTTPException as exc:
            target.unlink(missing_ok=True)
            if exc.status_code != 422:
                raise
            run(["ffmpeg", "-y", "-i", media_url, "-t", "180", "-c:v", "libx264",
                 "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "128k",
                 "-movflags", "+faststart", str(target)], timeout=600)
        if not target.exists() or target.stat().st_size == 0:
            raise HTTPException(422, "Kick's clip downloaded as an empty file.")
    except Exception:
        target.unlink(missing_ok=True)
        raise
    with db() as con:
        con.execute("INSERT INTO sources(id,filename,path,creator,source_url,rights_basis) VALUES(?,?,?,?,?,?)",
                    (source_id, safe_name, str(target), creator.strip() or channel, clip_page_url, basis))
    result = create_candidates(source_id, target)
    result["filename"] = safe_name
    result["source_url"] = clip_page_url
    return result


@app.get("/api/clips")
def list_clips(status: Optional[str] = None):
    with db() as con:
        if status in {"pending", "approved", "rejected"}:
            rows = con.execute("""SELECT c.*,s.filename,s.creator,s.source_url
                FROM clips c JOIN sources s ON s.id=c.source_id WHERE c.status=?
                ORDER BY c.created_at DESC""", (status,)).fetchall()
        else:
            rows = con.execute("""SELECT c.*,s.filename,s.creator,s.source_url
                FROM clips c JOIN sources s ON s.id=c.source_id ORDER BY c.created_at DESC""").fetchall()
    return [dict(row) | {"preview": f"/api/clips/{row['id']}/video"} for row in rows]


@app.get("/api/clips/{clip_id}/video")
def clip_video(clip_id: str):
    with db() as con:
        row = con.execute("SELECT path FROM clips WHERE id=?", (clip_id,)).fetchone()
    if not row or not Path(row["path"]).exists():
        raise HTTPException(404, "Clip not found.")
    return FileResponse(row["path"], media_type="video/mp4")


@app.post("/api/clips/{clip_id}/decision")
def decide(clip_id: str, payload: dict):
    status = payload.get("status")
    if status not in {"approved", "rejected"}:
        raise HTTPException(400, "Decision must be approved or rejected.")
    with db() as con:
        cur = con.execute("UPDATE clips SET status=? WHERE id=? AND status='pending'", (status, clip_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "Pending clip not found.")
    return {"id": clip_id, "status": status}


@app.get("/api/stats")
def stats():
    with db() as con:
        sources = con.execute("SELECT COUNT(*) n FROM sources").fetchone()["n"]
        counts = {r["status"]: r["n"] for r in con.execute("SELECT status,COUNT(*) n FROM clips GROUP BY status")}
    return {"sources": sources, "pending": counts.get("pending", 0),
            "approved": counts.get("approved", 0), "rejected": counts.get("rejected", 0)}
