from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from agent.models import ImageExecutionPackage, ImageExecutionPackageItem


class ImageExecutionPackager:
    def build(
        self,
        queue_payload: dict[str, Any],
        source_queue: str,
        package_root: Path,
    ) -> ImageExecutionPackage:
        project_key = str(queue_payload.get("project_key") or "unknown-project")
        work_item_id = str(queue_payload.get("work_item_id") or "unknown-work-item")
        jobs = queue_payload.get("jobs", [])
        if not isinstance(jobs, list):
            raise ValueError("image_generation_jobs.json must contain a jobs list.")

        payload_dir = package_root / "payloads"
        items: list[ImageExecutionPackageItem] = []
        warnings = list(queue_payload.get("warnings", []))
        for job in jobs:
            job_id = str(job.get("job_id") or "")
            variant_id = str(job.get("variant_id") or "")
            if not job_id or not variant_id:
                warnings.append("存在缺少 job_id 或 variant_id 的生成任务，已跳过。")
                continue
            payload_file = payload_dir / f"{job_id}.json"
            items.append(
                ImageExecutionPackageItem(
                    job_id=job_id,
                    variant_id=variant_id,
                    provider=str(job.get("provider") or "pixpark"),
                    title=str(job.get("title") or variant_id),
                    payload_file=str(payload_file),
                    output_dir=str(job.get("output_dir") or package_root / "outputs" / variant_id),
                    result_placeholder=f"<paste generated image path or URL for {variant_id}>",
                    safety_notes=list(job.get("safety_notes", [])),
                )
            )

        if not items:
            warnings.append("没有可交给执行器的生成任务。")

        return ImageExecutionPackage(
            project_key=project_key,
            work_item_id=work_item_id,
            created_at=datetime.now().isoformat(timespec="seconds"),
            source_queue=source_queue,
            package_root=str(package_root),
            execution_mode="handoff-only",
            requires_designer_confirmation=True,
            items=items,
            runbook=self._runbook(items),
            result_template=self._result_template(items),
            warnings=list(dict.fromkeys(warnings)),
            next_actions=self._next_actions(items),
        )

    @staticmethod
    def render_markdown(package: ImageExecutionPackage) -> str:
        lines = [
            f"# 图像生成执行交接包 - {package.work_item_id}",
            "",
            f"- 项目：`{package.project_key}`",
            f"- 创建时间：`{package.created_at}`",
            f"- 来源队列：`{package.source_queue}`",
            f"- 交接目录：`{package.package_root}`",
            f"- 执行模式：`{package.execution_mode}`",
            f"- 需要设计师确认：{'是' if package.requires_designer_confirmation else '否'}",
            "",
            "## 警告",
            *(f"- {item}" for item in package.warnings or ["无"]),
            "",
            "## 任务",
        ]
        if not package.items:
            lines.append("- 无")
        for item in package.items:
            lines.extend(
                [
                    f"### {item.job_id}",
                    f"- 方案：`{item.variant_id}` {item.title}",
                    f"- 工具：`{item.provider}`",
                    f"- Payload：`{item.payload_file}`",
                    f"- 输出目录：`{item.output_dir}`",
                    f"- 结果占位：`{item.result_placeholder}`",
                    "",
                    "安全说明:",
                    *(f"- {note}" for note in item.safety_notes or ["执行前必须由设计师确认。"]),
                    "",
                ]
            )
        lines.extend(["## 执行说明", *(f"- {item}" for item in package.runbook)])
        lines.extend(["", "## 下一步", *(f"- {item}" for item in package.next_actions)])
        return "\n".join(lines)

    @staticmethod
    def render_runbook(package: ImageExecutionPackage) -> str:
        return "\n".join(
            [
                f"# Pixpark 执行说明 - {package.work_item_id}",
                "",
                "## 安全边界",
                "- 本文件只说明如何手动执行，不会调用任何生图工具。",
                "- 执行前必须确认 `generation_approval_ticket.md` 已通过设计师审核。",
                "- 生成结果只能写入当前 package/output 或登记为 URL，不自动进入正式交付。",
                "",
                "## 步骤",
                *(f"{index}. {item}" for index, item in enumerate(package.runbook, start=1)),
                "",
                "## 结果登记",
                "- 把生成图片路径或 URL 填入 `generation_results_template.json`。",
                "- 然后运行 `register-image-results` 生成 gallery 和候选清单。",
            ]
        )

    @staticmethod
    def render_payload(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @staticmethod
    def _runbook(items: list[ImageExecutionPackageItem]) -> list[str]:
        if not items:
            return ["先创建 image_generation_jobs，再准备执行交接包。"]
        return [
            "逐个打开 payloads 目录里的 JSON，复制到对应生图工具或执行适配器。",
            "每个任务生成后，把图片保存到该任务 output_dir，或记录生成结果 URL。",
            "把最终要评审的图片路径/URL 填入 generation_results_template.json。",
            "运行 register-image-results，把结果登记为 generated_gallery 和 delivery_candidates。",
        ]

    @staticmethod
    def _result_template(items: list[ImageExecutionPackageItem]) -> dict[str, Any]:
        return {
            "assets": [
                {
                    "job_id": item.job_id,
                    "variant_id": item.variant_id,
                    "uri": item.result_placeholder,
                    "notes": ["candidate"],
                }
                for item in items
            ]
        }

    @staticmethod
    def _next_actions(items: list[ImageExecutionPackageItem]) -> list[str]:
        if not items:
            return ["先运行 create-image-generation-jobs 生成可执行队列。"]
        return [
            "设计师确认 execution package 和 generation_approval_ticket 后，再手动执行生图。",
            "生成完成后填写 generation_results_template.json。",
            "运行 register-image-results 进入候选图评审与学习闭环。",
        ]
