from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
PYDEPS = ROOT / ".codex_tmp_pydeps"
if PYDEPS.exists():
    sys.path.insert(0, str(PYDEPS))


BASE_WIDTH = 365
BASE_HEIGHT = 649
WIDTH = 1080
HEIGHT = 1920
OUT_DIR = ROOT / "workspace" / "psd-handoff" / "no-timer-demo"
ASSET_ROOT = Path(r"\\192.168.250.61\视频处理\0-基础素材\1-个人文件夹\王义倩\可玩广告\方块解谜\260305\工程文件\FKJM")


def sx(value: float) -> int:
    return round(value * WIDTH / BASE_WIDTH)


def sy(value: float) -> int:
    return round(value * HEIGHT / BASE_HEIGHT)


def sc(value: float) -> int:
    return max(1, round(value * ((WIDTH / BASE_WIDTH + HEIGHT / BASE_HEIGHT) / 2)))


def sbox(box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    return sx(box[0]), sy(box[1]), sx(box[2]), sy(box[3])


def load_pytoshop():
    try:
        from pytoshop import enums  # type: ignore
        from pytoshop.image_data import ImageData  # type: ignore
        from pytoshop.user import nested_layers  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "handoff-raster mode requires pytoshop. Install it with: "
            "python -m pip install pytoshop"
        ) from exc
    return enums, ImageData, nested_layers


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf") if bold else Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/seguisb.ttf") if bold else Path("C:/Windows/Fonts/segoeui.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def transparent() -> Image.Image:
    return Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))


def add_layer(layers: list[tuple[str, Image.Image]], name: str, im: Image.Image) -> None:
    layers.append((name, im))


def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    fill: tuple[int, int, int, int],
    text_font: ImageFont.ImageFont,
) -> None:
    box = sbox(box)
    bbox = draw.textbbox((0, 0), text, font=text_font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = box[0] + (box[2] - box[0] - tw) / 2 - bbox[0]
    y = box[1] + (box[3] - box[1] - th) / 2 - bbox[1]
    draw.text((x, y), text, font=text_font, fill=fill)


def rounded_rect_layer(
    box: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, int, int, int],
    outline: tuple[int, int, int, int] | None = None,
    width: int = 1,
) -> Image.Image:
    im = transparent()
    d = ImageDraw.Draw(im)
    d.rounded_rectangle(sbox(box), radius=sc(radius), fill=fill, outline=outline, width=sc(width))
    return im


def ellipse_layer(
    box: tuple[int, int, int, int],
    fill: tuple[int, int, int, int],
    outline: tuple[int, int, int, int] | None = None,
    width: int = 1,
) -> Image.Image:
    im = transparent()
    d = ImageDraw.Draw(im)
    d.ellipse(sbox(box), fill=fill, outline=outline, width=sc(width))
    return im


def ball_layer(cx: int, cy: int, color: str) -> Image.Image:
    source_name = "Ball_9.png" if color == "green" else "Ball_3.png"
    source_path = ASSET_ROOT / source_name
    size = sc(41)
    canvas = transparent()
    if source_path.exists():
        ball = Image.open(source_path).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
        shadow_path = ASSET_ROOT / "marbleShadow.png"
        if shadow_path.exists():
            shadow_w = round(size * 1.10)
            shadow_h = round(size * 0.58)
            shadow = Image.open(shadow_path).convert("RGBA").resize((shadow_w, shadow_h), Image.Resampling.LANCZOS)
            shadow.putalpha(shadow.getchannel("A").point(lambda a: round(a * 0.58)))
            canvas.alpha_composite(shadow, (sx(cx) - shadow_w // 2, sy(cy) + round(size * 0.19)))
        canvas.alpha_composite(ball, (sx(cx) - size // 2, sy(cy) - size // 2))
        return canvas

    scale = 8
    radius = size * scale / 2
    y, x = np.ogrid[: size * scale, : size * scale]
    center = (size * scale - 1) / 2
    dx = x - center
    dy = y - center
    dist = np.sqrt(dx * dx + dy * dy) / radius

    if color == "green":
        core = np.array([0, 205, 28], dtype=np.float32)
        rim = np.array([0, 88, 14], dtype=np.float32)
        mid = np.array([15, 235, 42], dtype=np.float32)
        glow = np.array([110, 255, 120], dtype=np.float32)
    else:
        core = np.array([194, 0, 225], dtype=np.float32)
        rim = np.array([82, 0, 141], dtype=np.float32)
        mid = np.array([218, 16, 246], dtype=np.float32)
        glow = np.array([255, 110, 255], dtype=np.float32)

    light = np.clip(1.18 - 0.55 * dist - 0.14 * (dx / radius) + 0.20 * (-dy / radius), 0.0, 1.25)
    edge_mix = np.clip((dist - 0.62) / 0.30, 0.0, 1.0)[..., None]
    rgb = mid * (1 - edge_mix) + rim * edge_mix
    rgb = np.clip(rgb * light[..., None] + core * 0.18, 0, 255)

    alpha = np.clip((1.02 - dist) / 0.06, 0.0, 1.0) * 255

    highlight_dist = ((dx + 10 * scale) / (9 * scale)) ** 2 + ((dy + 12 * scale) / (6 * scale)) ** 2
    highlight = np.clip(1 - highlight_dist, 0.0, 1.0)[..., None]
    rgb = rgb * (1 - highlight * 0.50) + glow * (highlight * 0.50)

    shine_dist = ((dx + 2 * scale) / (21 * scale)) ** 2 + ((dy + 1 * scale) / (19 * scale)) ** 2
    shine_ring = np.clip((shine_dist - 0.55) / 0.06, 0.0, 1.0) * np.clip((0.74 - shine_dist) / 0.08, 0.0, 1.0)
    left_mask = (dx < 0).astype(np.float32)
    rgb = rgb * (1 - shine_ring[..., None] * left_mask[..., None] * 0.38) + np.array([255, 255, 255], dtype=np.float32) * (shine_ring[..., None] * left_mask[..., None] * 0.38)

    arr = np.dstack([rgb, alpha]).astype(np.uint8)
    ball = Image.fromarray(arr, "RGBA").resize((size, size), Image.Resampling.LANCZOS)
    shadow = Image.new("RGBA", (size + 4, size + 4), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse((3, 4, size + 1, size + 2), fill=(0, 0, 0, 82))
    shadow = shadow.filter(ImageFilter.GaussianBlur(1.2))

    canvas.alpha_composite(shadow, (sx(cx) - size // 2 - sc(2), sy(cy) - size // 2 - sc(1)))
    canvas.alpha_composite(ball, (sx(cx) - size // 2, sy(cy) - size // 2))
    return canvas


def draw_background(layers: list[tuple[str, Image.Image]]) -> None:
    bg = Image.new("RGBA", (WIDTH, HEIGHT), (44, 60, 74, 255))
    add_layer(layers, "00_background_dark_blue", bg)

    watermark = transparent()
    d = ImageDraw.Draw(watermark)
    wm_font = font(sc(11))
    for x, y in [(120, 32), (94, 180), (25, 350), (70, 592)]:
        overlay = Image.new("RGBA", (sc(150), sc(24)), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.text((sc(4), sc(3)), "蓝湖风 0820", font=wm_font, fill=(94, 111, 125, 40))
        overlay = overlay.rotate(-18, expand=True)
        watermark.alpha_composite(overlay, (sx(x), sy(y)))
    add_layer(layers, "01_reference_watermarks_optional", watermark)


def draw_title(layers: list[tuple[str, Image.Image]]) -> None:
    shadow = transparent()
    sd = ImageDraw.Draw(shadow)
    title_font = font(sc(43), bold=True)
    draw_centered_text(sd, (0, 48, BASE_WIDTH, 112), "NO TIMER!", (0, 0, 0, 72), title_font)
    shadow = shadow.filter(ImageFilter.GaussianBlur(sc(2.0)))
    add_layer(layers, "10_title_shadow", shadow)

    title = transparent()
    td = ImageDraw.Draw(title)
    draw_centered_text(td, (0, 46, BASE_WIDTH, 110), "NO TIMER!", (255, 255, 255, 255), title_font)
    add_layer(layers, "11_title_no_timer_editable_raster", title)


def draw_board(layers: list[tuple[str, Image.Image]]) -> None:
    board_shadow = rounded_rect_layer((12, 151, 354, 538), 13, (22, 32, 44, 130))
    board_shadow = board_shadow.filter(ImageFilter.GaussianBlur(sc(2.4)))
    add_layer(layers, "20_board_shadow", board_shadow)

    frame = rounded_rect_layer((14, 153, 353, 537), 12, (130, 149, 196, 255), (102, 121, 171, 255), 3)
    add_layer(layers, "21_board_outer_frame", frame)

    grid = transparent()
    gd = ImageDraw.Draw(grid)
    tile = 46
    start_x = 23
    start_y = 163
    for r in range(8):
        for c in range(7):
            x = start_x + c * tile
            y = start_y + r * tile
            gd.rectangle(sbox((x, y, x + tile - 1, y + tile - 1)), fill=(166, 185, 204, 255), outline=(134, 154, 180, 255), width=sc(2))
            gd.line((sx(x + 3), sy(y + 2), sx(x + tile - 4), sy(y + 2)), fill=(188, 204, 218, 100), width=sc(1))
    add_layer(layers, "22_board_tile_grid", grid)

    maze = transparent()
    md = ImageDraw.Draw(maze)
    dark = (45, 60, 74, 255)
    outline = (115, 133, 183, 255)
    md.rounded_rectangle(sbox((60, 207, 110, 344)), radius=sc(8), fill=dark, outline=outline, width=sc(5))
    md.rounded_rectangle(sbox((161, 207, 207, 253)), radius=sc(8), fill=dark, outline=outline, width=sc(5))
    md.rounded_rectangle(sbox((202, 253, 254, 299)), radius=sc(8), fill=dark, outline=outline, width=sc(5))
    md.rounded_rectangle(sbox((252, 300, 300, 346)), radius=sc(8), fill=dark, outline=outline, width=sc(5))
    md.rounded_rectangle(sbox((14, 391, 116, 430)), radius=sc(8), fill=dark, outline=outline, width=sc(5))
    md.rounded_rectangle(sbox((207, 391, 254, 476)), radius=sc(8), fill=dark, outline=outline, width=sc(5))
    md.rounded_rectangle(sbox((162, 438, 253, 484)), radius=sc(8), fill=dark, outline=outline, width=sc(5))
    add_layer(layers, "23_maze_cutout_channels", maze)

    highlight = transparent()
    hd = ImageDraw.Draw(highlight)
    hd.rounded_rectangle(sbox((16, 155, 351, 535)), radius=sc(10), outline=(190, 205, 235, 115), width=sc(2))
    add_layer(layers, "24_board_top_edge_highlight", highlight)


def draw_special_tiles(layers: list[tuple[str, Image.Image]]) -> None:
    green = rounded_rect_layer((299, 164, 340, 206), 4, (12, 180, 22, 255), (83, 255, 94, 255), 3)
    d = ImageDraw.Draw(green)
    d.rectangle(sbox((302, 167, 337, 203)), outline=(6, 105, 13, 180), width=sc(1))
    draw_centered_text(d, (322, 164, 342, 181), "16", (255, 255, 255, 255), font(sc(12), bold=True))
    add_layer(layers, "50_green_counter_tile_16", green)

    purple = rounded_rect_layer((69, 346, 113, 390), 4, (140, 0, 217, 255), (184, 83, 255, 255), 3)
    d = ImageDraw.Draw(purple)
    draw_centered_text(d, (93, 346, 113, 364), "11", (255, 255, 255, 255), font(sc(12), bold=True))
    add_layer(layers, "51_purple_counter_tile_11", purple)


def draw_balls(groups: dict[str, list[tuple[str, Image.Image]]]) -> None:
    balls = [
        (47, 184, "purple"),
        (92, 184, "green"),
        (139, 184, "purple"),
        (181, 184, "green"),
        (276, 184, "green"),
        (139, 231, "green"),
        (231, 231, "green"),
        (47, 278, "purple"),
        (276, 278, "purple"),
        (323, 278, "green"),
        (47, 322, "purple"),
        (139, 322, "green"),
        (184, 322, "purple"),
        (231, 322, "green"),
        (47, 366, "green"),
        (323, 366, "purple"),
        (139, 413, "purple"),
        (184, 413, "green"),
        (323, 413, "green"),
        (47, 459, "green"),
        (323, 459, "purple"),
        (47, 505, "purple"),
        (92, 505, "green"),
        (139, 505, "green"),
        (231, 505, "green"),
        (276, 505, "purple"),
        (323, 505, "green"),
    ]
    for index, (cx, cy, color) in enumerate(balls, start=1):
        group_name = "purple_balls" if color == "purple" else "green_balls"
        add_layer(groups[group_name], f"60_ball_{index:02d}_{color}_{cx}_{cy}", ball_layer(cx, cy, color))


def composite(layers: list[tuple[str, Image.Image]]) -> Image.Image:
    out = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    for _, layer in layers:
        out.alpha_composite(layer)
    return out


def image_to_psd_layer(name: str, im: Image.Image, enums, nested_layers):
    arr = np.array(im.convert("RGBA"))
    alpha = arr[:, :, 3]
    ys, xs = np.where(alpha > 0)
    if len(xs) == 0 or len(ys) == 0:
        left = top = 0
        right = bottom = 1
        arr = np.zeros((1, 1, 4), dtype=np.uint8)
    else:
        left = int(xs.min())
        right = int(xs.max() + 1)
        top = int(ys.min())
        bottom = int(ys.max() + 1)
        arr = arr[top:bottom, left:right, :]
    channels = {
        0: arr[:, :, 0].astype(np.uint8),
        1: arr[:, :, 1].astype(np.uint8),
        2: arr[:, :, 2].astype(np.uint8),
        enums.ChannelId.transparency: arr[:, :, 3].astype(np.uint8),
    }
    return nested_layers.Image(
        name=name,
        top=top,
        left=left,
        bottom=bottom,
        right=right,
        channels=channels,
        color_mode=enums.ColorMode.rgb,
    )


def write_psd(groups: dict[str, list[tuple[str, Image.Image]]], preview: Image.Image, path: Path) -> None:
    enums, ImageData, nested_layers = load_pytoshop()

    def make_group(name: str, layers: list[tuple[str, Image.Image]], closed: bool = True):
        return nested_layers.Group(
            name=name,
            layers=[image_to_psd_layer(layer_name, im, enums, nested_layers) for layer_name, im in layers],
            closed=closed,
        )

    # Photoshop displays the first records at the top of the layer panel.
    # Keep visual foreground groups first so the full-canvas background never
    # covers the board and game objects.
    psd_layers = [
        make_group("05_TOP_UI_TITLE", groups["title"]),
        make_group("04_INTERACTION_COUNTERS", groups["interaction"]),
        nested_layers.Group(
            name="03_GAME_OBJECTS",
            layers=[
                make_group("03B_PURPLE_BALLS", groups["purple_balls"]),
                make_group("03A_GREEN_BALLS", groups["green_balls"]),
            ],
            closed=False,
        ),
        make_group("02_BOARD_CONTAINER", groups["board"]),
        make_group("01_BACKGROUND", groups["background"]),
    ]
    psd = nested_layers.nested_layers_to_psd(
        psd_layers,
        color_mode=enums.ColorMode.rgb,
        size=(WIDTH, HEIGHT),
        compression=enums.Compression.raw,
    )
    rgb = np.array(preview.convert("RGB")).transpose(2, 0, 1).astype(np.uint8)
    psd.image_data = ImageData(channels=rgb, compression=enums.Compression.raw)
    with path.open("wb") as fd:
        psd.write(fd)


def write_docs(groups: dict[str, list[tuple[str, Image.Image]]]) -> None:
    plan = """# PSD Handoff Plan - No Timer Puzzle Ad

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
"""

    layer_map = "# Layer Map\n\n"
    display_groups = [
        ("05_TOP_UI_TITLE", [name for name, _ in groups["title"]]),
        ("04_INTERACTION_COUNTERS", [name for name, _ in groups["interaction"]]),
        ("03_GAME_OBJECTS / 03B_PURPLE_BALLS", [name for name, _ in groups["purple_balls"]]),
        ("03_GAME_OBJECTS / 03A_GREEN_BALLS", [name for name, _ in groups["green_balls"]]),
        ("02_BOARD_CONTAINER", [name for name, _ in groups["board"]]),
        ("01_BACKGROUND", [name for name, _ in groups["background"]]),
    ]
    for title, names in display_groups:
        layer_map += f"## {title}\n"
        for name in names:
            layer_map += f"- `{name}`\n"
        layer_map += "\n"

    checklist = """# Slice Checklist

- Hide `01_reference_watermarks_optional` before any production export.
- Keep `05_TOP_UI_TITLE` independent from the background so localization can replace it.
- Keep `50_green_counter_tile_16` and `51_purple_counter_tile_11` independent if the gameplay number state changes.
- Keep `03A_GREEN_BALLS` and `03B_PURPLE_BALLS` independent for batch color swaps, repositioning, or animation tests.
- Export final full-frame ad at `1080x1920` for this demo; for real placement, resize/rebuild to the target store or ad network spec.
- Before delivery, run a visual pass for board alignment, title safe area, and contrast against the dark background.
"""

    layer_names = [name for group_layers in groups.values() for name, _ in group_layers]
    manifest = {
        "source": "uploaded chat screenshot reconstructed by visual inspection",
        "canvas": {"width": WIDTH, "height": HEIGHT},
        "psd": "no_timer_game_psd_handoff_v3_source_assets.psd",
        "preview": "no_timer_game_psd_preview_v3_source_assets.png",
        "layer_count": len(layer_names),
        "groups": {
            "01_BACKGROUND": [name for name, _ in groups["background"]],
            "02_BOARD_CONTAINER": [name for name, _ in groups["board"]],
            "03A_GREEN_BALLS": [name for name, _ in groups["green_balls"]],
            "03B_PURPLE_BALLS": [name for name, _ in groups["purple_balls"]],
            "04_INTERACTION_COUNTERS": [name for name, _ in groups["interaction"]],
            "05_TOP_UI_TITLE": [name for name, _ in groups["title"]],
        },
        "layers": layer_names,
        "handoff_status": "ready_for_photoshop_refinement",
        "technical_channel": "Python Pillow high-resolution raster reconstruction + original FKJM ball assets + pytoshop PSD writer; raw PSD compression for compatibility.",
        "asset_root": str(ASSET_ROOT),
        "source_assets": {
            "green_ball": str(ASSET_ROOT / "Ball_9.png"),
            "purple_ball": str(ASSET_ROOT / "Ball_3.png"),
            "ball_shadow": str(ASSET_ROOT / "marbleShadow.png"),
        },
        "limitations": [
            "Original image bytes were not available as a workspace file.",
            "Reconstruction is layered and editable, but not pixel-perfect.",
            "Layers are raster PSD layers, not Photoshop vector shapes or smart objects.",
        ],
    }

    (OUT_DIR / "psd_handoff_plan.md").write_text(plan, encoding="utf-8")
    (OUT_DIR / "layer_map.md").write_text(layer_map, encoding="utf-8")
    (OUT_DIR / "slice_checklist.md").write_text(checklist, encoding="utf-8")
    (OUT_DIR / "psd_handoff_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def export_source_assets() -> dict[str, str]:
    asset_dir = OUT_DIR / "source_assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    exported = {}
    for role, filename in {
        "green_ball": "Ball_9.png",
        "purple_ball": "Ball_3.png",
        "ball_shadow": "marbleShadow.png",
    }.items():
        src = ASSET_ROOT / filename
        if src.exists():
            dst = asset_dir / filename
            shutil.copy2(src, dst)
            exported[role] = str(dst)
    return exported


def build_groups() -> dict[str, list[tuple[str, Image.Image]]]:
    groups: dict[str, list[tuple[str, Image.Image]]] = {
        "background": [],
        "board": [],
        "green_balls": [],
        "purple_balls": [],
        "interaction": [],
        "title": [],
    }
    draw_background(groups["background"])
    draw_board(groups["board"])
    draw_balls(groups)
    draw_special_tiles(groups["interaction"])
    draw_title(groups["title"])
    return groups


def render_order(groups: dict[str, list[tuple[str, Image.Image]]]) -> list[tuple[str, Image.Image]]:
    return [
        *groups["background"],
        *groups["board"],
        *groups["green_balls"],
        *groups["purple_balls"],
        *groups["interaction"],
        *groups["title"],
    ]


def write_raster_mode(groups: dict[str, list[tuple[str, Image.Image]]]) -> dict:
    ordered_layers = render_order(groups)

    preview = composite(ordered_layers)
    preview_path = OUT_DIR / "no_timer_game_psd_preview_v3_source_assets.png"
    psd_path = OUT_DIR / "no_timer_game_psd_handoff_v3_source_assets.psd"
    preview.save(preview_path)
    write_psd(groups, preview, psd_path)
    write_docs(groups)
    exported_assets = export_source_assets()
    return {
        "mode": "handoff-raster",
        "out_dir": str(OUT_DIR),
        "psd": str(psd_path),
        "preview": str(preview_path),
        "source_assets": exported_assets,
        "layer_count": len(ordered_layers),
        "group_count": 6,
    }


def jsx_string(preview_path: Path, exported_assets: dict[str, str]) -> str:
    preview_for_js = str(preview_path).replace("\\", "/")
    green_for_js = exported_assets.get("green_ball", str(ASSET_ROOT / "Ball_9.png")).replace("\\", "/")
    purple_for_js = exported_assets.get("purple_ball", str(ASSET_ROOT / "Ball_3.png")).replace("\\", "/")
    shadow_for_js = exported_assets.get("ball_shadow", str(ASSET_ROOT / "marbleShadow.png")).replace("\\", "/")
    balls = [
        (47, 184, "purple"), (92, 184, "green"), (139, 184, "purple"), (181, 184, "green"), (276, 184, "green"),
        (139, 231, "green"), (231, 231, "green"), (47, 278, "purple"), (276, 278, "purple"), (323, 278, "green"),
        (47, 322, "purple"), (139, 322, "green"), (184, 322, "purple"), (231, 322, "green"), (47, 366, "green"),
        (323, 366, "purple"), (139, 413, "purple"), (184, 413, "green"), (323, 413, "green"), (47, 459, "green"),
        (323, 459, "purple"), (47, 505, "purple"), (92, 505, "green"), (139, 505, "green"), (231, 505, "green"),
        (276, 505, "purple"), (323, 505, "green"),
    ]
    ball_rows = "\n".join(
        f"  {{name: 'ball_{i:02d}_{color}_{sx(x)}_{sy(y)}', x: {sx(x)}, y: {sy(y)}, color: '{color}'}}," for i, (x, y, color) in enumerate(balls, start=1)
    )
    return f"""#target photoshop
app.displayDialogs = DialogModes.NO;

var DOC_W = {WIDTH};
var DOC_H = {HEIGHT};
var PREVIEW_PATH = "{preview_for_js}";
var GREEN_BALL_PATH = "{green_for_js}";
var PURPLE_BALL_PATH = "{purple_for_js}";
var BALL_SHADOW_PATH = "{shadow_for_js}";

function rgb(r, g, b) {{
  var c = new SolidColor();
  c.rgb.red = r;
  c.rgb.green = g;
  c.rgb.blue = b;
  return c;
}}

function makeGroup(name, parent) {{
  var g = parent.layerSets.add();
  g.name = name;
  return g;
}}

function fillRect(doc, parent, name, x, y, w, h, color) {{
  var layer = doc.artLayers.add();
  layer.name = name;
  layer.move(parent, ElementPlacement.INSIDE);
  doc.selection.select([[x, y], [x + w, y], [x + w, y + h], [x, y + h]]);
  doc.selection.fill(color, ColorBlendMode.NORMAL, 100, false);
  doc.selection.deselect();
  return layer;
}}

function fillCircleApprox(doc, parent, name, cx, cy, r, color) {{
  var pts = [];
  for (var i = 0; i < 48; i++) {{
    var a = Math.PI * 2 * i / 48;
    pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]);
  }}
  var layer = doc.artLayers.add();
  layer.name = name;
  layer.move(parent, ElementPlacement.INSIDE);
  doc.selection.select(pts);
  doc.selection.fill(color, ColorBlendMode.NORMAL, 100, false);
  doc.selection.deselect();
  return layer;
}}

function boundsPx(layer) {{
  var b = layer.bounds;
  return [b[0].as("px"), b[1].as("px"), b[2].as("px"), b[3].as("px")];
}}

function centerLayer(layer, cx, cy) {{
  var b = boundsPx(layer);
  var currentCx = (b[0] + b[2]) / 2;
  var currentCy = (b[1] + b[3]) / 2;
  layer.translate(cx - currentCx, cy - currentCy);
}}

function placePngLayer(doc, parent, path, name, cx, cy, targetW, targetH, opacity) {{
  var f = new File(path);
  if (!f.exists) return null;
  var src = app.open(f);
  src.activeLayer.name = name;
  src.activeLayer.duplicate(doc, ElementPlacement.PLACEATBEGINNING);
  src.close(SaveOptions.DONOTSAVECHANGES);
  app.activeDocument = doc;
  var layer = doc.activeLayer;
  layer.name = name;
  layer.move(parent, ElementPlacement.INSIDE);
  var b = boundsPx(layer);
  var w = b[2] - b[0];
  var h = b[3] - b[1];
  if (w > 0 && h > 0) layer.resize(targetW / w * 100, targetH / h * 100, AnchorPosition.MIDDLECENTER);
  centerLayer(layer, cx, cy);
  if (opacity != undefined) layer.opacity = opacity;
  return layer;
}}

function addEditableText(doc, parent) {{
  var layer = doc.artLayers.add();
  layer.name = "title_text_EDITABLE_NO_TIMER";
  layer.kind = LayerKind.TEXT;
  layer.move(parent, ElementPlacement.INSIDE);
  var t = layer.textItem;
  t.contents = "NO TIMER!";
  t.size = {sc(43)};
  t.font = "Arial-BoldMT";
  t.color = rgb(255, 255, 255);
  t.justification = Justification.CENTER;
  t.position = [DOC_W / 2, {sy(94)}];
  return layer;
}}

function placeReference(doc, parent) {{
  try {{
    var f = new File(PREVIEW_PATH);
    if (!f.exists) return;
    var refDoc = app.open(f);
    refDoc.activeLayer.name = "reference_preview_locked";
    refDoc.activeLayer.duplicate(doc, ElementPlacement.PLACEATBEGINNING);
    refDoc.close(SaveOptions.DONOTSAVECHANGES);
    app.activeDocument = doc;
    doc.activeLayer.name = "reference_preview_locked";
    doc.activeLayer.opacity = 35;
    doc.activeLayer.move(parent, ElementPlacement.INSIDE);
    doc.activeLayer.allLocked = true;
  }} catch (e) {{}}
}}

var doc = app.documents.add(DOC_W, DOC_H, 72, "no_timer_game_production_handoff", NewDocumentMode.RGB, DocumentFill.TRANSPARENT);

var bg = makeGroup("01_BACKGROUND", doc);
var board = makeGroup("02_BOARD_CONTAINER", doc);
var objects = makeGroup("03_GAME_OBJECTS", doc);
var greenBalls = makeGroup("03A_GREEN_BALLS", objects);
var purpleBalls = makeGroup("03B_PURPLE_BALLS", objects);
var counters = makeGroup("04_INTERACTION_COUNTERS", doc);
var title = makeGroup("05_TOP_UI_TITLE", doc);
var guides = makeGroup("99_REFERENCE_AND_GUIDES", doc);

fillRect(doc, bg, "background_dark_blue_FILL", 0, 0, DOC_W, DOC_H, rgb(44, 60, 74));

fillRect(doc, board, "board_outer_frame_placeholder", {sx(14)}, {sy(153)}, {sx(353)-sx(14)}, {sy(537)-sy(153)}, rgb(130, 149, 196));
fillRect(doc, board, "board_tile_grid_base_placeholder", {sx(23)}, {sy(163)}, {sx(345)-sx(23)}, {sy(531)-sy(163)}, rgb(166, 185, 204));
fillRect(doc, board, "maze_dark_cutout_placeholder", {sx(60)}, {sy(207)}, {sx(110)-sx(60)}, {sy(344)-sy(207)}, rgb(45, 60, 74));
fillRect(doc, board, "maze_dark_cutout_placeholder_2", {sx(202)}, {sy(253)}, {sx(254)-sx(202)}, {sy(299)-sy(253)}, rgb(45, 60, 74));
fillRect(doc, board, "maze_dark_cutout_placeholder_3", {sx(18)}, {sy(395)}, {sx(114)-sx(18)}, {sy(426)-sy(395)}, rgb(45, 60, 74));
fillRect(doc, board, "maze_dark_cutout_placeholder_4", {sx(207)}, {sy(391)}, {sx(254)-sx(207)}, {sy(479)-sy(391)}, rgb(45, 60, 74));

var balls = [
{ball_rows}
];
for (var i = 0; i < balls.length; i++) {{
  var b = balls[i];
  var target = b.color == "green" ? greenBalls : purpleBalls;
  var ballPath = b.color == "green" ? GREEN_BALL_PATH : PURPLE_BALL_PATH;
  placePngLayer(doc, target, BALL_SHADOW_PATH, b.name + "_shadow_from_FKJM", b.x, b.y + {sc(18)}, {sc(45)}, {sc(24)}, 58);
  var placed = placePngLayer(doc, target, ballPath, b.name + "_source_asset_from_FKJM", b.x, b.y, {sc(41)}, {sc(41)}, 100);
  if (placed == null) {{
    var color = b.color == "green" ? rgb(0, 205, 28) : rgb(194, 0, 225);
    fillCircleApprox(doc, target, b.name + "_fallback_shape", b.x, b.y, {sc(20)}, color);
  }}
}}

fillRect(doc, counters, "counter_green_16_editable_placeholder", {sx(299)}, {sy(164)}, {sx(340)-sx(299)}, {sy(206)-sy(164)}, rgb(12, 180, 22));
fillRect(doc, counters, "counter_purple_11_editable_placeholder", {sx(69)}, {sy(346)}, {sx(113)-sx(69)}, {sy(390)-sy(346)}, rgb(140, 0, 217));

addEditableText(doc, title);
placeReference(doc, guides);

doc.activeLayer = title;
alert("Production handoff scaffold created. Save as PSD after reviewing groups, editable title, reference, and object layers.");
"""


def write_production_mode(groups: dict[str, list[tuple[str, Image.Image]]]) -> dict:
    preview_path = OUT_DIR / "no_timer_game_psd_preview_v3_source_assets.png"
    if not preview_path.exists():
        composite(render_order(groups)).save(preview_path)

    exported_assets = export_source_assets()
    jsx_path = OUT_DIR / "no_timer_game_production_handoff.jsx"
    jsx_path.write_text(jsx_string(preview_path, exported_assets), encoding="utf-8")

    readme = """# Production PSD Mode

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
"""
    readme_path = OUT_DIR / "production_mode_readme.md"
    readme_path.write_text(readme, encoding="utf-8")

    return {
        "mode": "handoff-production",
        "out_dir": str(OUT_DIR),
        "jsx": str(jsx_path),
        "readme": str(readme_path),
        "reference_preview": str(preview_path),
        "source_assets": exported_assets,
        "creates": [
            "01_BACKGROUND",
            "02_BOARD_CONTAINER",
            "03_GAME_OBJECTS/03A_GREEN_BALLS",
            "03_GAME_OBJECTS/03B_PURPLE_BALLS",
            "04_INTERACTION_COUNTERS",
            "05_TOP_UI_TITLE",
            "99_REFERENCE_AND_GUIDES",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate No Timer PSD handoff assets.")
    parser.add_argument(
        "--mode",
        choices=["handoff-raster", "handoff-production", "both"],
        default="both",
        help="handoff-raster writes a grouped PSD directly; handoff-production writes a Photoshop JSX production scaffold.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    groups = build_groups()

    outputs = []
    if args.mode in {"handoff-raster", "both"}:
        outputs.append(write_raster_mode(groups))
    if args.mode in {"handoff-production", "both"}:
        outputs.append(write_production_mode(groups))

    print(json.dumps({"outputs": outputs}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
