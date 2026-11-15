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

Gaming highlight detection in the maintained notebook is a signal-based first pass using audio energy and FFmpeg scene-change signals. It does not yet provide the speech transcription, word-level captions, OCR event clues, narration, title animations, or scene-transition effects from the archived experimental workflow. Those features should be integrated into this same notebook only after they are tested against the persistent Drive project flow.

The notebook does not create AI scenes and does not publish automatically. Review the final video, audio, source rights, and YouTube metadata before uploading.
