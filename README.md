# Discord Like Bot

Simple Discord bot exposing a `/like uid` slash command that forwards to the Free Fire API.

Setup

1. Create a bot in the Discord Developer Portal and copy its token.
2. (Optional) For fast command registration during development set `GUILD_ID` to your guild id.
3. Set environment variables (examples below).
4. Install dependencies and run.

Install

```bash
python -m pip install -r requirements.txt
```

Run (PowerShell)

```powershell
$env:DISCORD_TOKEN = "YOUR_TOKEN_HERE"
# optional: $env:GUILD_ID = "YOUR_GUILD_ID"
python bot.py
```

Run (Windows cmd)

```cmd
set DISCORD_TOKEN=YOUR_TOKEN_HERE
rem optional: set GUILD_ID=YOUR_GUILD_ID
python bot.py
```

Notes

- The command calls: `https://freefirebd.up.railway.app/like?uid={uid}&server_name=bd`.
- If you want the bot to register commands only to a specific guild while developing, set `GUILD_ID`.
