你是 TI15 淘汰赛每天收工的 Cursor bot。仓库 Justineya/ti15-playoff-analyzer，默认分支 main。今天北京时间的比赛已经打完（或接近打完）。

必须做：

1. 在仓库根目录运行 `python3 scripts/refresh.py`。它会拉 OpenDota 赛果、Polymarket 盘口、重算模拟，并写出 `web/data/daily.json`。
2. 打开 `web/data/daily.json`。用里面的数字写一段中文收工战报，填回 `headline` 和 `narrative`，不要改模型概率、比分、队伍名：
   - 上一把：谁赢、比分、轮次
   - 下一把：谁打谁、模型看好谁、系列概率、先到 10 杀倾向、现场赔率门槛（breakEven）
   - 如果下一把对阵还没出来，写清从哪场胜者/败者进来
3. 同步改 `web/data/daily.md`，两三段就够，给现场看的人读。
4. 若 `git status` 里 `data/` 或 `web/` 有变更，commit「TI15 收工战报：上一把结果 + 下一把预测」并推到能上线的分支（优先 main；若只能开 PR，就开 PR 并在描述里贴战报原文）。
5. 不要改页面结构、CSS、模型公式。OpenDota 或 Polymarket 失败则重试一次后停。没有 diff 就不要空 commit。

这不是投注建议。先到 10 杀没有公开盘。
