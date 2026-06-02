# 图像生成执行交接包模板

## 目的

把已确认的 `image_generation_jobs.json` 拆成可执行交接文件：

- 每个任务一个 payload JSON
- 一个 Pixpark 执行说明
- 一个生成结果登记模板
- 一个本地安全说明和后续闭环清单

## 默认安全状态

- 不自动调用 Pixpark
- 不自动消耗算力
- 不下载远程结果
- 不写入正式交付目录
- 不发布到 Meegle

## 后续闭环

生成完成后填写 `generation_results_template.json`，再运行 `register-image-results` 生成 `generated_gallery.md` 和 `delivery_candidates.md`。
