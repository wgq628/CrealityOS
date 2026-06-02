from __future__ import annotations

import json
from datetime import datetime
from html import escape
from typing import Any


class DesignerDashboardBuilder:
    def build_payload(
        self,
        cockpit: dict[str, Any],
        design_brief: dict[str, Any] | None,
        creative_pack: dict[str, Any] | None,
        requirement_memory: dict[str, Any] | None,
        learning_digest: dict[str, Any] | None,
        project_profile: dict[str, Any] | None,
        workflow_plan: dict[str, Any] | None,
        delivery_readiness: dict[str, Any] | None,
    ) -> dict[str, Any]:
        artifact_index = cockpit.get("artifact_index") or {}
        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "cockpit": cockpit,
            "design_brief": design_brief or {},
            "creative_pack": creative_pack or {},
            "requirement_memory": requirement_memory or {},
            "learning_digest": learning_digest or {},
            "project_profile": project_profile or {},
            "workflow_plan": workflow_plan or {},
            "delivery_readiness": delivery_readiness or {},
            "artifact_index": artifact_index,
            "artifact_counts": {
                "present": sum(1 for value in artifact_index.values() if value),
                "missing": sum(1 for value in artifact_index.values() if not value),
                "total": len(artifact_index),
            },
        }

    def render_html(self, payload: dict[str, Any]) -> str:
        data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
        title = self._title(payload)
        return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      --ink: #202124;
      --muted: #69716f;
      --paper: #f4f1ea;
      --panel: #fffdf7;
      --line: #d8d0c3;
      --green: #1f7a4d;
      --amber: #a26311;
      --red: #af2d2d;
      --blue: #285f9f;
      --charcoal: #303437;
      --shadow: 0 18px 45px rgba(48, 52, 55, .12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        linear-gradient(90deg, rgba(32,33,36,.035) 1px, transparent 1px),
        linear-gradient(rgba(32,33,36,.035) 1px, transparent 1px),
        var(--paper);
      background-size: 28px 28px;
      font-family: "Aptos", "Segoe UI", "Microsoft YaHei", sans-serif;
      letter-spacing: 0;
    }}
    a {{ color: inherit; text-decoration: none; }}
    .shell {{
      min-height: 100vh;
      display: grid;
      grid-template-columns: minmax(220px, 280px) 1fr;
    }}
    .rail {{
      position: sticky;
      top: 0;
      height: 100vh;
      padding: 28px 22px;
      background: #242829;
      color: #f7f2e8;
      border-right: 1px solid #171a1b;
      display: flex;
      flex-direction: column;
      gap: 22px;
    }}
    .mark {{
      font-family: Georgia, "Times New Roman", serif;
      font-size: 30px;
      line-height: 1;
      letter-spacing: 0;
    }}
    .rail small {{ color: #c9c0b0; line-height: 1.45; }}
    .nav {{
      display: grid;
      gap: 8px;
      margin-top: 8px;
    }}
    .nav a {{
      padding: 10px 12px;
      border: 1px solid rgba(247,242,232,.16);
      background: rgba(255,255,255,.04);
      color: #f7f2e8;
      font-size: 13px;
    }}
    .railFooter {{
      margin-top: auto;
      font-size: 12px;
      color: #c9c0b0;
      line-height: 1.5;
    }}
    main {{
      padding: 28px clamp(18px, 3vw, 42px) 54px;
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1.3fr) minmax(280px, .7fr);
      gap: 18px;
      align-items: stretch;
      margin-bottom: 18px;
    }}
    .heroPanel, .panel {{
      background: rgba(255,253,247,.92);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
    }}
    .heroPanel {{
      padding: 28px;
      min-height: 220px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}
    .eyebrow {{
      color: var(--muted);
      text-transform: uppercase;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: .08em;
    }}
    h1 {{
      margin: 14px 0 12px;
      font-family: Georgia, "Times New Roman", "Microsoft YaHei", serif;
      font-size: clamp(34px, 5vw, 68px);
      line-height: .96;
      letter-spacing: 0;
    }}
    .summary {{
      max-width: 920px;
      color: #404744;
      font-size: 16px;
      line-height: 1.65;
    }}
    .statusBoard {{
      padding: 18px;
      display: grid;
      gap: 12px;
    }}
    .metric {{
      border: 1px solid var(--line);
      background: #fbf8ef;
      padding: 14px;
      min-height: 84px;
    }}
    .metric span {{ display: block; color: var(--muted); font-size: 12px; margin-bottom: 7px; }}
    .metric strong {{ font-size: 24px; line-height: 1.1; }}
    .status {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 7px 10px;
      border: 1px solid currentColor;
      font-size: 13px;
      font-weight: 700;
    }}
    .status::before {{
      content: "";
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: currentColor;
    }}
    .status.ready, .status.in_progress {{ color: var(--green); }}
    .status.blocked {{ color: var(--red); }}
    .status.needs_designer_confirmation {{ color: var(--amber); }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(12, 1fr);
      gap: 18px;
    }}
    .panel {{
      padding: 18px;
      min-width: 0;
    }}
    .span4 {{ grid-column: span 4; }}
    .span5 {{ grid-column: span 5; }}
    .span6 {{ grid-column: span 6; }}
    .span7 {{ grid-column: span 7; }}
    .span8 {{ grid-column: span 8; }}
    .span12 {{ grid-column: span 12; }}
    h2 {{
      margin: 0 0 14px;
      font-size: 16px;
      line-height: 1.2;
    }}
    .list {{
      display: grid;
      gap: 8px;
      margin: 0;
      padding: 0;
      list-style: none;
    }}
    .list li {{
      padding: 10px 12px;
      border: 1px solid #e2dacd;
      background: #fbf8ef;
      line-height: 1.45;
      overflow-wrap: anywhere;
    }}
    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .chip {{
      border: 1px solid #cfc4b4;
      background: #fbf8ef;
      padding: 7px 9px;
      font-size: 13px;
      line-height: 1.2;
    }}
    .copy {{
      color: #3e4642;
      line-height: 1.68;
      overflow-wrap: anywhere;
    }}
    .commands code {{
      display: block;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      font-family: "Cascadia Mono", "Consolas", monospace;
      font-size: 12px;
    }}
    .artifactGrid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 9px;
    }}
    .artifact {{
      padding: 10px;
      border: 1px solid #e2dacd;
      background: #fbf8ef;
      min-height: 72px;
    }}
    .artifact b {{ display: block; font-size: 13px; margin-bottom: 6px; }}
    .artifact span {{ color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }}
    .missing {{ opacity: .55; }}
    .timeline {{
      display: grid;
      gap: 10px;
    }}
    .step {{
      display: grid;
      grid-template-columns: 96px 1fr auto;
      gap: 10px;
      align-items: center;
      padding: 10px 12px;
      border: 1px solid #e2dacd;
      background: #fbf8ef;
    }}
    .step small {{ color: var(--muted); }}
    .phase {{ font-size: 12px; color: var(--blue); font-weight: 700; }}
    .badge {{
      border: 1px solid currentColor;
      padding: 5px 7px;
      font-size: 12px;
      color: var(--muted);
    }}
    .refs a {{
      display: block;
      color: var(--blue);
      margin: 7px 0;
      overflow-wrap: anywhere;
      text-decoration: underline;
      text-decoration-thickness: 1px;
      text-underline-offset: 3px;
    }}
    @media (max-width: 980px) {{
      .shell {{ grid-template-columns: 1fr; }}
      .rail {{
        position: relative;
        height: auto;
      }}
      .hero {{ grid-template-columns: 1fr; }}
      .span4, .span5, .span6, .span7, .span8, .span12 {{ grid-column: 1 / -1; }}
      .grid {{ grid-template-columns: 1fr; }}
      .step {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <script id="dashboard-data" type="application/json">{data}</script>
  <div class="shell">
    <aside class="rail">
      <div>
        <div class="mark">CrealityOS</div>
        <small>Designer Cockpit / static dashboard</small>
      </div>
      <nav class="nav">
        <a href="#brief">需求</a>
        <a href="#memory">记忆</a>
        <a href="#workflow">流程</a>
        <a href="#artifacts">产物</a>
      </nav>
      <div class="railFooter" id="railMeta"></div>
    </aside>
    <main>
      <section class="hero">
        <div class="heroPanel">
          <div>
            <div class="eyebrow" id="eyebrow"></div>
            <h1 id="title"></h1>
            <div class="summary" id="summary"></div>
          </div>
          <div class="chips" id="heroChips"></div>
        </div>
        <div class="heroPanel statusBoard" id="statusBoard"></div>
      </section>
      <section class="grid">
        <article class="panel span7" id="brief">
          <h2>平面需求与任务拆解</h2>
          <div class="copy" id="requirementSummary"></div>
          <ul class="list" id="tasks"></ul>
        </article>
        <article class="panel span5">
          <h2>下一步命令</h2>
          <ul class="list commands" id="commands"></ul>
        </article>
        <article class="panel span4" id="memory">
          <h2>游戏 / 受众 / 玩法</h2>
          <div class="copy" id="audience"></div>
          <div class="chips" id="gameplayTags"></div>
        </article>
        <article class="panel span4">
          <h2>投放美术方向</h2>
          <div class="chips" id="visualKeywords"></div>
        </article>
        <article class="panel span4">
          <h2>尺寸与交付</h2>
          <div class="chips" id="deliveryChips"></div>
        </article>
        <article class="panel span6">
          <h2>待设计师确认</h2>
          <ul class="list" id="confirmations"></ul>
        </article>
        <article class="panel span6">
          <h2>阻塞项</h2>
          <ul class="list" id="blockers"></ul>
        </article>
        <article class="panel span8" id="workflow">
          <h2>工作流</h2>
          <div class="timeline" id="workflowSteps"></div>
        </article>
        <article class="panel span4">
          <h2>参考图与素材路径</h2>
          <div class="refs" id="referenceAssets"></div>
        </article>
        <article class="panel span12" id="artifacts">
          <h2>关键产物</h2>
          <div class="artifactGrid" id="artifactsGrid"></div>
        </article>
      </section>
    </main>
  </div>
  <script>
    const data = JSON.parse(document.getElementById('dashboard-data').textContent);
    const cockpit = data.cockpit || {{}};
    const brief = data.design_brief || {{}};
    const memory = data.requirement_memory || {{}};
    const profile = data.project_profile || {{}};
    const workflow = data.workflow_plan || {{}};
    const readiness = data.delivery_readiness || {{}};

    const text = (value, fallback = '待确认') => {{
      if (Array.isArray(value)) return value.filter(Boolean).join('、') || fallback;
      return value || fallback;
    }};
    const el = id => document.getElementById(id);
    const list = (id, items, fallback = '无') => {{
      const target = el(id);
      const rows = (items && items.length ? items : [fallback]);
      target.innerHTML = rows.map(item => `<li>${{escapeHtml(String(item))}}</li>`).join('');
    }};
    const chips = (id, items) => {{
      const target = el(id);
      const rows = (items && items.length ? items : ['待确认']);
      target.innerHTML = rows.map(item => `<span class="chip">${{escapeHtml(String(item))}}</span>`).join('');
    }};
    const escapeHtml = value => value
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');

    el('eyebrow').textContent = `${{text(cockpit.project_key)}} / ${{text(cockpit.work_item_id)}}`;
    el('title').textContent = text(brief.game_name, cockpit.title || '设计师副驾驾驶舱');
    el('summary').textContent = cockpit.summary || brief.summary || '暂无摘要';
    el('railMeta').innerHTML = `生成时间<br>${{escapeHtml(data.generated_at || '')}}<br><br>输出目录<br>${{escapeHtml(cockpit.output_dir || '未绑定')}}`;

    const status = cockpit.status || 'draft';
    el('heroChips').innerHTML = [
      `<span class="status ${{escapeHtml(status)}}">${{escapeHtml(status)}}</span>`,
      `<span class="chip">${{escapeHtml(text(brief.same_category, cockpit.project_key))}}</span>`,
      `<span class="chip">产物 ${{data.artifact_counts?.present || 0}}/${{data.artifact_counts?.total || 0}}</span>`
    ].join('');
    el('statusBoard').innerHTML = `
      <div class="metric"><span>当前状态</span><strong>${{escapeHtml(status)}}</strong></div>
      <div class="metric"><span>设计确认</span><strong>${{(cockpit.confirmations || []).length}}</strong></div>
      <div class="metric"><span>硬阻塞</span><strong>${{(cockpit.blockers || []).length}}</strong></div>
    `;

    el('requirementSummary').textContent = brief.source_requirement_summary || memory.source_requirement_summary || '待确认';
    list('tasks', brief.task_breakdown || memory.task_breakdown, '暂无任务拆解');
    list('commands', (cockpit.next_commands || []).map(command => `<code>${{escapeHtml(command)}}</code>`), '暂无推荐命令');
    el('commands').innerHTML = (cockpit.next_commands || ['暂无推荐命令']).map(command => `<li><code>${{escapeHtml(command)}}</code></li>`).join('');
    el('audience').textContent = `受众：${{text(brief.target_audience || memory.learned_audience)}}`;
    chips('gameplayTags', profile.gameplay_tags || memory.learned_gameplay_tags);
    chips('visualKeywords', profile.visual_keywords || memory.learned_visual_keywords);
    chips('deliveryChips', [
      `尺寸：${{text(brief.sizes || memory.learned_default_sizes)}}`,
      `交付：${{text(brief.deliverables || memory.learned_deliverables)}}`,
      `截止：${{text(brief.deadline)}}`
    ]);
    list('confirmations', cockpit.confirmations, '无');
    list('blockers', cockpit.blockers, '无');

    const steps = workflow.steps || [];
    el('workflowSteps').innerHTML = (steps.length ? steps : []).slice(0, 14).map(step => `
      <div class="step">
        <div class="phase">${{escapeHtml(step.phase || '流程')}}</div>
        <div><b>${{escapeHtml(step.title || step.step_id || '未命名步骤')}}</b><br><small>${{escapeHtml(step.command || '')}}</small></div>
        <div class="badge">${{escapeHtml(step.status || 'unknown')}}</div>
      </div>
    `).join('') || '<div class="copy">暂无工作流计划</div>';

    const refs = brief.reference_assets || [];
    el('referenceAssets').innerHTML = refs.length
      ? refs.slice(0, 12).map(ref => {{
          const safe = escapeHtml(String(ref));
          const href = String(ref).startsWith('http') ? safe : '#';
          return href === '#' ? `<div>${{safe}}</div>` : `<a href="${{href}}" target="_blank" rel="noreferrer">${{safe}}</a>`;
        }}).join('')
      : '<div class="copy">暂无参考图或素材路径</div>';

    const artifactIndex = data.artifact_index || {{}};
    el('artifactsGrid').innerHTML = Object.entries(artifactIndex).map(([key, value]) => `
      <div class="artifact ${{value ? '' : 'missing'}}">
        <b>${{escapeHtml(key)}}</b>
        <span>${{escapeHtml(value || '缺失')}}</span>
      </div>
    `).join('');
  </script>
</body>
</html>
"""

    @staticmethod
    def _title(payload: dict[str, Any]) -> str:
        brief = payload.get("design_brief") or {}
        cockpit = payload.get("cockpit") or {}
        game_name = brief.get("game_name")
        if game_name and game_name != "待确认":
            return f"CrealityOS Dashboard - {game_name}"
        return f"CrealityOS Dashboard - {cockpit.get('title') or cockpit.get('work_item_id') or 'Designer Cockpit'}"
