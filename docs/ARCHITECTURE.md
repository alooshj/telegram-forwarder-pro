# Architecture Specification — Telegram Forwarder Pro

## Document Version
v1.0 — August 2026

## Table of Contents
1. [Overview](#1-overview)
2. [Module Structure](#2-module-structure)
3. [Data Flow](#3-data-flow)
4. [Non-Programmer UX](#4-non-programmer-ux)
5. [MongoDB Atlas M0 Integration](#5-mongodb-atlas-m0-integration)
6. [Reliability Features](#6-reliability-features)
7. [Deployment Architecture](#7-deployment-architecture)

---

## 1. Overview

Telegram Forwarder Pro is a commercial-grade, zero-cost Telegram auto-forwarder built on Telethon (MTProto). It allows non-programmers to:
- Select source and target Telegram channels
- Define text transformation rules (replace, strip, footer, prefix)
- Maintain a blacklist of channels
- Control everything via a web dashboard

### Core Constraints
- **Zero cost**: No credit card required. Uses MongoDB Atlas M0 + Render free tier.
- **24/7 reliability**: No missed posts, no duplicates, auto-reconnect, FLOOD_WAIT handling.
- **Non-programmer friendly**: Web UI handles all configuration. No code changes needed.

---

## 2. Module Structure

```
telegram-forwarder-pro/
├── main.py                    # Orchestrator: starts Flask + initializes DB
├── src/
│   ├── forwarder/engine.py    # Telethon client + forwarding loop
│   ├── rules/engine.py        # Text transformation + blacklist
│   ├── web/api.py             # Flask REST API (all endpoints)
│   ├── utils/database.py      # MongoDB connection manager
│   ├── utils/session_generator.py  # Session string CLI
│   └── dashboard/templates/index.html  # UI
├── config/.env.example        # Env template
├── Dockerfile                 # Container build
├── Procfile                   # Render process
└── render.yaml                # Render service definition
```

### Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `main.py` | Loads config, initializes DB, starts Flask server |
| `forwarder/engine.py` | MTProto client, periodic forwarding loop, FLOOD_WAIT handling, duplicate detection, auto-reconnect |
| `rules/engine.py` | Applies text transformation rules, checks blacklist membership |
| `web/api.py` | REST API: rule CRUD, blacklist CRUD, logs, start/stop, status |
| `utils/database.py` | MongoDB connection, collection helpers, TTL index for post history |
| `utils/session_generator.py` | Interactive CLI to generate session string for .env |
| `dashboard/templates/index.html` | Tailwind CSS dashboard with tabs for rules, blacklist, logs |

---

## 3. Data Flow

```
┌──────────┐    1. Message received    ┌──────────┐
│ Telegram │ ──────────────────────→ │ Forwarder │
│  Source  │                          │  Engine   │
└──────────┘                               │
                                           │ 2. Check processed_posts
                                           │    (duplicate prevention)
                                           ▼
                                  ┌─────────────┐    3. Apply rules
                                  │ RulesEngine │ ──────────────────→
                                  └─────────────┘    (replace/strip/footer/regex)
                                           │
                                           │ 4. Forward to target
                                           ▼
                                  ┌──────────┐
                                  │ Telegram │
                                  │  Target  │
                                  └──────────┘

                                           │
                                           │ 5. Record in MongoDB
                                           ▼
                              ┌─────────────────┐
                              │ MongoDB Atlas   │
                              │  (processed_posts│
                              │   , rules,       │
                              │   blacklist,     │
                              │   logs)          │
                              └─────────────────┘
```

### Flow Steps

1. **Message Capture**: Telethon event handler intercepts new messages in source channels.
2. **Duplicate Check**: Query `processed_posts` collection for `{source_id}:{message_id}` key. Skip if exists.
3. **Rule Application**: Load transformation rules from DB, apply in priority order.
4. **Forwarding**: Send transformed text via Telethon to target entity.
5. **Persistence**: Record `{source_id}:{message_id}` in `processed_posts` with TTL (30 days).

---

## 4. Non-Programmer UX

### Dashboard Tabs

| Tab | Action |
|-----|--------|
| **Forwarding Rules** | View, add, edit, delete forwarding route rules (source → target) |
| **Blacklist** | Add/remove channel IDs from blacklist |
| **Text Rules** | Configure transformation rules (replace, regex, strip, footer, prefix) |
| **Logs** | Real-time log viewer with timestamps |

### UX Principles
- All configuration via web UI — no terminal commands needed in normal operation
- One-click Start/Stop buttons
- Rule editor with dropdown for rule type, input fields for pattern/replacement
- Priority ordering via numeric input (lower = applied first)
- Inline status indicator (green = running, red = stopped)
- Auto-refreshing log panel (polls every 5 seconds)
- Form validation and error messages in browser

---

## 5. MongoDB Atlas M0 Integration

### Collections

| Collection | Purpose | TTL |
|-----------|---------|-----|
| `forwarding_rules` | Source→target routing rules | No |
| `rules` | Text transformation rules | No |
| `blacklist` | Excluded channel IDs | No |
| `processed_posts` | Deduplication history | 30 days |
| `forwarding_logs` | Application logs | 30 days |

### Free Tier Specs (M0)
- **512 MB storage** — sufficient for ~100K processed post records
- **Shared RAM/CPU** — adequate for low-to-moderate posting volume
- **500 max connections** — supports multiple userbots + web workers
- **No time limit** — permanently free
- **Network access**: Configurable IP whitelist (use 0.0.0.0/0 for free tier)

### Connection
- Connection string stored as `MONGO_URI` in environment
- `serverSelectionTimeoutMS=5000` for fast failure detection
- Indexes created on `source_id`, `target_id`, `forwarded_at`

---

## 6. Reliability Features

### No Duplicate Forwards
- Each forwarded post is recorded as `{source_id}:{message_id}` in `processed_posts`
- Before forwarding, check if key exists
- TTL index auto-cleans after 30 days

### No Missed Posts
- Periodic polling (every `CHECK_INTERVAL` seconds) using `iter_messages`
- `reverse=True` fetches oldest first → newest
- Last-seen offset tracked in DB

### FLOOD_WAIT Handling
- Catches `errors.FloodWaitError` from Telethon
- Stores timestamp + wait duration per channel
- Blocks further sends to that channel until wait expires
- 5-second buffer added to all waits

### Auto-Reconnect
- `TelegramClient` connection health check
- Max retries (default 3) with exponential backoff
- Re-initializes session from `SESSION_STRING` on reconnect

### Error Recovery
- All unhandled exceptions caught, logged, and retried
- Service restarts automatically on Render/Koyeb
- Logs persisted to MongoDB `forwarding_logs` collection

---

## 7. Deployment Architecture

### Primary: Render Free Tier (750 hrs/month ≈ 24/7)
- **Web service**: Python 3.11, 512MB RAM, free SSL
- **Auto-deploy** from GitHub
- **Free hours**: 750/month → covers one instance 24/7
- **Sleep**: Spins down after 15 min idle (cold start ~30-60s)
- **No credit card required**

### Backup: Koyeb Alternative
- If Render unavailable, deploy same Docker image to Koyeb
- Same zero-config setup

### Container
- Based on `python:3.11-slim`
- Gunicorn (1 worker, 4 threads) for production WSGI
- Dependencies cached in Docker layer
