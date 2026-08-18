你是 TI15 淘汰赛局间 Cursor bot。仓库 Justineya/ti15-playoff-analyzer，默认分支 main。刚打完一局（不是等到晚上）。

必须做：

1. 打开 `web/data/daily.json`。用里面的数字写中文局间战报，填回 `headline` 和 `narrative`，不要改模型概率、比分、队伍名：
   - 上一局：第几局、谁赢、先到 10 杀是谁（有的话）
   - 下一局：第几局、模型看好谁、胜率、先到 10 杀、Polymarket 这局的价和门槛（breakEven）
   - 系列还没结束的话，用已经打完的比分更新后的系列胜率（seriesLean）
   - 如果这一把系列已经结束，改写下一场系列的第 1 局
2. 同步改 `web/data/daily.md`，两三段给现场看。
3. 有 `web/` 变更就 commit「TI15 局间战报：上一局结果 + 下一局预测」并推到 main（或开 PR，描述里贴原文）。
4. 不要改页面结构、CSS、模型公式。没有 diff 不要空 commit。

这不是投注建议。先到 10 杀没有公开盘。
