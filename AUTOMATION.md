# 每天收工 · Cursor bot

淘汰赛每晚北京时间 23:05，GitHub Actions 会：

1. 跑 `python3 scripts/refresh.py`（赛果 + 盘口 + 模拟 + `web/data/daily.json`）
2. 推到 `main`，现场页立刻能看到上一把比分和下一把看好谁
3. 若仓库 Secrets 里有 `CURSOR_API_KEY`，再拉起一个 Cursor cloud agent，用中文把战报写顺

现场页也会每 30 秒向 Polymarket 拉实时序列赔率。Thunderpick / GG.BET / Pinnacle 没有能从浏览器直读的公开接口，只留跳转。

## 你需要做的（二选一，不要两个都开）

### A. 推荐：给仓库加一把 Cursor API key

1. 打开 https://cursor.com/settings 建 API key
2. 仓库 Settings → Secrets → Actions → `CURSOR_API_KEY`
3. 8/20–8/23 每天 23:05 会自动 spawn Cursor bot。提示词在 [`.github/eod-cursor-prompt.md`](.github/eod-cursor-prompt.md)

也可以在 Actions 里手动跑 **End-of-day briefing**。

### B. Cursor Automations 日历

打开 https://cursor.com/automations ，新建：

- Repository：`Justineya/ti15-playoff-analyzer`，branch `main`
- Trigger：cron `5 15 * * *`（UTC；即北京 23:05），8/20–8/23
- Prompt：把 [`.github/eod-cursor-prompt.md`](.github/eod-cursor-prompt.md) 全文贴进去

不要和 A 同时开，否则每晚会跑两次 bot。

## 可选：盘口刷新备份

GitHub Actions 已每 20 分钟刷新。若还要 Cursor 兜底：cron 每 30 分钟，提示词：

Run `python3 scripts/refresh.py` in the repo root. If git status shows changes under data/ or web/, commit with message "Auto-refresh TI15 playoff data." and push to main. Do not change page layout, CSS, or tab structure. If OpenDota or Polymarket fail, retry once then stop. If there is no diff, do nothing.
