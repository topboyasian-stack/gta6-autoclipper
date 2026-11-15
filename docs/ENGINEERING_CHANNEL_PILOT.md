# Animated Engineering Channel — Pilot 01

## Working editorial direction

**Format:** vertical 9:16 YouTube Short  
**Pilot title:** How a Parking Lot Can Store a Storm  
**Viewer question:** How can a parking lot temporarily store rainwater beneath its surface?  
**Editorial premise:** Follow one ordinary paved parking lot as the design changes from a runoff-producing surface into a site-specific stormwater-management system.

This is an original topic and production treatment. The channel's final name, logo, colour system and recurring graphics remain configurable; do not imitate another channel's wording, thumbnails, narration, scene composition or exact visual identity.

## Technical research notes

Use these references to check the script and visual details:

- US EPA, Types of Green Infrastructure: https://www.epa.gov/green-infrastructure/types-green-infrastructure
- US EPA, Green Infrastructure Design Strategies: https://www.epa.gov/green-infrastructure/green-infrastructure-design-strategies
- US EPA, Green Streets Design Manual (permeable pavement section): https://www.epa.gov/sites/default/files/2021-04/documents/green_streets_design_manual_feb_2021_web_res_small_508.pdf

Evidence points for the episode:
- Permeable pavement lets rainwater pass through a porous surface or gaps between pavers.
- Water can enter an underlying soil/gravel or stone storage layer.
- Depending on site and soil conditions, water can infiltrate into the ground or be conveyed through an underdrain.
- Bioswales are vegetated channels that slow, filter and treat stormwater.
- Performance depends on site evaluation, soil infiltration, slope, groundwater, loading, pretreatment and maintenance.

Do not invent reservoir dimensions, infiltration rates, rainfall capacity, cost savings or flood-protection guarantees. Do not imply that every parking lot can use the same design. Keep the underdrain as a conditional design element, not a universal requirement.

## Original narration draft (about 60–70 seconds)

"What if a parking lot could store a storm instead of sending all the water rushing away?

Ordinary pavement sheds rain toward drains. Permeable pavement changes the surface: water passes through porous material or open joints into a stone reservoir below.

The spaces between the stones temporarily store runoff while suitable soil absorbs it.

If the soil drains too slowly, a designed underdrain can carry excess water to another stormwater practice or an approved drain.

A planted swale can slow and filter incoming runoff, and help keep sediment away from the pavement.

The design depends on soil, slope, traffic, groundwater and local rainfall. It will not prevent every flood.

It is a site-specific way to reduce runoff and manage more water closer to where it falls."

This is a research-led draft, not a stamped design or engineering recommendation. Review wording, narration timing and technical sources before recording.

## Visual continuity bible for Google Flow

Use the same visual language for every scene:
- High-quality stylised 3D engineering visualization, not photorealistic news footage.
- One consistent medium-sized urban parking lot with the same rectangular footprint, same curb line, same road position and same planted edge.
- Camera geography: road always runs along the rear edge of the lot; planted swale stays along the right-hand edge; main cross-section reveals the same parking surface and subsurface layers.
- Materials: neutral charcoal pavers/asphalt, warm grey aggregate, brown engineered soil, muted green plants, clear blue water with restrained transparent flow.
- Clean daylight, soft shadows, controlled contrast, crisp cutaway edges, readable component silhouettes.
- No brand marks, no creator watermark, no fabricated statistics, no baked-in lettering, no random labels, no logos.
- Do not change the parking lot layout, number of parking bays, road direction, weather geography or material palette between clips.
- Use the first approved frame or still as a visual reference for subsequent Flow generations when the tool supports reference imagery.
- Keep each shot simple: one camera move and one engineering action. Add factual labels later in Colab, where they can be checked and corrected.

## Google Flow scene prompts

Generate seven separate scene clips. Aim for approximately 6–9 seconds each. Save the approved video exports as 01_opening.mp4 through 07_final_system.mp4. Export video files, not GIFs.

### Scene 01 — The problem
Vertical 9:16 stylised 3D engineering animation. Establish the recurring medium-sized urban parking lot in steady heavy rain. Show conventional dark sealed pavement and water flowing across the surface toward curb drains. Begin with a wide elevated view and make one slow push toward the moving runoff. Keep the road along the rear edge and the future planted strip on the right. The scene should communicate surface runoff, not a catastrophic flood. No text, no logos, no watermark.

### Scene 02 — Reveal the conventional surface
Use the same parking lot, same camera geography and same material palette. Transition into a clean vertical cutaway through one parking bay. Show sealed pavement above compacted base and soil, with rainwater staying on the surface and moving toward the drain rather than passing through. Make the layers clear and physically plausible. Slow side-to-side camera drift only. Do not invent measurements or labels.

### Scene 03 — Replace the surface
Continue the same parking lot cross-section. Show workers' hands or an abstract construction sequence replacing the sealed surface with permeable interlocking pavers; emphasize the small open joints between pavers. Rain begins to pass through the surface openings. Keep paving thickness and bay geometry consistent with the previous shot. This is a technical animation, not a time-lapse claim about actual installation duration.

### Scene 04 — The stone reservoir
Maintain the identical cutaway location and orientation. Reveal a clean open-graded stone storage layer beneath the permeable pavers. Blue water moves through the joints and into the voids between stones, temporarily occupying the spaces. Show gradual infiltration into suitable soil below, without numerical capacity indicators or invented flow rates. Smooth downward camera move.

### Scene 05 — The optional underdrain
Keep the exact cross-section and material positions. Add a perforated underdrain pipe within the stone layer as a conditional design option for sites where native soil infiltration is too slow or another controlled outlet is needed. Show water entering the pipe and moving toward an approved downstream stormwater practice. Make the pipe visibly perforated. Do not show it as required in every installation.

### Scene 06 — The planted swale
Return to the same parking lot exterior, with the planted swale along the right edge. Show runoff being guided into a shallow vegetated channel where plants and soil slow and filter the flow before it reaches the permeable pavement system. Use a clear cutaway-to-surface camera transition. Avoid exaggerated purification effects or claims that all pollutants disappear.

### Scene 07 — The complete system
Show the same parking lot in a calm post-rain view. Use one final vertical cutaway that reveals permeable pavers, the stone reservoir, soil infiltration, the optional underdrain route and the vegetated swale. A restrained blue flow animation traces the water path. Finish on a stable wide composition that makes the system understandable at a glance. No statistics, no text, no logos, no watermark.

## Suggested scene-manifest labels

| Order | Scene title | Engineering explanation |
|---|---|---|
| 1 | Rain runs off | Sealed pavement sheds water toward drains |
| 2 | A sealed surface | Conventional pavement limits infiltration |
| 3 | Permeable pavers | Open joints let water pass through |
| 4 | Stone storage | Voids in the stone layer hold runoff temporarily |
| 5 | Optional underdrain | A controlled outlet may help on low-infiltration sites |
| 6 | A planted swale | Vegetation slows and filters incoming runoff |
| 7 | The full system | The components form a site-specific treatment train |

## Audio and caption assembly

Place optional assets in the project after the first source-preparation cell has created the project folders:
- audio/narration.mp3 — a recorded or otherwise properly licensed original narration.
- audio/music.mp3 — original or properly licensed background music.
- captions/episode.srt — reviewed, timed captions.

The Colab renderer adds scene-title lower thirds from scene_manifest.csv, preserves the full Flow frame in a portrait layout, and mixes optional audio. A supplied SRT is burned into the video. The renderer does not generate a voice or fabricate timed captions from the script.

## Final review before upload

- Watch the full Short with sound and without sound.
- Confirm the seven scenes use the same parking lot geometry and material palette.
- Check that the underdrain is described as conditional.
- Check that all claims are supported by the cited references.
- Check narration wording, pronunciation, names and caption timing.
- Confirm Flow scene and audio rights for the intended use.
- Keep the export under three minutes for Shorts eligibility.
- Review YouTube's altered/synthetic-content disclosure guidance and channel monetisation policies before publishing.
