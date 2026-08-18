# TI15 淘汰赛分析台

观赛只用这一个地址：

**https://justineya.github.io/ti15-playoff-analyzer/**

打开就是下一场：谁打谁、买哪边、下多少。对阵图、已打的局和模型说明收在右上角「历史数据」。

淘汰赛期间（8/20–8/23）现场页每 30 秒向 Polymarket 拉实时序列赔率；仓库里还有大约每 20 分钟的快照兜底。每晚北京时间 23:05 会写收工战报：上一把比分 + 下一把看好谁。Thunderpick / GG.BET / Pinnacle 没有浏览器能直读的公开接口，只做跳转。先到 10 杀没有公开盘，用页面里的计算器手填现场赔率。

Cursor bot：仓库 Secrets 里加一条 `CURSOR_API_KEY` 就行，见 [`AUTOMATION.md`](AUTOMATION.md)。

## 口径

- 先到 10 杀：哪支队伍先获得 10 次英雄击杀
- 参与次数 = 击杀 + 助攻
- 模型 = TI15 地图 100% + EWC 八强地图 45%
