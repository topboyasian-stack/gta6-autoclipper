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
| Animated engineering explainer | Two or more original Google Flow engineering scenes | Research-led vertical explainer with automatically generated narration, SRT captions, licensed music, scene labels and production evidence |

The same processing path handles scene normalization, audio consistency, aspect-ratio framing, and MP4 assembly. Output can be vertical 9:16 or horizontal 16:9. The notebook creates a six-scene prompt pack, but you generate the video clips in Google Flow and export the MP4s for the notebook to assemble.

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
   Later episodes reuse these Drive assets. The studio rotates among available licensed tracks for new episodes and keeps the chosen track when resuming an existing episode. A Colab runtime may need the packages reinstalled after reconnecting; the large models/music are not downloaded again unless missing.

**Free-tier data notice:** Google says Gemini API free-tier content may be used to improve its products. Do not send private, confidential or sensitive material. Free tier has rate limits and is not unlimited. The studio uses Gemini text generation, not paid Google Search grounding.

### Make a new episode with Google AI Pro + Flow

1. In the Colab controls select **Animated engineering explainer**. The output is fixed to vertical 1080×1920 (9:16) Shorts.
2. Enter the new episode title and viewer question. Optional topic-focus notes can narrow the angle. Leave the script field blank; the studio writes the original sourced script after it sees the clips.
3. Click **Generate six Flow scene prompts**. The studio uses the Gemini API key saved in Colab Secrets and displays a copy-ready prompt for each scene. The prompt pack is saved under My Drive/GTA6_AutoClipper/flow_prompt_packs/ as Markdown and JSON. This step consumes Gemini API quota, not Flow video credits.
4. Open Google Flow and use **Veo 3.1 Lite**, **8 seconds**, **vertical 9:16**, **720p** for each clip. Google currently lists 10 credits per Veo 3.1 Lite generation for non-Ultra plans; check the visible credit cost in Flow before generating. If the account offers 1080p upscaling at no extra credits, use it after generation. Model names and costs can change.
5. Copy each of the six prompts into Flow and generate six clips in the same project, following the visual continuity guide. Download/export the approved clips as MP4 files.
6. The incoming folder changes to an episode-specific path under MyDrive/GTA6_AutoClipper/incoming/<episode-slug>/. Put only that episode's six Flow MP4 clips in this folder.
7. Enter the actual rights basis for the Flow clips/audio and confirm it only after checking the applicable rights. This is a rights record, not a claim that every Flow plan or third-party soundtrack is automatically cleared.
8. Leave the automatic research/storyboard switches enabled. Select the default narrator voice, or change it once; the preference is saved in assets/studio_config.json.
9. Run the source/preparation cell to copy the scene files into permanent Drive storage, then run the processing cell and preview the result.
10. Watch the finished preview. Caption match and timestamp checks run automatically; failed checks block final rendering and retain a diagnostic report. Run the export cell only after the preview is acceptable.

### Google AI Pro monthly credit budget

Google's current Flow help lists **1,000 monthly credits plus 50 daily credits** for AI Pro. Daily credits do not roll over. Veo 3.1 Lite currently costs **10 credits per generated clip** for the 4-, 6-, or 8-second options on non-Ultra plans; supported 1080p upscaling currently costs no extra credits for Pro, but always verify the current cost in Flow before generating.

At six 8-second scenes per Short, 20 Shorts require about **1,200 credits** before retries. A 25% replacement allowance brings the plan to about **1,500 credits**. The 1,000 monthly credits alone are not enough for the full reserve; daily credits can cover it when they are used on the days they refresh. Thirty Shorts with the same reserve would need about 2,250 credits and depends on making consistent use of those daily credits. These are planning estimates, not guaranteed quotas. Official reference: [Google Flow credit refresh and pricing](https://support.google.com/flow/answer/16526234).

The notebook does not control Google Flow or spend Flow credits automatically. You still generate and download the scenes yourself; the studio takes over after the MP4s are in the incoming folder.

The existing Pilot 01 prompt pack intentionally remains a separate seven-scene set so previously generated pilot clips can still be used. The six-scene credit plan applies to new prompt packs generated in the notebook.

### Automatic assets and licences

- **Voice:** Piper runs locally in Colab. The studio accepts Joe/Mike only when the downloaded MODEL_CARD confirms the CC0 rdh training chain, and uses a public-domain LJSpeech model as fallback when its own card confirms that status. The Piper engine is GPL-3.0-or-later; the voice-model dataset licence is separate. Piper notes that whether a trained model is legally a derivative of its training corpus is unsettled, so the included MODEL_CARD and engine licence note are preserved in each episode's evidence ZIP. This is not a blanket legal guarantee for all jurisdictions or uses.
- **Captions:** Faster-Whisper produces word timestamps from the actual narration audio. The studio does not simply display the script and pretend it is a transcript. It checks the spoken transcript against the script before export.
- **Music:** the shared library is seeded with multiple Kevin MacLeod tracks, each separately documented on Wikimedia Commons under CC BY 3.0. The studio rotates between available tracks for new episodes, records the source and licence, and inserts the required attribution, licence URL and modification note into the YouTube metadata. Additional tracks can be added only when their commercial-use rights and attribution are recorded.
- **Flow scenes:** you remain responsible for checking the Google Flow terms that apply to your account and any third-party audio embedded in a scene. Mute scene audio when it is not cleared; the generated narration and licensed music remain in the mix.

Official references:
- [Piper voice licensing and commercial-use list](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/COMMERCIAL_USE.md)
- [Piper Python API](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_PYTHON.md)
- [Gemini API pricing and free-tier data-use conditions](https://ai.google.dev/gemini-api/docs/pricing)
- [Faster-Whisper word timestamps](https://github.com/SYSTRAN/faster-whisper)
- [Music track source and CC BY 3.0 licence](https://commons.wikimedia.org/wiki/File:New_Direction_(ISRC_USUAN1100677).mp3)

### What it does not automate

It does not generate new Flow videos, log in to Google Flow on your behalf, upload to YouTube, guarantee engineering accuracy or guarantee YouTube monetisation. If fewer than two source pages can be verified, or the caption quality check fails, the studio stops rather than inventing facts or exporting unreliable captions.
