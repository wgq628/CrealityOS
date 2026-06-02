from __future__ import annotations

from datetime import datetime

from agent.models import CreativePack, ImageProductionBatch, ImageVariant, KnowledgeLevel, ProjectProfile


class ImageProductionPlanner:
    def build(
        self,
        creative_pack: CreativePack,
        profile: ProjectProfile | None,
        source_output_dir: str,
    ) -> ImageProductionBatch:
        brief = creative_pack.brief
        sizes = brief.sizes or (profile.default_sizes if profile else []) or ["1:1"]
        shared_negative = list(dict.fromkeys(creative_pack.prompt_pack.negative))
        warnings = self._warnings(creative_pack)
        variants = [
            self._variant(
                "V01",
                "稳妥项目风格版",
                "优先贴合已确认项目风格，适合作为第一轮基准稿。",
                creative_pack,
                profile,
                sizes,
                extra_positive=["严格遵守 K1/K2 风格规则", "信息层级稳健", "商业化素材完成度高"],
                extra_negative=[],
            ),
            self._variant(
                "V02",
                "转化强化版",
                "强化点击转化、利益点和按钮区域，适合广告投放素材探索。",
                creative_pack,
                profile,
                sizes,
                extra_positive=["强 CTA 区域", "标题与利益点更醒目", "高对比主体轮廓", "买量广告主视觉"],
                extra_negative=["避免装饰细节压过利益点"],
            ),
            self._variant(
                "V03",
                "构图突破版",
                "保留项目底线，探索更大胆的镜头、透视或主体占比。",
                creative_pack,
                profile,
                sizes,
                extra_positive=["更强动势", "夸张透视", "主体占比更大", "视觉冲击力强"],
                extra_negative=["不要牺牲项目识别度", "不要破坏文案安全区"],
            ),
            self._variant(
                "V04",
                "PSD切图友好版",
                "面向后续 PSD 分层和切图，优先保证元素可拆、边界清楚。",
                creative_pack,
                profile,
                sizes,
                extra_positive=["清晰分层", "按钮和底板可独立拆分", "背景与主体边界明确", "适合后续 PSD 重建"],
                extra_negative=["避免复杂交叠导致切图困难", "避免主体边缘过度碎片化"],
            ),
        ]
        return ImageProductionBatch(
            project_key=brief.project_key or "unknown-project",
            work_item_id=brief.work_item_id,
            created_at=datetime.now().isoformat(timespec="seconds"),
            source_output_dir=source_output_dir,
            variants=variants,
            shared_negative_prompt=shared_negative,
            acceptance_checklist=self._acceptance_checklist(creative_pack),
            feedback_questions=self._feedback_questions(),
            warnings=warnings,
        )

    @staticmethod
    def render_markdown(batch: ImageProductionBatch) -> str:
        lines = [
            f"# 出图批次计划 - {batch.work_item_id}",
            "",
            f"- 项目：`{batch.project_key}`",
            f"- 创建时间：`{batch.created_at}`",
            f"- 来源创作包：`{batch.source_output_dir}`",
            "",
            "## 批次警告",
            *(f"- {item}" for item in batch.warnings or ["无"]),
            "",
            "## 共享负面词",
            *(f"- {item}" for item in batch.shared_negative_prompt or ["无"]),
            "",
            "## 方案",
        ]
        for variant in batch.variants:
            lines.extend(
                [
                    f"### {variant.variant_id} {variant.title}",
                    f"- 意图：{variant.intent}",
                    f"- 尺寸：{', '.join(variant.target_sizes)}",
                    "",
                    "Positive:",
                    variant.positive_prompt,
                    "",
                    "Negative:",
                    variant.negative_prompt,
                    "",
                    "参考策略:",
                    *(f"- {item}" for item in variant.reference_policy),
                    "",
                    "评审尺子:",
                    *(f"- [ ] {item}" for item in variant.review_rubric),
                    "",
                    "PSD/切图提示:",
                    *(f"- {item}" for item in variant.psd_notes),
                    "",
                ]
            )
        lines.extend(
            [
                "## 通过标准",
                *(f"- [ ] {item}" for item in batch.acceptance_checklist),
                "",
                "## 给设计师的反馈问题",
                *(f"- {item}" for item in batch.feedback_questions),
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def render_evaluation_sheet(batch: ImageProductionBatch) -> str:
        lines = [
            f"# 出图评审表 - {batch.work_item_id}",
            "",
            "评分建议：1=不可用，3=可修，5=可进入 PSD/切图。",
            "",
            "| 方案 | 风格贴合 | 需求贴合 | 转化潜力 | PSD/切图友好 | 风险 | 结论 | 修改意见 |",
            "|---|---:|---:|---:|---:|---|---|---|",
        ]
        for variant in batch.variants:
            lines.append(f"| {variant.variant_id} {variant.title} |  |  |  |  |  |  |  |")
        lines.extend(
            [
                "",
                "## 回写建议",
                "- 如果某个方案被采纳：把“为什么像项目风格”写进 `ingest-feedback --decision approved`。",
                "- 如果某个方案被否：把“偏在哪里/为什么不要”写进 `ingest-feedback --decision rejected`。",
                "- 如果只是方向可探索：用 `--decision revise` 保持为 K3 待验证。",
            ]
        )
        return "\n".join(lines)

    def _variant(
        self,
        variant_id: str,
        title: str,
        intent: str,
        creative_pack: CreativePack,
        profile: ProjectProfile | None,
        sizes: list[str],
        extra_positive: list[str],
        extra_negative: list[str],
    ) -> ImageVariant:
        base_positive = list(creative_pack.prompt_pack.positive)
        rules = self._rule_prompts(creative_pack)
        positive = "，".join(item for item in base_positive + rules + extra_positive if item)
        negative_items = list(dict.fromkeys(creative_pack.prompt_pack.negative + extra_negative))
        negative = "，".join(negative_items)
        return ImageVariant(
            variant_id=variant_id,
            title=title,
            intent=intent,
            positive_prompt=positive,
            negative_prompt=negative,
            target_sizes=sizes,
            reference_policy=self._reference_policy(creative_pack, profile),
            review_rubric=self._review_rubric(creative_pack),
            psd_notes=self._psd_notes(creative_pack),
            tool_payloads={
                "pixpark_draft": {
                    "inputPrompt": positive,
                    "imageNum": 1,
                    "imageScale": self._pick_image_scale(sizes),
                    "resolution": "1K",
                    "version": 3,
                    "notes": "建议先用基础尺寸试方向，设计师确认后再提高分辨率或进入 PSD 重建。",
                }
            },
        )

    @staticmethod
    def _rule_prompts(creative_pack: CreativePack) -> list[str]:
        prompts: list[str] = []
        for rule in creative_pack.style_card.rules:
            if rule.level in {KnowledgeLevel.K1, KnowledgeLevel.K2, "K1", "K2"}:
                prompts.append(rule.statement)
        return prompts[:6]

    @staticmethod
    def _reference_policy(creative_pack: CreativePack, profile: ProjectProfile | None) -> list[str]:
        policy = [
            "优先使用已确认项目素材或同项目历史优胜稿作为参考图",
            "K3 假设只能用于探索方案，不作为必须执行规则",
            "参考图只服务构图/材质/色彩，不照搬竞品核心识别元素",
        ]
        if profile and profile.visual_keywords:
            policy.append("项目关键词必须可见：" + "，".join(profile.visual_keywords[:5]))
        if creative_pack.prompt_pack.reference_groups:
            policy.extend(creative_pack.prompt_pack.reference_groups[:2])
        return list(dict.fromkeys(policy))

    @staticmethod
    def _review_rubric(creative_pack: CreativePack) -> list[str]:
        rubric = [
            "是否满足需求目标和目标平台",
            "是否贴合 K1/K2 风格规则",
            "是否把主体、标题、利益点、CTA 层级拉开",
            "是否存在字体、世界观、材质或色彩冲突",
            "是否方便后续 PSD 分层、切图和多尺寸适配",
        ]
        if creative_pack.uncertainties:
            rubric.append("是否主动标出并处理了不确定项：" + "；".join(creative_pack.uncertainties[:3]))
        return rubric

    @staticmethod
    def _psd_notes(creative_pack: CreativePack) -> list[str]:
        return list(dict.fromkeys(creative_pack.psd_guidance + creative_pack.delivery_manifest.slicing_notes))[:8]

    @staticmethod
    def _acceptance_checklist(creative_pack: CreativePack) -> list[str]:
        items = [
            "至少选择一个方向进入人工精修或 PSD 重建",
            "所有采纳方向都要说明采纳原因，便于升级 K2/K1 记忆",
            "所有驳回方向都要说明偏差原因，便于下次避开",
            "正式交付前确认尺寸、命名、导出格式和切图要求",
        ]
        if creative_pack.uncertainties:
            items.insert(0, "先闭合创作包中的不确定项，或明确哪些可以带风险探索")
        return items

    @staticmethod
    def _feedback_questions() -> list[str]:
        return [
            "哪个方案最像这个项目？为什么？",
            "哪个方案最不像？偏差在角色、色彩、构图、材质、字体还是信息层级？",
            "哪些规则以后默认保留？哪些只是本次特例？",
            "是否允许把本次结论同步到同品类共享风格底座？",
        ]

    @staticmethod
    def _warnings(creative_pack: CreativePack) -> list[str]:
        warnings: list[str] = []
        if creative_pack.uncertainties:
            warnings.append("存在未闭合问题，出图批次应作为探索而非最终交付。")
        if any(rule.level in {KnowledgeLevel.K3, "K3"} for rule in creative_pack.style_card.rules):
            warnings.append("存在 K3 风格假设，评审时需要明确是否升级、保留或驳回。")
        if not creative_pack.brief.sizes:
            warnings.append("需求未明确尺寸，工具 payload 中的比例仅作临时建议。")
        return warnings

    @staticmethod
    def _pick_image_scale(sizes: list[str]) -> str:
        joined = " ".join(sizes).lower().replace(" ", "")
        if "9:16" in joined or "1080x1920" in joined or "720x1280" in joined:
            return "9:16"
        if "16:9" in joined or "1920x1080" in joined:
            return "16:9"
        if "3:4" in joined:
            return "3:4"
        if "4:3" in joined:
            return "4:3"
        if "2:3" in joined:
            return "2:3"
        if "3:2" in joined:
            return "3:2"
        return "1:1"
