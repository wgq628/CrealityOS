from __future__ import annotations

import json
import shutil
import time
import unittest
import uuid
from pathlib import Path

from agent.app import DesignCopilotApp
from agent.console_server import _state_from_request, render_console_html
from agent.settings import AppPaths


class CliEntrypointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path.cwd() / "workspace" / "test-sandboxes" / f"entrypoints-{uuid.uuid4().hex}"
        self.app = DesignCopilotApp(self.root)

    def tearDown(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)

    def test_doctor_writes_report_without_external_cli_requirements(self) -> None:
        result = self.app.doctor(project_key="DEMO")

        self.assertTrue(Path(result["doctor_report"]).exists())
        self.assertTrue(Path(result["doctor_report_md"]).exists())
        self.assertNotEqual(result["status"], "blocked")
        report = json.loads(Path(result["doctor_report"]).read_text(encoding="utf-8"))
        check_ids = {item["check_id"] for item in report["checks"]}
        self.assertIn("PYTHON", check_ids)
        self.assertIn("MEEGLE", check_ids)
        self.assertIn("LARK", check_ids)
        content = Path(result["doctor_report_md"]).read_text(encoding="utf-8")
        self.assertIn("本地环境诊断", content)
        self.assertIn("python -m unittest discover -s tests -v", content)

    def test_cockpit_without_session_creates_draft_entrypoint(self) -> None:
        result = self.app.cockpit(project_key="EMPTY")

        self.assertEqual(result["status"], "draft")
        self.assertTrue(Path(result["designer_cockpit"]).exists())
        self.assertTrue(Path(result["designer_cockpit_md"]).exists())
        self.assertTrue(any("build-local-creative-pack" in item for item in result["next_commands"]))
        content = Path(result["designer_cockpit_md"]).read_text(encoding="utf-8")
        self.assertIn("设计师副驾驾驶舱", content)
        self.assertIn("当前还没有创作包", content)

    def test_cockpit_aggregates_completed_local_cycle_artifacts(self) -> None:
        requirement_file = self.root / "requirement.md"
        requirement_file.write_text(
            "目标是提升点击转化，二次元角色突出，尺寸 1080x1920，输出 PSD、PNG，平台 Facebook。",
            encoding="utf-8",
        )
        self.app.build_local_creative_pack(
            project_key="LOCAL",
            work_item_id="5001",
            title="本地活动海报",
            requirement_file=str(requirement_file),
            same_category="anime-rpg",
        )
        self.app.create_design_workflow_plan(project_key="LOCAL", work_item_id="5001")
        self.app.create_designer_review_packet(project_key="LOCAL", work_item_id="5001")

        result = self.app.cockpit(project_key="LOCAL", work_item_id="5001")

        self.assertTrue(Path(result["designer_cockpit"]).exists())
        self.assertIn(result["status"], {"blocked", "in_progress", "needs_designer_confirmation", "ready_for_meegle_writeback_or_delivery"})
        self.assertTrue(result["next_commands"])
        payload = json.loads(Path(result["designer_cockpit"]).read_text(encoding="utf-8"))
        self.assertTrue(payload["artifact_index"]["creative_pack"])
        self.assertTrue(payload["artifact_index"]["design_workflow_plan"])
        self.assertTrue(payload["artifact_index"]["designer_review_packet"])

    def test_dashboard_generates_static_html_and_data_snapshot(self) -> None:
        requirement_file = self.root / "requirement.md"
        requirement_file.write_text(
            "参考竞品做 9:16 投放平面，卡片分类玩法，输出 PSD、PNG。",
            encoding="utf-8",
        )
        self.app.build_local_creative_pack(
            project_key="DASH",
            work_item_id="7001",
            title="卡片分类投放图",
            requirement_file=str(requirement_file),
            same_category="casual-card",
        )
        self.app.create_design_workflow_plan(project_key="DASH", work_item_id="7001")

        result = self.app.dashboard(project_key="DASH", work_item_id="7001")

        html_path = Path(result["dashboard"])
        data_path = Path(result["dashboard_data"])
        self.assertTrue(html_path.exists())
        self.assertTrue(data_path.exists())
        html = self._read_text_with_retry(html_path)
        payload = json.loads(self._read_text_with_retry(data_path))
        self.assertIn("CrealityOS", html)
        self.assertIn("dashboard-data", html)
        self.assertIn("卡片分类", html)
        self.assertEqual(payload["cockpit"]["work_item_id"], "7001")
        self.assertTrue(payload["design_brief"])
        self.assertTrue(payload["requirement_memory"])

    def test_console_state_and_html_render_from_local_artifacts(self) -> None:
        requirement_file = self.root / "requirement.md"
        requirement_file.write_text(
            "Need a 9:16 launch ad, strong gameplay read, output PSD and PNG.",
            encoding="utf-8",
        )
        self.app.build_local_creative_pack(
            project_key="CONSOLE",
            work_item_id="8101",
            title="Console Launch Ad",
            requirement_file=str(requirement_file),
            same_category="casual-card",
        )
        self.app.create_design_workflow_plan(project_key="CONSOLE", work_item_id="8101")

        payload = _state_from_request(
            "project=CONSOLE&work_item=8101",
            self.app,
            AppPaths.from_root(self.root),
            None,
            None,
        )
        html = render_console_html(payload)

        self.assertEqual(payload["console"]["project_key"], "CONSOLE")
        self.assertEqual(payload["console"]["work_item_id"], "8101")
        self.assertTrue(payload["artifact_index"]["creative_pack"])
        self.assertIn("CrealityOS Console", html)
        self.assertIn("console-data", html)
        self.assertIn("/api/state", html)

    def test_console_corrects_project_work_item_mismatch(self) -> None:
        real_requirement = self.root / "real.md"
        real_requirement.write_text("Real project task, output PNG.", encoding="utf-8")
        local_requirement = self.root / "local.md"
        local_requirement.write_text("Local project task, output PNG.", encoding="utf-8")
        self.app.build_local_creative_pack(
            project_key="REAL",
            work_item_id="9001",
            title="Real Task",
            requirement_file=str(real_requirement),
            same_category="casual-card",
        )
        self.app.build_local_creative_pack(
            project_key="LOCAL",
            work_item_id="5001",
            title="Local Task",
            requirement_file=str(local_requirement),
            same_category="casual-card",
        )

        payload = _state_from_request(
            "project=LOCAL&work_item=9001",
            self.app,
            AppPaths.from_root(self.root),
            None,
            None,
        )

        self.assertEqual(payload["console"]["requested_project_key"], "LOCAL")
        self.assertEqual(payload["console"]["project_key"], "REAL")
        self.assertEqual(payload["console"]["work_item_id"], "9001")
        self.assertTrue(payload["console"]["corrected"])
        self.assertTrue(payload["console"]["notices"])
        self.assertIn("REAL", payload["console"]["output_dir"])

    def test_generate_project_skill_from_learned_memory(self) -> None:
        requirement_file = self.root / "requirement.md"
        requirement_file.write_text(
            "平面需求描述：参考竞品做 9:16 投放素材，卡片分类玩法，面向休闲益智用户，输出 PSD、PNG、切图。",
            encoding="utf-8",
        )
        self.app.build_local_creative_pack(
            project_key="SKILL",
            work_item_id="9001",
            title="卡片分类投放素材",
            requirement_file=str(requirement_file),
            same_category="casual-card",
        )

        result = self.app.generate_project_skill(project_key="SKILL")

        skill_file = Path(result["skill_file"])
        manifest_file = Path(result["manifest_file"])
        self.assertTrue(skill_file.exists())
        self.assertTrue(manifest_file.exists())
        self.assertRegex(result["skill_name"], r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
        content = skill_file.read_text(encoding="utf-8")
        self.assertIn("---\nname:", content)
        self.assertIn("description:", content)
        self.assertIn("平面需求描述", content)
        self.assertIn("9:16", content)
        self.assertIn("PSD", content)
        self.assertIn("投放素材", content)
        self.assertIn("卡片分类", content)

    def test_storyboard_requirement_does_not_default_to_psd_or_slicing(self) -> None:
        requirement_file = self.root / "storyboard.md"
        requirement_file.write_text(
            "平面需求描述：剧情向片头制作分镜图，参考 3D 卡通动物电影感，拆弹小猪和悬崖小猪两个镜头，横竖适配，输出 PNG、JPG。",
            encoding="utf-8",
        )
        result = self.app.build_local_creative_pack(
            project_key="STORY",
            work_item_id="9101",
            title="剧情片头分镜",
            requirement_file=str(requirement_file),
            same_category="general-game-design",
        )

        run_dir = Path(result["output_dir"])
        memory_payload = json.loads((run_dir / "requirement_memory_report.json").read_text(encoding="utf-8"))
        creative_pack = (run_dir / "creative_pack.md").read_text(encoding="utf-8")
        skill = self.app.generate_project_skill(project_key="STORY")
        skill_content = Path(skill["skill_file"]).read_text(encoding="utf-8")

        self.assertNotIn("PSD", memory_payload["learned_deliverables"])
        self.assertIn("横竖构图适配", memory_payload["learned_visual_keywords"])
        self.assertIn("横竖适配 / 剧情向交付建议", creative_pack)
        self.assertNotIn("## PSD / 图层建议", creative_pack)
        self.assertNotIn("交付物涉及：PSD", creative_pack)
        self.assertIn("不默认套用 PSD 分层或切图规则", skill_content)

    @staticmethod
    def _read_text_with_retry(path: Path) -> str:
        for attempt in range(8):
            try:
                return path.read_text(encoding="utf-8")
            except PermissionError:
                if attempt == 7:
                    raise
                time.sleep(0.05)
        return path.read_text(encoding="utf-8")

    def test_cockpit_surfaces_blocked_style_alignment(self) -> None:
        run_dir = self.root / "workspace" / "runs" / "BLOCK" / "1001-title"
        run_dir.mkdir(parents=True)
        (run_dir / "style_alignment_report.json").write_text(
            json.dumps(
                {
                    "status": "blocked",
                    "blockers": ["K3 假设进入了正式提示词"],
                    "warnings": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = self.app.cockpit(project_key="BLOCK", work_item_id="1001", output_dir=str(run_dir))

        self.assertEqual(result["status"], "blocked")
        self.assertIn("K3 假设进入了正式提示词", result["blockers"])

    def test_user_visible_markdown_stays_readable_chinese(self) -> None:
        doctor = self.app.doctor(project_key="READABLE")
        cockpit = self.app.cockpit(project_key="READABLE")
        contents = [
            Path(doctor["doctor_report_md"]).read_text(encoding="utf-8"),
            Path(cockpit["designer_cockpit_md"]).read_text(encoding="utf-8"),
        ]
        for content in contents:
            self.assertNotIn("�", content)
            self.assertNotIn("璁捐", content)
            self.assertNotIn("娴嬭", content)
        self.assertIn("本地环境诊断", contents[0])
        self.assertIn("设计师副驾驾驶舱", contents[1])


if __name__ == "__main__":
    unittest.main()
