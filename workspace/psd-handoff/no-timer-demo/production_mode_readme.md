# Production PSD Mode

This mode generates a Photoshop JSX script instead of writing the final PSD directly.

## Use
1. Open Photoshop.
2. Run `File > Scripts > Browse...`.
3. Select `no_timer_game_production_handoff.jsx`.
4. Review the generated groups and editable title.
5. Save the document as PSD from Photoshop.

## Why this mode exists
- Photoshop can create a cleaner production document than a third-party PSD writer.
- Text can be editable.
- Groups and subgroups are created in Photoshop's native layer panel.
- The preview image is placed as a low-opacity locked reference layer.
- Green and purple ball layers are placed from the original FKJM source PNGs, not reconstructed from the reference screenshot.

## Current limits
- Board placeholders are Photoshop raster fills, not final vector smart objects yet.
- The script is a production scaffold: refine gradients, strokes, and exact geometry inside Photoshop.
- For final polish, convert placed FKJM ball layers to smart objects if repeated non-destructive edits are needed.
