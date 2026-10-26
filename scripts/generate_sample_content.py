"""Write original, unreviewed development content templates. Never publish automatically."""

import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "content" / "activities"
root.mkdir(parents=True, exist_ok=True)
groups = {
    "writing": [
        "写下此刻的一句话",
        "记下一件小事",
        "列出今天需要的支持",
        "给自己写一条温柔留言",
        "记录一次短暂的轻松",
    ],
    "daily_care": [
        "留三分钟休息",
        "整理眼前一小块空间",
        "暂停一下手头的工作",
        "给自己安排一段空白",
        "观察当前环境的舒适度",
    ],
    "mindfulness": [
        "观察窗外的颜色",
        "留意周围的声音",
        "看看身边的物品",
        "觉察此刻身体感受",
        "安静观察一个小物件",
    ],
    "movement": [
        "按舒适程度走一小段路",
        "站起来换一个位置",
        "做一次轻缓伸展",
        "在合适的地方慢慢走走",
        "留意走路时的感受",
    ],
    "music": [
        "选择一首自己喜欢的歌",
        "听一段自己已有的环境音",
        "安静听完一小段旋律",
        "记录音乐带来的感受",
        "为休息挑选一段声音",
    ],
}
items = []
for kind, titles in groups.items():
    for index, title in enumerate(titles):
        items.append(
            {
                "slug": f"draft-{kind.replace('_', '-')}-{index + 1}",
                "version": 1,
                "title": title,
                "type": kind,
                "duration_minutes": [2, 3, 5, 5, 10][index],
                "scenes": ["home", "office"]
                if kind != "movement"
                else ["home", "outdoor"],
                "steps": [
                    {
                        "order": 1,
                        "text": f"开发草稿：{title}。请由内容维护者完善具体步骤后审核。",
                    },
                    {
                        "order": 2,
                        "text": "按个人舒适程度选择，可随时停止，不必完成或填写反馈。",
                    },
                ],
                "audio_asset_key": None,
                "suitability_note": "未审核草稿，不能直接用于正式发布。",
                "source_name": "项目原创待审核草稿",
                "source_url": None,
                "license_note": "原创文字草稿，正式发布前复核；不包含音乐授权。",
                "reviewer": None,
                "reviewed_at": None,
                "review_due_at": None,
                "status": "draft",
            }
        )
(root / "drafts.json").write_text(
    json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(f"Created {len(items)} draft activity templates (not published).")
