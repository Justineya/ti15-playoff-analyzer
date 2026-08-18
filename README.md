# TI15 淘汰赛分析台

观赛只用这一个地址（发布成功后生效）：

**https://justineya.github.io/ti15-playoff-analyzer/**

淘汰赛期间（8/20–8/23）GitHub Actions 约每 20 分钟自动：拉 OpenDota 新局 → 解开对阵晋级 → 抓 Polymarket 快照 → 重跑模拟 → 发布站点。页面版式不会改，只更新数据和顶栏时间。

上海现场请**不要依赖**右上角「刷新赔率」（Polymarket 在国内常打不开）。赔率以页面里已烧进去的快照为准。先到 10 杀没有公开盘，用注码计算器手填现场赔率。

## 本地重建

```bash
python3 scripts/refresh.py
```

## 口径

- 先到 10 杀：哪支队伍先获得 10 次英雄击杀
- 参与次数 = 击杀 + 助攻
- 模型 = TI15 地图 100% + EWC 八强地图 45%
