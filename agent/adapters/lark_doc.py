from __future__ import annotations

from agent.models import RequirementDoc
from agent.shell import CommandError, ShellRunner
from agent.utils import first_non_empty


class LarkDocAdapter:
    def __init__(self, runner: ShellRunner) -> None:
        self.runner = runner

    def fetch_doc(self, token_or_url: str) -> RequirementDoc:
        payload = self.runner.run(
            [
                "lark-cli",
                "docs",
                "+fetch",
                "--api-version",
                "v2",
                "--doc",
                token_or_url,
                "--doc-format",
                "markdown",
                "--detail",
                "simple",
                "--format",
                "json",
            ]
        ).json()
        data = payload.get("data", payload)
        title = first_non_empty(
            [
                str(data.get("title", "")),
                str(data.get("meta", {}).get("title", "")) if isinstance(data.get("meta"), dict) else "",
            ]
        )
        content = first_non_empty(
            [
                str(data.get("content", "")),
                str(data.get("document", "")),
                str(data.get("markdown", "")),
            ]
        )
        return RequirementDoc(source="lark-doc", token_or_url=token_or_url, title=title or None, content=content)

    def fetch_docs(self, doc_links: list[str]) -> list[RequirementDoc]:
        documents: list[RequirementDoc] = []
        for link in doc_links:
            try:
                documents.append(self.fetch_doc(link))
            except CommandError:
                documents.append(
                    RequirementDoc(
                        source="lark-doc",
                        token_or_url=link,
                        title=None,
                        content="",
                    )
                )
        return documents
