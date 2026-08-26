# Project Architecture

## Core Stack
- **Telegram Client**: Telethon (MTProto userbot) — handles scraping from private channels
- **Web Framework**: Flask — REST API + dashboard server
- **Database**: MongoDB Atlas M0 (primary) with SQLite fallback — auto-detects on startup
- **Frontend**: Vanilla HTML/CSS (Tailwind CDN) embedded in Flask template
- **Deployment**: Render free tier (web service + background worker model)
- **Keep-Alive**: UptimeRobot HTTP monitor pings `/api/status` every 5 minutes

## Module Boundaries
```
src/
├── forwarder/
│   └── engine.py           # Telethon MTProto client + forwarding loop
├── rules/
│   └── engine.py           # Text transformation engine (replace, regex, strip, footer, prefix)
├── utils/
│   ├── config.py           # Env var loader — OS env > .env > defaults
│   ├── database.py         # Dual-backend: MongoDB + SQLite fallback
│   └── session_generator.py
├── web/
│   └── api.py              # Flask REST API + dashboard route
└── dashboard/
    └── templates/
        └── index.html      # Single-file Vue-free dashboard (28KB)

main.py                     # Entry point — starts Flask + forwarder thread
```

## Data Flow
1. Config loaded via `load_config()` — reads `MONGODB_URI`, `API_ID`, `API_HASH`, `SESSION_STRING`
2. DB initialized via `get_db_connection()` — tries Atlas, falls back to local SQLite
3. Forwarder engine starts in daemon thread — connects to Telegram as userbot
4. On message received:
   - Check blacklist (`is_blacklisted`)
   - Check duplicates (`_is_duplicate`)
   - Apply rules (`RulesEngine.apply_rules`)
   - Forward to target channels
5. Web API serves dashboard + REST endpoints for rule/blacklist/log management

## Key Design Decisions
- **Dual DB backend**: MongoDB Atlas is preferred for multi-user support, but SQLite ensures the app always works even without network access (free tier friendly)
- **Threading model**: Flask runs in main thread; forwarder runs in daemon thread — no blocking
- **Error isolation**: Each message is processed in try/except; failures don't crash the loop
- **FLOOD_WAIT handling**: Per-channel timestamp blocking + asyncio.sleep retry
