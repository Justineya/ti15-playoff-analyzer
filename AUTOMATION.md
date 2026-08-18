# Optional Cursor Automation (backup)

Not required. GitHub Actions is the live path.

If you still want a Cursor Automation at https://cursor.com/automations :

- Trigger: cron every 30 minutes, 8/20–8/23
- Repository: Justineya/ti15-playoff-analyzer, branch main
- Prompt:

Run `python3 scripts/refresh.py` in the repo root. If git status shows changes under data/ or web/, commit with message "Auto-refresh TI15 playoff data." and push to main. Do not change page layout, CSS, or tab structure. If OpenDota or Polymarket fail, retry once then stop. If there is no diff, do nothing.
