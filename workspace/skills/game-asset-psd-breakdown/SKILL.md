---
name: game-asset-psd-breakdown
description: Use when a user asks to split or rebuild a polished game image, ad creative, UI scene, level mockup, or generated artwork into reusable PSD-ready assets/layers; analyze elements as direct extraction, clean regeneration, or hybrid repair; create clean generated/repainted element PNGs, 3x3/atlas previews, layer manifests, recomposition checks, Photoshop JSX/UXP scripts, and verified real PSD files while preserving visual fidelity. Triggers include 拆PSD, 图片转PSD, 生成PSD, 拆图层, 拆素材, 游戏元素拆分, 九宫格素材, 可回拼PSD, element breakdown, PSD handoff, image-to-PSD, asset atlas.
---

# Game Asset PSD Breakdown

Use this skill to reverse-build a PSD-ready asset package from a finished game image. The goal is a high-fidelity reusable layer system that can recompose the original layout, not a loose collection of rough cutouts.

## Hard Rules

- If the user asks for a final PSD, deliver a real `.psd`, not only a PNG bundle or JSX. Use Photoshop JSX when Photoshop is available; otherwise be explicit that the package is PSD-ready but not yet a PSD.
- Lock the requested final canvas first, such as `1080 x 1920`. Do not inherit a smaller generated-image size unless the user explicitly accepts it.
- Always classify each visible element before cutting it. Every element must be one of:
  - `extract_direct`: can be cut from the source with no or minimal loss, such as a complete flower, basket, button, icon, prop, or clean foreground object.
  - `regenerate_clean`: should be redrawn as a clean single asset because it is occluded, cropped, polluted by background edges, too duplicated/noisy, or below the required polish.
  - `hybrid_repair`: use the source extraction for coordinate accuracy, then redraw/repair missing edges, occlusion, or contaminated pixels.
- Preserve source resolution and visual polish. Do not downscale, blur, simplify, or repaint over details unless creating a separate clean redraw/reference asset.
- Do not rely on a drawing model to output PSD files. Stable PSD delivery is PNG layers + `psd_layer_manifest.json` + Photoshop JSX/UXP assembly.
- Treat drawing-model output as clean asset reference or replacement candidate only. A generated asset can replace an extracted PSD source only after recomposition validation.
- For `gpt-image-2`, generate one concrete object at a time. Prompts must describe visual content, material, angle, lighting, silhouette, padding, and constraints; never use vague project labels such as a game name as the core prompt.
- Do not depend on transparent-background support from image generation. Default to an opaque pure chroma-key background for generated assets, then remove it with Pillow/OpenCV and validate edges locally.
- Repeated elements get one source asset plus many manifest placements. Do not export duplicate copies unless the repeats are visually different.
- Large non-repeating regions must be separated too: background, cabinets, shelves, boards, panels, floors, shadows, glow, particles, UI frames, and text/CTA.
- Always produce a recomposition preview, a 50% overlay, a diff/fidelity JSON, and a QA report before claiming PSD readiness.
- If the source is a flat raster, label the result as a reverse reconstruction package, not a native PSD recovery.
- If direct cutouts look dirty, stop using them as final PSD sources. Switch to the production route: regenerate clean assets, remove white/chroma background, and place them by the original layout coordinates.

## Default Package Layout

```text
breakdown/
├── assets/
│   ├── extracted/
│   ├── generated_reference/
│   └── final_psd_sources/
├── preview/
├── scripts/
│   └── compose_psd.jsx
├── psd_layer_manifest.json
├── asset_decision_report.md
├── fidelity_score.json
└── PSD_BREAKDOWN_QA.md
```

## Workflow

1. Gather inputs:
   - source image
   - optional clean/empty base image
   - target canvas size
   - user quality bar and whether generated assets may be considered
2. Analyze the image:
   - Use OpenCV for connected components, high-saturation regions, Canny edges, dominant colors, and repeated-element hints.
   - Use full-canvas layer strategy for large structures so shadows, perspective, and gradients are not lost to local crops.
   - For repeated objects, pick the cleanest and least occluded source instance as the single reusable asset.
3. Build or update the spec:
   - Start from `references/spec-template.json`.
   - Use `elements[]`, not only old `assets/layers`, for professional work.
   - Each element records `id`, `type`, `group`, `source_box`, `expected_instances`, `occlusion_level`, `repeat_key`, `decision`, `preferred_tool`, `mask_strategy`, `generation_prompt`, and `placements[]`.
4. Run the helper:
   - `python scripts/decompose_game_image.py --source <image.png> --out <breakdown-dir> --spec <spec.json>`
   - Add `--empty-base <image.png>` when a clean cabinet/background/base exists.
   - Add `--gpt-image-mode off|reference|repair` depending on whether generated assets are allowed.
   - Add `--quality strict|balanced|fast`; use `strict` for final art delivery.
5. Review outputs:
   - `asset_decision_report.md`: why each element was directly cut, regenerated, or hybrid repaired.
   - `preview/asset_atlas_3x3.png`: source assets arranged as an atlas.
   - `preview/recomposition_preview.png`: manifest-driven rebuild.
   - `preview/original_recompose_overlay_50pct.png`: original/rebuild overlay.
   - `fidelity_score.json`: mean RGB diff, hot spots, alpha/edge risks, and PSD-ready status.
6. Generate or repair clean assets only where needed:
   - For `regenerate_clean` and `hybrid_repair`, use `gpt-image-2` as a single-asset redraw/repair tool, not as a PSD generator.
   - Keep generated outputs in `assets/generated_reference/` until they pass local edge checks and recomposition.
   - If a generated replacement changes silhouette, petal count, material, perspective, lighting, or scale, keep it as reference and do not replace the manifest source.
7. Assemble PSD:
   - Use `scripts/compose_psd.jsx` in Photoshop via `File > Scripts > Browse`.
   - The JSX places transparent PNGs by manifest order, position, size, rotation, and layer names, then saves a layered PSD.
   - If Photoshop is unavailable, deliver the PNG bundle + manifest + JSX and state that the `.psd` itself still requires running the script.

## Production PSD Route

Use this route when the user cares about final quality more than reverse-extraction speed, or when a prior PSD has dirty edges, missing layers, wrong size, or bad placement.

1. Set the canvas exactly from the requirement, for example `1080 x 1920`.
2. Use the approved source image only as layout reference. Do not treat it as the main asset source unless a region is clean enough to pass QA.
3. Generate or redraw each reusable element separately:
   - one flower type per asset
   - one basket source
   - one cabinet/board structure source
   - one background source
   - one effects layer or effects cluster where particles are too small to isolate
4. Prefer white or pure chroma-key backgrounds during generation. Remove the background locally and inspect for white/green fringe.
5. Keep repeated assets as one source plus many placements. Scale placements from reference coordinates to the target canvas.
6. Generate a Photoshop JSX that creates/saves the PSD natively. If Photoshop path is known, run it and verify the resulting `.psd` with `psd-tools`.
7. Run a placement correction pass if the PSD composite does not match the approved source: size and position must be corrected, not explained away.

### Three-pass PSD Prompt Pattern

When using a multimodal image model as part of the workflow, adapt the user's three-pass pattern into concrete instructions:

```text
Pass 1: Split this illustration into separate images. Keep each element as its own layer source and do not change its relative position. Use a plain white background, not fake transparency.

Pass 2: Build a PSD at the required canvas size. Remove the white background, keep every element as an individual layer, minimize white fringe, and preserve the layout from the original image.

Pass 3: The PSD placement/scale is not close enough. Reposition every layer and restore the original sizes and coordinates relative to the approved image.
```

Do not send these lines verbatim if they are too abstract for the model. Expand them with concrete objects, colors, materials, view angle, and exact target canvas.

## Tool Decision Matrix

- `pillow`: RGBA management, exact crop, alpha composite, resizing, atlas, overlay, manifest-friendly previews.
- `opencv`: GrabCut, chroma-key removal, color/saturation thresholding, morphology, feathered edges, inpaint, connected-component analysis, diff heatmaps.
- `sam_optional`: useful when available for promptable segmentation; never make it a required v1 dependency.
- `gpt-image-2`: clean redraw/reference/repair for one element at a time; force concrete prompts and local validation.
- `manual_review`: required when the element is tiny, glossy, smoky, particle-heavy, text-like, strongly occluded, or visually critical but below fidelity threshold.

## Fidelity Gates

- Keep antialiased edges and soft shadows. Avoid hard rectangular crops unless the element is truly rectangular.
- Background, cabinet, shelf, board, floor, large light/shadow, and parallax backplates should usually be full-canvas layers.
- Effects may be isolated as surrounding transparent layers instead of over-cut into impossible individual pixels.
- Flag a layer as `needs_manual_refine` if alpha is noisy, edge color pollution is high, source crop is incomplete, generated transparency fails, or overlay hot spots hit a critical subject.
- The QA report must split layers into:
  - PSD-ready direct layers
  - generated/reference-only layers
  - hybrid or manual-refine layers
  - known differences from the flat source

## Prompting Clean Assets

Use concrete visual descriptions:

```text
Create one isolated reusable game asset: a front-facing pink five-petal blossom with a warm yellow center, soft hand-painted mobile game shading, slightly glossy petal edges, top-left warm light, no stem, centered with generous padding, on a solid pure green chroma-key background. No text, no watermark, no extra objects.
```

For atlas prompts, describe each cell's object and state that the atlas is a clean redraw reference, not a coordinate reconstruction source.

## Output Checklist

- [ ] `assets/extracted/`, `assets/generated_reference/`, and `assets/final_psd_sources/` exist.
- [ ] Every element has `decision` and `preferred_tool`.
- [ ] Repeated elements are represented by one source asset plus placements in manifest.
- [ ] Backgrounds, structures, props, effects, and UI/text areas are included where visible.
- [ ] `preview/asset_atlas_3x3.png` exists.
- [ ] `preview/recomposition_preview.png` matches source canvas size.
- [ ] `preview/original_recompose_overlay_50pct.png` exists.
- [ ] `fidelity_score.json` includes diff score, hot spots, alpha risks, and status.
- [ ] `asset_decision_report.md` explains direct/regenerate/hybrid decisions.
- [ ] `psd_layer_manifest.json` records canvas, assets, placements, paths, reuse keys, processing decisions, and source roles.
- [ ] `scripts/compose_psd.jsx` can be run in Photoshop to save a layered PSD.
- [ ] If final PSD is requested, the actual `.psd` exists and has been opened or parsed for canvas size, layer count, preview/composite, and key layer names.
- [ ] Target canvas size matches the request, not just the source-image pixel size.
- [ ] `PSD_BREAKDOWN_QA.md` clearly states exact layers, approximate layers, manual cleanup, and the reverse-reconstruction caveat.
