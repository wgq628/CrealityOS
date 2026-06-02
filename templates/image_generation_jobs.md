# 图像生成任务队列模板

## 目的

把 `image_generation_batch.json` 中选中的 V01/V02/V03/V04 方案转成可确认、可追踪、可交给执行适配器的生成任务。

## 默认安全状态

- 默认状态：`pending_designer_confirmation`
- 不自动调用 Pixpark
- 不自动消耗算力
- 不自动写入正式交付目录
- 不自动对外发送

## 产物

- `image_generation_jobs.json`：完整任务队列
- `image_generation_jobs.md`：人工审阅版
- `pixpark_requests.jsonl`：逐条 Pixpark payload
- `generation_approval_ticket.md`：执行前确认单

## 后续闭环

生成图进入 staging 后，用 `candidate_evaluation.md` 评审，再运行 `ingest-candidate-review` 回写学习记忆。
