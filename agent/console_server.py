from __future__ import annotations

import json
import mimetypes
from datetime import datetime
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from agent.app import DesignCopilotApp
from agent.artifact_resolver import ArtifactResolver, discover_projects, discover_work_items
from agent.settings import AppPaths
from agent.utils import load_json


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
        server_version = "CrealityOSConsole/0.1"

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._send_json({"ok": True, "time": datetime.now().isoformat(timespec="seconds")})
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

        def log_message(self, format: str, *args) -> None:  # noqa: A002 - stdlib name
            return

        def _send_json(self, payload: dict) -> None:
            raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(200)
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
    print(f"CrealityOS Console running at http://{host}:{port}/")
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
    payload["console"] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "project_key": selection.project_key,
        "work_item_id": selection.work_item_id,
        "output_dir": str(selection.output_dir) if selection.output_dir else payload.get("cockpit", {}).get("output_dir"),
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
            "health": "/health",
        },
    }
    payload["asset_previews"] = _asset_previews(payload, paths.root)
    return payload


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
    title = _page_title(payload)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      --paper: #f1eee6;
      --ink: #202322;
      --muted: #6b716c;
      --panel: #fffdf6;
      --line: #d8d0c0;
      --rail: #232724;
      --rail-2: #303731;
      --accent: #0f6b57;
      --blue: #245d90;
      --amber: #9a6415;
      --red: #a43a32;
      --violet: #624d88;
      --shadow: 0 18px 48px rgba(40, 37, 30, .12);
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        linear-gradient(90deg, rgba(35, 39, 36, .04) 1px, transparent 1px),
        linear-gradient(rgba(35, 39, 36, .04) 1px, transparent 1px),
        radial-gradient(circle at 70% 10%, rgba(15, 107, 87, .11), transparent 34%),
        var(--paper);
      background-size: 32px 32px, 32px 32px, auto, auto;
      font-family: "Aptos", "Segoe UI", "Microsoft YaHei UI", sans-serif;
      letter-spacing: 0;
    }}
    a {{ color: inherit; }}
    .app {{ min-height: 100vh; display: grid; grid-template-columns: 292px minmax(0, 1fr); }}
    .rail {{
      position: sticky; top: 0; height: 100vh; overflow: auto;
      background: linear-gradient(180deg, var(--rail), #171a18);
      color: #f8f3e8; border-right: 1px solid #101311; padding: 26px 18px;
    }}
    .brand {{ font-family: Georgia, "Times New Roman", serif; font-size: 31px; line-height: 1; margin-bottom: 8px; }}
    .rail small {{ color: #cfc6b6; line-height: 1.5; }}
    .selector {{ display: grid; gap: 10px; margin: 24px 0; }}
    select, button {{
      width: 100%; border: 1px solid rgba(248, 243, 232, .2); background: var(--rail-2);
      color: #f8f3e8; padding: 10px 11px; font: inherit; border-radius: 0;
    }}
    button {{ cursor: pointer; font-weight: 700; }}
    .nav {{ display: grid; gap: 7px; margin-top: 18px; }}
    .nav a {{ text-decoration: none; padding: 10px 11px; border: 1px solid rgba(248, 243, 232, .14); background: rgba(255,255,255,.04); }}
    .main {{ padding: 28px clamp(18px, 3vw, 42px) 56px; }}
    .hero {{ display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(300px, .65fr); gap: 16px; margin-bottom: 16px; }}
    .panel, .heroPanel {{ background: rgba(255, 253, 246, .94); border: 1px solid var(--line); box-shadow: var(--shadow); }}
    .heroPanel {{ padding: 26px; min-height: 236px; display: flex; flex-direction: column; justify-content: space-between; }}
    .eyebrow {{ color: var(--muted); text-transform: uppercase; font-size: 12px; font-weight: 800; }}
    h1 {{ margin: 12px 0; font-family: Georgia, "Times New Roman", "Microsoft YaHei UI", serif; font-size: clamp(38px, 5vw, 72px); line-height: .94; letter-spacing: 0; }}
    .summary {{ max-width: 980px; color: #414844; font-size: 16px; line-height: 1.62; }}
    .statusGrid {{ display: grid; gap: 10px; }}
    .metric {{ border: 1px solid var(--line); background: #faf6ec; padding: 13px; min-height: 78px; }}
    .metric span {{ display:block; color: var(--muted); font-size: 12px; margin-bottom: 8px; }}
    .metric strong {{ font-size: 23px; }}
    .grid {{ display: grid; grid-template-columns: repeat(12, 1fr); gap: 16px; }}
    .panel {{ padding: 17px; min-width: 0; }}
    .span3 {{ grid-column: span 3; }} .span4 {{ grid-column: span 4; }} .span5 {{ grid-column: span 5; }}
    .span6 {{ grid-column: span 6; }} .span7 {{ grid-column: span 7; }} .span8 {{ grid-column: span 8; }} .span12 {{ grid-column: span 12; }}
    h2 {{ margin: 0 0 13px; font-size: 15px; line-height: 1.25; }}
    .kicker {{ color: var(--muted); font-size: 12px; margin-top: -6px; margin-bottom: 12px; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .chip {{ border: 1px solid #cfc5b4; background: #fbf7ee; padding: 7px 9px; font-size: 12px; line-height: 1.2; }}
    .chip.ready, .chip.done {{ color: var(--accent); border-color: currentColor; }}
    .chip.blocked {{ color: var(--red); border-color: currentColor; }}
    .chip.waiting, .chip.needs_designer_confirmation {{ color: var(--amber); border-color: currentColor; }}
    .list {{ display: grid; gap: 8px; margin: 0; padding: 0; list-style: none; }}
    .list li {{ border: 1px solid #e3dacb; background: #fbf7ee; padding: 10px 11px; line-height: 1.45; overflow-wrap: anywhere; }}
    .noticeBar {{ display: none; margin: -2px 0 16px; border: 1px solid #d5b15e; background: #fff4d7; color: #583d09; padding: 11px 13px; line-height: 1.45; }}
    .noticeBar strong {{ display: block; margin-bottom: 4px; }}
    code {{ font-family: "Cascadia Mono", "Consolas", monospace; font-size: 12px; }}
    .timeline {{ display: grid; gap: 9px; }}
    .step {{ display: grid; grid-template-columns: 128px minmax(0, 1fr) auto; gap: 10px; align-items: center; border: 1px solid #e3dacb; background: #fbf7ee; padding: 10px 11px; }}
    .step b, .artifact b {{ display:block; margin-bottom: 4px; }}
    .phase {{ color: var(--blue); font-size: 12px; font-weight: 800; }}
    .muted {{ color: var(--muted); }}
    .artifactGrid {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 9px; }}
    .artifact {{ min-height: 78px; border: 1px solid #e3dacb; background: #fbf7ee; padding: 10px; overflow-wrap: anywhere; }}
    .missing {{ opacity: .48; }}
    .ruleGrid {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 9px; }}
    .rule {{ border-left: 4px solid var(--violet); background: #fbf7ee; padding: 10px; line-height: 1.45; }}
    .rule.k1, .rule.k2 {{ border-color: var(--accent); }} .rule.k3 {{ border-color: var(--amber); }} .rule.k4 {{ border-color: var(--red); }}
    .previews {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }}
    .preview {{ border: 1px solid #e3dacb; background:#fbf7ee; padding: 8px; }}
    .preview img {{ width: 100%; aspect-ratio: 4 / 3; object-fit: contain; display:block; background:#eee7da; border:1px solid #ddd2c1; }}
    .copy {{ line-height: 1.62; overflow-wrap: anywhere; }}
    @media (max-width: 1050px) {{
      .app {{ grid-template-columns: 1fr; }}
      .rail {{ position: relative; height: auto; }}
      .hero {{ grid-template-columns: 1fr; }}
      .grid {{ grid-template-columns: 1fr; }}
      .span3,.span4,.span5,.span6,.span7,.span8,.span12 {{ grid-column: 1 / -1; }}
      .step {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <script id="console-data" type="application/json">{data}</script>
  <div class="app">
    <aside class="rail">
      <div class="brand">CrealityOS</div>
      <small>Design Agent Operating System Console</small>
      <div class="selector">
        <label><small>Project</small><select id="projectSelect"></select></label>
        <label><small>Work item</small><select id="workItemSelect"></select></label>
        <button id="openSelection">Open selection</button>
      </div>
      <nav class="nav">
        <a href="#overview">Overview</a>
        <a href="#creative">Creative Pack</a>
        <a href="#style">Style Memory</a>
        <a href="#generation">Generation</a>
        <a href="#delivery">Delivery</a>
        <a href="#evolution">Evolution</a>
        <a href="#artifacts">Artifacts</a>
      </nav>
    </aside>
    <main class="main">
      <section class="hero" id="overview">
        <div class="heroPanel">
          <div>
            <div class="eyebrow" id="eyebrow"></div>
            <h1 id="title"></h1>
            <div class="summary" id="summary"></div>
          </div>
          <div class="chips" id="heroChips"></div>
        </div>
        <div class="heroPanel statusGrid" id="metrics"></div>
      </section>
      <section class="noticeBar" id="contextNotice"></section>
      <section class="grid">
        <article class="panel span8">
          <h2>Workflow Board</h2>
          <div class="kicker">Current phase evidence and next executable CLI steps.</div>
          <div class="timeline" id="workflow"></div>
        </article>
        <article class="panel span4">
          <h2>Next Commands</h2>
          <ul class="list" id="commands"></ul>
        </article>
        <article class="panel span6" id="creative">
          <h2>Creative Pack</h2>
          <div class="copy" id="brief"></div>
          <div class="chips" id="deliverables"></div>
        </article>
        <article class="panel span6">
          <h2>Prompt Pack</h2>
          <ul class="list" id="prompts"></ul>
        </article>
        <article class="panel span7" id="style">
          <h2>Style Memory</h2>
          <div class="ruleGrid" id="styleRules"></div>
        </article>
        <article class="panel span5">
          <h2>Open Confirmations</h2>
          <ul class="list" id="confirmations"></ul>
        </article>
        <article class="panel span5" id="generation">
          <h2>Generation And Candidates</h2>
          <div class="copy" id="generationSummary"></div>
          <div class="previews" id="previews"></div>
        </article>
        <article class="panel span4" id="delivery">
          <h2>Delivery Readiness</h2>
          <div class="copy" id="deliverySummary"></div>
          <ul class="list" id="blockers"></ul>
        </article>
        <article class="panel span3" id="evolution">
          <h2>Evolution</h2>
          <div class="copy" id="learning"></div>
        </article>
        <article class="panel span12" id="artifacts">
          <h2>Artifact Index</h2>
          <div class="artifactGrid" id="artifactsGrid"></div>
        </article>
      </section>
    </main>
  </div>
  <script>
    const data = JSON.parse(document.getElementById('console-data').textContent);
    const c = data.console || {{}};
    const cockpit = data.cockpit || {{}};
    const brief = data.design_brief || {{}};
    const creative = data.creative_pack || {{}};
    const profile = data.project_profile || {{}};
    const workflow = data.workflow_plan || {{}};
    const readiness = data.delivery_readiness || {{}};
    const extra = c.extra_payloads || {{}};
    const esc = value => String(value ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'","&#039;");
    const text = (value, fallback='Pending') => Array.isArray(value) ? (value.filter(Boolean).join(', ') || fallback) : (value || fallback);
    const list = (id, items, fallback='None') => {{
      const rows = Array.isArray(items) && items.length ? items : [fallback];
      document.getElementById(id).innerHTML = rows.map(item => `<li>${{item && item.startsWith && item.startsWith('<code>') ? item : esc(item)}}</li>`).join('');
    }};
    const chips = (id, items) => {{
      const rows = Array.isArray(items) && items.length ? items : ['Pending'];
      document.getElementById(id).innerHTML = rows.map(item => `<span class="chip">${{esc(item)}}</span>`).join('');
    }};

    const projectSelect = document.getElementById('projectSelect');
    projectSelect.innerHTML = (c.projects || []).map(p => `<option value="${{esc(p.project_key)}}">${{esc(p.project_key)}} · ${{esc(p.source)}}</option>`).join('') || `<option>${{esc(c.project_key || 'EMPTY')}}</option>`;
    projectSelect.value = c.project_key || projectSelect.value;
    const workItemSelect = document.getElementById('workItemSelect');
    workItemSelect.innerHTML = (c.work_items || []).map(item => `<option value="${{esc(item.work_item_id)}}">${{esc(item.work_item_id)}} · ${{esc(item.title || '')}}</option>`).join('') || `<option value="">Latest</option>`;
    workItemSelect.value = c.work_item_id || workItemSelect.value;
    document.getElementById('openSelection').onclick = () => {{
      const p = encodeURIComponent(projectSelect.value);
      const w = encodeURIComponent(workItemSelect.value || '');
      location.href = `/?project=${{p}}${{w ? `&work_item=${{w}}` : ''}}`;
    }};

    const status = cockpit.status || workflow.status || 'draft';
    document.getElementById('eyebrow').textContent = `${{c.project_key || 'project'}} / ${{c.work_item_id || 'work item'}}`;
    document.getElementById('title').textContent = brief.game_name || brief.title || cockpit.title || 'CrealityOS Console';
    document.getElementById('summary').textContent = cockpit.summary || brief.source_requirement_summary || brief.summary || 'No active design brief yet.';
    document.getElementById('heroChips').innerHTML = [
      `<span class="chip ${{esc(status)}}">${{esc(status)}}</span>`,
      `<span class="chip">${{esc(brief.same_category || profile.same_category || 'category pending')}}</span>`,
      `<span class="chip">Artifacts ${{data.artifact_counts?.present || 0}}/${{data.artifact_counts?.total || 0}}</span>`
    ].join('');
    const contextMessages = [...(c.notices || []), ...(c.warnings || [])];
    if (contextMessages.length) {{
      const notice = document.getElementById('contextNotice');
      notice.style.display = 'block';
      notice.innerHTML = `<strong>Context resolved</strong>${{contextMessages.map(esc).join('<br>')}}`;
    }}
    document.getElementById('metrics').innerHTML = [
      ['Blockers', (cockpit.blockers || readiness.blockers || []).length],
      ['Confirmations', (cockpit.confirmations || []).length],
      ['Workflow steps', (workflow.steps || []).length],
    ].map(([label, value]) => `<div class="metric"><span>${{label}}</span><strong>${{value}}</strong></div>`).join('');

    const steps = workflow.steps || [];
    document.getElementById('workflow').innerHTML = steps.length ? steps.map(step => `
      <div class="step">
        <div class="phase">${{esc(step.phase || step.step_id || 'phase')}}</div>
        <div><b>${{esc(step.title || step.step_id || 'Step')}}</b><div class="muted"><code>${{esc(step.command || '')}}</code></div></div>
        <span class="chip ${{esc(step.status || '')}}">${{esc(step.status || 'unknown')}}</span>
      </div>
    `).join('') : '<div class="copy">No workflow plan yet.</div>';
    list('commands', (cockpit.next_commands || workflow.next_commands || []).map(cmd => `<code>${{esc(cmd)}}</code>`), 'No recommended command.');

    document.getElementById('brief').innerHTML = `
      <b>Goal</b><br>${{esc(brief.source_requirement_summary || brief.objective || 'Pending')}}<br><br>
      <b>Audience</b><br>${{esc(brief.target_audience || 'Pending')}}<br><br>
      <b>Platform</b><br>${{esc(text(brief.platforms))}}
    `;
    chips('deliverables', [
      `Sizes: ${{text(brief.sizes)}}`,
      `Deliverables: ${{text(brief.deliverables)}}`,
      `Deadline: ${{text(brief.deadline)}}`
    ]);

    const promptPack = creative.prompt_pack || {{}};
    list('prompts', [
      `Positive: ${{text(promptPack.positive)}}`,
      `Negative: ${{text(promptPack.negative)}}`,
      `References: ${{text(promptPack.reference_groups)}}`
    ]);

    const styleCard = creative.style_card || extra.style_card || data.project_profile || {{}};
    const rules = styleCard.rules || [];
    document.getElementById('styleRules').innerHTML = rules.length ? rules.slice(0, 18).map(rule => `
      <div class="rule ${{esc(String(rule.level || '').toLowerCase())}}">
        <b>${{esc(rule.level || 'K?')}} · ${{esc(rule.kind || 'rule')}}</b>
        ${{esc(rule.statement || rule.text || '')}}
      </div>
    `).join('') : '<div class="copy">No style rules loaded.</div>';
    list('confirmations', cockpit.confirmations || []);

    const imageBatch = extra.image_generation_batch || {{}};
    const variants = imageBatch.variants || [];
    document.getElementById('generationSummary').innerHTML = variants.length
      ? variants.slice(0, 5).map(v => `<b>${{esc(v.variant_id || '')}}</b> ${{esc(v.title || v.intent || '')}}<br>`).join('')
      : 'No generation batch registered.';
    document.getElementById('previews').innerHTML = (data.asset_previews || []).length
      ? data.asset_previews.map(item => `<div class="preview"><img src="${{esc(item.url)}}" alt=""><small>${{esc(item.name)}}</small></div>`).join('')
      : '<div class="copy">No local image previews found.</div>';

    const findings = readiness.findings || [];
    document.getElementById('deliverySummary').textContent = readiness.status || 'Delivery readiness has not been generated.';
    list('blockers', cockpit.blockers || readiness.blockers || findings.filter(f => f.severity === 'blocker').map(f => f.message));

    const digest = data.learning_digest || {{}};
    document.getElementById('learning').innerHTML = `
      <b>Defaults</b><br>${{esc(text(digest.confirmed_defaults || digest.next_time_defaults))}}<br><br>
      <b>Avoid next time</b><br>${{esc(text(digest.avoid_next_time))}}<br><br>
      <b>K3 hypotheses</b><br>${{esc(text(digest.hypotheses || digest.k3_hypotheses))}}
    `;

    const artifactIndex = data.artifact_index || {{}};
    document.getElementById('artifactsGrid').innerHTML = Object.entries(artifactIndex).map(([key, value]) => `
      <div class="artifact ${{value ? '' : 'missing'}}">
        <b>${{esc(key)}}</b>
        <span>${{esc(value || 'missing')}}</span>
      </div>
    `).join('');
  </script>
</body>
</html>"""


def _first(values: list[str] | None) -> str | None:
    if not values:
        return None
    value = values[0].strip()
    return value or None


def _page_title(payload: dict) -> str:
    console = payload.get("console") or {}
    brief = payload.get("design_brief") or {}
    return f"CrealityOS Console - {brief.get('title') or console.get('work_item_id') or console.get('project_key') or 'local'}"
