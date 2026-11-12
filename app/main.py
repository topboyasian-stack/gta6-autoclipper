from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.getenv("DATA_DIR", ROOT / "data"))
UPLOADS = DATA / "uploads"
CLIPS = DATA / "clips"
for folder in (DATA, UPLOADS, CLIPS):
    folder.mkdir(parents=True, exist_ok=True)
DB = DATA / "clipper.sqlite3"
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "1024"))
CLIP_SECONDS = max(10, min(90, int(os.getenv("CLIP_SECONDS", "35"))))
MAX_CANDIDATES = max(1, min(20, int(os.getenv("MAX_CANDIDATES", "8"))))
ALLOWED = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}

app = FastAPI(title="GTA 6 AutoClipper", version="0.1.0")
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
            FOREIGN KEY(source_id) REFERENCES sources(id))""")


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
    if len(rights_basis.strip()) < 8:
        raise HTTPException(400, "Describe why you have permission to use this footage.")
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
                    (source_id, safe_name, str(target), creator.strip(), source_url.strip(), rights_basis.strip()))
    try:
        duration = probe(target)
        moments = detect_moments(target, duration)
        made = 0
        for start, length in moments:
            clip_id = uuid.uuid4().hex
            clip_path = CLIPS / f"{clip_id}.mp4"
            render_clip(target, clip_path, start, length)
            score = 0.0
            with db() as con:
                con.execute("INSERT INTO clips(id,source_id,start,duration,score,path) VALUES(?,?,?,?,?,?)",
                            (clip_id, source_id, start, length, score, str(clip_path)))
            made += 1
        return {"source_id": source_id, "duration": duration, "candidates_created": made}
    except Exception:
        # Preserve the source record for diagnosis; never silently publish.
        raise


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
