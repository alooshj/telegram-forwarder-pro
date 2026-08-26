# Telegram Forwarder Pro

A **non-programmer-friendly, 24/7 automated Telegram post forwarder and content transformer** designed for commercial use. Built for zero-cost deployment on free-tier infrastructure (MongoDB Atlas M0 + Render/Koyeb free tier).

## Features

- ✅ **24/7 Automated Forwarding** — Fetches posts from source channels and forwards to target channels without missing or duplicating
- ✅ **Exclusion/Blacklist** — Prevents forwarding to/from specific channel IDs
- ✅ **Automatic Post Editing** — Username/link replacement, text stripping, and custom branding footers
- ✅ **Session String Auth** — Easy Telegram login via generated session strings (no phone number exposure in code)
- ✅ **Web Dashboard** — Beginner-friendly interface to start/stop tasks, manage rules, and view real-time logs
- ✅ **Zero-Cost Infrastructure** — Runs entirely on free tiers (MongoDB Atlas M0, Render free tier)
- ✅ **Rate-Limit Protection** — Automatic FLOOD_WAIT handling and retry logic
- ✅ **Auto-Reconnect** — Recovers from connection drops without manual intervention

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Web Dashboard (Flask)                  │
│  ┌──────────────┐  ┌────────────┐  ┌──────────────┐   │
│  │ Start/Stop   │  │ Rules CRUD │  │ Real-time    │   │
│  │ Control      │  │ Manager    │  │ Log Viewer   │   │
│  └──────────────┘  └────────────┘  └──────────────┘   │
├──────────────────┬──────────────────┬─────────────────┤
│                  │                  │                 │
│   Forwarding     │   Rules Engine   │   MongoDB Atlas │
│   Engine         │   (Text Trans-  │   (M0 Free Tier)│
│   (Telethon)     │   formation)    │                 │
│  ▪ Fetch posts   │  ▪ Replace      │  ▪ Rules        │
│  ▪ Forward       │  ▪ Regex Strip  │  ▪ Sessions     │
│  ▪ Deduplicate  │  ▪ Footer Brand │  ▪ Post History │
│  ▪ FloodWait     │  ▪ Blacklist    │  ▪ Blacklist    │
└─────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Get Telegram API Credentials

1. Go to [https://my.telegram.org](https://my.telegram.org)
2. Log in with your phone number
3. Go to "API development tools"
4. Create a new application
5. Copy your **API ID** and **API HASH**

### 2. Generate Session String

```bash
cd telegram-forwarder-pro
python src/utils/session_generator.py
```

Follow the prompts with your API ID, API HASH, and phone number. The script will generate a session string.

### 3. Configure Environment

```bash
cp config/.env.example config/.env
# Edit config/.env and add your credentials:
#   - API_ID and API_HASH from step 1
#   - SESSION_STRING from step 2
#   - MONGO_URI from your MongoDB Atlas connection string
```

### 4. Set Up MongoDB Atlas (Free Tier)

1. Go to [https://mongodb.com](https://mongodb.com) and sign up (no credit card required)
2. Create a free cluster (M0)
3. Go to "Network Access" → "Add IP Address" → "Allow access from anywhere" (for free tier)
4. Go to "Database Access" → "Add New Database User"
5. Create a username/password and get the connection string
6. Replace the placeholder in your `.env` file

### 5. Run Locally

```bash
pip install -r requirements.txt
python main.py
```

Visit `http://localhost:5000` in your browser.

## Deployment

### Deploy to Render (Free Tier)

1. Fork or clone this repository
2. Go to [https://dashboard.render.com](https://dashboard.render.com)
3. Click "New" → "Web Service"
4. Connect your GitHub repo
5. Set the build command: `pip install -r requirements.txt`
6. Set the start command: `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120 main:app`
7. Add environment variables from your `.env` file
8. Deploy!

> **Note:** Render free tier spins down after 15 minutes of inactivity but stays within the 750 free monthly hours (enough for 24/7 operation).

### Deploy with Docker

```bash
docker build -t telegram-forwarder-pro .
docker run -p 5000:5000 --env-file config/.env telegram-forwarder-pro
```

## Project Structure

```
telegram-forwarder-pro/
├── main.py                    # Entry point - starts web dashboard + forwarder
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Container build definition
├── Procfile                   # Render/Heroku process definition
├── render.yaml                # Render deployment config
├── config/
│   └── .env.example           # Environment template
├── src/
│   ├── forwarder/
│   │   └── engine.py          # Telegram client + forwarding logic
│   ├── rules/
│   │   └── engine.py          # Text transformation rules engine
│   ├── utils/
│   │   ├── database.py        # MongoDB connection manager
│   │   └── session_generator.py  # Session string generator
│   ├── web/
│   │   └── api.py             # Flask REST API
│   └── dashboard/
│       ├── templates/
│       │   └── index.html     # Web dashboard UI
│       └── static/            # CSS/JS/images
├── tests/
│   └── test_rules_engine.py   # Unit tests
├── deploy/                    # Deployment scripts
├── docs/                      # Documentation
└── logs/                      # Application logs
```

## Usage

### Managing Forwarding Rules

Add a forwarding rule via the API:

```bash
curl -X POST http://localhost:5000/api/rules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "News Channel → Archive",
    "source_id": -1001234567890,
    "target_id": -1000987654321,
    "type": "replace",
    "pattern": "old-brand",
    "replacement": "new-brand",
    "priority": 1,
    "active": true
  }'
```

### Transformation Rule Types

| Type | Description | Fields |
|------|-------------|--------|
| `replace` | Simple text replacement | `pattern`, `replacement` |
| `regex` | Regex-based replacement | `pattern`, `replacement` |
| `strip` | Remove matching text | `pattern` |
| `footer` | Append text/footer | `replacement` |
| `prefix` | Prepend text | `replacement` |

Rules are applied in priority order (lower number = applied first).

### Blacklisting Channels

```bash
# Add to blacklist
curl -X POST http://localhost:5000/api/blacklist \
  -H "Content-Type: application/json" \
  -d '{"channel_id": -1001234567890, "reason": "Spam"}'

# Remove from blacklist
curl -X DELETE http://localhost:5000/api/blacklist/-1001234567890
```

## License

MIT License — see LICENSE file.
