from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from agent.models import FieldCalibrationReport, FieldMapping
from agent.utils import find_sizes, flatten_pairs, stringify


CANONICAL_FIELDS = {
    "objective": ("objective", "goal", "target", "目标", "诉求", "需求描述", "description", "brief", "内容"),
    "audience": ("audience", "user", "player", "target_user", "用户", "目标人群", "受众", "玩家"),
    "platform": ("platform", "placement", "channel", "media", "平台", "渠道", "投放", "版位"),
    "sizes": ("size", "ratio", "dimension", "spec", "尺寸", "比例", "规格"),
    "deliverables": ("deliverable", "handoff", "output", "format", "asset", "交付", "产出", "文件", "格式"),
    "deadline": ("deadline", "due", "end", "schedule", "截至", "截止", "完成时间", "排期"),
}

VALUE_HINTS = {
    "objective": ("点击", "转化", "下载", "活动", "提升", "目标", "诉求"),
    "audience": ("用户", "玩家", "受众", "人群", "女性", "男性", "核心"),
    "platform": ("facebook", "tiktok", "google", "ios", "android", "朋友圈", "穿山甲", "广点通"),
    "sizes": ("x", ":", "px", "像素", "尺寸"),
    "deliverables": ("psd", "png", "jpg", "切图", "源文件", "导出", "交付"),
    "deadline": ("202", "今天", "明天", "本周", "下周", "截止"),
}


class FieldCalibrator:
    def build_report(self, project_key: str, sample_file: str, payload: dict[str, Any]) -> FieldCalibrationReport:
        flat_pairs = flatten_pairs(payload)
        mapping_fields: dict[str, str] = {}
        confidence: dict[str, float] = {}
        candidates: dict[str, list[str]] = {}
        warnings: list[str] = []

        for canonical, aliases in CANONICAL_FIELDS.items():
            scored = self._score_candidates(flat_pairs, canonical, aliases)
            candidates[canonical] = [f"{key} ({score:.2f})" for key, _value, score in scored[:5]]
            if scored:
                best_key, _best_value, best_score = scored[0]
                mapping_fields[canonical] = best_key
                confidence[canonical] = round(best_score, 2)
                if best_score < 0.55:
                    warnings.append(f"{canonical} 字段置信度偏低，请人工确认：{best_key}")
            else:
                confidence[canonical] = 0.0
                warnings.append(f"未识别到 {canonical} 字段")

        mapping = FieldMapping(
            project_key=project_key,
            fields=mapping_fields,
            confidence=confidence,
            notes=["自动校准结果建议人工检查一次，确认后再长期复用。"],
        )
        return FieldCalibrationReport(
            project_key=project_key,
            sample_file=str(Path(sample_file)),
            created_at=datetime.now().isoformat(timespec="seconds"),
            mapping=mapping,
            candidates=candidates,
            warnings=warnings,
        )

    @staticmethod
    def render_markdown(report: FieldCalibrationReport) -> str:
        lines = [
            f"# 字段校准报告 - {report.project_key}",
            "",
            f"- 样本文件：`{report.sample_file}`",
            f"- 生成时间：`{report.created_at}`",
            "",
            "## 推荐映射",
        ]
        for canonical, field_path in report.mapping.fields.items():
            score = report.mapping.confidence.get(canonical, 0.0)
            lines.append(f"- `{canonical}` -> `{field_path}` | confidence={score:.2f}")
        lines.extend(["", "## 候选字段"])
        for canonical, values in report.candidates.items():
            lines.append(f"### {canonical}")
            lines.extend(f"- {item}" for item in values or ["无"])
        lines.extend(["", "## 警告", *(f"- {item}" for item in report.warnings or ["无"])])
        return "\n".join(lines)

    def _score_candidates(
        self,
        flat_pairs: list[tuple[str, str]],
        canonical: str,
        aliases: tuple[str, ...],
    ) -> list[tuple[str, str, float]]:
        scored: list[tuple[str, str, float]] = []
        for key, value in flat_pairs:
            if not value or value == "None":
                continue
            score = 0.0
            lower_key = key.lower()
            lower_value = stringify(value).lower()
            for alias in aliases:
                if alias.lower() in lower_key:
                    score += 0.7
            for hint in VALUE_HINTS[canonical]:
                if hint.lower() in lower_value:
                    score += 0.2
            if canonical == "sizes" and find_sizes(value):
                score += 0.6
            if canonical == "deadline" and any(ch.isdigit() for ch in value):
                score += 0.15
            if score > 0:
                scored.append((key, value, min(score, 1.0)))
        scored.sort(key=lambda item: (-item[2], len(item[0]), item[0]))
        return scored
