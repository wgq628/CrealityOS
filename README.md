# CrealityOS

CrealityOS 是一套面向设计需求处理、创作协同、风格记忆和交付检查的本地优先 AOS。当前仓库的工程名仍保留为 `design-copilot`，可以理解为 CrealityOS 的设计副驾内核。

它的核心目标不是替代设计师，而是把混乱需求拆解成可执行的设计蓝图、创作包、风格约束、出图任务、候选评审、PSD/切图交接和交付前检查，让每个工作项都有清楚的状态、证据和下一步命令。

## 系统定位

CrealityOS 当前属于“设计工作流 AOS / 需求粉碎系统”的第一阶段实现：

- 本地优先：主要产物写入本地 `workspace/`、`memory/`，不依赖云端才能运行。
- 人工确认优先：不会自动发布飞书评论、不会自动流转节点、不会自动执行出图消耗、不会覆盖正式交付文件。
- 记忆可进化：设计反馈、风格规则、项目档案、K3 假设和学习摘要会沉淀到项目记忆中。
- 证据可追踪：每个设计包、风格门、评审包、交付检查都保留 JSON 和 Markdown 产物。
- 可视化可检查：支持本地控制台，把工作项、产物索引、风格记忆、生成任务、交付状态集中展示。

## 主要能力

- 拉取或读取 Meegle / 飞书项目工作项。
- 读取工作项上下文、评论、关联飞书文档和本地需求文件。
- 诊断工作项字段映射，避免模板变化导致需求字段丢失。
- 把混乱需求转换为标准设计需求卡 `design_brief`。
- 生成可复用创作包 `creative_pack`。
- 生成需求澄清报告和评论草稿。
- 维护项目档案、同品类风格底座、风格卡和学习摘要。
- 区分 `K1` 到 `K4` 风格知识等级。
- 将 `K1/K2` 作为可执行约束，将 `K3` 保留为待验证探索。
- 生成风格迁移报告，避免机械套用同品类规则。
- 生成风格一致性报告，检查正向规则、禁忌项和 K3 泄漏。
- 生成设计决策记录，保留每轮创作的依据和假设。
- 生成多方案出图提示词批次。
- 准备待确认 Pixpark 出图任务，但不自动执行。
- 准备人工出图执行包和结果登记模板。
- 登记生成图路径或 URL，形成候选图库和交付候选索引。
- 生成候选图风格偏移报告。
- 生成候选方案对比矩阵。
- 摄入设计师候选评审，让采纳、驳回、修改建议进入记忆系统。
- 生成 PSD 重建、图层、切图和交接计划。
- 准备 PSD 安全 staging 包，不覆盖正式文件。
- 生成 PSD/切图规格检查报告。
- 生成交付前质量门报告。
- 生成设计师评审包，把散落产物汇总为一页决策材料。
- 生成 Meegle 回写草稿，但不自动发布。
- 生成 Meegle 流程流转草稿，执行必须显式确认。
- 生成工作流计划，把当前产物转换为 ready / waiting / blocked 状态板。
- 生成本地设计师 cockpit 和静态 dashboard。
- 运行本地 doctor 检查环境、目录、会话和测试命令。
- 运行元认知审计，检查 K3 不确定性、缺失约束和交付风险。
- 生成会话交接摘要，方便下次继续。
- 生成学习摘要，将下次默认项、避坑规则、K3 检查项压缩保存。
- 运行本地可视化控制台，查看项目、工作项、关键产物和上下文纠偏。

## 当前新增的可视化控制台

本版本新增了本地控制台服务：

```bash
python -m agent.cli serve --project-key artdesign --host 127.0.0.1 --port 8787
```

浏览器访问：

```text
http://127.0.0.1:8787/
```

控制台支持：

- 项目选择。
- 工作项选择。
- 当前设计需求摘要。
- 创作包查看。
- 风格记忆查看。
- 出图任务和候选状态查看。
- 交付状态查看。
- 自进化/学习摘要查看。
- 关键产物索引查看。
- URL 项目/工作项错配自动纠正。

例如当前浏览器 URL 如果传入：

```text
project=LOCAL&work_item=7002016443
```

但本地真实产物属于：

```text
artdesign / 7002016443
```

控制台会自动纠正上下文，并在页面显示提示，避免看板悄悄展示错工作项数据。

## 关键目录

```text
agent/                  Python 主包，包含应用入口、核心模块、适配器和控制台服务
agent/core/             创作包、风格记忆、评审、交付、工作流等核心逻辑
agent/adapters/         Meegle、Lark、Local file 等外部或本地适配器
docs/                   系统蓝图、架构说明和设计文档
memory/                 项目档案、风格记忆、反馈、会话快照和学习摘要
templates/              输出结构参考模板
tests/                  单元测试
tools/                  辅助工具
workspace/runs/         每个工作项的运行产物
workspace/deliveries/   交付前安全 staging 区
workspace/test-sandboxes/ 测试沙盒目录
```

## 关键模块

```text
agent/app.py
```

系统主应用入口。负责串联需求读取、创作包生成、风格报告、出图计划、PSD 交接、交付检查、cockpit、dashboard 等能力。

```text
agent/cli.py
```

命令行入口。所有 `design-copilot ...` 或 `python -m agent.cli ...` 命令都从这里进入。

```text
agent/artifact_resolver.py
```

中心产物解析器。统一负责项目发现、工作项发现、run 目录定位、关键产物收集和项目/工作项错配纠正。

```text
agent/console_server.py
```

本地可视化控制台服务。提供页面渲染、状态 API、健康检查和本地文件预览。

```text
agent/core/workflow_plan.py
```

工作流计划生成器。把当前产物状态转换为设计流程状态板，并给出下一步安全命令。

```text
agent/core/designer_cockpit.py
```

设计师 cockpit 生成器。把关键产物聚合成一个可读的工作项状态入口。

```text
agent/core/designer_dashboard.py
```

静态 dashboard 生成器。可以生成无需后端的 HTML 看板。

```text
agent/core/creative_pack.py
```

创作包生成器。把需求、风格卡和项目档案合成为可执行创作包。

```text
agent/core/style_alignment.py
agent/core/style_transfer.py
agent/core/style_learner.py
agent/core/style_memory_curator.py
```

风格一致性、风格迁移、风格学习和风格记忆治理相关模块。

```text
agent/core/image_production.py
agent/core/generation_queue.py
agent/core/image_execution_package.py
agent/core/generation_results.py
```

出图批次、待确认出图任务、人工执行包和生成结果登记相关模块。

```text
agent/core/candidate_style_drift.py
agent/core/candidate_comparison.py
agent/core/candidate_review.py
```

候选图风格偏移、候选方案对比和设计师候选评审摄入模块。

```text
agent/core/psd_handoff.py
agent/core/psd_handoff_package.py
agent/core/psd_slice_spec.py
```

PSD 重建、图层交接、切图检查和安全 staging 相关模块。

```text
agent/core/delivery_readiness.py
agent/core/review_packet.py
agent/core/meegle_writeback.py
```

交付前质量门、设计师评审包和 Meegle 回写草稿相关模块。

## 安装与初始化

建议使用 Python 3.11 或更高版本。

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

初始化运行目录：

```bash
design-copilot init
```

检查本地环境：

```bash
design-copilot doctor --project-key DEMO
```

运行测试：

```bash
python -m unittest discover -s tests -v
```

## 外部依赖

CrealityOS 可以在本地文件模式下运行。若要连接飞书项目和飞书文档，需要额外准备：

- `meegle` / Meego CLI：用于飞书项目工作项、评论、节点、流程状态。
- `lark-cli`：用于飞书文档、云空间、表格、IM、Wiki 等资源。

系统边界：

- 飞书项目 / Meego 是项目工作项系统。
- 飞书 / Lark 是协作文档系统。
- 正常链路是先通过 Meego 读取工作项，再在存在关联文档时通过 Lark 读取文档。

## 常用命令

### 本地控制台

```bash
python -m agent.cli serve --project-key artdesign --host 127.0.0.1 --port 8787
```

### 生成本地 cockpit

```bash
design-copilot cockpit --project-key DEMO --work-item-id 123456
```

### 生成静态 dashboard

```bash
design-copilot dashboard --project-key DEMO --work-item-id 123456
```

### 从本地需求文件生成创作包

```bash
design-copilot build-local-creative-pack --project-key DEMO --work-item-id 123456 --title "活动海报" --requirement-file .\req.md --category anime-rpg
```

### 从飞书项目工作项生成创作包

```bash
design-copilot build-creative-pack --project-key DEMO --work-item-id 123456
```

### 生成需求澄清报告

```bash
design-copilot create-requirement-clarification-report --project-key DEMO --work-item-id 123456
```

### 生成需求变更报告

```bash
design-copilot create-requirement-change-report --project-key DEMO --work-item-id 123456 --requirement-file .\updated_req.md --category anime-rpg
```

### 生成风格迁移报告

```bash
design-copilot create-style-transfer-report --project-key DEMO --work-item-id 123456
```

### 生成风格一致性报告

```bash
design-copilot create-style-alignment-report --project-key DEMO --work-item-id 123456
```

### 生成设计决策记录

```bash
design-copilot create-design-decision-record --project-key DEMO --work-item-id 123456
```

### 生成多方案出图批次

```bash
design-copilot create-image-production-batch --project-key DEMO --work-item-id 123456
```

### 准备待确认出图任务

```bash
design-copilot create-image-generation-jobs --project-key DEMO --work-item-id 123456 --variant V01 --variant V04
```

### 准备人工出图执行包

```bash
design-copilot prepare-image-execution-package --project-key DEMO --work-item-id 123456
```

### 登记生成结果

```bash
design-copilot register-image-results --project-key DEMO --work-item-id 123456 --results-file .\generation_results.json
```

### 生成候选风格偏移报告

```bash
design-copilot create-candidate-style-drift-report --project-key DEMO --work-item-id 123456
```

### 生成候选对比矩阵

```bash
design-copilot create-candidate-comparison-matrix --project-key DEMO --work-item-id 123456
```

### 摄入候选评审

```bash
design-copilot ingest-candidate-review --project-key DEMO --category anime-rpg --work-item-id 123456 --review-file .\candidate_review.json
```

### 生成 PSD 交接计划

```bash
design-copilot create-psd-handoff-plan --project-key DEMO --work-item-id 123456
```

### 准备 PSD 安全 staging 包

```bash
design-copilot prepare-psd-handoff-package --project-key DEMO --work-item-id 123456
```

### 生成 PSD/切图检查

```bash
design-copilot create-psd-slice-spec-report --project-key DEMO --work-item-id 123456
```

### 生成交付前质量门

```bash
design-copilot create-delivery-readiness-report --project-key DEMO --work-item-id 123456
```

### 生成设计师评审包

```bash
design-copilot create-designer-review-packet --project-key DEMO --work-item-id 123456
```

### 生成工作流计划

```bash
design-copilot create-design-workflow-plan --project-key DEMO --work-item-id 123456
```

### 创建 Meegle 回写草稿

```bash
design-copilot create-meegle-writeback-draft --project-key DEMO --work-item-id 123456
```

### 发布 Meegle 回写

默认是 dry-run，不会发布：

```bash
design-copilot publish-meegle-writeback --project-key DEMO --work-item-id 123456
```

真正发布必须显式确认：

```bash
design-copilot publish-meegle-writeback --project-key DEMO --work-item-id 123456 --execute --confirm-token PUBLISH_MEEGLE_WRITEBACK
```

### 创建 Meegle 流程流转草稿

```bash
design-copilot create-meegle-transition-draft --project-key DEMO --work-item-id 123456 --action confirm --node 待评审
```

### 执行 Meegle 流程流转

默认是 dry-run：

```bash
design-copilot publish-meegle-transition --project-key DEMO --work-item-id 123456
```

真正执行必须显式确认：

```bash
design-copilot publish-meegle-transition --project-key DEMO --work-item-id 123456 --execute --confirm-token TRANSITION_MEEGLE_WORKFLOW
```

### 运行完整本地设计循环

```bash
design-copilot run-local-design-cycle --project-key DEMO --work-item-id 123456 --title "活动海报" --requirement-file .\req.md --category anime-rpg --asset-root .\assets\promo
```

### 运行完整飞书工作项设计循环

```bash
design-copilot run-feishu-design-cycle --project-key DEMO --work-item-id 123456 --asset-root .\assets\promo
```

### 摄入风格参考

```bash
design-copilot ingest-style-reference --project-key DEMO --category anime-rpg --reference-file .\style_refs.json
```

### 摄入设计反馈

```bash
design-copilot ingest-feedback --project-key DEMO --category casual-card --work-item-id 123456 --decision revise --feedback-file feedback.txt
```

### 生成学习摘要

```bash
design-copilot create-learning-digest --project-key DEMO
```

### 治理风格记忆

只生成建议报告：

```bash
design-copilot curate-style-memory --project-key DEMO
```

确认安全动作后再写入：

```bash
design-copilot curate-style-memory --project-key DEMO --apply
```

### 运行元认知审计

```bash
design-copilot metacognition-audit --project-key DEMO
```

### 生成会话交接摘要

```bash
design-copilot create-transition-summary --project-key DEMO
```

### 恢复最近会话

```bash
design-copilot resume-session --project-key DEMO
```

## 标准产物

CrealityOS 会把关键产物写成 JSON 和 Markdown，常见产物包括：

```text
design_brief.json / design_brief.md
requirement_clarification_report.json / requirement_clarification_report.md
requirement_clarification_comment.md
requirement_change_report.json / requirement_change_report.md
style_card.json / style_card.md
creative_pack.json / creative_pack.md
style_transfer_report.json / style_transfer_report.md
style_alignment_report.json / style_alignment_report.md
design_decision_record.json / design_decision_record.md
image_generation_batch.json / image_generation_batch.md
candidate_evaluation.md
image_generation_jobs.json / image_generation_jobs.md
pixpark_requests.jsonl
generation_approval_ticket.md
image_execution_package.json / image_execution_package.md
pixpark_execution_runbook.md
generation_results_template.json
image_generation_results.json
generated_gallery.md
delivery_candidates.md
candidate_style_drift_report.json / candidate_style_drift_report.md
candidate_comparison_matrix.json / candidate_comparison_matrix.md
candidate_review.json / candidate_review.md
psd_handoff_plan.json / psd_handoff_plan.md
layer_map.md
slice_checklist.md
psd_handoff_package.json / psd_handoff_package.md
psd_handoff_approval_ticket.md
psd_slice_spec_report.json / psd_slice_spec_report.md
delivery_readiness_report.json / delivery_readiness_report.md
design_workflow_plan.json / design_workflow_plan.md
designer_review_packet.json / designer_review_packet.md
designer_cockpit.json / designer_cockpit.md
doctor_report.json / doctor_report.md
meegle_writeback_draft.json / meegle_writeback_draft.md
meegle_writeback_comment.md
meegle_writeback_approval_ticket.md
delivery_manifest.json / delivery_manifest.md
review_report.json / review_report.md
style_memory_curation_report.json / style_memory_curation_report.md
asset_index.json / asset_index.md
delivery_package.json / delivery_package.md
approval_ticket.md
project_profile.json / project_profile.md
project_profile_update_report.json / project_profile_update_report.md
workitem_intake_diagnostics.json / workitem_intake_diagnostics.md
automation_plan.json / automation_plan.md
automation_stub.ps1
photoshop_export_dry_run.jsx
photoshop_script_readme.md
photoshop_script_manifest.json
latest_learning_digest.json / latest_learning_digest.md
latest_audit.json / latest_audit.md
latest_transition.json / latest_transition.md
session_resume.json / session_resume.md
```

## 安全边界

当前版本默认遵守以下安全边界：

- 不自动发布 Meegle 评论。
- 不自动流转 Meegle 工作流节点。
- 不自动执行 Pixpark 或其他出图工具。
- 不自动消耗出图额度。
- 不自动打开或控制 Photoshop。
- 不自动导出 PSD。
- 不覆盖正式资产。
- 不下载远程候选图作为正式交付。
- 不把 `K3` 待验证假设当作已确认规则。
- 所有高影响动作必须经过设计师显式确认。

## 自进化和自动学习

系统会从以下来源沉淀经验：

- 项目需求。
- 工作项评论。
- 设计师反馈。
- 候选图评审。
- 风格参考图。
- 项目档案更新。
- 同品类风格底座。
- 交付前检查结果。

知识等级说明：

```text
K1：强规则，通常来自明确规范或高置信项目约束。
K2：已确认经验，通常来自设计师反馈或稳定项目偏好。
K3：待验证假设，只能作为探索方向，不能直接进入正式交付约束。
K4：禁忌或负向规则，用于避免错误风格、错误构图或错误交付方式。
```

学习摘要会写入：

```text
memory/projects/<project>/latest_learning_digest.json
memory/projects/<project>/latest_learning_digest.md
```

## 本地运行与版本管理

当前仓库已经推送到 GitHub：

```text
https://github.com/wgq628/CrealityOS
```

当前主分支：

```text
main
```

检查当前状态：

```bash
git status --short --branch
```

提交本地修改：

```bash
git add .
git commit -m "your message"
git push
```

## 备注

- `workspace/*.log` 已忽略，不会提交本地控制台日志。
- `.codex/` 已忽略，不会提交本地 Codex 环境元数据。
- `workspace/runs/` 和 `workspace/deliveries/` 默认忽略具体产物，只保留 `.gitkeep`。
- `memory/projects/`、`memory/reviews/`、`memory/sessions/` 等运行记忆目录默认忽略具体数据，只保留 `.gitkeep`。
- 如果要上传真实运行产物或项目记忆，需要先确认其中不包含隐私、客户资料、内部路径或敏感设计素材。
