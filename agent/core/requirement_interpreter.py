from __future__ import annotations

import re
from typing import Any

from agent.models import DesignBrief, FieldMapping, WorkItemContext
from agent.utils import find_sizes, first_non_empty, flatten_pairs, stringify


FIELD_ALIASES = {
    "objective": ("objective", "goal", "目标", "诉求", "需求描述", "description", "detail", "内容"),
    "audience": ("audience", "user", "target", "用户", "目标人群", "受众"),
    "platform": ("platform", "placement", "channel", "media", "端", "平台", "渠道"),
    "deliverables": ("deliverable", "output", "交付", "产出", "文件", "格式"),
    "deadline": ("deadline", "due", "end", "截至", "截止", "完成时间"),
}

CATEGORY_KEYWORDS = {
    "casual-card": ("休闲", "轻度", "合成", "消除", "卡通", "轻松"),
    "anime-rpg": ("二次元", "RPG", "角色", "冒险", "番剧"),
    "slg-war": ("策略", "SLG", "战争", "联盟", "国战"),
    "xianxia": ("仙侠", "修仙", "国风", "仙气"),
    "realistic-fantasy": ("写实", "奇幻", "史诗", "暗黑"),
}


class RequirementInterpreter:
    def build(self, context: WorkItemContext, field_mapping: FieldMapping | None = None) -> DesignBrief:
        flat_pairs = flatten_pairs(context.raw_item)
        comment_text = [stringify(comment) for comment in context.comments]
        primary_text = self._primary_requirement_text(context)
        supporting_text = "\n".join([context.title, stringify(context.raw_item)] + comment_text + [doc.content for doc in context.docs])
        interpretation_text = "\n".join(item for item in [context.title, primary_text] if item.strip())
        combined_text = "\n".join(item for item in [interpretation_text, supporting_text] if item.strip())
        effective_text = interpretation_text if primary_text else combined_text
        objective_fallback = self._summarize_objective(primary_text) if primary_text else self._summarize_objective(combined_text)
        if primary_text:
            objective_fallback = primary_text
        game_name = self._extract_game_name(context)
        game_project_id = self._extract_game_project_id(context)
        game_context = self._game_context_text(context)
        gameplay_summary = self._infer_gameplay_summary(primary_text, game_context)
        reference_assets = self._extract_reference_assets(primary_text)
        source_requirement_summary = self._summarize_primary_requirement(primary_text or combined_text)
        task_breakdown = self._extract_task_breakdown(primary_text or combined_text, game_context)
        style_direction = self._infer_style_direction(primary_text or combined_text, game_context)
        audience_fallback = self._infer_audience(effective_text)
        if audience_fallback == "待确认":
            audience_fallback = self._infer_audience_from_game_context(game_context)

        objective = self._fallback_if_unknown(
            self._find_mapped_or_alias(flat_pairs, field_mapping, "objective"),
            objective_fallback,
        )
        audience = self._fallback_if_unknown(
            self._find_mapped_or_alias(flat_pairs, field_mapping, "audience"),
            audience_fallback,
        )
        platform = self._fallback_if_unknown(self._find_mapped_or_alias(flat_pairs, field_mapping, "platform"), self._infer_platform(effective_text))
        deadline_candidates = [
            self._find_mapped_value(flat_pairs, field_mapping, "deadline"),
            self._extract_deadline(context),
            self._find_field(flat_pairs, FIELD_ALIASES["deadline"]),
            self._infer_deadline(combined_text),
        ]
        deadline = first_non_empty([value for value in deadline_candidates if value != "待确认"]) or "待确认"
        deliverables = self._split_items(self._find_mapped_or_alias(flat_pairs, field_mapping, "deliverables"))
        if not deliverables:
            deliverables = self._infer_deliverables(effective_text) or self._infer_deliverables(combined_text)
        mapped_sizes = find_sizes(self._find_mapped_value(flat_pairs, field_mapping, "sizes"))
        field_sizes = self._extract_sizes(context)
        sizes = list(dict.fromkeys(mapped_sizes + field_sizes + find_sizes(effective_text)))
        if not sizes and self._looks_like_performance_art_request(effective_text, deliverables):
            sizes = ["9:16"]
        same_category = self._infer_category(effective_text)
        raw_signals = self._extract_signals(effective_text)
        if self._looks_like_performance_art_request(effective_text, deliverables):
            raw_signals.append("投放素材")

        summary_parts = [
            f"工作项：{context.title}",
            f"游戏：{game_name}",
            f"玩法：{gameplay_summary}",
            f"目标：{objective or '待确认'}",
            f"平台：{platform}",
            f"目标人群：{audience}",
        ]
        if sizes:
            summary_parts.append(f"尺寸：{', '.join(sizes)}")
        if deliverables:
            summary_parts.append(f"交付物：{', '.join(deliverables)}")
        summary = "；".join(summary_parts) + "。"

        missing_information: list[str] = []
        if objective == "待确认":
            missing_information.append("缺少明确设计目标或转化诉求")
        if audience == "待确认":
            missing_information.append("缺少目标受众定义")
        if platform == "待确认":
            missing_information.append("缺少投放平台或使用场景")
        if not sizes:
            missing_information.append("缺少尺寸或比例信息")
        if not deliverables:
            missing_information.append("缺少交付物格式说明")
        if deadline == "待确认":
            missing_information.append("缺少明确截止时间")

        return DesignBrief(
            project_key=context.project_key,
            work_item_id=context.work_item_id,
            title=context.title,
            objective=objective,
            target_audience=audience,
            platform=platform,
            sizes=sizes,
            deliverables=deliverables,
            deadline=deadline,
            summary=summary,
            same_category=same_category,
            source_links=context.doc_links,
            missing_information=missing_information,
            risk_points=[],
            raw_signals=list(dict.fromkeys(raw_signals)),
            game_name=game_name,
            game_project_id=game_project_id,
            gameplay_summary=gameplay_summary,
            reference_assets=reference_assets,
            source_requirement_summary=source_requirement_summary,
            task_breakdown=task_breakdown,
            style_direction=style_direction,
        )

    @staticmethod
    def _primary_requirement_text(context: WorkItemContext) -> str:
        fields = context.raw_item.get("work_item_fields")
        if not isinstance(fields, list):
            return ""
        preferred_keys = {"field_39e0db"}
        preferred_name_tokens = ("平面需求描述", "平面需求")
        fallback_tokens = ("平面", "需求")
        fallback: list[str] = []
        for item in fields:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or "")
            name = str(item.get("name") or "")
            value = item.get("value")
            text = stringify(value).strip()
            if not text:
                continue
            if key in preferred_keys or any(token in name for token in preferred_name_tokens):
                return text
            if all(token in name for token in fallback_tokens):
                fallback.append(text)
        return first_non_empty(fallback)

    @staticmethod
    def _extract_game_name(context: WorkItemContext) -> str:
        fields = context.raw_item.get("work_item_fields")
        preferred_keys = ("field_74ac24", "field_68abca")
        preferred_names = ("项目名称", "游戏名称", "产品名称")
        candidates: list[str] = []
        if isinstance(fields, list):
            for item in fields:
                if not isinstance(item, dict):
                    continue
                key = str(item.get("key") or "")
                name = str(item.get("name") or "")
                if key not in preferred_keys and not any(token in name for token in preferred_names):
                    continue
                value = item.get("value")
                if isinstance(value, dict):
                    text = str(value.get("name") or value.get("label") or value.get("value") or "")
                else:
                    text = stringify(value)
                text = text.strip()
                if text and text != "None":
                    candidates.append(text)
        if not candidates:
            text = stringify(context.raw_item)
            for pattern in (
                r"(?:项目名称|游戏名称|产品名称)\s*[：:]\s*([^\n\r；;，,。]+)",
                r"(?:项目|游戏)\s*[：:]\s*([^\n\r；;，,。]+)",
            ):
                match = re.search(pattern, text)
                if match:
                    candidates.append(match.group(1).strip())
        return first_non_empty(candidates) or "待确认"

    @staticmethod
    def _extract_game_project_id(context: WorkItemContext) -> str:
        fields = context.raw_item.get("work_item_fields")
        preferred_keys = ("field_74ac24", "field_68abca")
        preferred_names = ("项目名称", "游戏名称", "产品名称")
        candidates: list[str] = []
        if isinstance(fields, list):
            for item in fields:
                if not isinstance(item, dict):
                    continue
                key = str(item.get("key") or "")
                name = str(item.get("name") or "")
                if key not in preferred_keys and not any(token in name for token in preferred_names):
                    continue
                value = item.get("value")
                if isinstance(value, dict):
                    text = str(value.get("id") or value.get("value") or "").strip()
                    if text and text != "None":
                        candidates.append(text)
        if not candidates:
            text = stringify(context.raw_item)
            for pattern in (r"(?:项目ID|游戏ID|产品ID)\s*[：:]\s*([A-Za-z0-9_-]+)",):
                match = re.search(pattern, text)
                if match:
                    candidates.append(match.group(1).strip())
        return first_non_empty(candidates) or "待确认"

    @staticmethod
    def _game_context_text(context: WorkItemContext) -> str:
        fields = context.raw_item.get("work_item_fields")
        if not isinstance(fields, list):
            return ""
        tokens = ("玩法", "品类", "项目名称", "游戏名称", "产品名称", "分级")
        parts: list[str] = []
        for item in fields:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "")
            if not any(token in name for token in tokens):
                continue
            value = item.get("value")
            if isinstance(value, dict):
                text = str(value.get("name") or value.get("label") or value.get("value") or "")
            else:
                text = stringify(value)
            text = text.strip()
            if text and text != "None":
                parts.append(f"{name}：{text}")
        return "\n".join(parts)

    @staticmethod
    def _extract_reference_assets(text: str) -> list[str]:
        if not text:
            return []
        scan_text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
        scan_text = re.sub(r"<[^>]+>", "", scan_text)
        scan_text = re.sub(r"\[([^\]]+)\]\(https?://[^)]+\)", r"\1", scan_text)
        assets: list[str] = []
        assets.extend(match.group(1).strip() for match in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", text))
        assets.extend(match.group(0).strip() for match in re.finditer(r"https?://[^\s)]+", scan_text))
        assets.extend(match.group(0).strip() for match in re.finditer(r"\\\\[^\n\r]+", scan_text))
        cleaned: list[str] = []
        for asset in assets:
            asset = asset.replace("[", "").replace("]", "").strip(" \t\r\n。；;，,")
            if asset and asset not in cleaned:
                cleaned.append(asset)
        return cleaned[:20]

    @staticmethod
    def _infer_gameplay_summary(primary_text: str, game_context: str) -> str:
        text = "\n".join(item for item in [primary_text, game_context] if item)
        if not text:
            return "待确认"
        clauses: list[str] = []
        if any(token in text for token in ("分类", "同一分类", "收集区", "拖到")):
            clauses.append("分类整理玩法：识别同类卡片/词条，并将其归入目标收集区。")
        if any(token in text for token in ("卡片", "书", "词条")):
            clauses.append("核心视觉元素是卡片/书本/词条组，需要保持分类信息可读。")
        if any(token in text for token in ("lv3", "lv4", "关卡")):
            clauses.append("本轮围绕 lv3、lv4 关卡做版式复用和差异化排版。")
        if any(token in text for token in ("三本书", "3本书", "四本书", "4本书")):
            clauses.append("需要分别覆盖三本书和四本书两类布局变体。")
        if any(token in text for token in ("竞品", "参考图", "参照排版", "参考")):
            clauses.append("参考图/竞品路径用于理解版式结构、目标关卡和 PSD 还原依据。")
        if clauses:
            return "".join(clauses)
        for line in game_context.splitlines():
            if "玩法" in line:
                return line.split("：", 1)[-1].strip()[:180]
        return "待确认"

    @staticmethod
    def _summarize_primary_requirement(text: str) -> str:
        clean = RequirementInterpreter._clean_requirement_text(text)
        lines = [line.strip("-• \t") for line in clean.splitlines() if line.strip()]
        useful = [
            line
            for line in lines
            if "http://" not in line and "https://" not in line and not line.startswith("\\\\") and len(line) > 4
        ]
        summary = "；".join(useful[:5]).strip("；")
        return summary[:600] if summary else "待确认"

    @staticmethod
    def _extract_task_breakdown(primary_text: str, game_context: str) -> list[str]:
        text = "\n".join(item for item in [primary_text, game_context] if item)
        tasks: list[str] = []
        storyboard = any(token in text for token in ("剧情", "片头", "分镜", "镜头", "画面描述"))
        if any(token in text for token in ("参考竞品", "竞品", "参照排版", "参考图")):
            tasks.append("参考竞品/参考图拆解版式结构，再做新的平面排版。")
        if any(token in text for token in ("lv3", "lv4", "关卡")):
            tasks.append("围绕指定关卡做平面化呈现，并保持关卡信息可识别。")
        if any(token in text for token in ("三本书", "3本书", "四本书", "4本书")):
            tasks.append("分别制作三本书与四本书两类布局变体。")
        count_match = re.search(r"(?:一共|共|总共)\s*(\d+|[一二三四五六七八九十]+)\s*(?:个|张|版)", text)
        if count_match:
            tasks.append(f"本轮需要输出 {count_match.group(1)} 个平面版本。")
        if any(token in text for token in ("保留", "必须", "框出", "词条")):
            tasks.append("保留需求中指定的关键词条、可读信息和不可替换区域。")
        if not storyboard and any(token in text for token in ("PSD", "psd", "切图")):
            tasks.append("按投放美术交付方式组织 PSD 源文件与切图元素。")
        if storyboard:
            tasks.append("按剧情向片头/分镜拆镜头、角色表情、关键道具和横竖裁切安全区。")
        if not tasks:
            summary = RequirementInterpreter._summarize_primary_requirement(primary_text)
            if summary != "待确认":
                tasks.append(summary)
        return list(dict.fromkeys(tasks))

    @staticmethod
    def _infer_style_direction(primary_text: str, game_context: str) -> str:
        text = "\n".join(item for item in [primary_text, game_context] if item)
        directions = ["投放素材美术：优先保证玩法一眼可懂、信息层级清晰、主元素可点击感强"]
        storyboard = any(token in text for token in ("剧情", "片头", "分镜", "镜头", "画面描述"))
        if storyboard:
            directions.append("剧情向分镜优先服务镜头叙事、角色表情、关键道具和横竖构图适配")
        if any(token in text for token in ("卡片", "书", "词条", "分类")):
            directions.append("画面风格围绕卡片/书本/词条做清晰可读的休闲益智视觉")
        if any(token in text for token in ("竞品", "参考图", "参照排版")):
            directions.append("版式先贴近参考图的信息结构，再在项目素材内做差异化")
        if not storyboard and any(token in text for token in ("PSD", "psd", "切图")):
            directions.append("图层需要服务 PSD 复用与独立切图")
        return "；".join(dict.fromkeys(directions)) + "。"

    @staticmethod
    def _looks_like_performance_art_request(text: str, deliverables: list[str]) -> bool:
        if any(item in deliverables for item in ("PSD", "PNG", "切图")):
            return True
        return any(token in text for token in ("平面", "投放", "买量", "素材", "PSD", "psd", "切图", "海报"))

    @staticmethod
    def _clean_requirement_text(text: str) -> str:
        clean = re.sub(r"!\[[^\]]*\]\(([^)]+)\)", "\n参考图已提取到素材线索。\n", text)
        clean = re.sub(r"<!--.*?-->", "", clean, flags=re.DOTALL)
        clean = re.sub(r"<[^>]+>", "", clean)
        clean = re.sub(r"\[([^\]]+)\]\(https?://[^)]+\)", r"\1", clean)
        return clean

    @staticmethod
    def _extract_deadline(context: WorkItemContext) -> str:
        fields = context.raw_item.get("work_item_fields")
        if not isinstance(fields, list):
            return ""
        preferred_keys = {"field_93c7d8"}
        preferred_name_tokens = ("平面期望完成时间", "平面需求截止时间", "平面截止")
        fallback_name_tokens = ("期望完成时间", "截止时间", "完成时间")
        preferred_candidates: list[str] = []
        fallback_candidates: list[str] = []
        for item in fields:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or "")
            name = str(item.get("name") or "")
            is_preferred = key in preferred_keys or any(token in name for token in preferred_name_tokens)
            is_fallback = any(token in name for token in fallback_name_tokens) and "视频" not in name
            if not is_preferred and not is_fallback:
                continue
            value = item.get("value")
            parsed = RequirementInterpreter._parse_deadline_value(value)
            if parsed:
                if is_preferred:
                    preferred_candidates.append(parsed)
                else:
                    fallback_candidates.append(parsed)
        return first_non_empty(preferred_candidates) or first_non_empty(fallback_candidates)

    @staticmethod
    def _extract_sizes(context: WorkItemContext) -> list[str]:
        fields = context.raw_item.get("work_item_fields")
        if not isinstance(fields, list):
            return []
        sizes: list[str] = []
        for item in fields:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "")
            key = str(item.get("key") or "")
            if key != "field_dbf716" and "尺寸" not in name and "比例" not in name:
                continue
            sizes.extend(RequirementInterpreter._parse_sizes_value(item.get("value")))
        return list(dict.fromkeys(sizes))

    @staticmethod
    def _parse_sizes_value(value: Any) -> list[str]:
        if isinstance(value, dict):
            parts: list[str] = []
            for key in ("label", "name", "value"):
                parts.extend(RequirementInterpreter._parse_sizes_value(value.get(key)))
            return parts
        if isinstance(value, list):
            parts: list[str] = []
            for item in value:
                parts.extend(RequirementInterpreter._parse_sizes_value(item))
            return parts
        text = stringify(value).replace("：", ":").replace("×", "x")
        return find_sizes(text)

    @staticmethod
    def _parse_deadline_value(value: Any) -> str:
        if isinstance(value, dict):
            for key in ("iso_time", "date", "datetime", "time", "value", "name"):
                parsed = RequirementInterpreter._parse_deadline_value(value.get(key))
                if parsed:
                    return parsed
            return ""
        if isinstance(value, list):
            for item in value:
                parsed = RequirementInterpreter._parse_deadline_value(item)
                if parsed:
                    return parsed
            return ""
        text = stringify(value).strip()
        if not text or text == "None":
            return ""
        iso_match = re.search(r"20\d{2}-\d{1,2}-\d{1,2}", text)
        if iso_match:
            return iso_match.group(0)
        return RequirementInterpreter._infer_deadline(text)

    def _find_field(self, flat_pairs: list[tuple[str, str]], aliases: tuple[str, ...]) -> str:
        candidates: list[str] = []
        normalized_aliases = tuple(alias.lower() for alias in aliases)
        for key, value in flat_pairs:
            lower = key.lower()
            if any(alias in lower for alias in normalized_aliases):
                if value and value != "None":
                    candidates.append(value)
        return first_non_empty(candidates) or "待确认"

    def _find_mapped_or_alias(
        self,
        flat_pairs: list[tuple[str, str]],
        field_mapping: FieldMapping | None,
        canonical: str,
    ) -> str:
        mapped = self._find_mapped_value(flat_pairs, field_mapping, canonical)
        if mapped:
            return mapped
        return self._find_field(flat_pairs, FIELD_ALIASES[canonical])

    @staticmethod
    def _find_mapped_value(flat_pairs: list[tuple[str, str]], field_mapping: FieldMapping | None, canonical: str) -> str:
        if not field_mapping:
            return ""
        field_path = field_mapping.fields.get(canonical)
        if not field_path:
            return ""
        for key, value in flat_pairs:
            if key == field_path and value and value != "None":
                return value
        return ""

    @staticmethod
    def _split_items(value: str) -> list[str]:
        if not value or value == "待确认":
            return []
        parts = [item.strip() for item in value.replace("；", ";").replace("，", ",").replace("\n", ";").split(";")]
        final: list[str] = []
        for part in parts:
            final.extend(piece.strip() for piece in part.split(",") if piece.strip())
        return list(dict.fromkeys(final))

    @staticmethod
    def _fallback_if_unknown(value: str, fallback: str) -> str:
        return fallback if not value or value == "待确认" else value

    @staticmethod
    def _summarize_objective(text: str) -> str:
        snippets = []
        for line in text.splitlines():
            line = line.strip()
            if any(token in line for token in ("目标", "诉求", "点击", "转化", "下载", "活动")):
                snippets.append(line)
        return first_non_empty(snippets) or "待确认"

    @staticmethod
    def _infer_deliverables(text: str) -> list[str]:
        formats = {
            "psd": "PSD",
            "psb": "PSB",
            "png": "PNG",
            "jpg": "JPG",
            "jpeg": "JPEG",
            "webp": "WebP",
            "gif": "GIF",
            "mp4": "MP4",
        }
        found: list[str] = []
        lowered = text.lower()
        for token, label in formats.items():
            if re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", lowered):
                found.append(label)
        for token in ("切图", "动效", "源文件"):
            if token in text:
                found.append(token)
        if RequirementInterpreter._negates_psd_or_slicing(text):
            found = [item for item in found if item not in {"PSD", "切图"}]
        return list(dict.fromkeys(found))

    @staticmethod
    def _negates_psd_or_slicing(text: str) -> bool:
        return any(token in text for token in ("不套用 PSD", "不默认套用 PSD", "PSD类和切图的不适用", "PSD/切图检查仅在需求明确要求"))

    @staticmethod
    def _infer_audience(text: str) -> str:
        patterns = (
            r"(?:目标人群|受众|面向|人群)[：:\s]*([^\n；;。]+)",
            r"(?:目标用户|目标玩家|核心用户|核心玩家)[：:\s]*([^\n；;。]+)",
        )
        for line in text.splitlines():
            if not any(token in line for token in ("受众", "目标人群", "面向", "人群", "目标用户", "目标玩家", "核心用户", "核心玩家")):
                continue
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    candidate = match.group(1).strip(" ：:，,。")
                    if candidate:
                        return candidate
            cleaned = re.sub(r"^[^：:]{0,12}[：:]", "", line).strip()
            if cleaned:
                return cleaned[:80]
        return "待确认"

    @staticmethod
    def _infer_audience_from_game_context(text: str) -> str:
        if not text:
            return "待确认"
        lowered = text.lower()
        if any(token in text for token in ("益智", "解谜", "分类", "卡片", "收集区", "拖到")):
            return "休闲益智/分类解谜用户（基于玩法描述推断）"
        if any(token in text for token in ("RPG", "角色", "抽卡", "二次元")):
            return "RPG/角色养成用户（基于玩法描述推断）"
        if any(token in text for token in ("SLG", "策略", "战争", "联盟")):
            return "策略/SLG 用户（基于玩法描述推断）"
        if any(token in text for token in ("消除", "合成", "休闲")):
            return "休闲游戏用户（基于玩法描述推断）"
        if "puzzle" in lowered:
            return "休闲解谜用户（基于玩法描述推断）"
        return "泛游戏买量用户（基于项目字段推断）"

    @staticmethod
    def _infer_platform(text: str) -> str:
        platforms = (
            "Facebook",
            "Meta",
            "Instagram",
            "TikTok",
            "YouTube",
            "Google",
            "Unity",
            "AppLovin",
            "Mintegral",
            "穿山甲",
            "巨量",
            "广点通",
            "优量汇",
            "微信",
            "朋友圈",
            "视频号",
            "快手",
            "商店页",
            "活动页",
            "落地页",
        )
        lowered = text.lower()
        found = [platform for platform in platforms if platform.lower() in lowered]
        if found:
            return "、".join(dict.fromkeys(found))
        for line in text.splitlines():
            if any(token in line for token in ("平台", "渠道", "投放", "版位", "场景")):
                candidate = re.sub(r"^[^：:]{0,16}[：:]", "", line).strip(" ，,。")
                if candidate:
                    return candidate[:80]
        return "待确认"

    @staticmethod
    def _infer_deadline(text: str) -> str:
        date_pattern = re.compile(
            r"(?:20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}日?|\d{1,2}月\d{1,2}日|周[一二三四五六日天]|星期[一二三四五六日天]|今天|今晚|明天|后天|本周|下周)"
        )
        priority_lines = [
            line.strip()
            for line in text.splitlines()
            if any(token.lower() in line.lower() for token in ("截止", "截至", "ddl", "deadline", "首稿", "终稿", "交付", "完成"))
        ]
        for line in priority_lines + [item.strip() for item in text.splitlines()]:
            match = date_pattern.search(line)
            if match:
                return match.group(0)
        return "待确认"

    @staticmethod
    def _extract_signals(text: str) -> list[str]:
        signals = []
        for keyword in ("二次元", "写实", "国风", "Q版", "高转化", "角色突出", "活动海报", "按钮", "主视觉"):
            if keyword.lower() in text.lower():
                signals.append(keyword)
        return signals

    @staticmethod
    def _infer_category(text: str) -> str:
        lowered = text.lower()
        for category, keywords in CATEGORY_KEYWORDS.items():
            if any(keyword.lower() in lowered for keyword in keywords):
                return category
        return "general-game-design"
