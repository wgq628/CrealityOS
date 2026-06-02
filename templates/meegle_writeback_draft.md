# Meegle 回写草稿模板

## 目的

把本地 design-copilot 的阶段性产物整理成可发布到飞书项目工作项评论的草稿。

## 安全边界

- 默认只生成草稿，不调用 `meegle comment add`。
- 发布前必须人工检查评论内容。
- 不把 K3 待验证假设写成确定结论。
- 不暴露敏感账号、未授权素材、内部实验信息。
- 路径如果是本地路径，需要确认协作者是否能访问。

## 产物

- `meegle_writeback_draft.json`
- `meegle_writeback_draft.md`
- `meegle_writeback_comment.md`
- `meegle_writeback_approval_ticket.md`

## 后续发布命令示例

Dry-run:

```bash
design-copilot publish-meegle-writeback --project-key <project_key> --work-item-id <work_item_id>
```

确认发布：

```bash
design-copilot publish-meegle-writeback --project-key <project_key> --work-item-id <work_item_id> --execute --confirm-token PUBLISH_MEEGLE_WRITEBACK
```

底层 Meegle 命令：

```bash
meegle comment add --project-key <project_key> --work-item-id <work_item_id> --content '<reviewed comment>' --format json
```

必须先通过确认票后再执行。
