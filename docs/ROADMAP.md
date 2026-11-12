# Roadmap

## Phase 1 — local MVP (implemented)
- Rights-aware manual source upload and public Kick clip import
- Combined audio-energy and scene-change candidate scoring (signal-based first pass)
- FFmpeg 9:16 rendering with blurred backdrop and full gameplay frame preserved
- Browser review and approve/reject queue
- Authorized RTMP/RTMPS live capture segmented while the local app is running
- YouTube OAuth uploads: approved clips upload privately, with a separate action to make public

## Phase 2 — better moment ranking
- Speech transcription and optional local model-based highlight scoring
- Scene-change, laughter, reaction and gameplay-event signals
- Candidate deduplication and adjustable clip duration

## Phase 3 — source adapters (partial)
- Public Kick clip-page import works when a permitted public video playlist is available
- Live capture accepts creator-authorized RTMP/RTMPS feeds; it does not auto-discover or scrape every platform
- Add platform-specific source adapters only when an approved API/feed or creator-authorized workflow exists
- No login bypass, DRM circumvention, or unauthorized stream downloading

## Phase 4 — publishing (implemented, OAuth setup still required)
- YouTube OAuth with the youtube.upload scope
- Upload only explicitly approved clips, private by default
- Separate explicit action to make an uploaded private clip public

## Deployment note
The dashboard can be hosted separately, but media processing requires a persistent machine with FFmpeg and storage. A static Pages deployment is not a video-processing worker. Start locally; evaluate a free compute option only after measuring real workloads.
