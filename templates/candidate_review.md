# 候选图评审回写模板

## JSON 输入格式

```json
{
  "variants": [
    {
      "variant_id": "V01",
      "decision": "approved",
      "scores": {
        "style_fit": 5,
        "requirement_fit": 5,
        "conversion": 4,
        "psd_ready": 4
      },
      "strengths": ["项目风格准确", "主体层级清楚"],
      "issues": [],
      "revision_notes": ["可继续精修按钮材质"],
      "learning": "保留 V01 的主体层级和按钮材质方向",
      "generated_assets": ["workspace/renders/v01.png"]
    }
  ]
}
```

## 决策含义

- `approved`：采纳为项目记忆，优先升级为 K2；包含“必须/禁止/统一”等强词时可进入 K1。
- `rejected`：记录为近期驳回点，下次出图默认避开。
- `revise`：记录为 K3 待验证假设，不当作确定风格规则。

## 简写文本格式

也可用每行一条：

```text
V01 | approved | 主体层级准确，可以进入 PSD 精修 | 保留主体层级和按钮留白方式
V02 | rejected | 背景太亮，利益点抢主体 | 避免背景过亮
V03 | revise | 动势可取但透视过强 | 强动势保持 K3 待验证
```
