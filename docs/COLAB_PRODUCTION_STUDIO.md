# Universal Colab Production Studio

There is **one maintained Google Colab notebook** for all production types. You do not need to download or upload a different notebook for gaming, AI scenes, Shorts, long-form videos, or compilations.

**[Open the Universal Colab Production Studio directly in Google Colab](https://colab.research.google.com/github/topboyasian-stack/gta6-autoclipper/blob/main/notebooks/GTA6_AutoClipper_Browser_Only.ipynb)**

The notebook is maintained at `notebooks/GTA6_AutoClipper_Browser_Only.ipynb` on the repository's `main` branch. Colab opens that GitHub notebook directly. Its setup cell clones or refreshes the repository's `main` branch, so the supporting code comes from GitHub.

The former `GTA6_AutoClipper_GrowthReady.ipynb` is preserved under `archive/` for historical reference only. Do not use it for new productions.

## What each mode does

| Mode | Input | Result |
| --- | --- | --- |
| Gaming highlights | One completed, permitted gameplay video | Ranked candidate highlights for manual review |
| AI scene assembly | Two or more rendered AI scene videos | One assembled video |
| Long-form video | One or more video files | One horizontal 16:9 video |
| Multi-clip compilation | Two or more permitted clips | One assembled video |
| Animated engineering explainer | Two or more original Google Flow engineering scenes | Research-led vertical explainer with scene labels, optional narration/music, reviewed captions and evidence pack |

The same processing path handles scene normalization, audio consistency, aspect-ratio framing, and MP4 assembly. Output can be vertical 9:16 or horizontal 16:9. The notebook does not generate AI scenes; it assembles scene videos generated elsewhere.

## First run

1. Open the Colab link above. Do not upload the `.ipynb` file into Colab.
2. Run the setup cell and allow Google Drive access when prompted.
3. In the control panel, choose the production mode and output format.
4. For the first source import, choose **Upload file(s) from this device once** or **Use a folder already in Google Drive**.
5. Give the project a stable name, such as `GTA6_Scene_Test`.
6. Enter the actual rights basis for the selected video and audio, then confirm it.
7. Run the source and processing cells. Review the preview before exporting.

For the current AI-scene test, place the already-generated scene videos in one Drive folder or select them together in the first upload. Prefix filenames with `03_` and `04_` if those scenes should appear in that order. The notebook processes the supplied files; it does not consume more scene-generation credits.

## Resume without uploading again

The notebook saves the project under:

```
MyDrive/GTA6_AutoClipper/projects/<project-name>/
```

This includes:
- `sources/` — persistent copies of the selected source videos
- `work/` — normalized scenes, draft output, and intermediate files
- `exports/` — final MP4 and export ZIP
- `project_state.json` — project settings and source identity

On a later Colab session, use the same project name and select **Reuse this project's saved sources**. Previously prepared scene files are cached by source size, modification time, output dimensions, and audio setting, so unchanged files do not need to be normalized again.

Colab runtimes are temporary and may terminate. Keep the project in Google Drive rather than relying on `/content` as permanent storage.

## Shorts versus standard YouTube

For standard YouTube channels, square or vertical videos up to three minutes are classified as Shorts. A vertical video longer than three minutes should not be treated as a Short. The notebook checks the duration of assembled Shorts exports and stops an over-length export. Select horizontal 16:9 for a standard long-form video.

Official guidance: [Understand three-minute YouTube Shorts](https://support.google.com/youtube/answer/15424877).

## Monetization and rights

Permission to reuse footage and eligibility for YouTube monetization are separate checks. YouTube's reused-content policy can apply even when a creator has permission. Minimal-change compilations, repetitive template videos, and generic mass-produced AI output may not qualify. Add meaningful original creative input—such as an authored storyline, narration, commentary, analysis, or a distinctive edit—before publishing. No notebook can guarantee monetization approval.

Official guidance: [YouTube channel monetization policies](https://support.google.com/youtube/answer/1311392).

Do not use private, subscriber-only, or otherwise restricted sources without authorization. The notebook accepts files you supply; it does not retrieve arbitrary Kick, Twitch, or YouTube watch-page media. Nothing is uploaded or published automatically.

## Current limitations

The notebook does not create Google Flow scenes and does not publish to YouTube automatically. You still export the new scene videos from Google Flow and place them in the episode's Drive incoming folder. Everything after scene intake is handled by the same studio sequence.

Gaming highlight detection in the separate gaming mode remains a signal-based first pass using audio energy and FFmpeg scene-change signals.

## Animated Engineering Explainer mode — fully reusable workflow

The first original pilot and Google Flow scene prompts are in [ENGINEERING_CHANNEL_PILOT.md](ENGINEERING_CHANNEL_PILOT.md).

This is a reusable episode engine, not a one-off notebook. Every episode receives its own project folder; shared voice, Whisper and licensed music assets live once in the common Drive workspace. You do not create, edit or upload a new notebook for later episodes.

### One-time setup

1. Open the single Colab notebook linked above.
2. In Google AI Studio create a Gemini API key using the free tier. The API key is used for topic research, source checking, and scene-matched script/storyboard creation. Do not enable paid billing for this workflow.
3. In Colab open the **Secrets** panel (key icon). Add a secret called \`GEMINI_API_KEY\`, paste your key, and enable notebook access. Do not paste the key into a notebook cell, GitHub file or ChatGPT.
4. Run the first Colab setup cell and approve Google Drive access.
5. The first engineering production installs the Python packages in the temporary Colab runtime and stores reusable assets in Drive:
   - \`assets/voice_models/\` — a Piper voice model and its downloaded voice MODEL_CARD
   - \`assets/whisper_models/\` — the speech-recognition model cache
   - \`assets/music_library/\` — the seed CC BY music track and licence sidecar
   Later episodes reuse these Drive assets. A Colab runtime may need the packages reinstalled after reconnecting; the large models/music are not downloaded again unless missing.

**Free-tier data notice:** Google says Gemini API free-tier content may be used to improve its products. Do not send private, confidential or sensitive material. Free tier has rate limits and is not unlimited. The studio uses Gemini text generation, not paid Google Search grounding.

### Make a new episode

1. In Google Flow generate and export the episode's scene clips as MP4 files. The Colab studio does not create the Flow clips.
2. In the Colab controls select **Animated engineering explainer**. The output is fixed to vertical 1080×1920 (9:16) Shorts.
3. Enter a new episode title and the question it should answer. Optional topic-focus notes can narrow the angle. Leave the script field blank; the studio writes the original script.
4. The incoming folder changes to an episode-specific path under \`MyDrive/GTA6_AutoClipper/incoming/<episode-slug>/\`. Put only that episode's Flow MP4 clips in this folder.
5. Enter the actual rights basis for the Flow clips/audio and confirm it. This is a rights record, not a claim that every Flow plan or third-party soundtrack is automatically cleared.
6. Leave the automatic research/storyboard switches enabled. Select the default narrator voice, or change it once; the preference is saved in \`assets/studio_config.json\`.
7. Run the second code cell to create a separate project ID and copy the Flow source files into permanent Drive storage.
8. Run the processing cell. It performs the same sequence for every episode:
   - proposes official technical source URLs, fetches the pages and keeps only accessible pages from trusted government, university or recognized engineering domains;
   - uses the fetched page text to prepare an evidence-based technical fact pack;
   - samples the actual Flow clips, builds a storyboard contact sheet, chooses a logical scene order and creates scene labels;
   - writes an original narration script to match the supplied scene set and its duration;
   - generates narration locally with Piper using the downloaded voice model;
   - transcribes the generated narration with Faster-Whisper, creates word-timed SRT captions and compares the transcript with the script;
   - selects a music track that has an explicit commercial-use licence record, and mixes it below the narration;
   - renders a vertical Short, burns in the captions and produces a render report.
9. Caption QA is automatic. If the transcript/script match and SRT structure pass the set thresholds, the studio proceeds without requiring you to edit an SRT. If they fail, rendering is blocked and the SRT plus quality report are saved for inspection. This is automated verification, not a promise that speech recognition is infallible.
10. Watch the finished preview for overall picture and sound quality. In the final cell type \`EXPORT\`. The MP4, metadata, licence credits and production evidence are saved in the episode's \`exports/\` folder and packaged into a ZIP.

### Repeat for as many episodes as you need

For the next video, use the same Colab link and same studio. Change only the new episode's title/question and put the new Flow MP4 files in the incoming folder displayed for that episode. Leave the narrator, caption and licensed-music setup in place. A new timestamped project ID is created automatically. No notebook upload, code edit, manual SRT creation, or per-scene CSV editing is required.

To re-render an earlier episode, set the project ID to that episode's saved ID and choose **Reuse this project's saved sources**. The source scenes, script, narration, music credit, captions and QC report are retained in Drive.

### Automatic assets and licences

- **Voice:** Piper runs locally in Colab. The studio accepts the selected voice only when its downloaded MODEL_CARD confirms the CC0 training chain expected by the production configuration. The Piper engine is GPL-3.0-or-later; the voice-model dataset licence is separate. The engine and voice must not be confused as one licence.
- **Captions:** Faster-Whisper produces word timestamps from the actual narration audio. The studio does not simply display the script and pretend it is a transcript. It checks the spoken transcript against the script before export.
- **Music:** the shared library is seeded with “New Direction” by Kevin MacLeod, licensed under CC BY 3.0 on the tracked Wikimedia Commons file. Required attribution and the licence URL are inserted in the YouTube metadata. Additional tracks can be added only when their commercial-use rights and attribution are recorded.
- **Flow scenes:** you remain responsible for checking the Google Flow terms that apply to your account and any third-party audio embedded in a scene. Mute scene audio when it is not cleared; the generated narration and licensed music remain in the mix.

Official references:
- [Piper voice licensing and commercial-use list](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/COMMERCIAL_USE.md)
- [Piper Python API](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_PYTHON.md)
- [Gemini API pricing and free-tier data-use conditions](https://ai.google.dev/gemini-api/docs/pricing)
- [Faster-Whisper word timestamps](https://github.com/SYSTRAN/faster-whisper)
- [Music track source and CC BY 3.0 licence](https://commons.wikimedia.org/wiki/File:New_Direction_(ISRC_USUAN1100677).mp3)

### What it does not automate

It does not generate new Flow videos, log in to Google Flow on your behalf, upload to YouTube, guarantee engineering accuracy or guarantee YouTube monetisation. If fewer than two source pages can be verified, or the caption quality check fails, the studio stops rather than inventing facts or exporting unreliable captions.
