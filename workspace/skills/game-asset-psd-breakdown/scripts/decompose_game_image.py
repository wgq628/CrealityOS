from __future__ import annotations

import argparse
import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


DECISIONS = {"extract_direct", "regenerate_clean", "hybrid_repair"}
PREFERRED_TOOLS = {"pillow", "opencv", "sam_optional", "gpt-image-2", "manual_review"}
QUALITY_THRESHOLDS = {
    "strict": {"mean_abs_rgb": 5.0, "p95_abs_rgb": 18.0},
    "balanced": {"mean_abs_rgb": 10.0, "p95_abs_rgb": 32.0},
    "fast": {"mean_abs_rgb": 18.0, "p95_abs_rgb": 55.0},
}

try:
    RESAMPLE_LANCZOS = Image.Resampling.LANCZOS
    RESAMPLE_BICUBIC = Image.Resampling.BICUBIC
except AttributeError:  # pragma: no cover - Pillow compatibility.
    RESAMPLE_LANCZOS = Image.LANCZOS
    RESAMPLE_BICUBIC = Image.BICUBIC


@dataclass
class AssetRecord:
    asset_id: str
    element_id: str
    type: str
    group: str
    decision: str
    preferred_tool: str
    mask_strategy: str
    path: Path
    extracted_path: Path | None
    generated_reference_path: Path | None
    source_box: list[int]
    full_canvas: bool
    repeat_key: str
    expected_instances: int
    occlusion_level: str
    source_role: str
    status: str
    alpha_stats: dict[str, Any]
    decision_reason: str
    generation_prompt: str


def load_rgba(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def save(img: Image.Image, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def save_text(text: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def read_spec(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rel_or_abs(path: Path) -> str:
    return str(path.resolve())


def safe_name(value: str) -> str:
    keep = []
    for ch in value.strip():
        if ch.isalnum() or ch in "-_":
            keep.append(ch)
        else:
            keep.append("_")
    return "".join(keep).strip("_") or "asset"


def clamp_box(box: list[int], width: int, height: int) -> list[int]:
    x1, y1, x2, y2 = box
    x1 = max(0, min(width, int(round(x1))))
    y1 = max(0, min(height, int(round(y1))))
    x2 = max(0, min(width, int(round(x2))))
    y2 = max(0, min(height, int(round(y2))))
    if x2 <= x1:
        x2 = min(width, x1 + 1)
    if y2 <= y1:
        y2 = min(height, y1 + 1)
    return [x1, y1, x2, y2]


def normalize_box(item: dict[str, Any], image_size: tuple[int, int]) -> list[int]:
    width, height = image_size
    if item.get("full_canvas", False):
        return [0, 0, width, height]

    raw = item.get("source_box", item.get("box", [0, 0, width, height]))
    fmt = item.get("source_box_format") or item.get("box_format")
    if fmt is None:
        fmt = "xyxy" if "box" in item and "source_box" not in item else "xywh"

    if isinstance(raw, dict):
        if {"left", "top", "right", "bottom"}.issubset(raw):
            return clamp_box([raw["left"], raw["top"], raw["right"], raw["bottom"]], width, height)
        x = int(raw.get("x", raw.get("left", 0)))
        y = int(raw.get("y", raw.get("top", 0)))
        w = int(raw.get("w", raw.get("width", width - x)))
        h = int(raw.get("h", raw.get("height", height - y)))
        return clamp_box([x, y, x + w, y + h], width, height)

    values = [int(round(float(v))) for v in raw]
    if len(values) != 4:
        raise ValueError(f"Expected 4 source_box values for {item.get('id')}, got {raw!r}")

    x, y, a, b = values
    if str(fmt).lower() == "xyxy":
        return clamp_box([x, y, a, b], width, height)
    if str(fmt).lower() == "xywh":
        return clamp_box([x, y, x + a, y + b], width, height)
    raise ValueError(f"Unsupported source_box_format for {item.get('id')}: {fmt}")


def trim_alpha_with_offset(img: Image.Image, padding: int = 0) -> tuple[Image.Image, tuple[int, int]]:
    bbox = img.getchannel("A").getbbox()
    if not bbox:
        return img, (0, 0)
    x1, y1, x2, y2 = bbox
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(img.width, x2 + padding)
    y2 = min(img.height, y2 + padding)
    return img.crop((x1, y1, x2, y2)), (x1, y1)


def mask_none(crop: Image.Image) -> Image.Image:
    return crop.convert("RGBA")


def mask_rect_soft(crop: Image.Image) -> Image.Image:
    alpha = Image.new("L", crop.size, 255).filter(ImageFilter.GaussianBlur(0.3))
    result = crop.convert("RGBA")
    result.putalpha(alpha)
    return result


def mask_ellipse(crop: Image.Image) -> Image.Image:
    alpha = Image.new("L", crop.size, 0)
    draw = ImageDraw.Draw(alpha)
    pad_x = max(2, round(crop.width * 0.04))
    pad_y = max(2, round(crop.height * 0.04))
    draw.ellipse((pad_x, pad_y, crop.width - pad_x, crop.height - pad_y), fill=255)
    result = crop.convert("RGBA")
    result.putalpha(alpha.filter(ImageFilter.GaussianBlur(1.0)))
    return result


def mask_alpha_from_luma(crop: Image.Image) -> Image.Image:
    rgba = crop.convert("RGBA")
    gray = rgba.convert("L")
    rgba.putalpha(gray)
    return rgba


def mask_chroma_key_green(crop: Image.Image) -> Image.Image:
    rgba = crop.convert("RGBA")
    arr = np.array(rgba)
    rgb = arr[:, :, :3].astype(np.int16)
    alpha = arr[:, :, 3].astype(np.uint8)
    green = np.array([0, 255, 0], dtype=np.int16)
    dist = np.linalg.norm(rgb - green, axis=2)
    key = dist < 60
    near = (dist >= 60) & (dist < 120)
    alpha[key] = 0
    alpha[near] = np.minimum(alpha[near], ((dist[near] - 60) / 60 * 255).astype(np.uint8))
    alpha = cv2.morphologyEx(alpha, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
    arr[:, :, 3] = alpha
    return Image.fromarray(arr, "RGBA")


def mask_saturation(crop: Image.Image) -> Image.Image:
    rgb = np.array(crop.convert("RGB"))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    alpha = (((hsv[:, :, 1] > 45) & (hsv[:, :, 2] > 40)) * 255).astype(np.uint8)
    alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
    return Image.fromarray(np.dstack([rgb, alpha]), "RGBA")


def mask_auto_subject(crop: Image.Image) -> Image.Image:
    rgb = np.array(crop.convert("RGB"))
    h, w = rgb.shape[:2]
    if h < 8 or w < 8:
        return crop.convert("RGBA")

    mask = np.full((h, w), cv2.GC_PR_BGD, np.uint8)
    border = max(3, min(h, w) // 14)
    mask[:border, :] = cv2.GC_BGD
    mask[-border:, :] = cv2.GC_BGD
    mask[:, :border] = cv2.GC_BGD
    mask[:, -border:] = cv2.GC_BGD
    cv2.rectangle(mask, (border, border), (w - border, h - border), cv2.GC_PR_FGD, -1)

    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    subject_hint = ((hsv[:, :, 1] > 45) & (hsv[:, :, 2] > 45)).astype(np.uint8)
    mask[subject_hint == 1] = cv2.GC_PR_FGD

    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(rgb, mask, None, bgd, fgd, 5, cv2.GC_INIT_WITH_MASK)
        alpha = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    except cv2.error:
        alpha = subject_hint * 255

    alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
    return Image.fromarray(np.dstack([rgb, alpha]), "RGBA")


MASKERS = {
    "none": mask_none,
    "rect_soft": mask_rect_soft,
    "ellipse": mask_ellipse,
    "alpha_from_luma": mask_alpha_from_luma,
    "auto_subject": mask_auto_subject,
    "grabcut": mask_auto_subject,
    "opencv_grabcut": mask_auto_subject,
    "saturation": mask_saturation,
    "chroma_key_green": mask_chroma_key_green,
    "green_screen": mask_chroma_key_green,
}


def crop_asset(source: Image.Image, item: dict[str, Any], box: list[int]) -> tuple[Image.Image, tuple[int, int]]:
    crop = source.crop(tuple(box))
    mask_name = str(item.get("mask_strategy", item.get("mask", "auto_subject")))
    if item.get("full_canvas", False) and mask_name == "auto_subject":
        mask_name = "none"
    masker = MASKERS.get(mask_name, mask_auto_subject)
    result = masker(crop)
    trim = bool(item.get("trim", not item.get("full_canvas", False)))
    if trim:
        result, offset = trim_alpha_with_offset(result, int(item.get("padding", 6)))
        return result, offset
    return result, (0, 0)


def alpha_stats(img: Image.Image, original_crop: Image.Image | None = None) -> dict[str, Any]:
    rgba = img.convert("RGBA")
    alpha = np.array(rgba.getchannel("A"))
    visible = alpha > 8
    soft = (alpha > 8) & (alpha < 245)
    bbox = rgba.getchannel("A").getbbox()
    visible_count = int(visible.sum())
    total = int(alpha.size)
    stats: dict[str, Any] = {
        "size": [rgba.width, rgba.height],
        "alpha_bbox": list(bbox) if bbox else None,
        "visible_pixel_ratio": round(visible_count / max(1, total), 4),
        "soft_edge_pixel_ratio": round(int(soft.sum()) / max(1, total), 4),
        "transparent_pixel_ratio": round(int((alpha <= 8).sum()) / max(1, total), 4),
    }
    if original_crop is not None and soft.any():
        crop_rgb = np.array(original_crop.convert("RGB"), dtype=np.float32)
        if crop_rgb.shape[:2] == alpha.shape:
            samples = np.concatenate(
                [
                    crop_rgb[: max(1, crop_rgb.shape[0] // 12), :, :].reshape(-1, 3),
                    crop_rgb[-max(1, crop_rgb.shape[0] // 12) :, :, :].reshape(-1, 3),
                    crop_rgb[:, : max(1, crop_rgb.shape[1] // 12), :].reshape(-1, 3),
                    crop_rgb[:, -max(1, crop_rgb.shape[1] // 12) :, :].reshape(-1, 3),
                ],
                axis=0,
            )
            bg = np.median(samples, axis=0)
            edge_rgb = crop_rgb[soft]
            dist = np.linalg.norm(edge_rgb - bg, axis=1)
            pollution = float(np.clip(np.mean(1.0 - np.minimum(dist, 90.0) / 90.0), 0.0, 1.0))
            stats["edge_color_pollution_score"] = round(pollution, 4)
    return stats


def rgb_hex(rgb: np.ndarray) -> str:
    r, g, b = [int(np.clip(v, 0, 255)) for v in rgb[:3]]
    return f"#{r:02x}{g:02x}{b:02x}"


def analyze_image(source: Image.Image) -> dict[str, Any]:
    rgb = np.array(source.convert("RGB"))
    h, w = rgb.shape[:2]
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 80, 160)
    sat_mask = ((hsv[:, :, 1] > 65) & (hsv[:, :, 2] > 45)).astype(np.uint8) * 255
    sat_mask = cv2.morphologyEx(sat_mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

    components: list[dict[str, Any]] = []
    count, labels, stats, _ = cv2.connectedComponentsWithStats(sat_mask, 8)
    for idx in range(1, count):
        x, y, bw, bh, area = [int(v) for v in stats[idx]]
        if area < max(24, (w * h) // 5000):
            continue
        components.append({"box_xywh": [x, y, bw, bh], "area": area})
    components.sort(key=lambda item: item["area"], reverse=True)

    small = cv2.resize(rgb, (min(180, w), max(1, round(h * min(180, w) / w))), interpolation=cv2.INTER_AREA)
    samples = small.reshape(-1, 3).astype(np.float32)
    k = min(6, len(samples))
    dominant: list[dict[str, Any]] = []
    if k > 0:
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
        _, labels_k, centers = cv2.kmeans(samples, k, None, criteria, 2, cv2.KMEANS_PP_CENTERS)
        counts = np.bincount(labels_k.flatten(), minlength=k)
        order = np.argsort(counts)[::-1]
        for idx in order:
            dominant.append({"hex": rgb_hex(centers[idx]), "percent": round(float(counts[idx] / len(samples)), 4)})

    return {
        "canvas": {"width": w, "height": h},
        "edge_density": round(float((edges > 0).mean()), 4),
        "saturated_region_components": components[:18],
        "dominant_colors": dominant,
    }


def legacy_to_elements(spec: dict[str, Any]) -> list[dict[str, Any]]:
    placements_by_asset: dict[str, list[dict[str, Any]]] = {}
    for layer_index, layer in enumerate(spec.get("layers", [])):
        for placement in layer.get("placements", []):
            item = dict(placement)
            item.setdefault("z_index", layer_index)
            placements_by_asset.setdefault(str(item["asset_id"]), []).append(item)

    elements: list[dict[str, Any]] = []
    for asset in spec.get("assets", []):
        element = dict(asset)
        element["source_box"] = asset.get("box", asset.get("source_box"))
        element["source_box_format"] = asset.get("box_format", "xyxy")
        element["mask_strategy"] = asset.get("mask", asset.get("mask_strategy", "auto_subject"))
        element.setdefault("type", "asset")
        element.setdefault("decision", "extract_direct")
        element.setdefault("preferred_tool", "opencv" if element["mask_strategy"] != "none" else "pillow")
        element.setdefault("expected_instances", len(placements_by_asset.get(str(asset["id"]), [])) or 1)
        element.setdefault("occlusion_level", "unknown")
        element.setdefault("repeat_key", str(asset["id"]))
        element.setdefault("generation_prompt", "")
        element.setdefault("decision_reason", asset.get("description", "Converted from legacy assets/layers spec."))
        element["placements"] = placements_by_asset.get(str(asset["id"]), [])
        if not element["placements"]:
            box = asset.get("box", [0, 0, 1, 1])
            element["placements"] = [{"name": str(asset["id"]), "x": box[0], "y": box[1], "z_index": 0}]
        elements.append(element)
    return elements


def get_elements(spec: dict[str, Any]) -> list[dict[str, Any]]:
    elements = spec.get("elements")
    if elements:
        return [dict(item) for item in elements]
    return legacy_to_elements(spec)


def validate_element(element: dict[str, Any]) -> None:
    decision = str(element.get("decision", "extract_direct"))
    preferred_tool = str(element.get("preferred_tool", "opencv"))
    if decision not in DECISIONS:
        raise ValueError(f"{element.get('id')} has unsupported decision: {decision}")
    if preferred_tool not in PREFERRED_TOOLS:
        raise ValueError(f"{element.get('id')} has unsupported preferred_tool: {preferred_tool}")


def load_optional_generated_asset(element: dict[str, Any], generated_root: Path, asset_id: str) -> tuple[Image.Image | None, Path | None]:
    generated_path = element.get("generated_asset_path")
    if not generated_path:
        return None, None
    src_path = Path(str(generated_path))
    if not src_path.exists():
        return None, None
    img = load_rgba(src_path)
    if element.get("generated_has_chroma_key", True):
        img = mask_chroma_key_green(img)
    out_path = generated_root / f"{safe_name(asset_id)}_generated.png"
    save(img, out_path)
    return img, out_path


def prepare_assets(
    elements: list[dict[str, Any]],
    source: Image.Image,
    empty_base: Image.Image | None,
    out: Path,
    gpt_image_mode: str,
    quality: str,
) -> tuple[dict[str, AssetRecord], list[dict[str, Any]], list[dict[str, Any]]]:
    extracted_root = out / "assets" / "extracted"
    generated_root = out / "assets" / "generated_reference"
    final_root = out / "assets" / "final_psd_sources"
    for path in (extracted_root, generated_root, final_root):
        path.mkdir(parents=True, exist_ok=True)

    records: dict[str, AssetRecord] = {}
    generation_queue: list[dict[str, Any]] = []
    placement_records: list[dict[str, Any]] = []

    for element in elements:
        validate_element(element)
        asset_id = safe_name(str(element["id"]))
        group = safe_name(str(element.get("group", "03_assets")))
        decision = str(element.get("decision", "extract_direct"))
        preferred_tool = str(element.get("preferred_tool", "opencv"))
        mask_strategy = str(element.get("mask_strategy", element.get("mask", "auto_subject")))
        src_name = str(element.get("source", "source"))
        src = empty_base if src_name == "empty_base" and empty_base is not None else source
        box = normalize_box(element, src.size)
        source_crop = src.crop(tuple(box))
        extracted_img, _trim_offset = crop_asset(src, element, box)

        extracted_path: Path | None = None
        if decision in {"extract_direct", "hybrid_repair"} or element.get("keep_reference_crop", True):
            extracted_path = extracted_root / group / f"{asset_id}.png"
            save(extracted_img, extracted_path)

        generated_img, generated_path = load_optional_generated_asset(element, generated_root / group, asset_id)
        if decision in {"regenerate_clean", "hybrid_repair"} and gpt_image_mode != "off":
            reference_crop_path = generated_root / group / f"{asset_id}_source_crop.png"
            save(source_crop, reference_crop_path)
            generation_queue.append(
                {
                    "element_id": asset_id,
                    "decision": decision,
                    "mode": gpt_image_mode,
                    "source_crop": rel_or_abs(reference_crop_path),
                    "expected_output": rel_or_abs(generated_root / group / f"{asset_id}_generated.png"),
                    "prompt": str(element.get("generation_prompt", "")),
                    "background_policy": "Generate on a pure chroma-key background; remove locally and validate alpha before replacement.",
                    "replacement_policy": "Do not replace final_psd_sources unless validated_replacement is true and recomposition passes.",
                }
            )

        validated_replacement = bool(element.get("validated_replacement", False))
        final_img = extracted_img
        source_role = "extracted_coordinate_source"
        status = "psd_ready_candidate"

        if decision == "extract_direct":
            final_img = extracted_img
            source_role = "direct_extraction"
        elif decision == "regenerate_clean":
            if generated_img is not None and validated_replacement:
                final_img = generated_img
                source_role = "validated_generated_replacement"
                status = "psd_ready_candidate"
            else:
                final_img = generated_img if generated_img is not None else extracted_img
                source_role = "generated_reference_pending_validation" if generated_img is not None else "source_crop_placeholder_pending_generation"
                status = "needs_generated_asset"
        elif decision == "hybrid_repair":
            if generated_img is not None and validated_replacement:
                final_img = generated_img
                source_role = "validated_hybrid_repair"
                status = "psd_ready_candidate"
            else:
                final_img = extracted_img
                source_role = "extracted_source_pending_hybrid_repair"
                status = "needs_manual_refine"

        if preferred_tool == "manual_review":
            status = "needs_manual_refine"
        if decision in {"regenerate_clean", "hybrid_repair"} and quality == "strict" and not validated_replacement:
            status = "needs_manual_refine"

        final_path = final_root / group / f"{asset_id}.png"
        save(final_img, final_path)

        stats = alpha_stats(final_img, source_crop if final_img.size == source_crop.size else None)
        if stats.get("edge_color_pollution_score", 0) and float(stats["edge_color_pollution_score"]) > 0.45:
            status = "needs_manual_refine"

        record = AssetRecord(
            asset_id=asset_id,
            element_id=str(element["id"]),
            type=str(element.get("type", "asset")),
            group=str(element.get("group", "03_assets")),
            decision=decision,
            preferred_tool=preferred_tool,
            mask_strategy=mask_strategy,
            path=final_path,
            extracted_path=extracted_path,
            generated_reference_path=generated_path,
            source_box=box,
            full_canvas=bool(element.get("full_canvas", False)),
            repeat_key=str(element.get("repeat_key", asset_id)),
            expected_instances=int(element.get("expected_instances", len(element.get("placements", [])) or 1)),
            occlusion_level=str(element.get("occlusion_level", "unknown")),
            source_role=source_role,
            status=status,
            alpha_stats=stats,
            decision_reason=str(element.get("decision_reason", element.get("description", ""))),
            generation_prompt=str(element.get("generation_prompt", "")),
        )
        records[asset_id] = record

        for index, placement in enumerate(element.get("placements", [])):
            resolved = dict(placement)
            resolved["asset_id"] = asset_id
            resolved.setdefault("name", f"{asset_id}_{index + 1:02d}")
            resolved.setdefault("group", record.group)
            resolved.setdefault("x", box[0])
            resolved.setdefault("y", box[1])
            resolved.setdefault("rotation", 0)
            resolved.setdefault("z_index", index)
            resolved["asset_path"] = rel_or_abs(final_path)
            placement_records.append(resolved)

    placement_records.sort(key=lambda item: (float(item.get("z_index", 0)), str(item.get("name", ""))))
    return records, placement_records, generation_queue


def make_atlas(records: list[AssetRecord], cols: int = 3, cell: int = 320) -> Image.Image:
    rows = max(1, int(math.ceil(max(1, len(records)) / cols)))
    atlas = Image.new("RGBA", (cols * cell, rows * cell), (246, 246, 240, 255))
    draw = ImageDraw.Draw(atlas)
    font = ImageFont.load_default()
    for i in range(0, cols * cell, 20):
        color = (232, 232, 224, 255) if (i // 20) % 2 else (242, 242, 236, 255)
        draw.line((i, 0, i, rows * cell), fill=color)
    for i in range(0, rows * cell, 20):
        color = (232, 232, 224, 255) if (i // 20) % 2 else (242, 242, 236, 255)
        draw.line((0, i, cols * cell, i), fill=color)

    for idx, record in enumerate(records):
        row, col = divmod(idx, cols)
        x0, y0 = col * cell, row * cell
        draw.rectangle((x0, y0, x0 + cell - 1, y0 + cell - 1), outline=(188, 176, 156, 255), width=2)
        img = load_rgba(record.path)
        max_side = cell - 92
        scale = min(max_side / max(1, img.width), max_side / max(1, img.height), 1.0)
        img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), RESAMPLE_LANCZOS)
        atlas.alpha_composite(img, (x0 + (cell - img.width) // 2, y0 + 50 + (max_side - img.height) // 2))
        label = record.asset_id[:32]
        draw.text((x0 + 12, y0 + 10), label, fill=(44, 39, 32, 255), font=font)
        draw.text((x0 + 12, y0 + 27), record.decision[:28], fill=(92, 74, 48, 255), font=font)
        if record.status != "psd_ready_candidate":
            draw.text((x0 + 12, y0 + cell - 22), record.status[:34], fill=(150, 46, 46, 255), font=font)
    return atlas.convert("RGB")


def resize_for_placement(img: Image.Image, placement: dict[str, Any]) -> Image.Image:
    target_w = placement.get("w")
    target_h = placement.get("h")
    if target_w is None and target_h is None:
        return img
    if target_w is None:
        scale = float(target_h) / max(1, img.height)
        target_w = max(1, round(img.width * scale))
    if target_h is None:
        scale = float(target_w) / max(1, img.width)
        target_h = max(1, round(img.height * scale))
    return img.resize((max(1, int(round(float(target_w)))), max(1, int(round(float(target_h))))), RESAMPLE_LANCZOS)


def alpha_composite_clipped(canvas: Image.Image, img: Image.Image, x: int, y: int) -> None:
    left = max(0, x)
    top = max(0, y)
    right = min(canvas.width, x + img.width)
    bottom = min(canvas.height, y + img.height)
    if right <= left or bottom <= top:
        return
    crop = img.crop((left - x, top - y, right - x, bottom - y))
    canvas.alpha_composite(crop, (left, top))


def compose(canvas_size: tuple[int, int], placements: list[dict[str, Any]]) -> Image.Image:
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    for placement in placements:
        img = load_rgba(Path(str(placement["asset_path"])))
        img = resize_for_placement(img, placement)
        rotation = float(placement.get("rotation", 0) or 0)
        if abs(rotation) > 0.001:
            img = img.rotate(rotation, expand=True, resample=RESAMPLE_BICUBIC)
        x = int(round(float(placement.get("x", 0))))
        y = int(round(float(placement.get("y", 0))))
        alpha_composite_clipped(canvas, img, x, y)
    return canvas


def overlay_50(source: Image.Image, recomposed: Image.Image) -> Image.Image:
    return Image.blend(source.convert("RGB"), recomposed.convert("RGB"), 0.5)


def diff_analysis(source: Image.Image, recomposed: Image.Image, preview_root: Path) -> dict[str, Any]:
    a = np.array(source.convert("RGB"), dtype=np.float32)
    b = np.array(recomposed.convert("RGB"), dtype=np.float32)
    diff = np.abs(a - b)
    gray = diff.mean(axis=2)
    h, w = gray.shape

    grid_rows = 8
    grid_cols = 8
    hotspots: list[dict[str, Any]] = []
    for gy in range(grid_rows):
        for gx in range(grid_cols):
            x1 = round(gx * w / grid_cols)
            x2 = round((gx + 1) * w / grid_cols)
            y1 = round(gy * h / grid_rows)
            y2 = round((gy + 1) * h / grid_rows)
            cell = gray[y1:y2, x1:x2]
            if cell.size:
                hotspots.append({"box_xywh": [x1, y1, x2 - x1, y2 - y1], "mean_abs_rgb": round(float(cell.mean()), 3)})
    hotspots.sort(key=lambda item: item["mean_abs_rgb"], reverse=True)

    normalized = np.clip(gray / max(1.0, float(np.percentile(gray, 99))) * 255, 0, 255).astype(np.uint8)
    heatmap = cv2.applyColorMap(normalized, cv2.COLORMAP_MAGMA)
    heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)
    heatmap_path = save(Image.fromarray(heatmap), preview_root / "difference_heatmap.png")

    return {
        "mean_abs_rgb": round(float(diff.mean()), 4),
        "p95_abs_rgb": round(float(np.percentile(diff, 95)), 4),
        "max_abs_rgb": round(float(diff.max()), 4),
        "local_diff_hotspots": hotspots[:8],
        "difference_heatmap": rel_or_abs(heatmap_path),
    }


def js_string(path: str | Path) -> str:
    return str(Path(path).resolve()).replace("\\", "/").replace("'", "\\'")


def js_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("'", "\\'")


def write_jsx(out: Path, canvas_size: tuple[int, int], placements: list[dict[str, Any]], output_psd: Path) -> Path:
    lines = [
        "#target photoshop",
        "app.displayDialogs = DialogModes.NO;",
        "var doc = app.documents.add(%d, %d, 72, 'game_asset_reconstruction', NewDocumentMode.RGB, DocumentFill.TRANSPARENT);"
        % (canvas_size[0], canvas_size[1]),
        "var groups = {};",
        "function ensureGroup(name) {",
        "  if (!groups[name]) {",
        "    groups[name] = doc.layerSets.add();",
        "    groups[name].name = name;",
        "  }",
        "  return groups[name];",
        "}",
        "function px(value) { return value.as('px'); }",
        "function placePng(path, name, groupName, x, y, targetW, targetH, rotation) {",
        "  var src = app.open(File(path));",
        "  src.activeLayer.name = name;",
        "  src.activeLayer.duplicate(doc, ElementPlacement.PLACEATBEGINNING);",
        "  src.close(SaveOptions.DONOTSAVECHANGES);",
        "  app.activeDocument = doc;",
        "  var layer = doc.activeLayer;",
        "  layer.name = name;",
        "  var b = layer.bounds;",
        "  var currentW = Math.max(1, px(b[2]) - px(b[0]));",
        "  var currentH = Math.max(1, px(b[3]) - px(b[1]));",
        "  if (targetW > 0 || targetH > 0) {",
        "    if (targetW <= 0) targetW = currentW * (targetH / currentH);",
        "    if (targetH <= 0) targetH = currentH * (targetW / currentW);",
        "    layer.resize((targetW / currentW) * 100, (targetH / currentH) * 100, AnchorPosition.TOPLEFT);",
        "  }",
        "  if (Math.abs(rotation) > 0.001) layer.rotate(rotation, AnchorPosition.MIDDLECENTER);",
        "  b = layer.bounds;",
        "  layer.translate(x - px(b[0]), y - px(b[1]));",
        "  var group = ensureGroup(groupName);",
        "  layer.move(group, ElementPlacement.INSIDE);",
        "}",
    ]
    for placement in placements:
        target_w = placement.get("w", -1)
        target_h = placement.get("h", -1)
        lines.append(
            "placePng('%s', '%s', '%s', %d, %d, %s, %s, %s);"
            % (
                js_string(str(placement["asset_path"])),
                js_text(str(placement.get("name") or placement["asset_id"])),
                js_text(str(placement.get("group", "assets"))),
                int(round(float(placement.get("x", 0)))),
                int(round(float(placement.get("y", 0)))),
                str(float(target_w)) if target_w is not None else "-1",
                str(float(target_h)) if target_h is not None else "-1",
                str(float(placement.get("rotation", 0) or 0)),
            )
        )
    lines.extend(
        [
            "var psdFile = File('%s');" % js_string(output_psd),
            "var opts = new PhotoshopSaveOptions();",
            "opts.layers = true;",
            "doc.saveAs(psdFile, opts, true, Extension.LOWERCASE);",
        ]
    )
    return save_text("\n".join(lines), out)


def group_layers(placements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for placement in placements:
        group = str(placement.get("group", "assets"))
        grouped.setdefault(group, []).append(placement)
    return [{"group": group, "placements": items} for group, items in grouped.items()]


def records_to_manifest_assets(records: dict[str, AssetRecord]) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for record in records.values():
        assets.append(
            {
                "asset_id": record.asset_id,
                "element_id": record.element_id,
                "type": record.type,
                "group": record.group,
                "decision": record.decision,
                "preferred_tool": record.preferred_tool,
                "mask_strategy": record.mask_strategy,
                "path": rel_or_abs(record.path),
                "extracted_path": rel_or_abs(record.extracted_path) if record.extracted_path else None,
                "generated_reference_path": rel_or_abs(record.generated_reference_path)
                if record.generated_reference_path
                else None,
                "source_box_xyxy": record.source_box,
                "full_canvas": record.full_canvas,
                "repeat_key": record.repeat_key,
                "expected_instances": record.expected_instances,
                "occlusion_level": record.occlusion_level,
                "source_role": record.source_role,
                "status": record.status,
                "alpha_stats": record.alpha_stats,
                "decision_reason": record.decision_reason,
                "generation_prompt": record.generation_prompt,
            }
        )
    return assets


def write_decision_report(
    path: Path,
    records: dict[str, AssetRecord],
    generation_queue: list[dict[str, Any]],
    image_analysis: dict[str, Any],
) -> Path:
    lines = [
        "# Asset Decision Report",
        "",
        "This package is a reverse reconstruction from a finished raster unless a native PSD was supplied separately.",
        "",
        "## Image Analysis Hints",
        "",
        f"- Canvas: `{image_analysis['canvas']['width']} x {image_analysis['canvas']['height']}`",
        f"- Edge density: `{image_analysis['edge_density']}`",
        f"- Saturated connected-component candidates: `{len(image_analysis['saturated_region_components'])}`",
        f"- Dominant colors: `{', '.join(item['hex'] for item in image_analysis['dominant_colors'][:6])}`",
        "",
        "## Element Decisions",
        "",
        "| Element | Group | Decision | Tool | Source role | Status | Reason |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for record in records.values():
        reason = record.decision_reason.replace("|", "/") or "No reason supplied in spec."
        lines.append(
            f"| `{record.asset_id}` | `{record.group}` | `{record.decision}` | `{record.preferred_tool}` | "
            f"`{record.source_role}` | `{record.status}` | {reason} |"
        )

    generated = [r for r in records.values() if r.decision in {"regenerate_clean", "hybrid_repair"}]
    lines.extend(["", "## Generated / Repair Queue", ""])
    if not generated:
        lines.append("- No generated or hybrid repair elements were requested.")
    else:
        for record in generated:
            lines.append(
                f"- `{record.asset_id}`: `{record.decision}` via `{record.preferred_tool}`. "
                f"Prompt present: `{bool(record.generation_prompt.strip())}`. Status: `{record.status}`."
            )

    lines.extend(["", "## gpt-image-2 Request Queue", ""])
    if generation_queue:
        lines.append(f"- Request queue JSON contains `{len(generation_queue)}` single-asset prompt(s).")
        lines.append("- Generated outputs must remain reference-only until edge and recomposition validation pass.")
    else:
        lines.append("- No drawing-model queue was written, or `--gpt-image-mode off` was used.")

    return save_text("\n".join(lines), path)


def write_qa_report(
    path: Path,
    source_path: Path,
    canvas_size: tuple[int, int],
    records: dict[str, AssetRecord],
    manifest_path: Path,
    jsx_path: Path | None,
    fidelity: dict[str, Any],
) -> Path:
    ready = [r.asset_id for r in records.values() if r.status == "psd_ready_candidate" and r.decision == "extract_direct"]
    generated = [r.asset_id for r in records.values() if r.decision == "regenerate_clean"]
    manual = [r.asset_id for r in records.values() if r.status != "psd_ready_candidate"]
    hybrid = [r.asset_id for r in records.values() if r.decision == "hybrid_repair"]

    lines = [
        "# PSD Breakdown QA",
        "",
        f"- Source: `{source_path}`",
        f"- Canvas: `{canvas_size[0]} x {canvas_size[1]}`",
        f"- Assets: `{len(records)}`",
        f"- Manifest: `{manifest_path}`",
        f"- JSX: `{jsx_path if jsx_path else 'manifest-only backend selected'}`",
        f"- Fidelity status: `{fidelity['status']}`",
        f"- Mean RGB difference: `{fidelity['diff']['mean_abs_rgb']}`",
        f"- P95 RGB difference: `{fidelity['diff']['p95_abs_rgb']}`",
        "",
        "## PSD-ready direct layers",
        "",
    ]
    lines.extend([f"- `{item}`" for item in ready] or ["- None confirmed yet."])
    lines.extend(["", "## Generated/reference-only layers", ""])
    lines.extend([f"- `{item}`" for item in generated] or ["- None."])
    lines.extend(["", "## Hybrid or manual-refine layers", ""])
    lines.extend([f"- `{item}`" for item in sorted(set(manual + hybrid))] or ["- None flagged."])
    lines.extend(["", "## Fidelity risks", ""])
    for suggestion in fidelity.get("manual_refine_suggestions", []):
        lines.append(f"- {suggestion}")
    if not fidelity.get("manual_refine_suggestions"):
        lines.append("- No automatic high-risk suggestion was generated. Manual visual inspection is still required.")
    lines.extend(
        [
            "",
            "## Caveat",
            "",
            "- This is a reverse reconstruction package from a flat raster unless a native PSD was supplied separately.",
            "- Running the JSX in Photoshop is required to create the actual layered `.psd` file.",
            "- Drawing-model references must not replace final PSD sources until local edge checks and recomposition validation pass.",
        ]
    )
    return save_text("\n".join(lines), path)


def status_from_fidelity(diff: dict[str, Any], records: dict[str, AssetRecord], quality: str) -> tuple[str, list[str]]:
    thresholds = QUALITY_THRESHOLDS[quality]
    suggestions: list[str] = []
    if diff["mean_abs_rgb"] > thresholds["mean_abs_rgb"]:
        suggestions.append(
            f"Mean RGB diff `{diff['mean_abs_rgb']}` exceeds {quality} threshold `{thresholds['mean_abs_rgb']}`; inspect overlay and heatmap."
        )
    if diff["p95_abs_rgb"] > thresholds["p95_abs_rgb"]:
        suggestions.append(
            f"P95 RGB diff `{diff['p95_abs_rgb']}` exceeds {quality} threshold `{thresholds['p95_abs_rgb']}`; refine hot spot regions."
        )
    for record in records.values():
        if record.status != "psd_ready_candidate":
            suggestions.append(f"`{record.asset_id}` is `{record.status}` and should not be marked PSD-ready.")
        pollution = record.alpha_stats.get("edge_color_pollution_score")
        if pollution is not None and float(pollution) > 0.45:
            suggestions.append(f"`{record.asset_id}` has edge color pollution score `{pollution}`; repair or manually trim edges.")
    status = "psd_ready_candidate" if not suggestions else "needs_manual_refine"
    return status, suggestions


def write_manifest_only_stub(path: Path) -> Path:
    return save_text(
        "\n".join(
            [
                "#target photoshop",
                "// Manifest-only backend was selected when this package was generated.",
                "// Re-run with --psd-backend jsx to generate an executable Photoshop assembly script.",
            ]
        ),
        path,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Split a polished game image into PSD-ready reusable assets.")
    parser.add_argument("--source", required=True, help="Source image path.")
    parser.add_argument("--out", required=True, help="Output breakdown directory.")
    parser.add_argument("--spec", required=True, help="Breakdown JSON spec path.")
    parser.add_argument("--empty-base", help="Optional clean/empty base image path.")
    parser.add_argument("--gpt-image-mode", choices=["off", "reference", "repair"], default="reference")
    parser.add_argument("--quality", choices=["strict", "balanced", "fast"], default="strict")
    parser.add_argument("--atlas-cols", type=int, default=3, help="Columns in the asset atlas; 3 gives a 3x3-style grid.")
    parser.add_argument("--psd-backend", choices=["jsx", "manifest-only"], default="jsx")
    parser.add_argument("--psd-name", default="reconstructed.psd", help="Output PSD filename for the JSX script.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_path = Path(args.source)
    out = Path(args.out)
    spec = read_spec(Path(args.spec))
    source = load_rgba(source_path)
    empty_base = load_rgba(Path(args.empty_base)) if args.empty_base else None
    canvas_size = (
        int(spec.get("canvas", {}).get("width", source.width)),
        int(spec.get("canvas", {}).get("height", source.height)),
    )

    preview_root = out / "preview"
    scripts_root = out / "scripts"
    preview_root.mkdir(parents=True, exist_ok=True)
    scripts_root.mkdir(parents=True, exist_ok=True)

    analysis = analyze_image(source)
    save_text(json.dumps(analysis, ensure_ascii=False, indent=2), out / "image_analysis.json")

    elements = get_elements(spec)
    records, placements, generation_queue = prepare_assets(
        elements,
        source,
        empty_base,
        out,
        args.gpt_image_mode,
        args.quality,
    )

    if generation_queue:
        queue_path = out / "assets" / "generated_reference" / "gpt_image_2_request_queue.json"
        save_text(json.dumps(generation_queue, ensure_ascii=False, indent=2), queue_path)

    recomposed = compose(canvas_size, placements)
    recomposed_path = save(recomposed.convert("RGB"), preview_root / "recomposition_preview.png")
    overlay_path = save(overlay_50(source.resize(canvas_size), recomposed), preview_root / "original_recompose_overlay_50pct.png")
    atlas = make_atlas(list(records.values()), cols=max(1, int(args.atlas_cols)))
    atlas_3x3_path = save(atlas, preview_root / "asset_atlas_3x3.png")
    atlas_alias_path = preview_root / "asset_atlas.png"
    if atlas_alias_path != atlas_3x3_path:
        shutil.copyfile(atlas_3x3_path, atlas_alias_path)

    diff = diff_analysis(source.resize(canvas_size), recomposed, preview_root)
    status, suggestions = status_from_fidelity(diff, records, args.quality)
    fidelity = {
        "quality": args.quality,
        "status": status,
        "diff": diff,
        "manual_refine_suggestions": suggestions,
        "asset_alpha_stats": {asset_id: record.alpha_stats for asset_id, record in records.items()},
        "critical_rule": "Generated or repaired assets are not PSD-ready until validated by recomposition.",
    }
    fidelity_path = out / "fidelity_score.json"
    save_text(json.dumps(fidelity, ensure_ascii=False, indent=2), fidelity_path)

    output_psd = out / args.psd_name
    jsx_path: Path | None
    if args.psd_backend == "jsx":
        jsx_path = write_jsx(scripts_root / "compose_psd.jsx", canvas_size, placements, output_psd)
    else:
        jsx_path = write_manifest_only_stub(scripts_root / "compose_psd.jsx")

    manifest = {
        "schema_version": "2.0",
        "project_key": spec.get("project_key"),
        "work_item_id": spec.get("work_item_id"),
        "canvas": {"width": canvas_size[0], "height": canvas_size[1]},
        "source": rel_or_abs(source_path),
        "empty_base": rel_or_abs(Path(args.empty_base)) if args.empty_base else None,
        "strategy": {
            "pipeline": ["analyze", "extract_or_reference", "manifest_recompose", "qa"],
            "gpt_image_mode": args.gpt_image_mode,
            "gpt_image_policy": {
                "native_psd_output": "not_used",
                "transparent_background": "do_not_depend_on_model_transparency; use chroma-key plus local alpha validation",
                "replacement_rule": "generated assets replace final_psd_sources only when validated_replacement is true and recomposition passes",
            },
            "psd_backend": args.psd_backend,
        },
        "assets": records_to_manifest_assets(records),
        "layers": group_layers(placements),
        "placements": placements,
        "previews": {
            "asset_atlas_3x3": rel_or_abs(atlas_3x3_path),
            "asset_atlas": rel_or_abs(atlas_alias_path),
            "recomposition_preview": rel_or_abs(recomposed_path),
            "overlay_50pct": rel_or_abs(overlay_path),
            "difference_heatmap": diff["difference_heatmap"],
        },
        "photoshop_jsx": rel_or_abs(jsx_path) if jsx_path else None,
        "fidelity_score": rel_or_abs(fidelity_path),
    }
    manifest_path = out / "psd_layer_manifest.json"
    save_text(json.dumps(manifest, ensure_ascii=False, indent=2), manifest_path)

    decision_path = write_decision_report(out / "asset_decision_report.md", records, generation_queue, analysis)
    qa_path = write_qa_report(out / "PSD_BREAKDOWN_QA.md", source_path, canvas_size, records, manifest_path, jsx_path, fidelity)

    print(
        json.dumps(
            {
                "manifest": rel_or_abs(manifest_path),
                "decision_report": rel_or_abs(decision_path),
                "qa": rel_or_abs(qa_path),
                "fidelity": rel_or_abs(fidelity_path),
                "jsx": rel_or_abs(jsx_path) if jsx_path else None,
                "atlas": rel_or_abs(atlas_3x3_path),
                "status": status,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
