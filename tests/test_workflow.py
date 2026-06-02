from __future__ import annotations

import shutil
import unittest
import uuid
import json
from pathlib import Path

from agent.app import DesignCopilotApp
from agent.models import DesignBrief, SessionSnapshot, WorkItemContext


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path.cwd() / "workspace" / "test-sandboxes" / f"workflow-{uuid.uuid4().hex}"
        app = DesignCopilotApp(self.root)
        app.local_files.ensure_runtime_directories()
        self.app = app

    def tearDown(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)

    def test_memory_project_key_prefers_readable_game_name(self) -> None:
        brief = DesignBrief(
            project_key="artdesign",
            work_item_id="7005309647",
            title="货柜花篮掉落",
            objective="制作插花三消平面投放素材",
            target_audience="待确认",
            platform="待确认",
            sizes=["9:16"],
            deliverables=["PSD"],
            deadline="2026-06-03",
            summary="货柜花篮掉落",
            same_category="general-game-design",
            source_links=[],
            missing_information=[],
            risk_points=[],
            raw_signals=[],
            game_name="插花三消C",
            game_project_id="6178760014",
        )

        self.assertEqual(self.app._memory_project_key_from_brief(brief, "artdesign"), "插花三消C")

    def test_feedback_ingest_generates_review_report(self) -> None:
        result = self.app.ingest_feedback(
            project_key="DEMO",
            same_category="casual-card",
            feedback="必须统一按钮高光方向\n避免背景抢主体",
            decision="approved",
            work_item_id="1001",
            share_to_base=True,
        )
        self.assertTrue(Path(result["review_report"]).exists())
        style_card = self.app.store.load_style_card("DEMO")
        self.assertIsNotNone(style_card)
        statements = {rule.statement: rule.level for rule in style_card.rules}
        self.assertEqual(statements["必须统一按钮高光方向"], "K1")
        self.assertEqual(statements["避免背景抢主体"], "K2")

        digest_result = self.app.create_learning_digest(project_key="DEMO")
        digest_md = Path(digest_result["learning_digest_md"])
        self.assertTrue(digest_md.exists())
        content = digest_md.read_text(encoding="utf-8")
        self.assertIn("必须统一按钮高光方向", content)
        self.assertIn("避免背景抢主体", content)
        self.assertTrue(any("K1/K2" in item for item in digest_result["next_time_checklist"]))

    def test_style_memory_curation_reports_and_applies_safe_actions(self) -> None:
        self.app.ingest_feedback(
            project_key="CURATE",
            same_category="anime-rpg",
            feedback="强动势可以保留但透视强度待验证",
            decision="revise",
            work_item_id="2001",
        )
        self.app.ingest_feedback(
            project_key="CURATE",
            same_category="anime-rpg",
            feedback="强动势可以保留但透视强度待验证",
            decision="revise",
            work_item_id="2002",
        )
        self.app.ingest_feedback(
            project_key="CURATE",
            same_category="anime-rpg",
            feedback="避免灰脏背景",
            decision="approved",
            work_item_id="2003",
        )
        seeded = self.app.store.load_style_card("CURATE")
        self.assertIsNotNone(seeded)
        for rule in seeded.rules:
            if rule.statement == "强动势可以保留但透视强度待验证":
                rule.level = "K3"
                rule.evidence_count = 2
        self.app.store.save_style_card(seeded)

        report_only = self.app.curate_style_memory(project_key="CURATE")
        self.assertTrue(Path(report_only["style_memory_curation_report"]).exists())
        self.assertGreaterEqual(report_only["action_count"], 2)
        self.assertEqual(report_only["applied_count"], 0)
        before = self.app.store.load_style_card("CURATE")
        self.assertIsNotNone(before)
        before_levels = {rule.statement: rule.level for rule in before.rules}
        self.assertEqual(before_levels["强动势可以保留但透视强度待验证"], "K3")
        self.assertNotIn("避免灰脏背景", before.do_not)

        applied = self.app.curate_style_memory(project_key="CURATE", apply=True)
        self.assertGreaterEqual(applied["applied_count"], 1)
        after = self.app.store.load_style_card("CURATE")
        self.assertIsNotNone(after)
        after_levels = {rule.statement: rule.level for rule in after.rules}
        self.assertEqual(after_levels["强动势可以保留但透视强度待验证"], "K2")
        self.assertIn("避免灰脏背景", after.do_not)
        markdown = Path(applied["style_memory_curation_report_md"]).read_text(encoding="utf-8")
        self.assertIn("风格记忆治理", markdown)
        self.assertIn("sync_confirmed_avoid_to_do_not", markdown)

    def test_style_reference_ingest_updates_style_memory(self) -> None:
        refs_dir = self.root / "style-refs"
        refs_dir.mkdir()
        (refs_dir / "positive.png").write_bytes(b"fake-png")
        reference_file = self.root / "style_refs.json"
        reference_file.write_text(
            json.dumps(
                {
                    "references": [
                        {
                            "reference_id": "REF001",
                            "path": "style-refs/positive.png",
                            "role": "positive",
                            "level": "K2",
                            "keywords": ["高饱和霓虹", "角色轮廓强"],
                            "rules": ["角色轮廓必须高对比，背景不能抢主体"],
                            "notes": ["适合作为本项目买量主视觉参考"],
                        },
                        {
                            "reference_id": "REF002",
                            "url": "https://example.com/bad.png",
                            "role": "negative",
                            "keywords": ["灰脏背景"],
                            "rules": ["避免灰脏背景和低对比主体"],
                        },
                        {
                            "reference_id": "REF003",
                            "url": "https://example.com/explore.png",
                            "role": "reference",
                            "keywords": ["夸张透视"],
                            "notes": ["可作为 K3 探索"],
                        },
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = self.app.ingest_style_reference(
            project_key="DEMO",
            same_category="anime-rpg",
            reference_file=str(reference_file),
            share_to_base=True,
        )

        self.assertTrue(Path(result["style_reference_report"]).exists())
        self.assertTrue(Path(result["style_reference_report_md"]).exists())
        self.assertEqual(result["reference_count"], 3)
        self.assertEqual(result["accepted_rule_count"], 1)
        self.assertEqual(result["rejected_rule_count"], 1)
        self.assertEqual(result["pending_rule_count"], 1)
        self.assertEqual(result["warnings"], [])

        style_card = self.app.store.load_style_card("DEMO")
        self.assertIsNotNone(style_card)
        self.assertIn("高饱和霓虹", style_card.visual_keywords)
        self.assertIn("夸张透视", style_card.visual_keywords)
        self.assertIn("灰脏背景", style_card.do_not)
        statements = {rule.statement: rule.level for rule in style_card.rules}
        self.assertEqual(statements["角色轮廓必须高对比，背景不能抢主体"], "K2")
        self.assertEqual(statements["避免灰脏背景和低对比主体"], "K2")
        self.assertEqual(statements["REF003 风格参考：可作为 K3 探索"], "K3")

        shared_card = self.app.store.load_style_base("anime-rpg")
        self.assertIsNotNone(shared_card)
        self.assertIn("高饱和霓虹", shared_card.visual_keywords)
        self.assertNotIn("灰脏背景", shared_card.visual_keywords)
        self.assertTrue(all(rule.scope == "shared" for rule in shared_card.rules))

    def test_resume_session_without_snapshot(self) -> None:
        result = self.app.resume_session("UNKNOWN")
        self.assertEqual(result["message"], "No session snapshot found.")

    def test_session_snapshot_relocates_workspace_paths(self) -> None:
        run_dir = self.root / "workspace" / "runs" / "RELOCATE" / "1001-title"
        run_dir.mkdir(parents=True)
        (run_dir / "design_brief.md").write_text("brief", encoding="utf-8")
        old_run_dir = Path("C:/Users/Administrator/Documents/old-root/workspace/runs/RELOCATE/1001-title")
        self.app.store.save_session_snapshot(
            SessionSnapshot(
                project_key="RELOCATE",
                same_category="casual-card",
                active_work_item_id="1001",
                title="title",
                output_dir=str(old_run_dir),
                key_decisions=[],
                unresolved_questions=[],
                last_artifacts=[str(old_run_dir / "design_brief.md")],
            )
        )

        snapshot = self.app.store.load_session_snapshot("RELOCATE")

        self.assertIsNotNone(snapshot)
        self.assertEqual(Path(snapshot.output_dir), run_dir)
        self.assertEqual(Path(snapshot.last_artifacts[0]), run_dir / "design_brief.md")

    def test_create_requirement_change_report_from_local_update(self) -> None:
        old_requirement = self.root / "old_requirement.json"
        old_requirement.write_text(
            json.dumps(
                {
                    "title": "Launch KV",
                    "objective": "Boost installs",
                    "target_audience": "RPG players",
                    "platform": "TikTok",
                    "deliverables": "PSD, PNG",
                    "deadline": "2026-06-10",
                    "size": "1080x1920",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.app.build_local_creative_pack(
            project_key="CHANGE",
            work_item_id="7001",
            title="Launch KV",
            requirement_file=str(old_requirement),
            same_category="casual-card",
        )
        new_requirement = self.root / "new_requirement.json"
        new_requirement.write_text(
            json.dumps(
                {
                    "title": "Launch KV",
                    "objective": "Boost purchases",
                    "target_audience": "RPG players",
                    "platform": "TikTok",
                    "deliverables": "PSD, PNG",
                    "deadline": "2026-06-10",
                    "size": "1200x628",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = self.app.create_requirement_change_report(
            project_key="CHANGE",
            work_item_id="7001",
            requirement_file=str(new_requirement),
            same_category="casual-card",
            title="Launch KV",
        )

        self.assertEqual(result["status"], "requires_rebuild")
        self.assertTrue(Path(result["requirement_change_report"]).exists())
        self.assertTrue(Path(result["requirement_change_report_md"]).exists())
        payload = json.loads(Path(result["requirement_change_report"]).read_text(encoding="utf-8"))
        changed_fields = {item["field"] for item in payload["change_items"]}
        self.assertIn("objective", changed_fields)
        self.assertIn("sizes", changed_fields)
        self.assertIn("creative_pack", result["impacted_artifacts"])
        snapshot = self.app.store.load_session_snapshot("CHANGE")
        self.assertIsNotNone(snapshot)
        self.assertIn(result["requirement_change_report"], snapshot.last_artifacts)

    def test_scan_assets_and_prepare_delivery_package(self) -> None:
        asset_root = self.root / "sample-assets"
        asset_root.mkdir()
        (asset_root / "banner_final.psd").write_bytes(b"psd-source")
        (asset_root / "button_play.png").write_bytes(b"png-render")
        (asset_root / "notes.txt").write_text("ignore", encoding="utf-8")

        scan_result = self.app.scan_assets(project_key="DEMO", asset_root=str(asset_root))
        self.assertEqual(scan_result["asset_count"], 2)
        self.assertTrue(Path(scan_result["asset_index"]).exists())

        package_result = self.app.prepare_delivery_package(
            project_key="DEMO",
            work_item_id="1002",
            source_root=str(asset_root),
            include_extensions=["psd", "png"],
        )
        self.assertEqual(package_result["file_count"], 2)
        self.assertTrue(Path(package_result["staged_root"]).exists())
        for artifact in package_result["artifacts"]:
            self.assertTrue(Path(artifact).exists())

    def test_init_profile_and_plan_automation(self) -> None:
        profile_result = self.app.init_project_profile(
            project_key="DEMO",
            same_category="casual-card",
            display_name="测试项目",
        )
        self.assertTrue(Path(profile_result["project_profile"]).exists())
        profile_file = self.root / "profile.json"
        profile_file.write_text(
            json.dumps(
                {
                    "display_name": "霓虹二游项目",
                    "gameplay_tags": ["抽卡", "回合制"],
                    "visual_keywords": ["霓虹能量", "强角色轮廓"],
                    "must_have_rules": ["标题必须保留强发光描边"],
                    "forbidden_rules": ["禁止灰脏背景"],
                    "default_sizes": ["1080x1920"],
                    "export_formats": ["PSD", "PNG", "WebP"],
                    "slice_requirements": ["CTA 按钮必须独立切图"],
                    "automation_preferences": {"photoshop_mode": "dry-run"},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        update_result = self.app.update_project_profile(
            project_key="DEMO",
            same_category="anime-rpg",
            profile_file=str(profile_file),
        )
        self.assertTrue(Path(update_result["project_profile_update_report"]).exists())
        self.assertIn("visual_keywords", update_result["changed_fields"])
        profile = self.app.store.load_project_profile("DEMO")
        self.assertIsNotNone(profile)
        self.assertIn("霓虹能量", profile.visual_keywords)
        self.assertIn("1080x1920", profile.default_sizes)
        self.assertIn("CTA 按钮必须独立切图", profile.slice_requirements)
        asset_root = self.root / "automation-assets"
        asset_root.mkdir()
        (asset_root / "hero_master.psd").write_bytes(b"psd-source")
        self.app.scan_assets(project_key="DEMO", asset_root=str(asset_root))
        plan_result = self.app.plan_automation(project_key="DEMO", work_item_id="3001")
        self.assertTrue(Path(plan_result["automation_plan"]).exists())
        self.assertTrue(Path(plan_result["automation_stub_ps1"]).exists())
        self.assertTrue(Path(plan_result["photoshop_jsx"]).exists())
        self.assertTrue(Path(plan_result["photoshop_script_readme"]).exists())
        self.assertTrue(Path(plan_result["photoshop_script_manifest"]).exists())
        jsx = Path(plan_result["photoshop_jsx"]).read_text(encoding="utf-8")
        self.assertIn("allowExport: false", jsx)

    def test_metacognition_audit_and_transition_summary(self) -> None:
        self.app.init_project_profile(
            project_key="DEMO",
            same_category="casual-card",
            display_name="测试项目",
        )
        self.app.ingest_feedback(
            project_key="DEMO",
            same_category="casual-card",
            feedback="必须统一按钮高光方向",
            decision="approved",
            work_item_id="1001",
            share_to_base=False,
        )
        asset_root = self.root / "audit-assets"
        asset_root.mkdir()
        (asset_root / "hero_master.psd").write_bytes(b"psd-source")
        self.app.scan_assets(project_key="DEMO", asset_root=str(asset_root))
        self.app.prepare_delivery_package(
            project_key="DEMO",
            work_item_id="1003",
            source_root=str(asset_root),
            include_extensions=["psd"],
        )
        self.app.store.save_session_snapshot(
            SessionSnapshot(
                project_key="DEMO",
                same_category="casual-card",
                active_work_item_id="1003",
                title="审计测试任务",
                output_dir=str(self.root / "workspace" / "runs" / "demo"),
                key_decisions=["统一按钮高光方向"],
                unresolved_questions=["需要确认默认尺寸"],
                last_artifacts=["design_brief.md", "creative_pack.md"],
            )
        )
        audit_result = self.app.metacognition_audit(project_key="DEMO")
        transition_result = self.app.create_transition_summary(project_key="DEMO")
        self.assertTrue(Path(audit_result["metacognition_audit"]).exists())
        self.assertTrue(Path(transition_result["transition_summary"]).exists())
        self.assertTrue(transition_result["restart_instructions"])

    def test_build_local_creative_pack_and_run_cycle(self) -> None:
        requirement_file = self.root / "requirement.md"
        requirement_file.write_text(
            "目标是提升点击转化，二次元角色突出，尺寸 1080x1920，输出 PSD、PNG，平台 Facebook。",
            encoding="utf-8",
        )
        doc_file = self.root / "notes.md"
        doc_file.write_text("需要按钮和标题留白，禁止灰脏背景。", encoding="utf-8")
        asset_root = self.root / "cycle-assets"
        asset_root.mkdir()
        (asset_root / "hero_master.psd").write_bytes(b"psd-source")
        (asset_root / "hero_final.png").write_bytes(b"png-render")

        pack_result = self.app.build_local_creative_pack(
            project_key="LOCAL",
            work_item_id="5001",
            title="本地活动海报",
            requirement_file=str(requirement_file),
            same_category="anime-rpg",
            doc_files=[str(doc_file)],
        )
        self.assertTrue(Path(pack_result["output_dir"]).exists())
        output_dir = Path(pack_result["output_dir"])
        task_sheet = Path(pack_result["task_sheet"])
        prompt_sheet = Path(pack_result["prompt_sheet"])
        self.assertTrue(task_sheet.exists())
        self.assertTrue(prompt_sheet.exists())
        task_content = task_sheet.read_text(encoding="utf-8")
        self.assertIn("制作任务单", task_content)
        self.assertIn("先生成完整 9:16 效果图", task_content)
        self.assertIn("同游戏历史优秀图", task_content)
        prompt_content = prompt_sheet.read_text(encoding="utf-8")
        self.assertIn("中文提示词", prompt_content)
        self.assertIn("第一轮先做整体效果图", prompt_content)
        self.assertTrue((output_dir / "creative_pack.json").exists())
        self.assertTrue((output_dir / "style_transfer_report.json").exists())
        self.assertFalse((output_dir / "style_transfer_report.md").exists())
        self.assertTrue((output_dir / "style_alignment_report.json").exists())
        self.assertFalse((output_dir / "style_alignment_report.md").exists())
        self.assertTrue((output_dir / "design_decision_record.json").exists())
        self.assertFalse((output_dir / "design_decision_record.md").exists())
        regenerated_alignment = self.app.create_style_alignment_report(
            project_key="LOCAL",
            work_item_id="5001",
        )
        self.assertTrue(Path(regenerated_alignment["style_alignment_report_md"]).exists())
        self.assertIn(regenerated_alignment["status"], {"aligned", "needs_designer_review", "blocked"})
        regenerated_transfer = self.app.create_style_transfer_report(
            project_key="LOCAL",
            work_item_id="5001",
        )
        self.assertTrue(Path(regenerated_transfer["style_transfer_report_md"]).exists())
        self.assertIn(regenerated_transfer["status"], {"transfer_ready", "needs_designer_review", "blocked"})
        transfer_md = Path(regenerated_transfer["style_transfer_report_md"]).read_text(encoding="utf-8")
        self.assertIn("风格迁移与项目覆盖报告", transfer_md)
        self.assertIn("K3 待验证假设", transfer_md)
        regenerated_decisions = self.app.create_design_decision_record(
            project_key="LOCAL",
            work_item_id="5001",
        )
        self.assertTrue(Path(regenerated_decisions["design_decision_record_md"]).exists())
        self.assertGreaterEqual(regenerated_decisions["decision_count"], 3)
        decision_md = Path(regenerated_decisions["design_decision_record_md"]).read_text(encoding="utf-8")
        self.assertIn("设计决策记录", decision_md)
        self.assertIn("需求范围", decision_md)
        self.assertIn("K3", decision_md)
        self.assertTrue((output_dir / "requirement_clarification_report.json").exists())
        self.assertFalse((output_dir / "requirement_clarification_report.md").exists())
        regenerated_clarification = self.app.create_requirement_clarification_report(
            project_key="LOCAL",
            work_item_id="5001",
        )
        self.assertTrue(Path(regenerated_clarification["requirement_clarification_comment"]).exists())
        self.assertGreaterEqual(regenerated_clarification["question_count"], 1)
        self.assertEqual(regenerated_clarification["blocker_count"], 0)
        self.assertTrue(regenerated_clarification["safe_to_continue"])
        regenerated_comment = Path(regenerated_clarification["requirement_clarification_comment"]).read_text(encoding="utf-8")
        self.assertIn("不会自动发布到飞书", regenerated_comment)
        regenerated_from_dir = self.app.create_requirement_clarification_report(
            project_key="LOCAL",
            output_dir=str(output_dir),
        )
        self.assertEqual(regenerated_from_dir["question_count"], regenerated_clarification["question_count"])
        self.assertTrue((output_dir / "image_generation_batch.json").exists())
        self.assertFalse((output_dir / "candidate_evaluation.md").exists())
        image_batch = self.app.create_image_production_batch(project_key="LOCAL", work_item_id="5001")
        self.assertTrue(Path(image_batch["image_generation_batch"]).exists())
        self.assertEqual(len(image_batch["artifacts"]), 3)
        jobs_result = self.app.create_image_generation_jobs(
            project_key="LOCAL",
            work_item_id="5001",
            variants=["V01", "V04"],
        )
        self.assertEqual(jobs_result["job_count"], 2)
        self.assertTrue(Path(jobs_result["image_generation_jobs"]).exists())
        self.assertTrue(Path(jobs_result["pixpark_requests_jsonl"]).exists())
        self.assertTrue(Path(jobs_result["generation_approval_ticket"]).exists())
        jsonl_content = Path(jobs_result["pixpark_requests_jsonl"]).read_text(encoding="utf-8")
        self.assertIn("5001-V01-pixpark", jsonl_content)
        self.assertIn("5001-V04-pixpark", jsonl_content)
        execution_package = self.app.prepare_image_execution_package(project_key="LOCAL", work_item_id="5001")
        self.assertEqual(execution_package["item_count"], 2)
        self.assertTrue(Path(execution_package["image_execution_package"]).exists())
        self.assertTrue(Path(execution_package["image_execution_package_md"]).exists())
        self.assertTrue(Path(execution_package["pixpark_execution_runbook"]).exists())
        self.assertTrue(Path(execution_package["generation_results_template"]).exists())
        payload_files = [Path(path) for path in execution_package["artifacts"] if path.endswith(".json") and "payloads" in path]
        self.assertEqual(len(payload_files), 2)
        self.assertTrue(all(path.exists() for path in payload_files))
        execution_md = Path(execution_package["image_execution_package_md"]).read_text(encoding="utf-8")
        self.assertIn("图像生成执行交接包", execution_md)
        template_payload = json.loads(Path(execution_package["generation_results_template"]).read_text(encoding="utf-8"))
        self.assertEqual(len(template_payload["assets"]), 2)
        generated_png = self.root / "v01_result.png"
        generated_png.write_bytes(b"fake-png")
        results_file = self.root / "generation_results.json"
        results_file.write_text(
            json.dumps(
                {
                    "assets": [
                        {
                            "variant_id": "V01",
                            "uri": str(generated_png),
                            "notes": ["candidate", "角色表情最好"],
                        },
                        {
                            "variant_id": "V04",
                            "url": "https://example.com/v04_result.png",
                            "notes": ["切图友好"],
                        },
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        result_index = self.app.register_image_results(
            project_key="LOCAL",
            work_item_id="5001",
            results_file=str(results_file),
        )
        self.assertEqual(result_index["asset_count"], 2)
        self.assertEqual(result_index["delivery_candidates_count"], 1)
        self.assertTrue(Path(result_index["generated_gallery"]).exists())
        self.assertTrue(Path(result_index["delivery_candidates"]).exists())
        self.assertTrue(Path(result_index["candidate_style_drift_report"]).exists())
        self.assertTrue(Path(result_index["candidate_style_drift_report_md"]).exists())
        self.assertTrue(Path(result_index["candidate_comparison_matrix"]).exists())
        self.assertTrue(Path(result_index["candidate_comparison_matrix_md"]).exists())
        drift_md = Path(result_index["candidate_style_drift_report_md"]).read_text(encoding="utf-8")
        self.assertIn("候选图风格偏移预警", drift_md)
        self.assertIn("候选图评审", drift_md)
        comparison_md = Path(result_index["candidate_comparison_matrix_md"]).read_text(encoding="utf-8")
        self.assertIn("候选方案对比矩阵", comparison_md)
        self.assertIn("V01", comparison_md)
        regenerated_drift = self.app.create_candidate_style_drift_report(project_key="LOCAL", work_item_id="5001")
        self.assertTrue(Path(regenerated_drift["candidate_style_drift_report_md"]).exists())
        regenerated_comparison = self.app.create_candidate_comparison_matrix(project_key="LOCAL", work_item_id="5001")
        self.assertTrue(Path(regenerated_comparison["candidate_comparison_matrix_md"]).exists())
        gallery = Path(result_index["generated_gallery"]).read_text(encoding="utf-8")
        self.assertIn("V01", gallery)
        self.assertIn("https://example.com/v04_result.png", gallery)
        handoff = self.app.create_psd_handoff_plan(project_key="LOCAL", work_item_id="5001")
        self.assertEqual(handoff["asset_count"], 1)
        self.assertTrue(Path(handoff["psd_handoff_plan"]).exists())
        self.assertTrue(Path(handoff["layer_map"]).exists())
        self.assertTrue(Path(handoff["slice_checklist"]).exists())
        handoff_md = Path(handoff["psd_handoff_plan_md"]).read_text(encoding="utf-8")
        self.assertIn("PSD 重建步骤", handoff_md)
        self.assertIn("v01_result", handoff_md)
        handoff_package = self.app.prepare_psd_handoff_package(project_key="LOCAL", work_item_id="5001")
        self.assertEqual(handoff_package["item_count"], 1)
        self.assertTrue(Path(handoff_package["staged_root"]).exists())
        self.assertTrue(Path(handoff_package["psd_handoff_package"]).exists())
        self.assertTrue(Path(handoff_package["psd_handoff_approval_ticket"]).exists())
        staged_files = list(Path(handoff_package["staged_root"]).rglob("*.png"))
        self.assertEqual(len(staged_files), 1)
        psd_spec = self.app.create_psd_slice_spec_report(project_key="LOCAL", work_item_id="5001")
        self.assertTrue(Path(psd_spec["psd_slice_spec_report"]).exists())
        self.assertTrue(Path(psd_spec["psd_slice_spec_report_md"]).exists())
        self.assertIn(psd_spec["status"], {"ready_for_psd_work", "needs_designer_review"})
        psd_spec_md = Path(psd_spec["psd_slice_spec_report_md"]).read_text(encoding="utf-8")
        self.assertIn("PSD/切图规格核对", psd_spec_md)
        self.assertIn("命名样例", psd_spec_md)
        self.assertIn("安全门控", psd_spec_md)
        writeback = self.app.create_meegle_writeback_draft(project_key="LOCAL", work_item_id="5001")
        self.assertEqual(writeback["status"], "psd_slice_spec_checked")
        self.assertTrue(Path(writeback["meegle_writeback_draft"]).exists())
        self.assertTrue(Path(writeback["meegle_writeback_comment"]).exists())
        self.assertTrue(Path(writeback["meegle_writeback_approval_ticket"]).exists())
        comment = Path(writeback["meegle_writeback_comment"]).read_text(encoding="utf-8")
        self.assertIn("设计副驾进度回写", comment)
        self.assertIn("设计决策记录", comment)
        self.assertIn("候选方案对比矩阵", comment)
        self.assertIn("PSD 交接 staging 包", comment)
        self.assertIn("PSD/切图规格核对报告", comment)
        dry_run_publish = self.app.publish_meegle_writeback(project_key="LOCAL", work_item_id="5001")
        self.assertFalse(dry_run_publish["executed"])
        self.assertTrue(Path(dry_run_publish["meegle_publish_receipt"]).exists())
        with self.assertRaises(PermissionError):
            self.app.publish_meegle_writeback(project_key="LOCAL", work_item_id="5001", execute=True)
        published: dict[str, str] = {}
        self.app.meegle.add_comment = lambda project_key, work_item_id, content: published.setdefault(
            "content",
            content,
        ) or {"comment_id": "mock-comment"}
        execute_publish = self.app.publish_meegle_writeback(
            project_key="LOCAL",
            work_item_id="5001",
            execute=True,
            confirm_token="PUBLISH_MEEGLE_WRITEBACK",
        )
        self.assertTrue(execute_publish["executed"])
        self.assertIn("设计副驾进度回写", published["content"])
        review_file = self.root / "candidate_review.json"
        review_file.write_text(
            json.dumps(
                {
                    "variants": [
                        {
                            "variant_id": "V01",
                            "decision": "approved",
                            "scores": {"style_fit": 5, "conversion": 4, "psd_ready": 4},
                            "strengths": ["角色情绪准确", "按钮留白合理"],
                            "learning": "保留 V01 的角色情绪和按钮留白方式，后续同项目默认沿用",
                        },
                        {
                            "variant_id": "V02",
                            "decision": "rejected",
                            "scores": {"style_fit": 2, "conversion": 4},
                            "issues": ["利益点太抢主体", "背景过亮"],
                            "learning": "避免 V02 这种背景过亮且利益点抢主体的处理",
                        },
                        {
                            "variant_id": "V03",
                            "decision": "revise",
                            "revision_notes": ["动势可以保留，但透视需要收敛"],
                            "learning": "V03 的强动势可作为 K3 探索，透视强度待验证",
                        },
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        review_result = self.app.ingest_candidate_review(
            project_key="LOCAL",
            same_category="anime-rpg",
            review_file=str(review_file),
            work_item_id="5001",
        )
        self.assertTrue(Path(review_result["candidate_review"]).exists())
        self.assertEqual(review_result["accepted_variant_ids"], ["V01"])
        self.assertEqual(review_result["rejected_variant_ids"], ["V02"])
        self.assertEqual(review_result["pending_variant_ids"], ["V03"])
        self.assertTrue(Path(review_result["candidate_style_drift_report"]).exists())
        self.assertTrue(Path(review_result["candidate_comparison_matrix"]).exists())
        self.assertTrue(Path(review_result["candidate_comparison_matrix_md"]).exists())
        self.assertGreaterEqual(len(review_result["generated_review_reports"]), 3)
        reviewed_comparison_md = Path(review_result["candidate_comparison_matrix_md"]).read_text(encoding="utf-8")
        self.assertIn("候选方案对比矩阵", reviewed_comparison_md)
        self.assertIn("V01", reviewed_comparison_md)
        self.assertIn("采纳", reviewed_comparison_md)
        digest_content = Path(review_result["learning_digest"]).with_suffix(".md").read_text(encoding="utf-8")
        self.assertIn("V01", digest_content)
        self.assertIn("V02", digest_content)
        readiness = self.app.create_delivery_readiness_report(project_key="LOCAL", work_item_id="5001")
        self.assertTrue(Path(readiness["delivery_readiness_report"]).exists())
        self.assertTrue(Path(readiness["delivery_readiness_report_md"]).exists())
        self.assertNotEqual(readiness["status"], "blocked")
        self.assertFalse(readiness["blocking_items"])
        readiness_md = Path(readiness["delivery_readiness_report_md"]).read_text(encoding="utf-8")
        self.assertIn("交付前质量门", readiness_md)
        self.assertIn("风格迁移与项目覆盖", readiness_md)
        self.assertIn("风格一致性闸门", readiness_md)
        self.assertIn("候选图风格偏移预警", readiness_md)
        self.assertIn("候选方案对比矩阵", readiness_md)
        self.assertIn("PSD/切图规格核对", readiness_md)
        self.assertIn("安全门控", readiness_md)
        self.assertIn("需要设计师确认：是", readiness_md)
        workflow_plan = self.app.create_design_workflow_plan(project_key="LOCAL", work_item_id="5001")
        self.assertTrue(Path(workflow_plan["design_workflow_plan"]).exists())
        self.assertTrue(Path(workflow_plan["design_workflow_plan_md"]).exists())
        self.assertIn(workflow_plan["status"], {"blocked", "in_progress", "needs_designer_confirmation", "ready_for_meegle_writeback_or_delivery"})
        workflow_md = Path(workflow_plan["design_workflow_plan_md"]).read_text(encoding="utf-8")
        self.assertIn("设计工作流计划", workflow_md)
        self.assertIn("步骤看板", workflow_md)
        self.assertIn("create-meegle-writeback-draft", workflow_md)
        review_packet = self.app.create_designer_review_packet(project_key="LOCAL", work_item_id="5001")
        self.assertTrue(Path(review_packet["designer_review_packet"]).exists())
        self.assertTrue(Path(review_packet["designer_review_packet_md"]).exists())
        packet_md = Path(review_packet["designer_review_packet_md"]).read_text(encoding="utf-8")
        self.assertIn("设计师评审包", packet_md)
        self.assertIn("design_decision_record", packet_md)
        self.assertIn("style_transfer_report", packet_md)
        self.assertIn("style_alignment_report", packet_md)
        self.assertIn("requirement_clarification_report", packet_md)
        self.assertIn("generated_gallery", packet_md)
        self.assertIn("candidate_style_drift_report", packet_md)
        self.assertIn("candidate_comparison_matrix", packet_md)
        self.assertIn("psd_slice_spec_report", packet_md)
        self.assertIn("delivery_readiness_report", packet_md)
        self.assertIn("design_workflow_plan", packet_md)
        self.assertIn("人工确认清单", packet_md)
        resume = self.app.resume_session(project_key="LOCAL")
        self.assertTrue(Path(resume["session_resume"]).exists())
        self.assertTrue(Path(resume["session_resume_md"]).exists())
        self.assertEqual(resume["active_work_item_id"], "5001")
        self.assertIn("next_commands", resume)
        resume_md = Path(resume["session_resume_md"]).read_text(encoding="utf-8")
        self.assertIn("会话恢复简报", resume_md)
        self.assertIn("design_decision_record", resume_md)
        self.assertIn("style_transfer_report", resume_md)
        self.assertIn("style_alignment_report", resume_md)
        self.assertIn("candidate_style_drift_report", resume_md)
        self.assertIn("candidate_comparison_matrix", resume_md)
        self.assertIn("psd_slice_spec_report", resume_md)
        self.assertIn("design_workflow_plan", resume_md)
        cycle_result = self.app.run_local_design_cycle(
            project_key="LOCAL",
            work_item_id="5001",
            title="本地活动海报",
            requirement_file=str(requirement_file),
            same_category="anime-rpg",
            doc_files=[str(doc_file)],
            asset_root=str(asset_root),
        )
        self.assertTrue(Path(cycle_result["cycle_report"]).exists())
        self.assertIn("metacognition_audit", cycle_result["artifacts"])
        self.assertIn("learning_digest", cycle_result["artifacts"])
        self.assertIn("image_generation_batch", cycle_result["artifacts"])
        self.assertIn("style_transfer_report", cycle_result["artifacts"])
        self.assertIn("style_alignment_report", cycle_result["artifacts"])
        self.assertIn("design_decision_record", cycle_result["artifacts"])
        self.assertIn("photoshop_jsx", cycle_result["artifacts"])
        self.assertIn("delivery_readiness_report", cycle_result["artifacts"])
        self.assertIn("design_workflow_plan", cycle_result["artifacts"])
        self.assertIn("designer_review_packet", cycle_result["artifacts"])

    def test_product_requirement_flow_keeps_default_outputs_slim(self) -> None:
        requirement_file = self.root / "product-flow.md"
        requirement_file.write_text(
            "平面+视频需求：先做 9:16 1080x1920 整体效果图，确认后再进入 PSD、PNG 切图和多尺寸拓展。",
            encoding="utf-8",
        )

        result = self.app.process_local_requirement(
            project_key="PRODUCT",
            work_item_id="8601",
            title="产品化主流程",
            requirement_file=str(requirement_file),
            same_category="casual-match",
        )

        output_dir = Path(result["output_dir"])
        workpack_dir = Path(result["designer_workpack"])
        state_path = workpack_dir / "_system" / "state.json"
        self.assertEqual(result["output_mode"], "designer")
        self.assertTrue(workpack_dir.exists())
        self.assertTrue(Path(result["task_sheet"]).exists())
        self.assertTrue(Path(result["prompt_sheet"]).exists())
        self.assertTrue(state_path.exists())
        self.assertTrue((output_dir / "design_brief.json").exists())
        self.assertTrue((output_dir / "creative_pack.json").exists())
        self.assertTrue((output_dir / "style_transfer_report.json").exists())
        self.assertFalse((output_dir / "design_brief.md").exists())
        self.assertFalse((output_dir / "creative_pack.md").exists())
        self.assertFalse((output_dir / "style_transfer_report.md").exists())
        self.assertFalse((output_dir / "candidate_evaluation.md").exists())

        direction = self.app.prepare_image_direction(project_key="PRODUCT", work_item_id="8601")
        self.assertTrue(Path(direction["prompt_sheet"]).exists())
        self.assertEqual(Path(direction["prompt_sheet"]), Path(result["prompt_sheet"]))

        delivery = self.app.prepare_delivery_review(project_key="PRODUCT", work_item_id="8601")
        review_sheet = Path(delivery["delivery_review_sheet"])
        self.assertTrue(review_sheet.exists())
        self.assertEqual(review_sheet.parent, workpack_dir)
        self.assertTrue((output_dir / "delivery_readiness" / "delivery_readiness_report.json").exists())
        self.assertFalse((output_dir / "delivery_readiness" / "delivery_readiness_report.md").exists())
        state_payload = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(Path(state_payload["visible_files"]["delivery_review_sheet"]), review_sheet)

    def test_field_calibration_guides_local_brief(self) -> None:
        sample_file = self.root / "workitem.json"
        sample_file.write_text(
            """{
  "fields": {
    "creative_goal_custom": "目标是首日提升点击转化",
    "player_segment_custom": "二次元RPG核心玩家",
    "media_channel_custom": "TikTok",
    "asset_spec_custom": "1080x1920",
    "handoff_custom": "PSD, PNG, 切图",
    "finish_time_custom": "2026-06-05"
  }
}""",
            encoding="utf-8",
        )
        result = self.app.calibrate_field_mapping(project_key="FIELD", sample_file=str(sample_file))
        self.assertTrue(Path(result["field_mapping"]).exists())

        pack_result = self.app.build_local_creative_pack(
            project_key="FIELD",
            work_item_id="7001",
            title="字段校准海报",
            requirement_file=str(sample_file),
            same_category="anime-rpg",
        )
        output_dir = Path(pack_result["output_dir"])
        brief_payload = json.loads((output_dir / "design_brief.json").read_text(encoding="utf-8"))
        content = json.dumps(brief_payload, ensure_ascii=False)
        self.assertIn("TikTok", content)
        self.assertIn("1080x1920", content)
        self.assertIn("PSD", content)
        self.assertFalse((output_dir / "design_brief.md").exists())

    def test_diagnose_workitem_intake_from_local_sample(self) -> None:
        sample_file = self.root / "intake_workitem.json"
        sample_file.write_text(
            json.dumps(
                {
                    "fields": {
                        "creative_goal_custom": "目标是提升点击转化",
                        "player_segment_custom": "二次元RPG核心玩家",
                        "media_channel_custom": "TikTok",
                        "asset_spec_custom": "1080x1920",
                        "handoff_custom": "PSD, PNG, 切图",
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        result = self.app.diagnose_workitem_intake(
            project_key="INTAKE",
            sample_file=str(sample_file),
            title="入口诊断海报",
        )
        self.assertTrue(Path(result["workitem_intake_diagnostics"]).exists())
        self.assertTrue(Path(result["workitem_intake_diagnostics_md"]).exists())
        self.assertIn(result["status"], {"ready_for_creative_pack", "needs_field_review", "blocked"})
        self.assertIn("缺少明确截止时间", result["missing_information"])
        content = Path(result["workitem_intake_diagnostics_md"]).read_text(encoding="utf-8")
        self.assertIn("工作项入口诊断", content)
        self.assertIn("推荐字段映射", content)
        self.assertIn("解析出的设计需求卡", content)
        self.assertIsNone(self.app.store.load_field_mapping("INTAKE"))

    def test_screen_todos_finds_design_candidates(self) -> None:
        self.app.meegle.fetch_todos = lambda action, asset_key=None, max_pages=1: [
            {
                "work_item_id": "8001",
                "project_key": "DEMO",
                "name": "平面广告海报 PSD 制作",
                "status": "设计中",
            },
            {
                "work_item_id": "8002",
                "project_key": "DEMO",
                "name": "后端接口联调",
                "status": "开发中",
            },
        ]
        result = self.app.screen_todos(action="todo", max_pages=1)
        self.assertEqual(result["design_count"], 1)
        self.assertTrue(Path(result["todo_screening"]).exists())

    def test_run_feishu_design_cycle_with_mocked_context(self) -> None:
        self.app.meegle.fetch_workitem_context = lambda project_key, work_item_id: WorkItemContext(
            project_key=project_key,
            work_item_id=work_item_id,
            title="飞书平面海报",
            raw_item={
                "name": "飞书平面海报",
                "description": "目标是提升点击转化，二次元角色突出，尺寸 1080x1920，输出 PSD、PNG。",
                "platform": "Facebook",
                "audience": "二次元RPG玩家",
            },
            comments=[],
            doc_links=[],
            docs=[],
        )
        self.app.lark_docs.fetch_docs = lambda doc_links: []
        result = self.app.run_feishu_design_cycle(project_key="FEISHU", work_item_id="9001")
        self.assertTrue(Path(result["cycle_report"]).exists())
        self.assertIn("creative_pack", result["artifacts"])
        self.assertIn("requirement_memory_report", result["artifacts"])
        self.assertIn("requirement_clarification_report", result["artifacts"])
        self.assertIn("style_transfer_report", result["artifacts"])
        self.assertIn("style_alignment_report", result["artifacts"])
        self.assertIn("design_decision_record", result["artifacts"])
        self.assertIn("learning_digest", result["artifacts"])
        self.assertIn("delivery_readiness_report", result["artifacts"])
        self.assertIn("designer_review_packet", result["artifacts"])
        memory_report = Path(result["artifacts"]["requirement_memory_report"])
        self.assertTrue(memory_report.exists())
        memory_payload = json.loads(memory_report.read_text(encoding="utf-8"))
        memory_content = json.dumps(memory_payload, ensure_ascii=False)
        self.assertIn("learned_deliverables", memory_payload)
        self.assertIn("投放素材", memory_content)
        self.assertFalse(memory_report.with_suffix(".md").exists())
        profile = self.app.store.load_project_profile("FEISHU")
        self.assertIsNotNone(profile)
        self.assertIn("1080x1920", profile.default_sizes)
        self.assertIn("投放素材", profile.gameplay_tags)

    def test_diagnose_workitem_intake_with_mocked_meegle_context(self) -> None:
        self.app.meegle.fetch_workitem_context = lambda project_key, work_item_id: WorkItemContext(
            project_key=project_key,
            work_item_id=work_item_id,
            title="Meegle 入口诊断",
            raw_item={
                "name": "Meegle 入口诊断",
                "description": "目标是提升预约转化，尺寸 1080x1920，输出 PSD、PNG。",
                "platform": "Facebook",
                "audience": "二次元RPG玩家",
            },
            comments=[{"content": "补充：截止 2026-06-05，按钮需要独立切图"}],
            doc_links=["https://example.feishu.cn/docx/ABC123"],
            docs=[],
        )
        result = self.app.diagnose_workitem_intake(project_key="FEISHU", work_item_id="9002")
        self.assertTrue(Path(result["workitem_intake_diagnostics"]).exists())
        self.assertIn(result["status"], {"ready_for_creative_pack", "needs_field_review", "blocked"})
        content = Path(result["workitem_intake_diagnostics_md"]).read_text(encoding="utf-8")
        self.assertIn("关联文档", content)
        self.assertIn("fetch-requirement-docs", content)

    def test_meegle_transition_gate_requires_confirmation(self) -> None:
        draft = self.app.create_meegle_transition_draft(
            project_key="FLOW",
            work_item_id="9101",
            action="confirm",
            node_names=["待评审"],
        )
        self.assertTrue(Path(draft["meegle_transition_draft"]).exists())
        dry_run = self.app.publish_meegle_transition(project_key="FLOW", work_item_id="9101")
        self.assertFalse(dry_run["executed"])
        with self.assertRaises(PermissionError):
            self.app.publish_meegle_transition(project_key="FLOW", work_item_id="9101", execute=True)
        called: dict[str, str] = {}
        self.app.meegle.transition_workflow = lambda project_key, work_item_id, action, node_id=None, node_names=None, rollback_reason=None: called.setdefault(
            "node",
            ",".join(node_names or []),
        ) or {"transition_id": "mock-transition"}
        executed = self.app.publish_meegle_transition(
            project_key="FLOW",
            work_item_id="9101",
            execute=True,
            confirm_token="TRANSITION_MEEGLE_WORKFLOW",
        )
        self.assertTrue(executed["executed"])
        self.assertEqual(called["node"], "待评审")


if __name__ == "__main__":
    unittest.main()
