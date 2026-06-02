# PSD 交接 staging 包模板

## 目的

把 `psd_handoff_plan.json` 中选中的候选资产整理成一个安全工作包，供设计师进入 PSD 精修、切图或最终交付前复核。

## 安全边界

- 只复制本地存在的候选图。
- 远程 URL 只登记为 external reference，不自动下载。
- 不覆盖已有正式文件。
- 不自动对外发送。
- 正式交付前必须再次人工确认。

## 产物

- `psd_handoff_package.json`
- `psd_handoff_package.md`
- `psd_handoff_approval_ticket.md`
- `references/<variant>/...`

## 后续动作

- 用 `layer_map.md` 重建 PSD 图层。
- 用 `slice_checklist.md` 拆分切图。
- 精修后再运行正式交付 staging 或人工确认交付。
