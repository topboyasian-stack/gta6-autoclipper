# Universal Colab Production Studio

The repository has one Colab notebook for the production workflows. Open it here:

[Open the Universal Colab Production Studio](https://colab.research.google.com/github/topboyasian-stack/gta6-autoclipper/blob/feature/universal-colab-production-studio/notebooks/GTA6_AutoClipper_Browser_Only.ipynb)

## What each mode does

| Mode | Input | Result |
| --- | --- | --- |
| Gaming highlights | One completed gameplay video | Candidate highlights for manual review |
| AI scene assembly | Two or more rendered AI scene videos | One assembled video |
| Long-form video | One or more video files | One horizontal 16:9 video |
| Multi-clip compilation | Two or more permitted clips | One assembled video |

The same processing path handles scene normalization, audio consistency, aspect-ratio framing, and MP4 assembly. Output can be vertical 9:16 or horizontal 16:9. The notebook does not generate AI scenes; it assembles scene videos generated elsewhere.

## First run

1. Open the notebook link above in Google Colab and run the cells from top to bottom.
2. In the control panel, choose the production mode and output format.
3. For the first run, select **Upload file(s) from this device once** or **Use a folder already in Google Drive**.
4. Give the project a stable name, such as `GTA6_Scene_Test`.
5. Enter the actual rights basis for the selected video and audio, then confirm it.
6. Run the source and processing cells. Review the preview before exporting.

For the current AI-scene test, put the already-generated scene videos in one Drive folder or select them together in the upload picker. Prefix filenames with `03_` and `04_` if those scenes should appear in that order. The notebook processes the supplied files; it does not consume more scene-generation credits.

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

## Shorts versus standard YouTube

For standard YouTube channels, YouTube currently categorizes square or vertical videos up to three minutes as Shorts. A vertical video longer than three minutes should not be treated as a Short. The notebook checks the duration of assembled Shorts exports and stops an over-length export. Select horizontal 16:9 for a standard long-form video.

Official guidance: [Understand three-minute YouTube Shorts](https://support.google.com/youtube/answer/15424877).

## Monetization and rights

Permission to reuse footage and eligibility for YouTube monetization are separate checks. YouTube's reused-content policy can apply even when a creator has permission. Minimal-change compilations, repetitive template videos, and generic mass-produced AI output may not qualify. Add meaningful original creative input—such as an authored storyline, narration, commentary, analysis, or a distinctive edit—before publishing. No notebook can guarantee monetization approval.

Official guidance: [YouTube channel monetization policies](https://support.google.com/youtube/answer/1311392).

Do not use private, subscriber-only, or otherwise restricted sources without authorization. The notebook accepts files you supply; it does not retrieve arbitrary Kick, Twitch, or YouTube watch-page media. Nothing is uploaded or published automatically.

## Current limitations

This version assembles supplied video files and generates basic YouTube metadata. It does not yet generate narration or speech captions, create AI scenes, add title animations, or apply scene-transition effects. Review the final video and its audio before uploading.
