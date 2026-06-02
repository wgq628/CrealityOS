# PSD Handoff Plan - No Timer Puzzle Ad

## Objective
- Rebuild the supplied mobile puzzle ad image as a Photoshop-friendly layered file.
- Preserve the visible creative structure: dark background, top headline, maze board, colored balls, and numbered counter tiles.
- Treat this as a production handoff PSD, not a pixel-perfect extraction from the original screenshot.

## Designer Notes
- Open `no_timer_game_psd_handoff_v3_source_assets.psd` in Photoshop.
- Work from the top-level groups: background, board container, game objects, interaction counters, and top UI title.
- Green balls and purple balls are separated into their own subgroups for batch color/style adjustment.
- Most layers are cropped to their non-transparent bounds so transform handles are easier to use.
- Replace raster title with editable text if final localization or typography changes are needed.
- Use the preview PNG as a quick visual reference.

## Limitations
- The original uploaded image bytes were not available in the workspace, so this PSD is a structural reconstruction from the visible screenshot.
- Ball layers use original FKJM game assets (`Ball_3.png` and `Ball_9.png`) at high resolution; board/container layers are still reconstructed raster layers.
- Watermarks are isolated in an optional layer and can be hidden before delivery.
