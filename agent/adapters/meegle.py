from __future__ import annotations

from typing import Any

from agent.models import WorkItemContext
from agent.shell import CommandError, ShellRunner
from agent.utils import find_doc_links, first_non_empty, stringify


class MeegleAdapter:
    def __init__(self, runner: ShellRunner) -> None:
        self.runner = runner

    def fetch_todos(self, action: str = "todo", asset_key: str | None = None, max_pages: int = 1) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for page in range(1, max_pages + 1):
            command = ["meegle", "mywork", "todo", "--action", action, "--page-num", str(page), "-o", "json"]
            if asset_key:
                command.extend(["--asset-key", asset_key])
            payload = self.runner.run(command).json()
            records = self._extract_records(payload)
            if not records:
                break
            items.extend(records)
        return items

    def fetch_workitem_context(self, project_key: str, work_item_id: str) -> WorkItemContext:
        item_payload = self.runner.run(
            [
                "meegle",
                "workitem",
                "get",
                "--project-key",
                project_key,
                "--work-item-id",
                work_item_id,
                "--fields",
                "_all",
                "-o",
                "json",
            ]
        ).json()
        comments = self._safe_fetch_comments(project_key, work_item_id)
        raw_item = self._unwrap_data(item_payload)
        title = self._pick_title(raw_item, fallback=work_item_id)
        doc_links = find_doc_links(raw_item)
        for comment in comments:
            doc_links.extend(find_doc_links(comment))
        return WorkItemContext(
            project_key=project_key,
            work_item_id=work_item_id,
            title=title,
            raw_item=raw_item,
            comments=comments,
            doc_links=list(dict.fromkeys(doc_links)),
        )

    def add_comment(self, project_key: str, work_item_id: str, content: str) -> dict[str, Any]:
        payload = self.runner.run(
            [
                "meegle",
                "comment",
                "add",
                "--project-key",
                project_key,
                "--work-item-id",
                work_item_id,
                "--content",
                content,
                "--format",
                "json",
            ]
        ).json()
        data = self._unwrap_data(payload)
        return data if isinstance(data, dict) else {"data": data}

    def transition_workflow(
        self,
        project_key: str,
        work_item_id: str,
        action: str,
        node_id: str | None = None,
        node_names: list[str] | None = None,
        rollback_reason: str | None = None,
    ) -> dict[str, Any]:
        command = [
            "meegle",
            "workflow",
            "transition",
            "--project-key",
            project_key,
            "--work-item-id",
            work_item_id,
            "--action",
            action,
            "--format",
            "json",
        ]
        if node_id:
            command.extend(["--node-id", node_id])
        if node_names:
            command.extend(["--node-ids", ",".join(node_names)])
        if rollback_reason:
            command.extend(["--rollback-reason", rollback_reason])
        payload = self.runner.run(command).json()
        data = self._unwrap_data(payload)
        return data if isinstance(data, dict) else {"data": data}

    def _safe_fetch_comments(self, project_key: str, work_item_id: str) -> list[dict[str, Any]]:
        try:
            payload = self.runner.run(
                [
                    "meegle",
                    "comment",
                    "list",
                    "--project-key",
                    project_key,
                    "--work-item-id",
                    work_item_id,
                    "-o",
                    "json",
                ]
            ).json()
        except CommandError:
            return []
        return self._extract_records(payload)

    @staticmethod
    def _extract_records(payload: Any) -> list[dict[str, Any]]:
        data = MeegleAdapter._unwrap_data(payload)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            for key in ("items", "list", "records", "data"):
                value = data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
            return [data]
        return []

    @staticmethod
    def _unwrap_data(payload: Any) -> Any:
        if isinstance(payload, dict):
            if "data" in payload and payload["data"] not in (None, {}):
                return payload["data"]
            return payload
        return payload

    @staticmethod
    def _pick_title(raw_item: dict[str, Any], fallback: str) -> str:
        candidates: list[str] = []
        for key in ("title", "name", "summary", "subject"):
            value = raw_item.get(key)
            if value:
                candidates.append(stringify(value))
        for key, value in raw_item.items():
            lower = key.lower()
            if any(token in lower for token in ("title", "name", "summary", "标题", "名称")):
                candidates.append(stringify(value))
        return first_non_empty(candidates) or fallback
