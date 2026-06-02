# 生成结果登记模板

## JSON 输入格式

```json
{
  "assets": [
    {
      "variant_id": "V01",
      "path": "D:/renders/v01_result.png",
      "notes": ["candidate", "角色表情最好"],
      "width": 1080,
      "height": 1920
    },
    {
      "variant_id": "V04",
      "url": "https://example.com/v04_result.png",
      "notes": ["切图友好"]
    }
  ]
}
```

## 简写文本格式

```text
V01 | D:/renders/v01_result.png | candidate;角色表情最好
V04 | https://example.com/v04_result.png | 切图友好
```

## 生成产物

- `image_generation_results.json`：结构化结果索引
- `generated_gallery.md`：候选图预览与来源记录
- `delivery_candidates.md`：进入 PSD/切图前的候选清单

## 后续闭环

先用 `generated_gallery.md` 评审图片，再把结论写入 `candidate_review.json` 并运行 `ingest-candidate-review`。
