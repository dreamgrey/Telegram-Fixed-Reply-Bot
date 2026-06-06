# Telegram Fixed-Reply Bot

A Telegram bot that automatically replies to user messages with a preset multi-stage conversation flow. Designed for scenarios where you need consistent, timed, and human-like automated responses.

## Features

- **Multi-stage conversation flow** — 3-stage state machine: send intro messages → wait for reply → send follow-up → silence
- **Human-like delays** — Random 15-30s delay before replying (mark_read + typing), helps avoid anti-spam detection
- **Concurrency safety** — Per-user `asyncio.Lock` prevents reply mix-ups when users message simultaneously
- **Persistent state** — Completed users saved to JSON, survives restarts (no re-sending to same users)
- **Daily statistics** — Logs `replied` and `completed` counts per day with deduplication
- **Auto-reconnect** — Handles proxy/network disconnections with exponential backoff retry
- **Proxy support** — SOCKS5/HTTP proxy for regions with Telegram access restrictions
- **Offline message processing** — Optionally process unread messages from before bot startup
- **Graceful shutdown** — Triple-layer save protection (on-change + every 60s + on-exit)

## How It Works

```
User sends first message
  → wait 5-10s → mark_read
  → wait 10-20s → send MSG_1 + MSG_2 + MSG_2_5
  → start 5-minute timeout timer

User replies within 5min:
  → wait 5-10s → mark_read
  → wait 10-20s → send MSG_3
  → mark user as "completed" → never reply again

User does NOT reply within 5min:
  → auto-send MSG_3
  → mark user as "completed" → never reply again
```

## Prerequisites

- Python 3.8+
- Telegram API credentials (get at https://my.telegram.org/apps)
- (Optional) SOCKS5 proxy if Telegram is blocked in your region

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/your-username/telegram-fixed-reply-bot.git
cd telegram-fixed-reply-bot

# 2. Install dependencies
pip install telethon python-dotenv

# 3. Configure
cp .env.example .env
# Edit .env: fill in TELEGRAM_API_ID and TELEGRAM_API_HASH

# 4. Customize your messages
# Edit ai/client6_public.py - look for the "自定义" section:
#   MSG_1, MSG_2, MSG_2_5, MSG_3

# 5. Run
python ai/client6_public.py
```

## Configuration

See [.env.example](.env.example) for all available options:

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_API_ID` | Yes | Your Telegram API ID |
| `TELEGRAM_API_HASH` | Yes | Your Telegram API Hash |
| `TELEGRAM_PROXY` | No | SOCKS5 proxy (e.g. `socks5://127.0.0.1:7890`) |
| `DOWNLOAD_LINK` | No | Your target link (defaults to example URL) |
| `PROCESS_OFFLINE` | No | Process unread messages on startup (`true`/`false`) |

## Project Structure

```
├── ai/
│   ├── client6_public.py      # Main bot code (template - customize this)
│   └── client6.py             # (your private production version)
├── .env.example               # Configuration template
├── completed_users.json       # Auto-generated: completed user IDs
├── daily_stats.json           # Auto-generated: daily statistics
└── README.md
```

## Important Notes

- **Do not commit `.env`** — it contains your API credentials. Only commit `.env.example`.
- The bot replies to **all** incoming private messages (text and non-text like stickers/images).
- Once a user completes the 3-message flow, they are permanently marked as done and will receive no further replies.

## License

MIT