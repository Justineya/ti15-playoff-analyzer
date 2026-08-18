# TI15 淘汰赛分析台

观赛只用这一个地址：

**https://justineya.github.io/ti15-playoff-analyzer/**

打开就是下一场：谁打谁、买哪边、下多少。对阵图、已打的局和模型说明收在右上角「历史数据」。

淘汰赛期间（8/20–8/23）现场页每 30 秒向 Polymarket 拉实时赔率；仓库大约每 5 分钟拉 OpenDota。**每打完一局**更新下一局看好谁和盘口门槛，并拉 Cursor bot。Thunderpick / GG.BET / Pinnacle 只做跳转。先到 10 杀没有公开盘，用计算器手填。

Cursor bot：仓库 Secrets 里加一条 `CURSOR_API_KEY` 就行，见 [`AUTOMATION.md`](AUTOMATION.md)。

## 口径

- 先到 10 杀：哪支队伍先获得 10 次英雄击杀
- 参与次数 = 击杀 + 助攻
- 模型 = TI15 地图 100% + EWC 八强地图 45%
