# 内容管理

`activities/drafts.json` 现已包含 25 项完整的原创文字活动，覆盖书写、日常关怀、觉察、轻量活动、音乐与声音五类，均已设置为 published。保留旧文件名和 slug，便于覆盖已有文件，并将同 slug 的数据库草稿直接升级，不产生重复活动。

每项活动均含具体步骤、可选参与及停止提示、适用说明和来源说明。内容由 AI 辅助编写并自动校验结构；reviewer 如实记录此方式，不代表人工或专业心理审核。reviewed_at 记录本次整理时间，review_due_at 为 180 天后的复核期限，届时未更新的活动会从页面隐藏。不要仅为恢复展示而虚构新的审核时间。

在服务器 `/srv/emotion/app/backend` 执行以下命令即可批量导入发布，无需逐项修改：

```bash
sudo -u emotion /srv/emotion/env/bin/python -m app.cli.import_content --path /srv/emotion/app/content --validate-only
sudo -u emotion /srv/emotion/env/bin/python -m app.cli.import_content --path /srv/emotion/app/content
```

第二条仅在校验成功后执行。导入是单次事务；相同发布数据重复导入不会产生新记录。已发布版本不能原地改写，后续内容变更应使用新版本 slug 并归档旧版本。导入后刷新页面即可，不需要重启或重新构建。

本地 `seed --demo` 可显式创建 3 项标明“开发演示”的联调活动，仅允许 development/test，不能作为生产审核记录。

音乐类是使用用户已有合法音源的文字指引，未内置音乐、录音或播放功能，不声称已取得第三方音频授权。所有活动只提供日常自我关怀建议，不承诺治疗效果。地区支持资源不含任何编造的号码，需要实际核验后维护。
