# 候选方案对比矩阵

用于把 `V01/V02/V03/V04` 等候选方案放在同一张表里比较，避免只凭单张图的第一印象做决定。

## 必看字段

- `status`：`blocked` / `needs_designer_decision` / `candidate_selected`
- `recommended_variant_ids`：建议采纳的方案
- `revise_variant_ids`：建议修正或补评审的方案
- `rejected_variant_ids`：建议驳回或保留为反例的方案
- `rows`：每个方案的意图、资产数、偏移等级、评审结论、评分和推荐动作

## 安全边界

- 对比矩阵只做本地决策辅助，不自动发布到 Meegle。
- 对比矩阵不调用任何出图工具，不消耗生成算力。
- 当风格偏移为 `blocker` 时，不允许把该方案直接推进 PSD 或交付。
- 设计师仍是最终采纳、修正或驳回的负责人。
