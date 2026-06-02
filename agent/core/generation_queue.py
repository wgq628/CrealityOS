from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from agent.models import ImageGenerationJob, ImageGenerationQueue
from agent.utils import ensure_directory, slugify


class ImageGenerationQueueBuilder:
    def build(
        self,
        batch_payload: dict[str, Any],
        source_batch: str,
        selected_variants: list[str] | None,
        output_root: Path,
        execution_mode: str = "manual-confirmation",
    ) -> ImageGenerationQueue:
        project_key = str(batch_payload.get("project_key") or "unknown-project")
        work_item_id = str(batch_payload.get("work_item_id") or "unknown-work-item")
        selected = {item.upper() for item in selected_variants or []}
        variants = batch_payload.get("variants", [])
        if not isinstance(variants, list):
            raise ValueError("image_generation_batch.json must contain a variants list.")

        jobs: list[ImageGenerationJob] = []
        warnings = list(batch_payload.get("warnings", []))
        for variant in variants:
            variant_id = str(variant.get("variant_id") or "").upper()
            if not variant_id or (selected and variant_id not in selected):
                continue
            payload = dict((variant.get("tool_payloads") or {}).get("pixpark_draft") or {})
            if not payload:
                warnings.append(f"{variant_id} 缺少 pixpark_draft payload，已跳过")
                continue
            job_output_dir = output_root / slugify(variant_id, fallback="variant")
            ensure_directory(job_output_dir)
            jobs.append(
                ImageGenerationJob(
                    job_id=f"{work_item_id}-{variant_id}-pixpark",
                    variant_id=variant_id,
                    title=str(variant.get("title") or variant_id),
                    provider="pixpark",
                    status="pending_designer_confirmation",
                    payload=payload,
                    output_dir=str(job_output_dir),
                    safety_notes=[
                        "本队列只准备生成请求，不自动消耗算力。",
                        "执行前必须由设计师确认方案、参考图、比例和数量。",
                        "生成结果只能进入 workspace staging，不自动对外发送或覆盖正式资产。",
                    ],
                    expected_outputs=[
                        f"{variant_id}_draft_01.png",
                        f"{variant_id}_source_payload.json",
                        f"{variant_id}_review_note.md",
                    ],
                )
            )

        if selected and not jobs:
            warnings.append("指定的 variant 没有生成任何任务，请检查 V01/V02/V03/V04 是否存在。")
        if not selected and not jobs:
            warnings.append("没有可生成的 Pixpark 任务。")

        return ImageGenerationQueue(
            project_key=project_key,
            work_item_id=work_item_id,
            created_at=datetime.now().isoformat(timespec="seconds"),
            source_batch=source_batch,
            execution_mode=execution_mode,
            requires_designer_confirmation=True,
            jobs=jobs,
            warnings=list(dict.fromkeys(warnings)),
            next_actions=self._next_actions(jobs),
        )

    @staticmethod
    def render_markdown(queue: ImageGenerationQueue) -> str:
        lines = [
            f"# 图像生成任务队列 - {queue.work_item_id}",
            "",
            f"- 项目：`{queue.project_key}`",
            f"- 创建时间：`{queue.created_at}`",
            f"- 来源批次：`{queue.source_batch}`",
            f"- 执行模式：`{queue.execution_mode}`",
            f"- 需要设计师确认：{'是' if queue.requires_designer_confirmation else '否'}",
            "",
            "## 警告",
            *(f"- {item}" for item in queue.warnings or ["无"]),
            "",
            "## 任务",
        ]
        if not queue.jobs:
            lines.append("- 无可执行任务")
        for job in queue.jobs:
            lines.extend(
                [
                    f"### {job.job_id}",
                    f"- 方案：`{job.variant_id}` {job.title}",
                    f"- 工具：`{job.provider}`",
                    f"- 状态：`{job.status}`",
                    f"- 输出目录：`{job.output_dir}`",
                    "",
                    "Payload:",
                    "```json",
                    json.dumps(job.payload, ensure_ascii=False, indent=2),
                    "```",
                    "",
                    "安全说明:",
                    *(f"- {item}" for item in job.safety_notes),
                    "",
                    "预期产物:",
                    *(f"- `{item}`" for item in job.expected_outputs),
                    "",
                ]
            )
        lines.extend(["## 下一步", *(f"- {item}" for item in queue.next_actions)])
        return "\n".join(lines)

    @staticmethod
    def render_pixpark_jsonl(queue: ImageGenerationQueue) -> str:
        lines: list[str] = []
        for job in queue.jobs:
            lines.append(
                json.dumps(
                    {
                        "job_id": job.job_id,
                        "variant_id": job.variant_id,
                        "provider": job.provider,
                        "status": job.status,
                        "payload": job.payload,
                        "output_dir": job.output_dir,
                    },
                    ensure_ascii=False,
                )
            )
        return "\n".join(lines) + ("\n" if lines else "")

    @staticmethod
    def _next_actions(jobs: list[ImageGenerationJob]) -> list[str]:
        if not jobs:
            return ["先重新生成 image_generation_batch，或检查方案 payload 是否完整。"]
        return [
            "设计师确认要执行的 variant、比例、参考图和张数。",
            "确认后可将 pixpark_requests.jsonl 交给执行适配器逐条生成。",
            "生成图进入 output_dir 后，用 candidate_evaluation.md 评审并运行 ingest-candidate-review 回写记忆。",
        ]
