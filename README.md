# CrealityOS

需求粉碎系统。This repository contains the local-first Design Copilot / CrealityOS AOS workspace.

# Design Copilot

`design-copilot` is a local-first designer copilot for Feishu Project workflows. It helps you:

- fetch pending work items from Meegle
- collect work item context and linked Feishu docs
- diagnose Meegle/local work item field mappings before building a creative pack
- turn messy requirements into a standard design brief
- synthesize project and same-category style memory
- ingest style reference images or URLs so visual examples become graded style memory
- generate a reusable creative pack and delivery manifest
- split one creative pack into multi-variant image production prompts and review sheets
- ingest candidate image reviews so accepted/rejected/revise decisions become reusable style memory
- create confirmed-before-execution Pixpark job queues from selected image variants
- register generated image paths or URLs back into a gallery and delivery-candidate index
- create candidate image style drift warnings before designer acceptance or PSD work
- create a step-by-step design workflow plan so each work item has visible next actions
- create PSD handoff plans, layer maps, and slicing checklists from selected generated candidates
- stage PSD handoff candidate assets and approval docs into a safe working package
- create PSD/slicing spec check reports before Photoshop refinement or slicing
- create a designer-facing review packet that gathers creative, image, PSD, delivery, and learning artifacts
- create a designer cockpit that turns local artifacts into one readable status entrypoint
- run a local doctor check for runtime folders, optional Feishu/Meegle CLIs, sessions, and test commands
- create reviewable Meegle writeback comment drafts without publishing automatically
- index local PSD and render assets into reusable asset cards
- stage a delivery package into a safe workspace folder before formal handoff
- keep a project-specific profile that overrides same-category defaults
- update project profiles from designer-provided JSON/text calibration files
- create style transfer reports that separate reusable same-category rules from project-level overrides
- generate a Photoshop/export automation action plan, PowerShell dry-run stub, and reviewable Photoshop JSX script
- audit memory and style certainty with a metacognition report
- generate a transition summary for the next session to resume safely
- ingest your review feedback so the agent learns over time
- curate style memory so repeated K3 evidence and confirmed avoid rules do not stay messy forever
- summarize reusable learning into next-time defaults, avoid rules, and K3 checks
- resume the latest active session without re-explaining project context

## Phase 1 scope

This repository implements the first runnable phase of the plan:

- local Python orchestrator
- Meegle and Lark Doc CLI adapters
- work item comments participate in requirement understanding, so later clarifications can fill audience, platform, deadline, size, and deliverable gaps
- knowledge grading with `K1` to `K4`
- confidence-aware creative packs: `K1/K2` rules enter executable prompts, while `K3` stays as exploration and uncertainty
- project memory, style cards, review reports, and session snapshots
- local asset index and delivery staging workflow
- project profile and automation planning workflow
- standardized outputs:
  - `design_brief.json` / `design_brief.md`
  - `requirement_clarification_report.json` / `requirement_clarification_report.md`
  - `requirement_clarification_comment.md`
  - `requirement_change_report.json` / `requirement_change_report.md`
  - `style_card.json` / `style_card.md`
  - `latest_style_reference_report.json` / `latest_style_reference_report.md`
  - `creative_pack.json`
  - `creative_pack.md`
  - `style_transfer_report.json` / `style_transfer_report.md`
  - `style_alignment_report.json` / `style_alignment_report.md`
  - `design_decision_record.json` / `design_decision_record.md`
  - `image_generation_batch.json` / `image_generation_batch.md`
  - `candidate_evaluation.md`
  - `image_generation_jobs.json` / `image_generation_jobs.md`
  - `pixpark_requests.jsonl`
  - `generation_approval_ticket.md`
  - `image_execution_package.json` / `image_execution_package.md`
  - `pixpark_execution_runbook.md`
  - `generation_results_template.json`
  - `image_generation_results.json`
  - `generated_gallery.md`
  - `delivery_candidates.md`
  - `candidate_style_drift_report.json` / `candidate_style_drift_report.md`
  - `candidate_comparison_matrix.json` / `candidate_comparison_matrix.md`
  - `psd_handoff_plan.json` / `psd_handoff_plan.md`
  - `layer_map.md`
  - `slice_checklist.md`
  - `psd_handoff_package.json` / `psd_handoff_package.md`
  - `psd_handoff_approval_ticket.md`
  - `psd_slice_spec_report.json` / `psd_slice_spec_report.md`
  - `delivery_readiness_report.json` / `delivery_readiness_report.md`
  - `design_workflow_plan.json` / `design_workflow_plan.md`
  - `designer_review_packet.json` / `designer_review_packet.md`
  - `designer_cockpit.json` / `designer_cockpit.md`
  - `doctor_report.json` / `doctor_report.md`
  - `meegle_writeback_draft.json` / `meegle_writeback_draft.md`
  - `meegle_writeback_comment.md`
  - `meegle_writeback_approval_ticket.md`
  - `*-candidate_review.json` / `*-candidate_review.md`
  - `delivery_manifest.json` / `delivery_manifest.md`
  - `review_report.json` / `review_report.md`
  - `style_memory_curation_report.json` / `style_memory_curation_report.md`
  - `asset_index.json` / `asset_index.md`
  - `delivery_package.json` / `delivery_package.md`
  - `approval_ticket.md`
  - `project_profile.json` / `project_profile.md`
  - `project_profile_update_report.json` / `project_profile_update_report.md`
  - `workitem_intake_diagnostics.json` / `workitem_intake_diagnostics.md`
  - `automation_plan.json` / `automation_plan.md`
  - `automation_stub.ps1`
  - `photoshop_export_dry_run.jsx`
  - `photoshop_script_readme.md`
  - `photoshop_script_manifest.json`
  - `latest_learning_digest.json` / `latest_learning_digest.md`
  - `latest_audit.json` / `latest_audit.md`
  - `latest_transition.json` / `latest_transition.md`
  - `session_resume.json` / `session_resume.md`

## Requirements

- Python 3.11+
- `meegle` / Meego CLI available in `PATH` for Feishu Project / Meego work items, nodes, comments, and workflow state.
- `lark-cli` available in `PATH` for Feishu / Lark docs, cloud files, sheets, IM, wiki, and other Lark resources.

## System boundary

- Feishu Project / Meego is the project-work-item system. Use `meegle` for work item reads, comments, node transitions, todos, and project workflow metadata.
- Feishu / Lark is the collaboration/document system. Use `lark-cli` for docs, cloud drive, sheets, IM, wiki, and linked document resources.
- A creative work item can reference Feishu docs, so the normal route is: read the work item through Meego first, then read linked docs through Lark only when links exist.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

Initialize runtime directories:

```bash
design-copilot init
```

Check the local environment and optional external CLI availability:

```bash
design-copilot doctor --project-key DEMO
```

Open the designer cockpit for the latest local session:

```bash
design-copilot cockpit --project-key DEMO
```

Generate a no-backend static HTML dashboard from the latest local JSON artifacts:

```bash
design-copilot dashboard --project-key DEMO --work-item-id <work-item-id>
```

This writes `dashboard/dashboard.html` and `dashboard/dashboard_data.json` under the active run directory. The HTML embeds the same local JSON snapshot so it can be opened directly from disk without starting a server.

Generate a local project style Skill from learned game memory:

```bash
design-copilot generate-project-skill --project-key DEMO
```

This reads `memory/projects/<project>/project_profile.json`, `style_card.json`, `latest_requirement_memory_report.json`, and `latest_learning_digest.json`, then writes `memory/projects/<project>/skills/<skill-name>/SKILL.md`. The generated Skill keeps `平面需求描述` as the primary source, preserves project gameplay/audience/style defaults, and reminds the agent that K3 style rules still need designer confirmation before delivery.

Fetch pending todos:

```bash
design-copilot fetch-todos --action todo --max-pages 1
```

Screen todos for likely design requirements:

```bash
design-copilot screen-todos --action todo --max-pages 1
```

Create a project-specific profile scaffold:

```bash
design-copilot init-project-profile --project-key DEMO --category casual-card --display-name "测试项目"
```

Update a project profile from designer calibration data:

```bash
design-copilot update-project-profile --project-key DEMO --category anime-rpg --profile-file .\project_profile.json
```

Profile JSON can include gameplay tags, visual keywords, hard rules, forbidden rules, default sizes, export formats, slicing requirements, naming templates, and automation preferences:

```json
{
  "display_name": "霓虹二游项目",
  "gameplay_tags": ["抽卡", "回合制"],
  "visual_keywords": ["霓虹能量", "强角色轮廓"],
  "must_have_rules": ["标题必须保留强发光描边"],
  "forbidden_rules": ["禁止灰脏背景"],
  "default_sizes": ["1080x1920"],
  "export_formats": ["PSD", "PNG", "WebP"],
  "slice_requirements": ["CTA 按钮必须独立切图"],
  "delivery_naming_template": "{project_key}_{work_item_id}_{size}_{version}",
  "automation_preferences": {"photoshop_mode": "dry-run"}
}
```

The default mode merges new values into existing memory. Use `--replace` only when you intentionally want to rebuild the project profile.

Calibrate field mapping from a work item export:

```bash
design-copilot calibrate-field-mapping --project-key DEMO --sample-file .\workitem.json
```

Diagnose a Meegle work item or local export before building a creative pack:

```bash
design-copilot diagnose-workitem-intake --project-key DEMO --work-item-id 123456
design-copilot diagnose-workitem-intake --project-key DEMO --sample-file .\workitem.json --title "活动海报"
```

This writes `workspace/intake/<project>/<workitem>/workitem_intake_diagnostics.json/md`. The report shows recommended field mappings, mapping confidence, parsed design brief fields, missing information, comment/doc evidence, and next commands. It does not save the mapping automatically; use `calibrate-field-mapping` only after you confirm the suggestion.

Build a creative pack from a work item:

```bash
design-copilot build-creative-pack --project-key DEMO --work-item-id 123456
```

Compare a refreshed requirement against the current design brief without rebuilding downstream artifacts:

```bash
design-copilot create-requirement-change-report --project-key DEMO --work-item-id 123456 --requirement-file .\updated_req.md --category anime-rpg
```

This writes `requirement_change_report.json/md` next to the current `design_brief.json`. It flags changed fields, impacted artifacts, blockers, and the safest next commands. If you omit `--requirement-file`, the command fetches the live Meegle work item and compares it with the latest local brief.

Create or refresh a multi-variant image production batch from the latest creative pack:

```bash
design-copilot create-image-production-batch --project-key DEMO --work-item-id 123456
```

Ingest candidate review results after you compare generated directions:

```bash
design-copilot ingest-candidate-review --project-key DEMO --category anime-rpg --work-item-id 123456 --review-file .\candidate_review.json
```

Candidate review JSON can look like:

```json
{
  "variants": [
    {
      "variant_id": "V01",
      "decision": "approved",
      "scores": {"style_fit": 5, "conversion": 4, "psd_ready": 4},
      "strengths": ["角色情绪准确", "按钮留白合理"],
      "learning": "保留 V01 的角色情绪和按钮留白方式，后续同项目默认沿用"
    },
    {
      "variant_id": "V02",
      "decision": "rejected",
      "issues": ["背景过亮", "利益点抢主体"],
      "learning": "避免背景过亮且利益点抢主体的处理"
    },
    {
      "variant_id": "V03",
      "decision": "revise",
      "revision_notes": ["动势可以保留，但透视需要收敛"],
      "learning": "强动势可作为 K3 探索，透视强度待验证"
    }
  ]
}
```

Ingest style references before or between tasks:

```bash
design-copilot ingest-style-reference --project-key DEMO --category anime-rpg --reference-file .\style_refs.json
```

Style reference JSON can mix local files and URLs. Local relative paths are resolved from the JSON file directory. Positive and negative examples default to `K2`; exploratory references default to `K3` until you validate them.

```json
{
  "references": [
    {
      "reference_id": "REF001",
      "path": "refs/positive.png",
      "role": "positive",
      "keywords": ["高饱和霓虹", "角色轮廓强"],
      "rules": ["角色轮廓必须高对比，背景不能抢主体"]
    },
    {
      "reference_id": "REF002",
      "url": "https://example.com/bad.png",
      "role": "negative",
      "keywords": ["灰脏背景"],
      "rules": ["避免灰脏背景和低对比主体"]
    },
    {
      "reference_id": "REF003",
      "url": "https://example.com/explore.png",
      "role": "reference",
      "keywords": ["夸张透视"],
      "notes": ["可作为 K3 探索"]
    }
  ]
}
```

Add `--share-to-base` only after you want accepted positive references to seed the same-category base. Negative examples and `K3` exploratory references stay project-scoped.

Prepare selected Pixpark generation jobs without executing them:

```bash
design-copilot create-image-generation-jobs --project-key DEMO --work-item-id 123456 --variant V01 --variant V04
```

This creates `image_generation_jobs.json`, `image_generation_jobs.md`, `pixpark_requests.jsonl`, and `generation_approval_ticket.md`. The queue stays in `pending_designer_confirmation` state and does not consume generation credits by itself.

Prepare a handoff package for manual Pixpark execution:

```bash
design-copilot prepare-image-execution-package --project-key DEMO --work-item-id 123456
```

This writes per-job payload JSON files, `image_execution_package.md`, `pixpark_execution_runbook.md`, and `generation_results_template.json`. It still does not call Pixpark or consume credits; it only prepares the files needed for a confirmed manual execution and later result registration.

Register generated local images or URLs after execution:

```bash
design-copilot register-image-results --project-key DEMO --work-item-id 123456 --results-file .\generation_results.json
```

Generation results JSON can look like:

```json
{
  "assets": [
    {
      "variant_id": "V01",
      "path": "D:/renders/v01_result.png",
      "notes": ["candidate", "角色表情最好"]
    },
    {
      "variant_id": "V04",
      "url": "https://example.com/v04_result.png",
      "notes": ["切图友好"]
    }
  ]
}
```

After registering results, the app also writes `candidate_style_drift_report.json/md` and `candidate_comparison_matrix.json/md`. Regenerate the drift report manually after editing notes or after candidate review:

```bash
design-copilot create-candidate-style-drift-report --project-key DEMO --work-item-id 123456
```

This report checks local metadata, style gates, candidate notes, project forbidden rules, K3 exploration boundaries, and candidate review scores. It does not inspect pixels as a final aesthetic judge and does not call any image generation tool; it only warns before you decide which candidate enters PSD, slicing, or delivery.

Regenerate the candidate comparison matrix after editing candidate review scores or variant notes:

```bash
design-copilot create-candidate-comparison-matrix --project-key DEMO --work-item-id 123456
```

This matrix compares each candidate's variant intent, registered assets, style drift risk, review decision, style/conversion/PSD scores, and recommended action. It is the local handoff point for deciding which direction is `采纳`, `修正`, or `驳回`; it does not execute generation, Photoshop, Meegle publish, or workflow transitions.

Create a PSD reconstruction and slicing handoff plan from registered candidates:

```bash
design-copilot create-psd-handoff-plan --project-key DEMO --work-item-id 123456
```

To force specific assets or variants:

```bash
design-copilot create-psd-handoff-plan --project-key DEMO --work-item-id 123456 --asset V01
```

Stage the selected PSD handoff candidates into a safe working package:

```bash
design-copilot prepare-psd-handoff-package --project-key DEMO --work-item-id 123456
```

This copies existing local candidate images into `workspace/deliveries/.../references/`, records remote URLs as external references, and writes a confirmation ticket. It does not download remote files, overwrite formal assets, or perform final delivery.

Create a PSD/slicing spec check before opening Photoshop or exporting slices:

```bash
design-copilot create-psd-slice-spec-report --project-key DEMO --work-item-id 123456
```

This writes `psd_slice_spec_report.json/md` and checks required layer groups, slicing tasks, naming examples, PSD staging status, and safety gates. It is a local review artifact only: it does not open Photoshop, export slices, download remote files, publish to Meegle, or overwrite formal assets.

Create a pre-delivery quality gate report:

```bash
design-copilot create-delivery-readiness-report --project-key DEMO --work-item-id 123456
```

This checks the current creative pack, K3 style assumptions, registered generation results, candidate style drift report, candidate comparison matrix, candidate review, PSD handoff plan, PSD staging package, PSD/slicing spec report, and delivery staging package. It only writes `delivery_readiness_report.json/md`; it does not publish to Meegle, transition workflow nodes, export PSDs, or overwrite formal files.

Create a designer review packet:

```bash
design-copilot create-designer-review-packet --project-key DEMO --work-item-id 123456
```

This creates one decision page that links the design brief, creative pack, style card, image batch, gallery, candidate review, PSD handoff, delivery readiness, learning digest, and audit artifacts when they exist. Full local and Feishu cycles also create this packet automatically.

Create a step-by-step workflow plan for the current work item:

```bash
design-copilot create-design-workflow-plan --project-key DEMO --work-item-id 123456
```

This writes `design_workflow_plan.json/md`. It turns the current local artifacts into a status board across requirement intake, style gates, image generation, candidate review, PSD/slicing, delivery readiness, designer review, and Meegle writeback. The plan suggests next commands but still does not execute generation, Photoshop, Meegle publish, workflow transitions, or file overwrite actions.

Create a Meegle work item comment draft without publishing it:

```bash
design-copilot create-meegle-writeback-draft --project-key DEMO --work-item-id 123456
```

This writes `meegle_writeback_comment.md` and `meegle_writeback_approval_ticket.md`. It does not call `meegle comment add`; publishing should remain behind an explicit designer approval gate.

Dry-run a Meegle publish attempt:

```bash
design-copilot publish-meegle-writeback --project-key DEMO --work-item-id 123456
```

Actually publish only after explicit confirmation:

```bash
design-copilot publish-meegle-writeback --project-key DEMO --work-item-id 123456 --execute --confirm-token PUBLISH_MEEGLE_WRITEBACK
```

You can also pass an approval ticket file if it contains `[x] 允许发布到 Meegle 评论`:

```bash
design-copilot publish-meegle-writeback --project-key DEMO --work-item-id 123456 --execute --approval-file .\meegle_writeback_approval_ticket.md
```

Create a Meegle workflow transition draft:

```bash
design-copilot create-meegle-transition-draft --project-key DEMO --work-item-id 123456 --action confirm --node 待评审
```

Dry-run the transition:

```bash
design-copilot publish-meegle-transition --project-key DEMO --work-item-id 123456
```

Execute only after explicit confirmation:

```bash
design-copilot publish-meegle-transition --project-key DEMO --work-item-id 123456 --execute --confirm-token TRANSITION_MEEGLE_WORKFLOW
```

Run the full live Feishu work item cycle:

```bash
design-copilot run-feishu-design-cycle --project-key DEMO --work-item-id 123456 --asset-root .\assets\promo
```

The full cycle also writes `delivery_readiness_report.json/md` and `design_workflow_plan.json/md` so every run leaves a local quality gate and a step-by-step next-action board for designer review.

Build a creative pack from a local requirement file:

```bash
design-copilot build-local-creative-pack --project-key DEMO --work-item-id 123456 --title "活动海报" --requirement-file .\req.md --category anime-rpg --doc-file .\notes.md
```

Every creative pack run also writes a local requirement clarification report. It turns missing fields and risk points into concrete questions, temporary assumptions, and `requirement_clarification_comment.md`. The comment file is only a draft for designer review; it is not posted to Feishu or Meegle automatically.

Regenerate the clarification report from the latest session or an existing run directory:

```bash
design-copilot create-requirement-clarification-report --project-key DEMO --work-item-id 123456
design-copilot create-requirement-clarification-report --project-key DEMO --output-dir .\workspace\runs\DEMO\123456-活动海报
```

Every creative pack run also writes a style alignment report. It checks whether confirmed `K1/K2` style rules are covered, whether forbidden rules enter Negative/do_not constraints, and whether `K3` hypotheses accidentally entered executable Positive prompts.

Every creative pack run also writes a style transfer report. It explains which same-category base rules can be reused, which project profile or project style rules override the base, which shared rules are blocked by current project forbidden rules, and which `K3` hypotheses must remain exploratory:

```bash
design-copilot create-style-transfer-report --project-key DEMO --work-item-id 123456
design-copilot create-style-transfer-report --project-key DEMO --output-dir .\workspace\runs\DEMO\123456-活动海报
```

This report is read-only. It does not promote `K3`, modify style memory, or rewrite project profiles; it exists to keep same-category reuse from becoming accidental style drift.

Regenerate the style gate from the latest session or an existing run directory:

```bash
design-copilot create-style-alignment-report --project-key DEMO --work-item-id 123456
design-copilot create-style-alignment-report --project-key DEMO --output-dir .\workspace\runs\DEMO\123456-活动海报
```

Every creative pack run also writes a design decision record. It explains why the agent chose the category, delivery plan, style constraints, K3 boundaries, and safety gates, so a later session can resume the reasoning instead of only seeing final artifacts.

Regenerate the decision ledger from the latest session or an existing run directory:

```bash
design-copilot create-design-decision-record --project-key DEMO --work-item-id 123456
design-copilot create-design-decision-record --project-key DEMO --output-dir .\workspace\runs\DEMO\123456-活动海报
```

Index a local asset folder:

```bash
design-copilot scan-assets --project-key DEMO --asset-root .\assets\promo
```

Stage a delivery package safely:

```bash
design-copilot prepare-delivery-package --project-key DEMO --work-item-id 123456 --source-root .\assets\promo --include-ext psd --include-ext png
```

Generate a Photoshop/export automation plan:

```bash
design-copilot plan-automation --project-key DEMO --work-item-id 123456 --asset-root .\assets\promo
```

This also writes a reviewable Photoshop script:

- `photoshop_export_dry_run.jsx` inspects the PSD/PSB, writes `photoshop_layer_report.md`, and writes `photoshop_slice_checklist.md`.
- The JSX defaults to `allowExport: false`, so it does not export images, save PSDs, or overwrite formal files.
- If you approve the plan and want a flattened staging PNG preview, manually change `allowExport` to `true` inside the JSX before running it again in Photoshop.

Run a metacognition audit:

```bash
design-copilot metacognition-audit --project-key DEMO
```

Create a transition summary for the next session:

```bash
design-copilot create-transition-summary --project-key DEMO
```

Create a reusable learning digest before the next task:

```bash
design-copilot create-learning-digest --project-key DEMO
```

Create style memory governance suggestions:

```bash
design-copilot curate-style-memory --project-key DEMO
```

This is report-only by default. It highlights repeated `K3` evidence that can be promoted, confirmed avoid rules that should sync into `do_not`, and keyword conflicts that need designer judgment. Apply only the safe actions after review:

```bash
design-copilot curate-style-memory --project-key DEMO --apply
```

Run the full local design cycle:

```bash
design-copilot run-local-design-cycle --project-key DEMO --work-item-id 123456 --title "活动海报" --requirement-file .\req.md --category anime-rpg --doc-file .\notes.md --asset-root .\assets\promo
```

The local cycle also produces a delivery readiness report. Early runs may show warnings for missing generated candidates or PSD staging; those are guidance, not automatic blockers unless required assets are missing or staging is empty.

Create or refresh the cockpit after any cycle or manual artifact step:

```bash
design-copilot cockpit --project-key DEMO --work-item-id 123456
```

Run the standard regression suite:

```bash
python -m unittest discover -s tests -v
```

If you prefer pytest, install the optional test extra first:

```bash
pip install -e .[test]
python -m pytest -q
```

Ingest your review feedback:

```bash
design-copilot ingest-feedback --project-key DEMO --category casual-card --work-item-id 123456 --decision revise --feedback-file feedback.txt
```

Resume the latest session:

```bash
design-copilot resume-session --project-key DEMO
```

This writes `memory/sessions/<project>/session_resume.json/md`. The resume brief gathers the active work item, current style gate, decision summary, unresolved questions, important artifacts, recent feedback names, and recommended next commands so a new conversation can continue without reloading the full chat history.

## Project structure

```text
agent/                  Python package
memory/                 persistent style, review, and session memory
templates/              output structure references
tests/                  unit tests for the core flow
workspace/runs/         generated outputs per work item
workspace/deliveries/   safe staging area for pre-delivery packages
```

## Notes

- The agent does not auto-export PSDs or overwrite formal assets in phase 1.
- Delivery staging copies files into a new workspace folder and always leaves formal files untouched.
- Automation planning only generates reviewed action plans, a dry-run PowerShell stub, and a manual Photoshop JSX script; it does not auto-launch or directly control Photoshop yet.
- Image production batches create four reviewable directions by default: safe project style, conversion-focused, bold composition, and PSD/slicing-friendly.
- Candidate review ingestion converts designer comparison into approved, rejected, or K3 pending memory, then refreshes the learning digest.
- Style reference ingestion records positive, negative, and exploratory image examples as graded style memory without downloading remote URLs or treating K3 hypotheses as settled rules.
- Style transfer reports make cross-project reuse explicit: same-category base first, project profile overrides second, K3 stays exploratory.
- Creative packs keep `K3` style hypotheses out of core positive prompts and Pixpark payloads; they appear as explicit exploration notes until you validate them.
- Style alignment reports act as a pre-generation style gate for `K1/K2`, forbidden rules, and `K3` boundaries.
- Design decision records preserve the rationale, evidence, confidence level, assumptions, and safety notes behind each creative pack.
- Image generation jobs are queued for manual confirmation first; real generation tool execution should be added behind an explicit approval gate.
- Image execution packages split confirmed jobs into per-task payload files and a result template, bridging manual Pixpark execution back into local review.
- Generated image results are registered into a gallery and delivery-candidate checklist before candidate review or PSD work begins.
- Candidate style drift reports provide a metadata/feedback-based warning layer before you accept generated images or move them into PSD work.
- PSD handoff plans convert selected generated candidates into layer maps, reconstruction steps, slicing tasks, and approval checklists.
- PSD handoff packages safely gather local candidate files and references for manual refinement, slicing, or final delivery review.
- Delivery readiness reports act as a final local quality gate across requirements, style confidence, candidate review, PSD/slicing, staging, and safety confirmation.
- Design workflow plans translate artifacts and quality gates into a current task board with ready/waiting/blocked steps and safe next commands.
- Designer review packets gather the scattered artifacts into one human decision page so the designer can quickly decide what to approve, revise, or hand off.
- Meegle writeback drafts summarize local progress for work item comments but never publish automatically.
- Meegle writeback publishing is dry-run by default and requires `--execute` plus a confirmation token or approved ticket file.
- Meegle workflow transitions are also gated: drafts are generated first, execution requires `TRANSITION_MEEGLE_WORKFLOW` or an approved ticket.
- Metacognition audits help the agent inspect K3 uncertainty, missing project constraints, and delivery readiness before it overcommits.
- Transition summaries compress the current project state so the next session can resume without reloading full chat history.
- Session resume reports turn the latest snapshot into an actionable startup page with current task, decisions, open questions, artifact links, and recommended next commands.
- Learning digests compress project memory into next-time defaults, avoid rules, K3 hypotheses, unresolved questions, and recommended commands.
- The local workflow lets you run the whole loop from exported Feishu text, markdown notes, or local requirement drafts when live APIs are unavailable.
- Field calibration lets the agent learn which real project fields mean objective, audience, platform, size, deliverables, and deadline.
- Work item intake diagnostics catch changed Meegle templates before requirement understanding silently drops fields.
- Requirement interpretation reads Meegle comments as clarification evidence, so demand-side replies can reduce missing-information warnings without manually editing the work item body.
- Project profile updates let the designer seed or revise gameplay tags, visual keywords, hard rules, forbidden rules, sizes, naming, and slicing requirements without editing JSON memory by hand.
- Style memory curation keeps long-running project memory tidy: report mode proposes safe upgrades and syncs, while `--apply` explicitly writes conservative changes.
- All uncertain style judgments are preserved as `K3` until your feedback upgrades them.
- The adapters degrade gracefully when fields, docs, or comments are missing.
