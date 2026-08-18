# Cursor bot

只要一把 Cursor API key。

1. 打开 https://cursor.com/settings 建 API key  
2. 打开 https://github.com/Justineya/ti15-playoff-analyzer/settings/secrets/actions  
3. New secret，名字必须是 `CURSOR_API_KEY`，值贴那把 key

开赛后大约每 5 分钟查一次 OpenDota。**每打完一局**才拉 Cursor bot：上一局谁赢、下一局看好谁、盘口门槛。不是等到每天晚上。

现在去 Actions 里手动 Run 一次只是测试，不会把自动任务关掉，也不会挡住局间触发。
