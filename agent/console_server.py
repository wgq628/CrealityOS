from __future__ import annotations

import json
import mimetypes
import re
import traceback
from datetime import datetime
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from agent.app import DesignCopilotApp
from agent.artifact_resolver import ArtifactResolver, discover_projects, discover_work_items
from agent.settings import AppPaths
from agent.utils import load_json


ACTION_DEFINITIONS: tuple[dict, ...] = (
    {
        "action_id": "refresh_state",
        "label": "刷新工作台",
        "group": "安全本地动作",
        "stage": "接单",
        "tier": "safe",
        "produces": ["最新状态快照"],
        "description": "重新读取当前项目、工作项和本地产物。",
    },
    {
        "action_id": "create_requirement_clarification_report",
        "label": "生成需求澄清",
        "group": "安全本地动作",
        "stage": "需求",
        "tier": "safe",
        "produces": ["requirement_clarification_report.json", "requirement_clarification_comment.md"],
        "description": "从设计需求卡生成澄清问题和评论草稿。",
    },
    {
        "action_id": "create_style_transfer_report",
        "label": "生成风格迁移",
        "group": "安全本地动作",
        "stage": "创作",
        "tier": "safe",
        "produces": ["style_transfer_report.json"],
        "description": "检查同品类规则和项目覆盖规则的边界。",
    },
    {
        "action_id": "create_style_alignment_report",
        "label": "生成风格门",
        "group": "安全本地动作",
        "stage": "创作",
        "tier": "safe",
        "produces": ["style_alignment_report.json"],
        "description": "检查 K1/K2、禁忌项和 K3 泄漏。",
    },
    {
        "action_id": "create_design_decision_record",
        "label": "生成决策记录",
        "group": "安全本地动作",
        "stage": "创作",
        "tier": "safe",
        "produces": ["design_decision_record.json"],
        "description": "记录本轮设计判断、证据、假设和安全边界。",
    },
    {
        "action_id": "create_image_production_batch",
        "label": "生成图片方案",
        "group": "安全本地动作",
        "stage": "图片",
        "tier": "safe",
        "produces": ["image_generation_batch.json", "candidate_evaluation.md"],
        "description": "生成多方向图片提示词批次，不调用出图工具。",
    },
    {
        "action_id": "create_design_workflow_plan",
        "label": "生成工作流计划",
        "group": "安全本地动作",
        "stage": "流程",
        "tier": "safe",
        "produces": ["design_workflow_plan.json"],
        "description": "把本地产物转换为 ready / waiting / blocked 状态板。",
    },
    {
        "action_id": "create_designer_review_packet",
        "label": "生成评审包",
        "group": "安全本地动作",
        "stage": "评审",
        "tier": "safe",
        "produces": ["designer_review_packet.json"],
        "description": "把需求、创作、图片、PSD、交付和学习产物汇总成评审入口。",
    },
    {
        "action_id": "create_delivery_readiness_report",
        "label": "生成交付检查",
        "group": "安全本地动作",
        "stage": "交付",
        "tier": "safe",
        "produces": ["delivery_readiness_report.json"],
        "description": "生成交付前质量门，不发布、不覆盖文件。",
    },
    {
        "action_id": "create_learning_digest",
        "label": "生成学习摘要",
        "group": "安全本地动作",
        "stage": "学习",
        "tier": "safe",
        "produces": ["latest_learning_digest.json"],
        "description": "压缩项目记忆，沉淀下次默认项、避坑项和 K3 检查。",
    },
    {
        "action_id": "create_image_generation_jobs",
        "label": "创建出图任务队列",
        "group": "需确认动作",
        "stage": "图片",
        "tier": "confirm",
        "produces": ["image_generation_jobs.json", "pixpark_requests.jsonl"],
        "description": "创建待确认出图任务，不执行 Pixpark，不消耗额度。",
    },
    {
        "action_id": "prepare_image_execution_package",
        "label": "准备人工出图包",
        "group": "需确认动作",
        "stage": "图片",
        "tier": "confirm",
        "produces": ["image_execution_package.json", "generation_results_template.json"],
        "description": "拆分出图 payload 和登记模板，供人工执行后回填结果。",
    },
    {
        "action_id": "create_psd_handoff_plan",
        "label": "生成 PSD 计划",
        "group": "需确认动作",
        "stage": "PSD",
        "tier": "confirm",
        "produces": ["psd_handoff_plan.json", "layer_map.md", "slice_checklist.md"],
        "description": "从候选图和交付目标生成 PSD 重建、图层和切图计划。",
    },
    {
        "action_id": "prepare_psd_handoff_package",
        "label": "准备 PSD staging",
        "group": "需确认动作",
        "stage": "PSD",
        "tier": "confirm",
        "produces": ["psd_handoff_package.json", "psd_handoff_approval_ticket.md"],
        "description": "复制本地候选素材到安全 staging，不覆盖正式资产。",
    },
    {
        "action_id": "create_psd_slice_spec_report",
        "label": "生成切图规范",
        "group": "需确认动作",
        "stage": "切图",
        "tier": "confirm",
        "produces": ["psd_slice_spec_report.json"],
        "description": "检查 PSD 图层、命名、尺寸和 PNG 切图规范。",
    },
    {
        "action_id": "create_meegle_writeback_draft",
        "label": "生成飞书回写草稿",
        "group": "需确认动作",
        "stage": "协同",
        "tier": "confirm",
        "produces": ["meegle_writeback_comment.md", "meegle_writeback_approval_ticket.md"],
        "description": "只生成评论草稿，不发布到 Meegle。",
    },
    {
        "action_id": "execute_pixpark_generation",
        "label": "执行真实出图",
        "group": "高风险动作",
        "stage": "图片",
        "tier": "locked",
        "produces": ["真实生成结果"],
        "description": "当前锁定：真实出图消耗额度，必须另行设计审批门。",
        "enabled": False,
    },
    {
        "action_id": "publish_meegle_writeback",
        "label": "发布飞书评论",
        "group": "高风险动作",
        "stage": "协同",
        "tier": "locked",
        "produces": ["外部系统评论"],
        "description": "当前锁定：会影响外部系统，不能作为普通按钮执行。",
        "enabled": False,
    },
    {
        "action_id": "publish_meegle_transition",
        "label": "流转飞书节点",
        "group": "高风险动作",
        "stage": "协同",
        "tier": "locked",
        "produces": ["外部流程状态变更"],
        "description": "当前锁定：会改变工作流状态，必须显式确认。",
        "enabled": False,
    },
)


AUTOPILOT_SEQUENCE = (
    "create_requirement_clarification_report",
    "create_style_transfer_report",
    "create_style_alignment_report",
    "create_design_decision_record",
    "create_image_production_batch",
    "create_design_workflow_plan",
    "create_designer_review_packet",
    "create_delivery_readiness_report",
    "create_learning_digest",
)


def run_console_server(
    root: Path,
    host: str = "127.0.0.1",
    port: int = 8787,
    project_key: str | None = None,
    work_item_id: str | None = None,
) -> None:
    root = root.resolve()
    app = DesignCopilotApp(root)
    paths = AppPaths.from_root(root)

    class ConsoleHandler(BaseHTTPRequestHandler):
        server_version = "CrealityOSWorkbench/0.2"

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._send_json({"ok": True, "time": datetime.now().isoformat(timespec="seconds")})
                return
            if parsed.path == "/api/actions":
                self._send_json(_available_actions())
                return
            if parsed.path == "/api/state":
                self._send_json(_state_from_request(parsed.query, app, paths, project_key, work_item_id))
                return
            if parsed.path == "/file":
                self._send_file(parsed.query, root)
                return
            if parsed.path in ("", "/"):
                payload = _state_from_request(parsed.query, app, paths, project_key, work_item_id)
                self._send_html(render_console_html(payload))
                return
            self.send_error(404, "Not found")

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
            parsed = urlparse(self.path)
            payload = self._read_json_body()
            if parsed.path == "/api/intake/resolve":
                self._send_json(_resolve_intake_link(payload, paths))
                return
            if parsed.path == "/api/action/run":
                result = _run_action_from_payload(payload, app, paths, project_key, work_item_id)
                self._send_json(result, 200 if result.get("ok") else 400)
                return
            self.send_error(404, "Not found")

        def log_message(self, format: str, *args) -> None:  # noqa: A002 - stdlib name
            return

        def _read_json_body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if not length:
                return {}
            raw = self.rfile.read(length)
            try:
                return json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                return {}

        def _send_json(self, payload: dict, status: int = 200) -> None:
            raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _send_html(self, html: str) -> None:
            raw = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _send_file(self, query: str, root_dir: Path) -> None:
            raw_path = parse_qs(query).get("path", [""])[0]
            if not raw_path:
                self.send_error(400, "Missing path")
                return
            path = Path(unquote(raw_path)).resolve()
            try:
                path.relative_to(root_dir)
            except ValueError:
                self.send_error(403, "File is outside console root")
                return
            if not path.exists() or not path.is_file():
                self.send_error(404, "File not found")
                return
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            raw = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    server = ThreadingHTTPServer((host, port), ConsoleHandler)
    print(f"CrealityOS Workbench running at http://{host}:{port}/")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _state_from_request(
    query: str,
    app: DesignCopilotApp,
    paths: AppPaths,
    default_project_key: str | None,
    default_work_item_id: str | None,
) -> dict:
    params = parse_qs(query)
    requested_project = _first(params.get("project")) or _first(params.get("project_key")) or default_project_key
    requested_work_item = _first(params.get("work_item")) or _first(params.get("work_item_id")) or default_work_item_id
    resolver = ArtifactResolver(paths)
    projects = discover_projects(paths)
    selection = resolver.resolve(project_key=requested_project, work_item_id=requested_work_item)

    dashboard_result = app.dashboard(
        project_key=selection.project_key,
        work_item_id=selection.work_item_id,
        output_dir=str(selection.output_dir) if selection.output_dir else None,
    )
    payload = load_json(Path(dashboard_result["dashboard_data"]), {})
    artifact_index = payload.get("artifact_index") or {}
    extra_payloads = {
        key: load_json(Path(value), None)
        for key, value in artifact_index.items()
        if value and Path(value).suffix.lower() == ".json"
    }
    work_items = discover_work_items(paths, selection.project_key)
    output_dir = str(selection.output_dir) if selection.output_dir else payload.get("cockpit", {}).get("output_dir")
    payload["console"] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "project_key": selection.project_key,
        "work_item_id": selection.work_item_id,
        "output_dir": output_dir,
        "requested_project_key": selection.requested_project_key,
        "requested_work_item_id": selection.requested_work_item_id,
        "corrected": selection.corrected,
        "notices": selection.notices,
        "warnings": selection.warnings,
        "projects": projects,
        "work_items": work_items,
        "extra_payloads": extra_payloads,
        "routes": {
            "state": "/api/state",
            "actions": "/api/actions",
            "run_action": "/api/action/run",
            "intake": "/api/intake/resolve",
            "health": "/health",
        },
    }
    payload["asset_previews"] = _asset_previews(payload, paths.root)
    payload["workbench"] = {
        "version": "0.2",
        "actions": _available_actions(),
        "planar_analysis": _planar_analysis(payload),
        "output_matrix": _output_matrix(payload),
        "asset_inventory": _asset_inventory(payload, paths.root),
        "safety": {
            "safe": "只写本地产物，不发布、不出图、不覆盖正式文件。",
            "confirm": "会生成执行包或协同草稿，需要设计师确认。",
            "locked": "高风险动作当前锁定，不从工作台直接执行。",
        },
    }
    return payload


def _available_actions() -> dict:
    actions = [dict(action, enabled=action.get("enabled", True)) for action in ACTION_DEFINITIONS]
    by_id = {action["action_id"]: action for action in actions}
    return {
        "actions": actions,
        "autopilot_sequence": [by_id[action_id] for action_id in AUTOPILOT_SEQUENCE if action_id in by_id],
        "groups": list(dict.fromkeys(action["group"] for action in actions)),
        "tiers": ["safe", "confirm", "locked"],
    }


def _run_action_from_payload(
    payload: dict,
    app: DesignCopilotApp,
    paths: AppPaths,
    default_project_key: str | None = None,
    default_work_item_id: str | None = None,
) -> dict:
    action_id = str(payload.get("action_id") or "")
    action = _find_action(action_id)
    if not action:
        return {"ok": False, "error": f"Unknown action: {action_id}", "allowed_actions": [item["action_id"] for item in ACTION_DEFINITIONS]}
    if not action.get("enabled", True) or action.get("tier") == "locked":
        return {"ok": False, "action_id": action_id, "error": "This action is locked by the safety gate.", "tier": action.get("tier")}
    if action.get("tier") == "confirm" and payload.get("confirmation") != "confirmed":
        return {"ok": False, "action_id": action_id, "requires_confirmation": True, "error": "Designer confirmation is required before running this action."}

    resolver = ArtifactResolver(paths)
    selection = resolver.resolve(
        project_key=str(payload.get("project_key") or default_project_key or ""),
        work_item_id=str(payload.get("work_item_id") or default_work_item_id or "") or None,
    )
    project_key = selection.project_key
    work_item_id = selection.work_item_id
    if action_id != "create_learning_digest" and not work_item_id:
        return {"ok": False, "action_id": action_id, "error": "work_item_id is required for this action."}

    started = datetime.now().isoformat(timespec="seconds")
    try:
        result = _execute_action(action_id, app, project_key, work_item_id, payload)
    except Exception as exc:  # pragma: no cover - returned to browser for diagnosis
        return {
            "ok": False,
            "action_id": action_id,
            "project_key": project_key,
            "work_item_id": work_item_id,
            "started_at": started,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "error": str(exc),
            "traceback": traceback.format_exc(limit=6),
        }

    return {
        "ok": True,
        "action_id": action_id,
        "label": action["label"],
        "project_key": project_key,
        "work_item_id": work_item_id,
        "started_at": started,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "result": result,
    }


def _execute_action(action_id: str, app: DesignCopilotApp, project_key: str, work_item_id: str | None, payload: dict) -> dict:
    if action_id == "refresh_state":
        return {"status": "refreshed"}
    if action_id == "create_requirement_clarification_report":
        return app.create_requirement_clarification_report(project_key=project_key, work_item_id=work_item_id)
    if action_id == "create_style_transfer_report":
        return app.create_style_transfer_report(project_key=project_key, work_item_id=work_item_id)
    if action_id == "create_style_alignment_report":
        return app.create_style_alignment_report(project_key=project_key, work_item_id=work_item_id)
    if action_id == "create_design_decision_record":
        return app.create_design_decision_record(project_key=project_key, work_item_id=work_item_id)
    if action_id == "create_image_production_batch":
        return app.create_image_production_batch(project_key=project_key, work_item_id=work_item_id)
    if action_id == "create_design_workflow_plan":
        return app.create_design_workflow_plan(project_key=project_key, work_item_id=work_item_id)
    if action_id == "create_designer_review_packet":
        return app.create_designer_review_packet(project_key=project_key, work_item_id=work_item_id)
    if action_id == "create_delivery_readiness_report":
        return app.create_delivery_readiness_report(project_key=project_key, work_item_id=work_item_id)
    if action_id == "create_learning_digest":
        return app.create_learning_digest(project_key=project_key)
    if action_id == "create_image_generation_jobs":
        variants = payload.get("variants") or ["V01"]
        return app.create_image_generation_jobs(project_key=project_key, work_item_id=work_item_id, variants=variants)
    if action_id == "prepare_image_execution_package":
        return app.prepare_image_execution_package(project_key=project_key, work_item_id=work_item_id)
    if action_id == "create_psd_handoff_plan":
        return app.create_psd_handoff_plan(project_key=project_key, work_item_id=work_item_id, selected_assets=payload.get("selected_assets"))
    if action_id == "prepare_psd_handoff_package":
        return app.prepare_psd_handoff_package(project_key=project_key, work_item_id=work_item_id)
    if action_id == "create_psd_slice_spec_report":
        return app.create_psd_slice_spec_report(project_key=project_key, work_item_id=work_item_id)
    if action_id == "create_meegle_writeback_draft":
        return app.create_meegle_writeback_draft(project_key=project_key, work_item_id=work_item_id)
    raise ValueError(f"No executor for action: {action_id}")


def _resolve_intake_link(payload: dict, paths: AppPaths) -> dict:
    raw = str(payload.get("url") or payload.get("link") or payload.get("text") or "").strip()
    project_key = str(payload.get("project_key") or "").strip() or None
    work_item_id = str(payload.get("work_item_id") or "").strip() or None
    numbers = re.findall(r"\d{4,}", raw)
    if not work_item_id and numbers:
        work_item_id = numbers[-1]
    project_match = re.search(r"(?:project|project_key|space)[=/]([A-Za-z0-9_-]+)", raw)
    if not project_key and project_match:
        project_key = project_match.group(1)
    owner = ArtifactResolver(paths).find_work_item(work_item_id) if work_item_id else None
    if owner and not project_key:
        project_key = owner[0]
    return {
        "ok": bool(project_key or work_item_id),
        "input": raw,
        "project_key": project_key,
        "work_item_id": work_item_id,
        "matched_local_project": owner[0] if owner else None,
        "matched_output_dir": str(owner[1]) if owner else None,
        "warnings": [] if (project_key or work_item_id) else ["未能从输入中识别 project_key 或 work_item_id。"],
    }


def _find_action(action_id: str) -> dict | None:
    return next((action for action in ACTION_DEFINITIONS if action["action_id"] == action_id), None)


def _planar_analysis(payload: dict) -> dict:
    brief = payload.get("design_brief") or (payload.get("creative_pack") or {}).get("brief") or {}
    raw_text = "\n".join(
        str(item or "")
        for item in (
            brief.get("objective"),
            brief.get("source_requirement_summary"),
            brief.get("summary"),
            brief.get("style_direction"),
        )
    )
    return {
        "primary_source": "平面需求描述",
        "title": brief.get("title"),
        "game_name": brief.get("game_name"),
        "summary": brief.get("source_requirement_summary") or brief.get("summary") or "未读取到需求摘要。",
        "style_direction": brief.get("style_direction") or "待确认",
        "sizes": _as_list(brief.get("sizes")),
        "deliverables": _as_list(brief.get("deliverables")),
        "deadline": brief.get("deadline") or "待确认",
        "target_audience": brief.get("target_audience") or "待确认",
        "platform": brief.get("platform") or brief.get("platforms") or "待确认",
        "risk_points": _as_list(brief.get("risk_points")),
        "missing_information": _as_list(brief.get("missing_information")),
        "signals": {
            "mentions_psd": "psd" in raw_text.lower(),
            "mentions_slice": "切图" in raw_text or "slice" in raw_text.lower(),
            "mentions_storyboard": any(token in raw_text for token in ("分镜", "片头", "剧情")),
            "mentions_video": any(token.lower() in raw_text.lower() for token in ("mp4", "video", "视频", "gif")),
        },
    }


def _output_matrix(payload: dict) -> list[dict]:
    brief = payload.get("design_brief") or (payload.get("creative_pack") or {}).get("brief") or {}
    artifact_index = payload.get("artifact_index") or {}
    text = json.dumps(brief, ensure_ascii=False).lower()
    deliverables = [item.lower() for item in _as_list(brief.get("deliverables"))]
    needs_image = not deliverables or any(item in {"png", "jpg", "jpeg", "webp", "gif", "mp4"} for item in deliverables)
    needs_psd = "psd" in deliverables or "psd" in text
    needs_slice = "切图" in text or "slice" in text or "slicing" in text
    return [
        {
            "output_id": "image",
            "label": "图片",
            "selected": needs_image,
            "dependency": "创作包、风格门、出图方案",
            "status": "done" if artifact_index.get("image_generation_results") else ("ready" if artifact_index.get("image_generation_batch") else "pending"),
            "format": ", ".join(_as_list(brief.get("deliverables"))) or "PNG/JPG",
            "next_action": "create_image_production_batch",
        },
        {
            "output_id": "psd",
            "label": "PSD",
            "selected": needs_psd,
            "dependency": "候选图、PSD 交接计划",
            "status": "done" if artifact_index.get("psd_handoff_package") else ("ready" if artifact_index.get("psd_handoff_plan") else "pending"),
            "format": "PSD",
            "next_action": "create_psd_handoff_plan",
        },
        {
            "output_id": "slice_demo",
            "label": "切图 + 示意图",
            "selected": needs_slice or needs_psd,
            "dependency": "PSD、切图命名、尺寸表",
            "status": "done" if artifact_index.get("psd_slice_spec_report") else "pending",
            "format": "PNG",
            "next_action": "create_psd_slice_spec_report",
        },
        {
            "output_id": "writeback",
            "label": "飞书回写",
            "selected": False,
            "dependency": "评审包、交付检查",
            "status": "done" if artifact_index.get("meegle_writeback_draft") else "pending",
            "format": "Markdown 草稿",
            "next_action": "create_meegle_writeback_draft",
        },
    ]


def _asset_inventory(payload: dict, root: Path) -> dict:
    raw_output_dir = (payload.get("console") or {}).get("output_dir")
    output_dir = Path(raw_output_dir) if raw_output_dir else None
    items: list[dict] = []
    if output_dir and output_dir.exists():
        for path in sorted(output_dir.rglob("*"))[:600]:
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".mov", ".psd", ".psb", ".md", ".json"}:
                items.append(_asset_item(path, root, "run"))
    for preview in payload.get("asset_previews") or []:
        path = Path(preview.get("path", ""))
        if path.exists():
            items.append(_asset_item(path, root, "preview"))
    unique: dict[str, dict] = {}
    for item in items:
        unique[item["path"]] = item
    counts: dict[str, int] = {}
    for item in unique.values():
        counts[item["type"]] = counts.get(item["type"], 0) + 1
    return {
        "items": list(unique.values())[:80],
        "counts": counts,
        "total": len(unique),
        "warnings": [] if unique else ["未在当前运行目录中发现可预览素材。"],
    }


def _asset_item(path: Path, root: Path, source: str) -> dict:
    suffix = path.suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        kind = "image"
    elif suffix in {".mp4", ".mov"}:
        kind = "video"
    elif suffix in {".psd", ".psb"}:
        kind = "psd"
    elif suffix == ".md":
        kind = "doc"
    elif suffix == ".json":
        kind = "data"
    else:
        kind = "asset"
    url = f"/file?path={quote(str(path.resolve()))}" if path.exists() and path.is_file() else None
    try:
        display_path = str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        display_path = str(path.resolve())
    return {
        "name": path.name,
        "path": str(path.resolve()),
        "display_path": display_path,
        "type": kind,
        "source": source,
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "url": url,
    }


def _asset_previews(payload: dict, root: Path) -> list[dict]:
    previews: list[dict] = []
    for source in (payload.get("console", {}).get("extra_payloads") or {}).values():
        previews.extend(_asset_paths(source, root))
    seen = set()
    unique = []
    for item in previews:
        key = item["path"]
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique[:16]


def _asset_paths(value, root: Path) -> list[dict]:
    found: list[dict] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"path", "uri", "source_path", "staged_root"} and isinstance(item, str):
                found.extend(_asset_paths(item, root))
            else:
                found.extend(_asset_paths(item, root))
    elif isinstance(value, list):
        for item in value:
            found.extend(_asset_paths(item, root))
    elif isinstance(value, str):
        suffix = Path(value).suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            path = Path(value)
            if not path.is_absolute():
                path = root / value
            if path.exists():
                found.append({"path": str(path.resolve()), "name": path.name, "url": f"/file?path={quote(str(path.resolve()))}"})
    return found


def render_console_html(payload: dict) -> str:
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    title = escape(_page_title(payload))
    html = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__TITLE__</title>
  <style>
    :root {
      --ink: #222421;
      --muted: #6c716d;
      --paper: #efede3;
      --panel: #fffdf6;
      --line: #d7d0c1;
      --rail: #1e2421;
      --rail-soft: #29302c;
      --green: #0d6b57;
      --blue: #265f93;
      --amber: #9b6517;
      --red: #a33c32;
      --violet: #65508c;
      --shadow: 0 18px 48px rgba(37, 35, 27, .12);
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      color: var(--ink);
      background:
        linear-gradient(90deg, rgba(31, 37, 33, .045) 1px, transparent 1px),
        linear-gradient(rgba(31, 37, 33, .045) 1px, transparent 1px),
        var(--paper);
      background-size: 34px 34px, 34px 34px, auto;
      font-family: "Aptos", "Segoe UI", "Microsoft YaHei UI", sans-serif;
      letter-spacing: 0;
    }
    button, input, select, textarea { font: inherit; }
    button { cursor: pointer; }
    .app { min-height: 100vh; display: grid; grid-template-columns: 286px minmax(0, 1fr); }
    .rail {
      position: sticky; top: 0; height: 100vh; overflow: auto;
      background: linear-gradient(180deg, var(--rail), #171b19);
      color: #f7f1e5; padding: 24px 16px; border-right: 1px solid #101411;
    }
    .brand { font-family: Georgia, "Times New Roman", serif; font-size: 30px; line-height: 1; }
    .subtitle { color: #cfc7b8; font-size: 12px; margin-top: 8px; line-height: 1.5; }
    .modeSwitch { display: grid; grid-template-columns: 1fr 1fr; border: 1px solid rgba(247,241,229,.18); margin: 22px 0 14px; }
    .modeSwitch button { border: 0; background: transparent; color: #f7f1e5; padding: 10px 8px; }
    .modeSwitch button.active { background: #f7f1e5; color: #1d2320; font-weight: 800; }
    .selector { display: grid; gap: 10px; margin: 16px 0; }
    .selector label { display: grid; gap: 5px; color: #cfc7b8; font-size: 12px; }
    .selector select, .selector input, .selector textarea {
      width: 100%; border: 1px solid rgba(247,241,229,.2); background: var(--rail-soft);
      color: #f7f1e5; padding: 10px; border-radius: 0;
    }
    .selector textarea { min-height: 78px; resize: vertical; }
    .railBtn { width: 100%; border: 1px solid rgba(247,241,229,.25); background: #f7f1e5; color: #1d2320; padding: 10px; font-weight: 800; }
    .ghostBtn { width: 100%; border: 1px solid rgba(247,241,229,.2); background: transparent; color: #f7f1e5; padding: 10px; }
    .nav { display: grid; gap: 7px; margin-top: 18px; }
    .nav a { color: inherit; text-decoration: none; padding: 10px; border: 1px solid rgba(247,241,229,.13); background: rgba(255,255,255,.04); }
    .main { padding: 24px clamp(16px, 2.8vw, 38px) 48px; }
    .topline { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(320px, .75fr); gap: 14px; margin-bottom: 14px; }
    .panel { background: rgba(255,253,246,.96); border: 1px solid var(--line); box-shadow: var(--shadow); padding: 16px; min-width: 0; }
    .hero { min-height: 238px; display: flex; flex-direction: column; justify-content: space-between; }
    .eyebrow { color: var(--muted); text-transform: uppercase; font-size: 12px; font-weight: 800; }
    h1 { margin: 12px 0 10px; font-family: Georgia, "Times New Roman", "Microsoft YaHei UI", serif; font-size: clamp(34px, 4vw, 64px); line-height: .98; letter-spacing: 0; }
    h2 { margin: 0 0 12px; font-size: 15px; line-height: 1.25; }
    h3 { margin: 0 0 8px; font-size: 13px; }
    .summary, .copy { line-height: 1.62; overflow-wrap: anywhere; color: #3f4641; }
    .chips { display: flex; flex-wrap: wrap; gap: 8px; }
    .chip { border: 1px solid #cfc5b4; background: #fbf7ee; padding: 7px 9px; font-size: 12px; line-height: 1.2; }
    .chip.safe, .chip.done, .chip.ready { color: var(--green); border-color: currentColor; }
    .chip.confirm, .chip.waiting, .chip.needs_designer_confirmation { color: var(--amber); border-color: currentColor; }
    .chip.locked, .chip.blocked { color: var(--red); border-color: currentColor; }
    .metrics { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
    .metric { border: 1px solid var(--line); background: #faf6ec; padding: 12px; min-height: 78px; }
    .metric span { display: block; color: var(--muted); font-size: 12px; margin-bottom: 7px; }
    .metric strong { font-size: 22px; }
    .noticeBar { display: none; margin: 0 0 14px; border: 1px solid #d4ae5d; background: #fff4d7; color: #573b09; padding: 11px 13px; line-height: 1.45; }
    .grid { display: grid; grid-template-columns: repeat(12, 1fr); gap: 14px; }
    .span3 { grid-column: span 3; } .span4 { grid-column: span 4; } .span5 { grid-column: span 5; }
    .span6 { grid-column: span 6; } .span7 { grid-column: span 7; } .span8 { grid-column: span 8; } .span12 { grid-column: span 12; }
    .matrix { display: grid; gap: 8px; }
    .matrixRow, .node, .artifact, .asset, .logItem {
      border: 1px solid #e2dacb; background: #fbf7ee; padding: 10px; overflow-wrap: anywhere;
    }
    .matrixRow { display: grid; grid-template-columns: 30px minmax(90px, .7fr) minmax(0, 1fr) 92px; gap: 10px; align-items: center; }
    .matrixRow input { width: 18px; height: 18px; }
    .status { font-size: 12px; font-weight: 800; color: var(--blue); }
    .actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 9px; }
    .node { display: grid; gap: 8px; align-content: start; }
    .node button { border: 1px solid #2a332e; background: #2a332e; color: #fff8ec; padding: 9px; font-weight: 800; }
    .node button:disabled { opacity: .45; cursor: not-allowed; }
    .node small { color: var(--muted); line-height: 1.45; }
    .node .produces { color: var(--blue); font-size: 12px; }
    .confirmLine { display: flex; gap: 7px; align-items: center; font-size: 12px; color: var(--muted); }
    .confirmLine input { width: 16px; height: 16px; }
    .list { display: grid; gap: 8px; margin: 0; padding: 0; list-style: none; }
    .list li { border: 1px solid #e2dacb; background: #fbf7ee; padding: 10px; line-height: 1.45; overflow-wrap: anywhere; }
    .assetGrid, .artifactGrid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 8px; }
    .asset b, .artifact b { display: block; margin-bottom: 5px; }
    .missing { opacity: .48; }
    .previewGrid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 9px; }
    .preview { border: 1px solid #e2dacb; background: #fbf7ee; padding: 8px; }
    .preview img { width: 100%; aspect-ratio: 4 / 3; object-fit: contain; display: block; background: #eee7da; border: 1px solid #ddd2c1; }
    .log { max-height: 360px; overflow: auto; display: grid; gap: 8px; }
    .logItem.ok { border-left: 4px solid var(--green); }
    .logItem.fail { border-left: 4px solid var(--red); }
    code { font-family: "Cascadia Mono", "Consolas", monospace; font-size: 12px; }
    @media (max-width: 1120px) {
      .app { grid-template-columns: 1fr; }
      .rail { position: relative; height: auto; }
      .topline { grid-template-columns: 1fr; }
      .grid { grid-template-columns: 1fr; }
      .span3,.span4,.span5,.span6,.span7,.span8,.span12 { grid-column: 1 / -1; }
      .matrixRow { grid-template-columns: 28px 1fr; }
    }
  </style>
</head>
<body>
  <script id="console-data" type="application/json">__DATA__</script>
  <div class="app">
    <aside class="rail">
      <div class="brand">CrealityOS</div>
      <div class="subtitle">Workbench v0.2</div>
      <div class="modeSwitch">
        <button id="autoMode" class="active">自动档</button>
        <button id="manualMode">手动挡</button>
      </div>
      <div class="selector">
        <label>飞书项目链接或工作项 ID<textarea id="intakeInput" placeholder="粘贴飞书项目链接、工作项链接或工作项 ID"></textarea></label>
        <button class="railBtn" id="resolveIntake">识别接单信息</button>
        <label>Project<select id="projectSelect"></select></label>
        <label>Work item<select id="workItemSelect"></select></label>
        <button class="railBtn" id="openSelection">打开工作项</button>
        <button class="ghostBtn" id="reloadState">刷新状态</button>
      </div>
      <nav class="nav">
        <a href="#overview">总览</a>
        <a href="#outputs">产出矩阵</a>
        <a href="#actions">操作节点</a>
        <a href="#analysis">需求分析</a>
        <a href="#assets">素材</a>
        <a href="#artifacts">产物</a>
      </nav>
    </aside>
    <main class="main">
      <section class="topline" id="overview">
        <article class="panel hero">
          <div>
            <div class="eyebrow" id="eyebrow"></div>
            <h1 id="title"></h1>
            <div class="summary" id="summary"></div>
          </div>
          <div class="chips" id="heroChips"></div>
        </article>
        <article class="panel">
          <h2>状态仪表</h2>
          <div class="metrics" id="metrics"></div>
        </article>
      </section>
      <section class="noticeBar" id="contextNotice"></section>
      <section class="grid">
        <article class="panel span7" id="outputs">
          <h2>最终产出矩阵</h2>
          <div class="matrix" id="outputMatrix"></div>
        </article>
        <article class="panel span5">
          <h2>自动档队列</h2>
          <div class="actions" id="autopilotActions"></div>
        </article>
        <article class="panel span12" id="actions">
          <h2>手动挡功能节点</h2>
          <div class="actions" id="manualActions"></div>
        </article>
        <article class="panel span6" id="analysis">
          <h2>平面需求描述分析</h2>
          <div class="copy" id="planarAnalysis"></div>
        </article>
        <article class="panel span6">
          <h2>最终产出分析</h2>
          <ul class="list" id="outputAnalysis"></ul>
        </article>
        <article class="panel span7" id="assets">
          <h2>可用素材</h2>
          <div class="chips" id="assetCounts"></div>
          <div class="assetGrid" id="assetGrid"></div>
        </article>
        <article class="panel span5">
          <h2>执行日志</h2>
          <div class="log" id="runLog"></div>
        </article>
        <article class="panel span6">
          <h2>预览图</h2>
          <div class="previewGrid" id="previews"></div>
        </article>
        <article class="panel span6">
          <h2>下一步命令</h2>
          <ul class="list" id="commands"></ul>
        </article>
        <article class="panel span12" id="artifacts">
          <h2>产物索引</h2>
          <div class="artifactGrid" id="artifactsGrid"></div>
        </article>
      </section>
    </main>
  </div>
  <script>
    const data = JSON.parse(document.getElementById('console-data').textContent);
    const c = data.console || {};
    const cockpit = data.cockpit || {};
    const brief = data.design_brief || {};
    const creative = data.creative_pack || {};
    const workflow = data.workflow_plan || {};
    const readiness = data.delivery_readiness || {};
    const workbench = data.workbench || {};
    const esc = value => String(value ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'","&#039;");
    const arr = value => Array.isArray(value) ? value.filter(Boolean) : (value ? [value] : []);
    const text = (value, fallback='待确认') => arr(value).join('，') || value || fallback;
    const logBox = document.getElementById('runLog');

    function addLog(item) {
      const ok = item.ok !== false;
      const div = document.createElement('div');
      div.className = `logItem ${ok ? 'ok' : 'fail'}`;
      const result = item.result ? Object.entries(item.result).slice(0, 5).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`).join('<br>') : '';
      div.innerHTML = `<b>${esc(item.label || item.action_id || '动作')}</b><br><small>${esc(item.finished_at || new Date().toLocaleTimeString())}</small><br>${ok ? result : esc(item.error || '执行失败')}`;
      logBox.prepend(div);
    }

    function list(id, items, fallback='暂无') {
      const rows = Array.isArray(items) && items.length ? items : [fallback];
      document.getElementById(id).innerHTML = rows.map(item => `<li>${item && item.startsWith && item.startsWith('<code>') ? item : esc(item)}</li>`).join('');
    }

    function setMode(mode) {
      document.body.dataset.mode = mode;
      document.getElementById('autoMode').classList.toggle('active', mode === 'auto');
      document.getElementById('manualMode').classList.toggle('active', mode === 'manual');
      document.getElementById('autopilotActions').style.opacity = mode === 'auto' ? '1' : '.46';
      document.getElementById('manualActions').style.opacity = mode === 'manual' ? '1' : '.72';
      localStorage.setItem('crealityos.mode', mode);
    }

    document.getElementById('autoMode').onclick = () => setMode('auto');
    document.getElementById('manualMode').onclick = () => setMode('manual');
    setMode(localStorage.getItem('crealityos.mode') || 'auto');

    const projectSelect = document.getElementById('projectSelect');
    projectSelect.innerHTML = (c.projects || []).map(p => `<option value="${esc(p.project_key)}">${esc(p.project_key)} / ${esc(p.source)}</option>`).join('') || `<option>${esc(c.project_key || 'EMPTY')}</option>`;
    projectSelect.value = c.project_key || projectSelect.value;
    const workItemSelect = document.getElementById('workItemSelect');
    workItemSelect.innerHTML = (c.work_items || []).map(item => `<option value="${esc(item.work_item_id)}">${esc(item.work_item_id)} / ${esc(item.title || '')}</option>`).join('') || `<option value="">Latest</option>`;
    workItemSelect.value = c.work_item_id || workItemSelect.value;
    document.getElementById('openSelection').onclick = () => {
      const p = encodeURIComponent(projectSelect.value);
      const w = encodeURIComponent(workItemSelect.value || '');
      location.href = `/?project=${p}${w ? `&work_item=${w}` : ''}`;
    };
    document.getElementById('reloadState').onclick = () => location.reload();

    document.getElementById('resolveIntake').onclick = async () => {
      const response = await fetch('/api/intake/resolve', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({url: document.getElementById('intakeInput').value})
      });
      const result = await response.json();
      addLog({ok: result.ok, label: '识别接单信息', result, error: (result.warnings || []).join('；')});
      if (result.project_key) projectSelect.value = result.project_key;
      if (result.work_item_id) {
        const option = Array.from(workItemSelect.options).find(item => item.value === result.work_item_id);
        if (option) workItemSelect.value = result.work_item_id;
      }
    };

    const status = cockpit.status || workflow.status || 'draft';
    document.getElementById('eyebrow').textContent = `${c.project_key || 'project'} / ${c.work_item_id || 'work item'}`;
    document.getElementById('title').textContent = brief.game_name || brief.title || cockpit.title || 'CrealityOS Workbench';
    document.getElementById('summary').textContent = cockpit.summary || brief.source_requirement_summary || brief.summary || '暂无活动设计需求。';
    document.getElementById('heroChips').innerHTML = [
      `<span class="chip ${esc(status)}">${esc(status)}</span>`,
      `<span class="chip">${esc(brief.same_category || '品类待确认')}</span>`,
      `<span class="chip">产物 ${data.artifact_counts?.present || 0}/${data.artifact_counts?.total || 0}</span>`
    ].join('');
    const contextMessages = [...(c.notices || []), ...(c.warnings || [])];
    if (contextMessages.length) {
      const notice = document.getElementById('contextNotice');
      notice.style.display = 'block';
      notice.innerHTML = `<b>上下文已解析</b><br>${contextMessages.map(esc).join('<br>')}`;
    }
    document.getElementById('metrics').innerHTML = [
      ['阻塞', (cockpit.blockers || readiness.blockers || []).length],
      ['待确认', (cockpit.confirmations || []).length],
      ['素材', workbench.asset_inventory?.total || 0],
      ['动作', workbench.actions?.actions?.filter(a => a.enabled).length || 0],
    ].map(([label, value]) => `<div class="metric"><span>${label}</span><strong>${value}</strong></div>`).join('');

    const outputRows = workbench.output_matrix || [];
    document.getElementById('outputMatrix').innerHTML = outputRows.map(row => `
      <div class="matrixRow">
        <input type="checkbox" data-output="${esc(row.output_id)}" ${row.selected ? 'checked' : ''}>
        <b>${esc(row.label)}</b>
        <span>${esc(row.dependency)}<br><small>${esc(row.format)}</small></span>
        <span class="status">${esc(row.status)}</span>
      </div>
    `).join('');
    list('outputAnalysis', outputRows.map(row => `${row.label}：${row.selected ? '建议产出' : '可选'}；前置：${row.dependency}；下一步：${row.next_action}`));

    const pa = workbench.planar_analysis || {};
    document.getElementById('planarAnalysis').innerHTML = `
      <b>主依据</b><br>${esc(pa.primary_source || '平面需求描述')}<br><br>
      <b>需求摘要</b><br>${esc(pa.summary || '待确认')}<br><br>
      <b>风格方向</b><br>${esc(pa.style_direction || '待确认')}<br><br>
      <b>尺寸 / 交付</b><br>${esc(text(pa.sizes))} / ${esc(text(pa.deliverables))}<br><br>
      <b>缺失信息</b><br>${esc(text(pa.missing_information, '暂无'))}
    `;

    async function runAction(action) {
      const confirmation = action.tier === 'confirm' ? document.getElementById(`confirm-${action.action_id}`)?.checked : false;
      const payload = {
        action_id: action.action_id,
        project_key: c.project_key,
        work_item_id: c.work_item_id,
        confirmation: confirmation ? 'confirmed' : undefined
      };
      const response = await fetch('/api/action/run', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      const result = await response.json();
      addLog(result);
      if (result.ok) setTimeout(() => location.reload(), 800);
    }

    function actionNode(action) {
      const locked = !action.enabled || action.tier === 'locked';
      return `
        <div class="node">
          <div class="chips"><span class="chip ${esc(action.tier)}">${esc(action.stage)}</span><span class="chip ${esc(action.tier)}">${esc(action.tier)}</span></div>
          <b>${esc(action.label)}</b>
          <small>${esc(action.description)}</small>
          <div class="produces">${esc((action.produces || []).join(' / '))}</div>
          ${action.tier === 'confirm' ? `<label class="confirmLine"><input id="confirm-${esc(action.action_id)}" type="checkbox">确认生成执行包/草稿</label>` : ''}
          <button data-action="${esc(action.action_id)}" ${locked ? 'disabled' : ''}>${locked ? '已锁定' : '执行'}</button>
        </div>
      `;
    }

    const actions = workbench.actions?.actions || [];
    document.getElementById('autopilotActions').innerHTML = (workbench.actions?.autopilot_sequence || []).map(actionNode).join('');
    document.getElementById('manualActions').innerHTML = actions.map(actionNode).join('');
    document.querySelectorAll('button[data-action]').forEach(button => {
      const action = actions.find(item => item.action_id === button.dataset.action);
      button.onclick = () => runAction(action);
    });

    const inventory = workbench.asset_inventory || {};
    document.getElementById('assetCounts').innerHTML = Object.entries(inventory.counts || {}).map(([key, value]) => `<span class="chip">${esc(key)} ${value}</span>`).join('') || '<span class="chip">暂无素材</span>';
    document.getElementById('assetGrid').innerHTML = (inventory.items || []).slice(0, 24).map(item => `
      <div class="asset"><b>${esc(item.name)}</b><span>${esc(item.type)} / ${esc(item.source)}</span><br><small>${esc(item.display_path)}</small></div>
    `).join('') || '<div class="copy">暂无可用素材。</div>';

    document.getElementById('previews').innerHTML = (data.asset_previews || []).length
      ? data.asset_previews.map(item => `<div class="preview"><img src="${esc(item.url)}" alt=""><small>${esc(item.name)}</small></div>`).join('')
      : '<div class="copy">暂无本地预览图。</div>';
    list('commands', (cockpit.next_commands || workflow.next_commands || []).map(cmd => `<code>${esc(cmd)}</code>`), '暂无推荐命令。');
    const artifactIndex = data.artifact_index || {};
    document.getElementById('artifactsGrid').innerHTML = Object.entries(artifactIndex).map(([key, value]) => `
      <div class="artifact ${value ? '' : 'missing'}"><b>${esc(key)}</b><span>${esc(value || '缺失')}</span></div>
    `).join('');
  </script>
</body>
</html>"""
    return html.replace("__TITLE__", title).replace("__DATA__", data)


def _first(values: list[str] | None) -> str | None:
    if not values:
        return None
    value = values[0].strip()
    return value or None


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if item]
    if isinstance(value, tuple):
        return [item for item in value if item]
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[,，、/]+", value) if item.strip()]
    return [value]


def _page_title(payload: dict) -> str:
    console = payload.get("console") or {}
    brief = payload.get("design_brief") or {}
    return f"CrealityOS Workbench - {brief.get('title') or console.get('work_item_id') or console.get('project_key') or 'local'}"
