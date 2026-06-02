from __future__ import annotations

import shutil
import unittest
import uuid
from pathlib import Path

from agent.core.automation_planner import AutomationPlanner
from agent.core.candidate_comparison import CandidateComparisonMatrixBuilder
from agent.core.candidate_style_drift import CandidateStyleDriftAuditor
from agent.core.creative_pack import CreativePackBuilder
from agent.core.image_production import ImageProductionPlanner
from agent.core.project_profiles import ProjectProfileManager
from agent.core.requirement_interpreter import RequirementInterpreter
from agent.core.risk_detector import RiskDetector
from agent.core.session import SessionManager
from agent.core.style_alignment import StyleAlignmentAuditor
from agent.core.style_learner import StyleLearner
from agent.core.style_transfer import StyleTransferAuditor
from agent.core.workflow_plan import DesignWorkflowPlanner
from agent.memory.store import MemoryStore
from agent.models import KnowledgeLevel, RequirementDoc, StyleCard, StyleRule, WorkItemContext
from agent.settings import AppPaths


class CoreLogicTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path.cwd() / "workspace" / "test-sandboxes" / f"core-{uuid.uuid4().hex}"
        self.paths = AppPaths.from_root(self.root)
        for path in (
            self.paths.memory / "projects",
            self.paths.memory / "audits",
            self.paths.memory / "style_bases",
            self.paths.memory / "reviews",
            self.paths.memory / "sessions",
            self.paths.memory / "session-transition",
            self.paths.workspace,
        ):
            path.mkdir(parents=True, exist_ok=True)
        self.store = MemoryStore(self.paths)

    def tearDown(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)

    def test_requirement_to_creative_pack(self) -> None:
        context = WorkItemContext(
            project_key="DEMO",
            work_item_id="1001",
            title="活动海报主视觉",
            raw_item={
                "name": "活动海报主视觉",
                "description": "目标是提高点击转化，二次元角色突出，尺寸 1080x1920，输出 PSD、PNG。",
                "platform": "Facebook",
                "audience": "二次元 RPG 用户",
            },
            comments=[{"content": "需要按钮和标题留白"}],
            doc_links=["https://example.feishu.cn/docx/ABC123"],
            docs=[RequirementDoc(source="lark-doc", token_or_url="https://example.feishu.cn/docx/ABC123", title="需求", content="活动海报主视觉，1080x1920，角色突出。")],
        )

        interpreter = RequirementInterpreter()
        brief = interpreter.build(context)
        brief.risk_points = RiskDetector().detect(brief, context)
        profile = ProjectProfileManager(self.store).ensure_profile("DEMO", brief.same_category, title="活动海报主视觉")
        profile.visual_keywords = ["霓虹能量", "二次元角色"]
        profile.must_have_rules = ["标题必须保留强发光描边"]
        profile.forbidden_rules = ["禁止使用灰脏背景"]
        self.store.save_project_profile(profile)
        style_card = StyleLearner(self.store).synthesize("DEMO", brief.same_category, brief.raw_signals, brief.missing_information)
        style_card = ProjectProfileManager(self.store).apply_profile_to_style_card(style_card, profile)
        pack = CreativePackBuilder().build(brief, style_card, profile)

        self.assertEqual(brief.same_category, "anime-rpg")
        self.assertIn("1080x1920", brief.sizes)
        self.assertIn("PSD", brief.deliverables)
        self.assertIn("PNG", brief.deliverables)
        self.assertTrue(pack.prompt_pack.positive)
        self.assertTrue(pack.delivery_manifest.requires_confirmation)
        self.assertIn("禁止使用灰脏背景", pack.prompt_pack.negative)
        self.assertTrue(any("标题必须保留强发光描边" in item for item in pack.references))
        positive_prompt = "\n".join(pack.prompt_pack.positive)
        self.assertIn("标题必须保留强发光描边", positive_prompt)
        self.assertNotIn("角色脸部和情绪表达要明确，避免过于写实的质感", positive_prompt)
        self.assertTrue(any("K3待验证风格" in item for item in pack.uncertainties))
        self.assertTrue(any("K3待验证探索" in item for item in pack.prompt_pack.reference_groups))
        image_batch = ImageProductionPlanner().build(pack, profile, str(self.paths.workspace / "demo"))
        self.assertNotIn("角色脸部和情绪表达要明确，避免过于写实的质感", image_batch.variants[0].positive_prompt)

        alignment = StyleAlignmentAuditor().build(pack)
        self.assertNotEqual(alignment.status, "blocked")
        self.assertFalse(alignment.blockers)
        pack.prompt_pack.positive.append("角色脸部和情绪表达要明确，避免过于写实的质感")
        leaked_alignment = StyleAlignmentAuditor().build(pack)
        self.assertEqual(leaked_alignment.status, "blocked")
        self.assertTrue(any("K3" in item for item in leaked_alignment.blockers))

        snapshot = SessionManager().build_snapshot(pack, self.paths.workspace / "demo")
        self.assertEqual(snapshot.active_work_item_id, "1001")
        self.assertTrue(snapshot.unresolved_questions)

    def test_requirement_interpreter_uses_comments_as_clarification_source(self) -> None:
        context = WorkItemContext(
            project_key="COMMENT",
            work_item_id="1002",
            title="评论补充需求",
            raw_item={"name": "评论补充需求", "description": "目标是提升预约转化。"},
            comments=[
                {
                    "content": "补充：受众：二次元RPG核心玩家；平台：TikTok；截止 2026-06-05；输出 PSD、PNG、切图；尺寸 1080x1920",
                }
            ],
            doc_links=[],
            docs=[],
        )

        brief = RequirementInterpreter().build(context)

        self.assertEqual(brief.target_audience, "二次元RPG核心玩家")
        self.assertEqual(brief.platform, "TikTok")
        self.assertEqual(brief.deadline, "2026-06-05")
        self.assertIn("PSD", brief.deliverables)
        self.assertIn("PNG", brief.deliverables)
        self.assertIn("切图", brief.deliverables)
        self.assertIn("1080x1920", brief.sizes)
        self.assertNotIn("缺少目标受众定义", brief.missing_information)
        self.assertNotIn("缺少投放平台或使用场景", brief.missing_information)
        self.assertNotIn("缺少明确截止时间", brief.missing_information)

    def test_requirement_interpreter_prioritizes_flat_design_description(self) -> None:
        context = WorkItemContext(
            project_key="artdesign",
            work_item_id="7002359257",
            title="翻牌关卡",
            raw_item={
                "work_item_attribute": {
                    "create_time": "2026-05-28T18:11:26+08:00",
                    "update_time": "2026-06-01T12:19:36+08:00",
                },
                "work_item_fields": [
                    {
                        "key": "field_352a5d",
                        "name": "视频需求描述",
                        "value": "视频版需要 30s，16:9，结尾 logo 和 Play Now。",
                    },
                    {
                        "key": "field_39e0db",
                        "name": "平面需求描述",
                        "value": "参考竞品重新排版 lv3 和 lv4 关卡，每个关卡各出一个三本书版本和一个四本书版本，一共 4 版。保留图中可见的模糊文字块位置。![](https://example.com/ref.png) \\\\[192.168.250.50](http://192.168.250.50)\\meishu-share\\c++游戏\\卡片分类\\切图",
                    },
                    {
                        "key": "field_58a39e",
                        "name": "玩法描述",
                        "value": "游戏以平面卡片的形式展示各种分类，需要把同一分类拖到目标收集区。",
                    },
                    {"key": "field_74ac24", "name": "项目名称", "value": {"id": 6854626926, "name": "卡片分类U"}},
                    {"key": "field_8ea9cf", "name": "玩法", "value": "益智"},
                    {
                        "key": "field_93c7d8",
                        "name": "平面需求截止时间",
                        "value": {"iso_time": "2026-06-01T00:00:00+08:00"},
                    },
                ],
            },
            comments=[],
            doc_links=[],
            docs=[],
        )

        brief = RequirementInterpreter().build(context)

        self.assertIn("参考竞品重新排版", brief.objective)
        self.assertNotIn("视频版需要", brief.objective)
        self.assertEqual(brief.game_name, "卡片分类U")
        self.assertEqual(brief.target_audience, "休闲益智/分类解谜用户（基于玩法描述推断）")
        self.assertIn("分类整理玩法", brief.gameplay_summary)
        self.assertIn("三本书和四本书", brief.gameplay_summary)
        self.assertIn("https://example.com/ref.png", brief.reference_assets)
        self.assertIn("\\\\192.168.250.50\\meishu-share\\c++游戏\\卡片分类\\切图", brief.reference_assets)
        self.assertNotIn("http://192.168.250.50", brief.reference_assets)
        self.assertEqual(brief.deadline, "2026-06-01")
        self.assertNotIn("11:26", brief.sizes)
        self.assertNotIn("19:36", brief.sizes)
        self.assertEqual(brief.sizes, ["9:16"])
        self.assertIn("投放素材", brief.raw_signals)
        self.assertIn("投放素材美术", brief.style_direction)
        self.assertTrue(any("三本书" in item for item in brief.task_breakdown))

    def test_requirement_interpreter_prefers_flat_deadline_and_reads_size_field(self) -> None:
        context = WorkItemContext(
            project_key="artdesign",
            work_item_id="7002016443",
            title="录屏加剧情片头",
            raw_item={
                "work_item_fields": [
                    {
                        "key": "field_1870b0",
                        "name": "视频期望完成时间",
                        "value": {"iso_time": "2026-06-04T00:00:00+08:00"},
                    },
                    {
                        "key": "field_39e0db",
                        "name": "平面需求描述",
                        "value": "给以下片头制作分镜图。片头1：拆弹小猪。片头2：悬崖小猪。",
                    },
                    {"key": "field_74ac24", "name": "项目名称", "value": {"id": 6747537719, "name": "挪出小猪U"}},
                    {
                        "key": "field_93c7d8",
                        "name": "平面期望完成时间",
                        "value": {"iso_time": "2026-06-01T00:00:00+08:00"},
                    },
                    {
                        "key": "field_dbf716",
                        "name": "尺寸",
                        "value": [
                            {"label": "9：16", "value": "82ar4r62v"},
                            {"label": "16：9", "value": "g17h22sbk"},
                            {"label": "2：3", "value": "k61uh3tpc"},
                            {"label": "1：1", "value": "0m2losh2d"},
                        ],
                    },
                ],
            },
            comments=[],
            doc_links=[],
            docs=[],
        )

        brief = RequirementInterpreter().build(context)

        self.assertEqual(brief.game_name, "挪出小猪U")
        self.assertEqual(brief.deadline, "2026-06-01")
        self.assertEqual(brief.sizes, ["9:16", "16:9", "2:3", "1:1"])

    def test_requirement_interpreter_extracts_game_name_from_local_markdown(self) -> None:
        context = WorkItemContext(
            project_key="artdesign",
            work_item_id="7002016443",
            title="录屏加剧情片头",
            raw_item={
                "title": "录屏加剧情片头",
                "description": "项目名称：挪出小猪U\n平面需求描述：剧情向片头制作分镜图，横竖适配，输出 PNG、JPG。",
            },
            comments=[],
            doc_links=[],
            docs=[],
        )

        brief = RequirementInterpreter().build(context)

        self.assertEqual(brief.game_name, "挪出小猪U")
        self.assertIn("PNG", brief.deliverables)
        self.assertEqual(brief.target_audience, "待确认")

    def test_project_profile_update_feeds_creative_pack(self) -> None:
        profile_file = self.root / "profile.json"
        profile_file.write_text(
            """{
  "display_name": "霓虹二游项目",
  "visual_keywords": ["霓虹能量", "强角色轮廓"],
  "must_have_rules": ["标题必须保留强发光描边"],
  "forbidden_rules": ["禁止灰脏背景"],
  "default_sizes": ["1080x1920"],
  "slice_requirements": ["CTA 按钮必须独立切图"]
}""",
            encoding="utf-8",
        )
        manager = ProjectProfileManager(self.store)
        profile, report = manager.update_profile_from_file(
            project_key="PROFILE",
            same_category="anime-rpg",
            profile_file=str(profile_file),
        )
        self.assertIn("visual_keywords", report.changed_fields)
        self.assertIn("霓虹能量", profile.visual_keywords)

        context = WorkItemContext(
            project_key="PROFILE",
            work_item_id="2002",
            title="档案校准海报",
            raw_item={"description": "目标是提升点击转化，输出 PSD。"},
            comments=[],
            doc_links=[],
            docs=[],
        )
        brief = RequirementInterpreter().build(context)
        style_card = StyleLearner(self.store).synthesize("PROFILE", "anime-rpg", brief.raw_signals, brief.missing_information)
        style_card = manager.apply_profile_to_style_card(style_card, profile)
        pack = CreativePackBuilder().build(brief, style_card, profile)
        positive = "\n".join(pack.prompt_pack.positive)
        negative = "\n".join(pack.prompt_pack.negative)
        self.assertIn("标题必须保留强发光描边", positive)
        self.assertIn("霓虹能量", positive)
        self.assertIn("禁止灰脏背景", negative)
        self.assertIn("1080x1920", [item.size for item in pack.delivery_manifest.export_items])

    def test_style_transfer_blocks_conflicting_shared_base(self) -> None:
        shared = StyleCard(
            project_key="anime-rpg-shared",
            same_category="anime-rpg",
            visual_keywords=["高饱和霓虹", "灰脏背景"],
            composition_preferences=[],
            color_rules=[],
            material_rules=[],
            typography_rules=[],
            ui_mood=[],
            do_not=[],
            rules=[
                StyleRule(
                    statement="角色轮廓必须高对比",
                    level=KnowledgeLevel.K2,
                    rationale="同品类多项目验证",
                    scope="shared",
                ),
                StyleRule(
                    statement="灰脏背景强化废土感",
                    level=KnowledgeLevel.K2,
                    rationale="旧项目可用",
                    scope="shared",
                ),
            ],
        )
        profile = ProjectProfileManager(self.store).ensure_profile("TRANSFER", "anime-rpg", title="迁移测试")
        profile.forbidden_rules = ["灰脏背景"]
        effective = StyleCard(
            project_key="TRANSFER",
            same_category="anime-rpg",
            visual_keywords=["高饱和霓虹"],
            composition_preferences=[],
            color_rules=[],
            material_rules=[],
            typography_rules=[],
            ui_mood=[],
            do_not=["灰脏背景"],
            rules=[
                StyleRule(
                    statement="角色轮廓必须高对比",
                    level=KnowledgeLevel.K2,
                    rationale="来自同品类底座",
                    scope="shared",
                ),
                StyleRule(
                    statement="透视强度待验证",
                    level=KnowledgeLevel.K3,
                    rationale="本次需求推测",
                    scope="project",
                ),
            ],
        )

        report = StyleTransferAuditor().build(
            project_key="TRANSFER",
            work_item_id="3003",
            same_category="anime-rpg",
            shared_base=shared,
            effective_style=effective,
            profile=profile,
            source_artifacts={},
        )
        self.assertEqual(report.status, "blocked")
        self.assertIn("灰脏背景强化废土感", report.blocked_shared_rules)
        self.assertTrue(any("角色轮廓必须高对比" in item for item in report.transferable_rules))
        self.assertIn("透视强度待验证", report.k3_hypotheses)
        markdown = StyleTransferAuditor().render_markdown(report)
        self.assertIn("风格迁移与项目覆盖报告", markdown)
        self.assertIn("被项目覆盖或阻断的同品类规则", markdown)

    def test_candidate_style_drift_blocks_forbidden_notes(self) -> None:
        context = WorkItemContext(
            project_key="DRIFT",
            work_item_id="3004",
            title="偏移预警测试",
            raw_item={"description": "目标是提升点击转化，二次元角色突出，尺寸 1080x1920，输出 PNG。"},
            comments=[],
            doc_links=[],
            docs=[],
        )
        brief = RequirementInterpreter().build(context)
        profile = ProjectProfileManager(self.store).ensure_profile("DRIFT", "anime-rpg", title="偏移预警测试")
        profile.forbidden_rules = ["灰脏背景"]
        self.store.save_project_profile(profile)
        style_card = StyleLearner(self.store).synthesize("DRIFT", "anime-rpg", brief.raw_signals, [])
        style_card = ProjectProfileManager(self.store).apply_profile_to_style_card(style_card, profile)
        pack = CreativePackBuilder().build(brief, style_card, profile)
        report = CandidateStyleDriftAuditor().build(
            project_key="DRIFT",
            work_item_id="3004",
            generation_results={
                "assets": [
                    {
                        "asset_id": "bad-v01",
                        "variant_id": "V01",
                        "uri": "https://example.com/bad.png",
                        "notes": ["candidate", "背景灰脏背景明显"],
                    }
                ],
                "missing_assets": [],
                "delivery_candidates": ["https://example.com/bad.png"],
            },
            creative_pack=pack,
            style_transfer={"status": "transfer_ready", "blockers": [], "warnings": []},
            style_alignment={"status": "aligned", "blockers": [], "warnings": []},
            candidate_review=None,
            source_artifacts={},
        )
        self.assertEqual(report.status, "blocked")
        self.assertTrue(any("灰脏背景" in item for item in report.blockers))
        markdown = CandidateStyleDriftAuditor().render_markdown(report)
        self.assertIn("候选图风格偏移预警", markdown)
        self.assertIn("禁忌项命中", markdown)

    def test_candidate_comparison_matrix_recommends_and_rejects_variants(self) -> None:
        matrix = CandidateComparisonMatrixBuilder().build(
            project_key="COMPARE",
            work_item_id="9001",
            image_batch={
                "variants": [
                    {"variant_id": "V01", "title": "稳妥项目风格版", "intent": "贴合 K1/K2 项目风格"},
                    {"variant_id": "V02", "title": "转化强化版", "intent": "强化利益点和点击区域"},
                ]
            },
            generation_results={
                "assets": [
                    {"asset_id": "v01-a", "variant_id": "V01", "uri": "D:/renders/v01.png"},
                    {"asset_id": "v02-a", "variant_id": "V02", "uri": "D:/renders/v02.png"},
                ]
            },
            candidate_style_drift={
                "status": "blocked",
                "items": [
                    {"variant_id": "V01", "drift_level": "info", "recommended_action": "可进入人工精修"},
                    {"variant_id": "V02", "drift_level": "blocker", "recommended_action": "命中禁忌项，建议重出"},
                ],
                "blockers": ["V02 命中项目禁忌项"],
                "warnings": [],
            },
            candidate_review={
                "items": [
                    {
                        "variant_id": "V01",
                        "decision": "approved",
                        "scores": {"style_fit": 5, "conversion": 4, "psd_ready": 4},
                        "strengths": ["角色情绪准确"],
                    },
                    {
                        "variant_id": "V02",
                        "decision": "rejected",
                        "scores": {"style_fit": 2, "conversion": 4},
                        "issues": ["利益点抢主体"],
                    },
                ]
            },
            source_artifacts={},
        )

        self.assertEqual(matrix.status, "blocked")
        self.assertEqual(matrix.recommended_variant_ids, ["V01"])
        self.assertEqual(matrix.rejected_variant_ids, ["V02"])
        markdown = CandidateComparisonMatrixBuilder().render_markdown(matrix)
        self.assertIn("候选方案对比矩阵", markdown)
        self.assertIn("V01", markdown)
        self.assertIn("采纳：进入 PSD/切图准备", markdown)
        self.assertIn("驳回/重出：存在风格阻塞", markdown)

    def test_automation_plan_prefers_psd_and_staging(self) -> None:
        profile = ProjectProfileManager(self.store).ensure_profile("DEMO", "casual-card", title="测试项目")
        plan = AutomationPlanner().build_plan(
            project_key="DEMO",
            work_item_id="2001",
            profile=profile,
            asset_index=None,
            delivery_package=None,
        )
        self.assertTrue(plan.actions)
        self.assertTrue(plan.warnings)
        self.assertIsNone(plan.source_psd)
        jsx = AutomationPlanner().render_photoshop_jsx(plan)
        self.assertIn("allowExport: false", jsx)
        self.assertIn("photoshop_layer_report.md", jsx)
        self.assertIn("photoshop_slice_checklist.md", jsx)

    def test_workflow_plan_marks_blocked_reports_and_next_commands(self) -> None:
        planner = DesignWorkflowPlanner()
        artifact_index = {Path(name).stem: None for name in planner.IMPORTANT_FILES}
        artifact_index.update(
            {
                "design_brief": "workspace/design_brief.json",
                "creative_pack": "workspace/creative_pack.json",
                "style_alignment_report": "workspace/style_alignment_report.json",
            }
        )
        plan = planner.build(
            project_key="FLOW",
            work_item_id="1001",
            title="流程计划测试",
            output_dir=self.paths.workspace,
            artifact_index=artifact_index,
            payloads={
                "style_alignment_report": {
                    "status": "blocked",
                    "blockers": ["K3 假设进入了正向提示词"],
                }
            },
        )

        self.assertEqual(plan.status, "blocked")
        blocked = {step.step_id: step for step in plan.steps}
        self.assertEqual(blocked["style_alignment"].status, "blocked")
        self.assertTrue(any("K3" in item for item in plan.blockers))
        markdown = planner.render_markdown(plan)
        self.assertIn("设计工作流计划", markdown)
        self.assertIn("步骤看板", markdown)
        self.assertIn("不自动发布 Meegle", markdown)


if __name__ == "__main__":
    unittest.main()
