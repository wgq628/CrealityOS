# Meegle 工作流流转草稿模板

## 目的

把“进入待评审 / 确认节点 / 回滚节点”等 Meegle 工作流操作变成可审阅草稿，避免智能体自动改变飞书项目状态。

## 安全边界

- 默认只生成草稿，不调用 `meegle workflow transition`。
- 真实流转必须显式 `--execute`。
- 真实流转还必须提供 `--confirm-token TRANSITION_MEEGLE_WORKFLOW`，或确认文件包含 `[x] 允许流转 Meegle 工作项`。
- 流转前必须确认工作项、节点、评审状态和交付物准备情况。

## 常用命令

```bash
design-copilot create-meegle-transition-draft --project-key DEMO --work-item-id 123456 --action confirm --node 待评审
design-copilot publish-meegle-transition --project-key DEMO --work-item-id 123456
design-copilot publish-meegle-transition --project-key DEMO --work-item-id 123456 --execute --confirm-token TRANSITION_MEEGLE_WORKFLOW
```

## 底层 Meegle 命令

```bash
meegle workflow transition --project-key DEMO --work-item-id 123456 --action confirm --node-ids 待评审 --format json
```
