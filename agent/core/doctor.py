from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import shutil
import sys

from agent.models import DoctorCheck, DoctorReport, SessionSnapshot
from agent.settings import AppPaths


class Doctor:
    def build(
        self,
        paths: AppPaths,
        project_key: str | None = None,
        snapshot: SessionSnapshot | None = None,
    ) -> DoctorReport:
        checks: list[DoctorCheck] = [
            self._python_check(),
            self._path_check("ROOT", "仓库根目录", paths.root, must_exist=True, must_write=False),
            self._path_check("MEMORY", "记忆目录", paths.memory, must_exist=False, must_write=True),
            self._path_check("WORKSPACE", "运行产物目录", paths.workspace, must_exist=False, must_write=True),
            self._path_check("TEMPLATES", "模板目录", paths.templates, must_exist=True, must_write=False),
            self._cli_check("MEEGLE", "Meego / Feishu Project CLI", "meegle"),
            self._cli_check("LARK", "Lark / Feishu collaboration CLI", "lark-cli"),
            self._session_check(project_key, snapshot),
            self._test_command_check(),
        ]
        checks.extend(self._artifact_checks(snapshot))
        blockers = [check.detail for check in checks if check.status == "blocked"]
        warnings = [check.detail for check in checks if check.status == "warning"]
        status = "blocked" if blockers else "ready_with_warnings" if warnings else "ready"
        return DoctorReport(
            project_key=project_key,
            created_at=datetime.now().isoformat(timespec="seconds"),
            status=status,
            checks=checks,
            warnings=warnings,
            blockers=blockers,
            recommended_commands=self._recommended_commands(project_key, snapshot),
        )

    @staticmethod
    def render_markdown(report: DoctorReport) -> str:
        lines = [
            "# 本地环境诊断",
            "",
            f"- 项目：`{report.project_key or '未指定'}`",
            f"- 创建时间：`{report.created_at}`",
            f"- 状态：`{report.status}`",
            "",
            "## 检查项",
            "| 检查 | 状态 | 说明 |",
            "|---|---|---|",
        ]
        for check in report.checks:
            lines.append(f"| {check.title} | `{check.status}` | {check.detail} |")
        lines.extend(["", "## 阻塞项", *(f"- {item}" for item in report.blockers or ["无"])])
        lines.extend(["", "## 提醒", *(f"- {item}" for item in report.warnings or ["无"])])
        lines.extend(["", "## 推荐命令", *(f"- `{command}`" for command in report.recommended_commands)])
        return "\n".join(lines)

    @staticmethod
    def _python_check() -> DoctorCheck:
        version = ".".join(str(item) for item in sys.version_info[:3])
        if sys.version_info < (3, 11):
            return DoctorCheck("PYTHON", "Python 版本", "blocked", f"当前 Python {version}，需要 3.11+。")
        return DoctorCheck("PYTHON", "Python 版本", "pass", f"当前 Python {version}，满足 3.11+。")

    @staticmethod
    def _path_check(check_id: str, title: str, path: Path, must_exist: bool, must_write: bool) -> DoctorCheck:
        if must_exist and not path.exists():
            return DoctorCheck(check_id, title, "blocked", f"路径不存在：{path}")
        if must_write:
            try:
                path.mkdir(parents=True, exist_ok=True)
                probe = path / ".doctor-write-probe"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink(missing_ok=True)
            except OSError as exc:
                return DoctorCheck(check_id, title, "blocked", f"路径不可写：{path}（{exc}）")
        return DoctorCheck(check_id, title, "pass", f"路径可用：{path}")

    @staticmethod
    def _cli_check(check_id: str, title: str, executable: str) -> DoctorCheck:
        resolved = shutil.which(executable)
        if resolved:
            return DoctorCheck(check_id, title, "pass", f"已找到 `{executable}`：{resolved}")
        return DoctorCheck(
            check_id,
            title,
            "warning",
            f"未找到 `{executable}`；本地流程仍可用，对应的 Meego 项目或 Lark 协作系统集成会受限。",
        )

    @staticmethod
    def _session_check(project_key: str | None, snapshot: SessionSnapshot | None) -> DoctorCheck:
        if not project_key:
            return DoctorCheck("SESSION", "最近会话", "warning", "未指定项目，跳过最近会话检查。")
        if not snapshot:
            return DoctorCheck("SESSION", "最近会话", "warning", f"项目 `{project_key}` 暂无最近会话，可先运行本地或飞书设计周期。")
        return DoctorCheck("SESSION", "最近会话", "pass", f"最近工作项 `{snapshot.active_work_item_id}`，输出目录：{snapshot.output_dir}")

    @staticmethod
    def _test_command_check() -> DoctorCheck:
        return DoctorCheck("TESTS", "测试发现", "pass", "标准回归命令：python -m unittest discover -s tests -v")

    @staticmethod
    def _artifact_checks(snapshot: SessionSnapshot | None) -> list[DoctorCheck]:
        if not snapshot:
            return []
        output_dir = Path(snapshot.output_dir)
        source_mode = Doctor._detect_cycle_source_mode(output_dir)
        lean_mode = bool(source_mode and source_mode.endswith("-lean"))
        required = (
            ("BRIEF", "设计需求卡", "design_brief.json"),
            ("CREATIVE", "创作包", "creative_pack.json"),
        )
        checks: list[DoctorCheck] = []
        for check_id, title, relative in required:
            path = output_dir / relative
            if path.exists():
                checks.append(DoctorCheck(check_id, title, "pass", f"已存在：{path}"))
            else:
                checks.append(DoctorCheck(check_id, title, "warning", f"缺少常见产物：{path}"))
        workflow_path = output_dir / "workflow" / "design_workflow_plan.json"
        if workflow_path.exists():
            checks.append(DoctorCheck("WORKFLOW", "工作流计划", "pass", f"已存在：{workflow_path}"))
        elif lean_mode:
            checks.append(
                DoctorCheck(
                    "WORKFLOW",
                    "工作流计划",
                    "pass",
                    f"轻量模式 `{source_mode}` 下工作流计划为可选项：{workflow_path}",
                )
            )
        else:
            mode_hint = f"（来源模式：{source_mode}）" if source_mode else ""
            checks.append(DoctorCheck("WORKFLOW", "工作流计划", "warning", f"缺少常见产物{mode_hint}：{workflow_path}"))
        return checks

    @staticmethod
    def _detect_cycle_source_mode(output_dir: Path) -> str | None:
        cycle_report = output_dir / "cycle" / "design_cycle_report.json"
        if not cycle_report.exists():
            return None
        try:
            payload = json.loads(cycle_report.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        value = payload.get("source_mode")
        if not isinstance(value, str):
            return None
        value = value.strip()
        return value or None

    @staticmethod
    def _recommended_commands(project_key: str | None, snapshot: SessionSnapshot | None) -> list[str]:
        commands = ["python -m unittest discover -s tests -v"]
        if project_key:
            commands.append(f"python -m agent.cli doctor --project-key {project_key}")
            if snapshot:
                commands.append(f"python -m agent.cli cockpit --project-key {project_key} --work-item-id {snapshot.active_work_item_id}")
            else:
                commands.append(
                    f"python -m agent.cli build-local-creative-pack --project-key {project_key} --work-item-id <id> --title <title> --requirement-file <req.md>"
                )
        else:
            commands.append("python -m agent.cli doctor --project-key <project-key>")
        return commands
