# TI15 淘汰赛分析台

观赛只用这一个地址：

**https://justineya.github.io/ti15-playoff-analyzer/**

打开就是下一场：谁打谁、买哪边、下多少。主页下面是带队徽的对阵图。四天开赛时间在顶栏「赛程」。已打的局和模型说明收在右上角「历史数据」。想先看第一轮打完之后长什么样，打开模拟页：

**https://justineya.github.io/ti15-playoff-analyzer/demo.html**

淘汰赛期间（8/20–8/23）现场页每 30 秒向 Polymarket 拉实时赔率；仓库大约每 5 分钟拉 OpenDota，并跟液体百科核对四天开赛时间（主办方改点，倒计时跟着改）。**每打完一局**，上一局结果和下一局看好谁会直接写进这个网页。不用打开 Cursor。Thunderpick / GG.BET / Pinnacle 只做跳转。先到 10 杀没有公开盘，用计算器手填。

## 口径

- 先到 10 杀：哪支队伍先获得 10 次英雄击杀
- 参与次数 = 击杀 + 助攻
- 模型 = TI15 地图 100% + EWC 八强地图 45%
