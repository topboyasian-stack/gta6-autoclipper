# THE 2:17 SIGNAL — series production guide

**Status: pre-production build.** The story bible and writing/rendering pipeline are in the repository. The character sheets and voices still require human approval, and Google Flow clips are still generated and exported manually.

## The show

THE 2:17 SIGNAL is an original serialized animated science-fiction mystery set in the fictional coastal West African city of Aderin Bay. A radio repairer restores a decommissioned emergency transmitter and starts receiving incomplete distress calls at 02:17, approximately one day before the events they describe. With an investigative journalist and a municipal power-grid engineer, she follows the warnings into the buried LANTERN project and the city's unresolved Night of Silence.

The show is designed for a general teen-and-adult audience. Its tone is serious, grounded, atmospheric and character-led. It is not a children's show and does not use comedy or gag reactions as default engagement devices.

## Canon files

- \`series/the_217_signal/series_bible.json\` — premise, locations, cast, world rules, visual style, themes and character appearance locks.
- \`series/the_217_signal/season_01/outline.json\` — eight episode arcs and their required story beats.
- \`series/the_217_signal/character_reference_prompts.md\` — one turnaround-reference prompt per recurring character.
- \`app/series_studio.py\` — persistent series workspace, episode writing, continuity, voice casting, dialogue and rendering gates.

The canonical copy used during production is under:

\`\`\`
MyDrive/GTA6_AutoClipper/series/the_217_signal/
\`\`\`

Episode projects are separate under:

\`\`\`
MyDrive/GTA6_AutoClipper/projects/the_217_signal_s01e01/
\`\`\`

Drive is authoritative for assets already approved or edited there. The initializer copies a repository template only when a Drive file does not already exist; it does not overwrite the user’s canonical edits.

## Episode format and workflow

The pilot format is 24 ordered clips, approximately eight seconds each, assembled into a 3–4 minute landscape 1920×1080 episode. A vertical Short is a separate discovery edit and must not replace the full episode.

1. Open the maintained Universal Colab Production Studio and select **Original serialized series — THE 2:17 SIGNAL**.
2. Keep the default project ID for Season 1, Episode 1. Generate the screenplay and Flow prompt pack before creating any video.
3. Review the script, scene order, episode summary and ending hook. The writer must satisfy the first-season story beats and all established world rules.
4. Generate the three character turnaround images separately. Save them as \`amara_reference.png\`, \`dami_reference.png\` and \`kato_reference.png\` in the Drive series \`character_references/\` folder. The first generated sheet is a candidate, not an approved reference.
5. Review each sheet for face, hair, skin tone, body proportions, wardrobe, and identifying marks. Use the approval controls only after the three images meet the design brief. Approved files are fingerprinted; replacing a sheet requires re-approval.
6. Select proposed voices and generate the three audition WAVs. Listen to all three. Approve only voices that are intelligible, distinct and suitable. The current locally verified Piper catalogue exposes three US-English candidates; their regional suitability is not assumed. If a model silently falls back to another voice or two characters resolve to the same model, casting cannot be locked.
7. Lock the voice cast after listening. The selected model IDs and approval are saved in the persistent series folder.
8. Open the saved \`flow_prompt_pack.md\`. In one Google Flow project, add the same approved character reference images as reference ingredients for every scene in which each character appears. Generate the 24 silent clips in order. Do not ask Flow to create dialogue or subtitles. Export the MP4s as \`scene_001.mp4\` through \`scene_024.mp4\` into the episode’s incoming folder.
9. Return to Colab, run source/preparation and the dedicated series render step. It checks that there are exactly 24 clips and their filenames are correctly sequenced. It creates dialogue audio from the locked per-character models, SRT captions, a landscape master and a render-quality report.
10. Watch the entire episode, not just the preview opening. Check the character look, visual geography, line delivery, pronunciation, dialogue-to-picture fit, captions, transitions, music and immediate story resolution. Fix failed scenes or lines before export.
11. Type \`EXPORT\` only after the complete review passes. That action packages the episode and records its approved ending state in the season continuity ledger. Drafts never update canon.
12. Generate Episode 2 only after Episode 1 is marked canonical. Each subsequent episode reads only approved continuity records, not abandoned drafts.

## Important honesty and quality limits

- The notebook does **not** operate Google Flow or create video credits automatically. You still generate and export Flow clips in the Flow interface.
- The visual reference lock stores, fingerprints and inserts the same reference instructions into prompts. It cannot force an external video model to reproduce a face perfectly. Human review remains mandatory.
- The initial voice models are technical candidates from the existing licence-checked local catalogue. They are US-English and may not sound like the intended Aderin Bay cast. The voice cast stays provisional until auditioned. Do not use a synthetic voice for a real person's identity without proper rights and permission.
- Dialogue is synthesized and timed independently, then mixed with silent Flow visuals. This first build does not provide true frame-level lip-sync. Stage conversations with cinematic coverage, cutaways, over-shoulder shots and visual reactions; do not present mouth movement as synchronized speech. A later lip-sync integration must be separately tested before it can be considered production quality.
- Generated dialogue has a strict duration gate. The renderer does not accelerate speech excessively just to squeeze a line into a clip.
- Visual consistency is not fully machine-verifiable. A human must compare the generated episode against the approved references and reject visible character drift.
- Music is selected from the existing library only when its licence record is present. The export retains its attribution information. Review all Flow plan terms and any third-party audio before publishing.
- The series is original fiction; factual engineering research checks from the separate engineering production are not repurposed as story facts.
- Nothing is published automatically. Review YouTube synthetic-content disclosure, audience designation, copyright/usage permissions and monetization rules for every release. A series format or AI workflow does not guarantee YPP approval.

## Production files

Each episode package includes:

- \`series_episode_package.json\` — screenplay, story summary, scene manifest, dialogue, continuity in/out and ending hook.
- \`original_script.md\` — readable character dialogue script.
- \`flow_prompt_pack.md\` — the ordered silent-video prompts and continuity directions.
- \`audio/series_dialogue.wav\` — assembled, per-character dialogue track.
- \`audio/series_dialogue_manifest.json\` — speaker/model/timing evidence for each line.
- \`captions/episode.srt\` — timed captions generated from the actual synthesized line durations.
- \`work/series_quality_report.json\` — codec, dimensions, duration, scene count, voice map and manual-review status.
- \`exports/\` — approved final MP4, YouTube metadata and evidence ZIP.

Legacy Puffy Kids Story, engineering explainers, gaming highlights, AI-scene assembly and long-form video remain separate production modes. Do not rename or move their Drive folders to use the new series workflow.
