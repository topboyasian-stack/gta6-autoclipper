# Universal Colab Production Studio

There is **one maintained Google Colab notebook** for all production types. You do not need to download or upload a different notebook for the new serialized fiction series, gaming highlights, AI scene assembly, engineering explainers, legacy Puffy stories, Shorts or long-form videos.

**[Open the Universal Colab Production Studio directly in Google Colab](https://colab.research.google.com/github/topboyasian-stack/gta6-autoclipper/blob/main/notebooks/GTA6_AutoClipper_Browser_Only.ipynb)**

The notebook is maintained at `notebooks/GTA6_AutoClipper_Browser_Only.ipynb` on the repository's `main` branch. Colab opens that GitHub notebook directly. Its setup cell clones or refreshes the repository's `main` branch, so the supporting code comes from GitHub.

For the current **first six-scene mystery/sci-fi test**, you can instead [open the one-click runner directly in Colab](https://colab.research.google.com/github/topboyasian-stack/gta6-autoclipper/blob/main/notebooks/Mystery_SciFi_One_Click.ipynb). It has one code cell that syncs current code, checks the `GEMINI_API_KEY` Colab Secret, runs preparation, and logs progress to the same project folder in Drive. Use this shortcut only for the six-scene mystery test; it does not replace the Universal Studio for other productions.

The former `GTA6_AutoClipper_GrowthReady.ipynb` is preserved under `archive/` for historical reference only. Do not use it for new productions.

## What each mode does

| Mode | Input | Result |
| --- | --- | --- |
| Gaming highlights | One completed, permitted gameplay video | Ranked candidate highlights for manual review |
| AI scene assembly | Two or more rendered AI scene videos | One assembled video |
| Long-form video | One or more video files | One horizontal 16:9 video |
| Serialized fiction series (THE 2:17 SIGNAL) | 24 ordered silent Google Flow clips plus locked series references and voice cast | Story-first 3–4 minute landscape episode with individual character dialogue, timed captions, licensed score and canonical continuity tracking |
| Kids story production (Puffy — legacy test) | Two or more ordered Google Flow scene MP4s | Original scene-grounded children's story using the preserved Puffy Storybook profile |
| Animated engineering explainer | Two or more original Google Flow engineering scenes | Research-led vertical explainer with automatically generated narration, SRT captions, licensed music, scene labels and production evidence |

The same processing path handles scene normalization, audio consistency, aspect-ratio framing, and MP4 assembly. Output can be vertical 9:16 or horizontal 16:9. The notebook creates a six-scene prompt pack, but you generate the video clips in Google Flow and export the MP4s for the notebook to assemble.

## First run

1. Open the Colab link above. Do not upload the `.ipynb` file into Colab.
2. Run the setup cell and allow Google Drive access when prompted.
3. In the control panel, choose the production mode and output format.
4. The Project ID is generated automatically for every new production mode. Its matching Drive intake folder appears in the **Drive folder** field as `MyDrive/GTA6_AutoClipper/incoming/<Project ID>/`.
5. For source import, choose **Upload file(s) from this device once** or **Use a folder already in Google Drive**. For a later session, choose **Reuse this project's saved sources** and enter the same Project ID.
6. Enter the actual rights basis for the selected video and audio, then confirm it for those exact files.
7. Run the source and processing cells. Review the preview before exporting.

For the current AI-scene test, place the already-generated scene videos in one Drive folder or select them together in the first upload. Prefix filenames with `03_` and `04_` if those scenes should appear in that order. The notebook processes the supplied files; it does not consume more scene-generation credits.

The notebook preserves existing Drive workspaces that use the historical folder spelling `incomming/`: when that folder already exists, it remains the active intake root. Fresh workspaces use `incoming/`. If a per-project intake is empty, the studio checks both folder spellings and their immediate project subfolders, preferring a folder whose name matches the current Puffy story. It never deletes, renames or moves the user's original uploads; recovered scenes are copied into the current project's `sources/` folder.

## Resume without uploading again

Every mode uses the same project manager and receives a unique Project ID. The matching intake folder is:

```
MyDrive/GTA6_AutoClipper/incoming/<Project ID>/
```

The permanent project is saved separately under:

```
MyDrive/GTA6_AutoClipper/projects/<Project ID>/
```

This includes:
- `sources/` — persistent copies of the selected source videos
- `work/` — normalized scenes, draft output, and intermediate files
- `exports/` — final MP4 and export ZIP
- `project_state.json` — project settings and source identity

On a later Colab session, select **Reuse this project's saved sources** and enter the same Project ID. Project state records the production mode; the studio refuses to reuse a project ID for a different mode, so an engineering project cannot accidentally be overwritten by a kids story or gaming edit. Previously prepared scene files are cached by source size, modification time, output dimensions, and audio setting, so unchanged files do not need to be normalized again.

This applies to **Gaming highlights**, **AI scene assembly**, **Long-form video**, **Kids story production**, and **Animated engineering explainer**. Each receives its own `incoming/<Project ID>/` intake and `projects/<Project ID>/` workspace. Shared assets remain in the single `assets/` folder, including the licensed narrator voice model reused by Kids Story and Engineering Explainer. Technical research, engineering-specific storyboard rules, caption QA, music selection and the engineering evidence package remain exclusive to Engineering Explainer mode.

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

## Puffy kids story mode — replaces the compilation slot

Choose **Kids story production — Puffy / legacy test** only to resume the old workflow. It remains inside the same Universal Colab Production Studio and is not the new main series.

1. Leave the Story title at **Puffy's Little Lesson**, or change it for a new story. The Project ID and its separate incoming folder are created automatically.
2. Leave the auto-generated Project ID in place for this new story. The Drive folder field is automatically set to `MyDrive/GTA6_AutoClipper/incoming/<Project ID>/`. This is a separate intake folder, not the Engineering Explainer project.
3. Put the approved Google Flow MP4 scenes in that folder. Use numeric filenames such as `scene_001.mp4`, `scene_002.mp4`, and `scene_003.mp4`; the studio orders them naturally. Two or more scenes are required.
4. Choose **YouTube Shorts — vertical 9:16** or **Standard YouTube — horizontal 16:9**. The standard format fits portrait Flow scenes on a landscape canvas without cropping the main picture.
5. Keep **Mute original source/scene audio** unchecked to preserve Flow sound effects and ambience. Selecting Kids Story resets this setting to unmuted by default.
6. Enter the actual rights basis, confirm it for these exact files, then run the same source-preparation, processing/preview, and export cells used by the other modes.

The legacy narrated Puffy Kids Story path inspects the supplied scene frames and writes one connected, age-appropriate story. It uses a dedicated **Puffy Storybook** narrator profile based on the licence-checked `en_US-ljspeech-medium` public-domain model, with a gentle pitch/formant lift and audio polish. The resulting synthetic narration is child-friendly in style; it is not a recording of an actual child. The profile and audio are saved separately from the Engineering narrator setting, so Engineering's Joe voice is not changed. Original Flow audio is retained underneath at a lower level unless muted. Scene joins are re-encoded to reset timestamps at cuts, and each intermediate video is checked against the source duration. Speech captions are not included in this mode. The engineering explainer continues to use its existing separate research, technical script, narration, caption-QA, licensed-music, and evidence-pack workflow.

The export ZIP contains the finished MP4, YouTube metadata, and project manifest. The metadata reminds you to set the YouTube audience to **Made for Kids** when the video is directed to children. Review the complete story and confirm all Flow scene/audio rights before publishing.

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
6. The incoming folder changes to the episode's dedicated path under `MyDrive/GTA6_AutoClipper/incoming/<Project ID>/`. Put only that episode's six Flow MP4 clips in this folder.
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


## THE 2:17 SIGNAL — serialized animated series

The new default production is a story-first continuing mystery, not a scene-first children's story. Its source of truth is the separate series bible in \`series/the_217_signal/\`. The complete setup and limitations are documented in [THE 2:17 SIGNAL production guide](THE_217_SIGNAL_PRODUCTION.md).

### First-season premise

Amara Dike, a radio repairer in the fictional coastal city of Aderin Bay, restores a decommissioned emergency transmitter. At exactly 02:17, it begins receiving incomplete distress calls describing events approximately 24 hours before they happen. With journalist Dami Folarin and grid engineer Kato Mensah, she follows the warnings into the buried LANTERN project and the unresolved Night of Silence.

The first season is outlined as eight connected episodes. Episode 1 is the only episode that can be prepared before any earlier episode has entered the approved continuity ledger. Later episode scripts read canonical continuity only; abandoned drafts do not change the story bible or future episode context.

### Story-first production sequence

1. Select **Original serialized series — THE 2:17 SIGNAL**. The output is fixed to landscape 1920×1080, with an intended 3–4 minute runtime.
2. Generate the episode screenplay and its 24-scene silent Flow prompt pack before creating footage. Review the logline, immediate dramatic resolution, continuity in/out and ending hook.
3. Generate the three character turnaround sheets with the separate prompts in \`series/the_217_signal/character_reference_prompts.md\`. Save the files to the persistent Drive folder \`series/the_217_signal/character_references/\` as \`amara_reference.png\`, \`dami_reference.png\` and \`kato_reference.png\`.
4. Review the character identities and lock the approved reference images. Their fingerprints are stored; replacing a reference image requires re-approval.
5. Select a proposed voice for each character, create the voice auditions and listen to them. The current Piper catalogue provides only three licence-checked US-English candidates. The voices are provisional and may not fit the intended regional accents. Duplicate fallback models are rejected. Do not approve a voice just because it can generate audio.
6. Lock the voice cast only after every character has a distinct model and the human approval boxes are checked.
7. In the same Google Flow project, add the approved character reference images for each scene and generate the 24 silent clips in prompt order. Dialogue and captions are created separately in the production studio. Export as \`scene_001.mp4\` through \`scene_024.mp4\` into the selected episode's incoming folder.
8. Run the source/preparation and processing cells. The renderer requires locked character images, locked distinct voices and exactly 24 correctly numbered scenes. It creates per-character dialogue, an SRT file, the landscape episode master, music attribution records and a technical render report.
9. Watch the entire episode and check the generated character images against the references. Visual identity cannot yet be automatically certified. Review every line, pronunciation, dialogue-to-picture fit, caption, cut, soundtrack and story beat.
10. Type \`EXPORT\` only after review passes. The export action marks the episode canonical and updates the season ledger. A later episode cannot be drafted until every earlier episode is canonical.

### Known limitations — do not mistake a gate for a guarantee

- Google Flow generation remains manual. The notebook does not log in to Flow, create clips or consume Flow credits.
- Reference images and prompt instructions encourage continuity but cannot force a video model to reproduce a face perfectly. Human review is compulsory.
- This initial render creates voice dialogue independently of the Flow picture. It does not provide true frame-level lip-sync. Use over-shoulder compositions, cutaways, reaction shots and off-screen dialogue until a tested lip-sync process is available.
- The episode renderer checks clip count/order, audio file timing, output codecs, dimensions and duration. It does not automatically judge acting quality, facial continuity, dramatic clarity or audience appeal.
- Character designs, voice assets, script, Flow clips and music each need suitable rights for the intended commercial use. Keep model cards and music licence records with each export.
- The series is in pre-production until reference sheets and voice casting are approved and an end-to-end pilot passes human review. There is no monetization guarantee.
