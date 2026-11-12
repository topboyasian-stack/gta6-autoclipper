# Roadmap

## Phase 1 — local MVP (this commit)
- Rights-aware manual source upload
- Audio-energy candidate detection
- FFmpeg 9:16 rendering
- Browser review and approval/rejection

## Phase 2 — better moment ranking
- Speech transcription and optional local model-based highlight scoring
- Scene-change, laughter, reaction and gameplay-event signals
- Candidate deduplication and adjustable clip duration

## Phase 3 — source adapters
- Add only sources with an approved API/feed or creator-authorized workflow
- Store creator, source URL, permission evidence, permitted platforms and expiry
- No login bypass, DRM circumvention, or unauthorized stream downloading

## Phase 4 — publishing
- YouTube OAuth with least-privilege scopes
- Upload only explicitly approved clips
- Draft/private by default, with upload history and revoke controls

## Deployment note
The dashboard can be hosted separately, but media processing requires a persistent machine with FFmpeg and storage. A static Pages deployment is not a video-processing worker. Start locally; evaluate a free compute option only after measuring real workloads.
