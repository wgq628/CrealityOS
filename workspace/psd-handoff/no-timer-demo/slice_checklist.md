# Slice Checklist

- Hide `01_reference_watermarks_optional` before any production export.
- Keep `05_TOP_UI_TITLE` independent from the background so localization can replace it.
- Keep `50_green_counter_tile_16` and `51_purple_counter_tile_11` independent if the gameplay number state changes.
- Keep `03A_GREEN_BALLS` and `03B_PURPLE_BALLS` independent for batch color swaps, repositioning, or animation tests.
- Export final full-frame ad at `1080x1920` for this demo; for real placement, resize/rebuild to the target store or ad network spec.
- Before delivery, run a visual pass for board alignment, title safe area, and contrast against the dark background.
