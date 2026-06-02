from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from agent.models import CreativePack, ProjectProfile, PsdSliceSpecFinding, PsdSliceSpecReport
from agent.utils import slugify


class PsdSliceSpecAuditor:
    REQUIRED_GROUPS = ("00_refs", "01_background", "02_subject", "03_effects", "04_copy", "05_cta", "06_ui_slices", "99_exports")

    def build(
        self,
        project_key: str,
        work_item_id: str,
        psd_handoff_plan: dict[str, Any] | None,
        psd_handoff_package: dict[str, Any] | None,
        creative_pack: CreativePack | None,
        profile: ProjectProfile | None,
        source_artifacts: dict[str, str | None],
    ) -> PsdSliceSpecReport:
        required_groups = self._required_groups(psd_handoff_plan, creative_pack)
        slicing_tasks = self._slicing_tasks(psd_handoff_plan, creative_pack, profile)
        naming_examples = self._naming_examples(project_key, work_item_id, psd_handoff_plan, creative_pack, profile)
        findings = [
            self._candidate_asset_check(psd_handoff_plan),
            self._layer_group_check(required_groups, psd_handoff_plan),
            self._slicing_task_check(slicing_tasks),
            self._naming_check(naming_examples),
            self._staging_check(psd_handoff_package),
            self._safety_check(),
        ]
        blockers = [finding.action for finding in findings if finding.severity == "blocker" and finding.action]
        warnings = [finding.action for finding in findings if finding.severity == "warning" and finding.action]
        status = "blocked" if blockers else "needs_designer_review" if warnings else "ready_for_psd_work"
        return PsdSliceSpecReport(
            project_key=project_key,
            work_item_id=work_item_id,
            created_at=datetime.now().isoformat(timespec="seconds"),
            status=status,
            required_layer_groups=required_groups,
            slicing_tasks=slicing_tasks,
            naming_examples=naming_examples,
            findings=findings,
            blockers=list(dict.fromkeys(blockers)),
            warnings=list(dict.fromkeys(warnings)),
            source_artifacts=source_artifacts,
            next_actions=self._next_actions(status),
        )

    @staticmethod
    def render_markdown(report: PsdSliceSpecReport) -> str:
        lines = [
            f"# PSD/切图规格核对 - {report.work_item_id}",
            "",
            f"- 项目：`{report.project_key}`",
            f"- 创建时间：`{report.created_at}`",
            f"- 状态：`{report.status}`",
            "",
            "## 来源产物",
        ]
        lines.extend(f"- {key}: `{value or '缺失'}`" for key, value in report.source_artifacts.items())
        lines.extend(["", "## 必要图层组", *(f"- `{item}`" for item in report.required_layer_groups)])
        lines.extend(["", "## 切图任务", *(f"- [ ] {item}" for item in report.slicing_tasks or ["待补充"])])
        lines.extend(["", "## 命名样例", *(f"- `{item}`" for item in report.naming_examples or ["待补充"])])
        lines.extend(["", "## 阻塞项", *(f"- {item}" for item in report.blockers or ["无"])])
        lines.extend(["", "## 风险提醒", *(f"- {item}" for item in report.warnings or ["无"])])
        lines.append("")
        lines.append("## 检查项")
        for finding in report.findings:
            lines.extend(
                [
                    f"### {finding.check_id} {finding.title}",
                    f"- 状态：`{finding.status}`",
                    f"- 严重级别：`{finding.severity}`",
                    *(f"- 证据：{item}" for item in finding.evidence or ["无"]),
                    f"- 建议动作：{finding.action or '无'}",
                    "",
                ]
            )
        lines.extend(["## 下一步", *(f"- {item}" for item in report.next_actions)])
        return "\n".join(lines)

    def _required_groups(self, psd_handoff_plan: dict[str, Any] | None, creative_pack: CreativePack | None) -> list[str]:
        groups = list(self.REQUIRED_GROUPS)
        groups.extend(str(item) for item in (psd_handoff_plan or {}).get("layer_groups", []))
        if creative_pack and creative_pack.delivery_manifest.slicing_notes:
            groups.append("slice_notes")
        return list(dict.fromkeys(groups))

    @staticmethod
    def _slicing_tasks(
        psd_handoff_plan: dict[str, Any] | None,
        creative_pack: CreativePack | None,
        profile: ProjectProfile | None,
    ) -> list[str]:
        tasks: list[str] = []
        tasks.extend(str(item) for item in (psd_handoff_plan or {}).get("slicing_tasks", []))
        if creative_pack:
            tasks.extend(creative_pack.delivery_manifest.slicing_notes)
        if profile:
            tasks.extend(profile.slice_requirements)
        return list(dict.fromkeys(item for item in tasks if item))

    @staticmethod
    def _naming_examples(
        project_key: str,
        work_item_id: str,
        psd_handoff_plan: dict[str, Any] | None,
        creative_pack: CreativePack | None,
        profile: ProjectProfile | None,
    ) -> list[str]:
        rules: list[str] = []
        rules.extend(str(item) for item in (psd_handoff_plan or {}).get("naming_rules", []))
        if creative_pack:
            rules.extend(creative_pack.delivery_manifest.naming_rules)
        if profile and profile.delivery_naming_template:
            rules.append(profile.delivery_naming_template)
        examples: list[str] = []
        sample_size = "1080x1920"
        sample_role = "cta"
        for rule in list(dict.fromkeys(rules))[:5]:
            example = rule
            replacements = {
                "{project_key}": project_key,
                "{work_item_id}": work_item_id,
                "{asset_role}": sample_role,
                "{size}": sample_size,
                "{version}": "v001",
            }
            for key, value in replacements.items():
                example = example.replace(key, value)
            examples.append(slugify(example, fallback=f"{project_key}_{work_item_id}_{sample_role}_{sample_size}_v001"))
        return list(dict.fromkeys(examples))

    @staticmethod
    def _candidate_asset_check(psd_handoff_plan: dict[str, Any] | None) -> PsdSliceSpecFinding:
        if not psd_handoff_plan:
            return PsdSliceSpecFinding(
                "CANDIDATE",
                "PSD 候选资产",
                "missing_plan",
                "blocker",
                ["缺少 PSD 交接计划"],
                "先运行 create-psd-handoff-plan 生成 PSD 交接计划。",
            )
        assets = psd_handoff_plan.get("assets", [])
        warnings = [str(item) for item in psd_handoff_plan.get("warnings", [])]
        evidence = [f"候选资产数：{len(assets)}", *warnings[:3]]
        if not assets:
            return PsdSliceSpecFinding(
                "CANDIDATE",
                "PSD 候选资产",
                "missing_assets",
                "blocker",
                evidence,
                "先登记生成结果或选择本地候选图，再进入 PSD/切图规格检查。",
            )
        return PsdSliceSpecFinding("CANDIDATE", "PSD 候选资产", "pass", "info", evidence)

    def _layer_group_check(self, required_groups: list[str], psd_handoff_plan: dict[str, Any] | None) -> PsdSliceSpecFinding:
        actual = set(str(item) for item in (psd_handoff_plan or {}).get("layer_groups", []))
        missing = [group for group in self.REQUIRED_GROUPS if group not in actual]
        evidence = [f"必要组：{len(self.REQUIRED_GROUPS)}", f"计划中图层组：{len(actual)}"]
        if not psd_handoff_plan:
            return PsdSliceSpecFinding("LAYER", "PSD 图层组", "missing_plan", "blocker", evidence, "先运行 create-psd-handoff-plan 生成 PSD 交接计划。")
        if missing:
            return PsdSliceSpecFinding("LAYER", "PSD 图层组", "missing_groups", "warning", evidence + missing, "PSD 计划缺少部分标准图层组，请确认是否需要补齐。")
        return PsdSliceSpecFinding("LAYER", "PSD 图层组", "pass", "info", evidence + required_groups[:6])

    @staticmethod
    def _slicing_task_check(slicing_tasks: list[str]) -> PsdSliceSpecFinding:
        evidence = [f"切图任务数：{len(slicing_tasks)}"]
        if not slicing_tasks:
            return PsdSliceSpecFinding("SLICE", "切图任务", "missing", "warning", evidence, "请补充切图任务，或确认本次只交整图不切图。")
        if not any(any(token in task for token in ("按钮", "底板", "图标", "icon", "CTA", "cta")) for task in slicing_tasks):
            return PsdSliceSpecFinding("SLICE", "切图任务", "too_generic", "warning", evidence + slicing_tasks[:5], "切图任务缺少按钮/底板/icon/CTA 等明确对象，请补充。")
        return PsdSliceSpecFinding("SLICE", "切图任务", "pass", "info", evidence + slicing_tasks[:5])

    @staticmethod
    def _naming_check(naming_examples: list[str]) -> PsdSliceSpecFinding:
        evidence = naming_examples[:5] or ["无命名样例"]
        if not naming_examples:
            return PsdSliceSpecFinding("NAMING", "命名样例", "missing", "warning", evidence, "请补充命名模板或确认使用默认命名规则。")
        return PsdSliceSpecFinding("NAMING", "命名样例", "pass", "info", evidence)

    @staticmethod
    def _staging_check(psd_handoff_package: dict[str, Any] | None) -> PsdSliceSpecFinding:
        if not psd_handoff_package:
            return PsdSliceSpecFinding("STAGING", "PSD staging", "missing", "warning", action="建议运行 prepare-psd-handoff-package，把候选图复制到安全 staging。")
        items = psd_handoff_package.get("items", [])
        staged = [item for item in items if item.get("status") == "staged"]
        external = [item for item in items if item.get("status") == "external-reference"]
        missing = [item for item in items if item.get("status") == "missing-local-file"]
        evidence = [f"staged={len(staged)}", f"external={len(external)}", f"missing={len(missing)}"]
        if missing:
            return PsdSliceSpecFinding("STAGING", "PSD staging", "missing_files", "blocker", evidence, "先补齐 staging 中缺失的本地候选图。")
        if not staged and external:
            return PsdSliceSpecFinding("STAGING", "PSD staging", "external_only", "warning", evidence, "当前只有远程引用，进入 Photoshop 前请人工下载或确认工具可访问。")
        return PsdSliceSpecFinding("STAGING", "PSD staging", "pass", "info", evidence)

    @staticmethod
    def _safety_check() -> PsdSliceSpecFinding:
        return PsdSliceSpecFinding(
            "SAFETY",
            "安全门控",
            "pass",
            "info",
            ["本报告只做本地规格核对，不打开 Photoshop、不导出、不覆盖正式文件。"],
            "正式 PSD 精修、切图导出或交付前仍需设计师确认。",
        )

    @staticmethod
    def _next_actions(status: str) -> list[str]:
        if status == "blocked":
            return [
                "先处理阻塞项，再进入 Photoshop 或切图。",
                "修正后重新生成 PSD/切图规格核对报告。",
            ]
        return [
            "设计师复核图层组、切图任务和命名样例。",
            "确认后再进入 Photoshop 手工精修、脚本 dry-run 检查或正式 staging。",
            "正式导出和覆盖文件前仍需单独确认。",
        ]
