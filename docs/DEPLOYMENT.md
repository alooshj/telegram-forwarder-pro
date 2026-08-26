# Deployment Guide — Telegram Forwarder Pro

## Overview

This guide walks you through deploying Telegram Forwarder Pro with **zero cost** and **no credit card required**.

## Required Accounts

| Service | Account | Credit Card |
|---------|---------|-------------|
| Telegram | Any phone number | ❌ |
| MongoDB Atlas | Email signup | ❌ |
| Render | GitHub login | ❌ |

---

## Step 1: Telegram API Credentials

1. Visit [https://my.telegram.org](https://my.telegram.org)
2. Log in with your phone number
3. Navigate to **API Development Tools** → **Create New Application**
4. Record:
   - **api_id** (numeric, e.g., `12345678`)
   - **api_hash** (hex string)

---

## Step 2: MongoDB Atlas (Free Tier M0)

1. Sign up at [https://mongodb.com/cloud/atlas](https://mongodb.com/cloud/atlas) — **no credit card**
2. Click **"Build a Database"**
3. Choose provider: **AWS** / region: nearest to you
4. Select **M0 (Free tier)** cluster
5. Under **Security Quickstart**:
   - Database username: create username (e.g., `forwarder`) + password
   - Network access: **Allow access from anywhere** (`0.0.0.0/0`) — required for Render
6. Click **Finish and Close**
7. Click **Connect** → **Drivers** → copy the connection string

```
mongodb+srv://forwarder:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
```

Save this string — you'll need it in the next step.

---

## Step 3: Session String

Generate your session string by running the generator script locally:

```bash
pip install -r requirements.txt
python src/utils/session_generator.py
```

Enter your `api_id`, `api_hash`, and phone number. The script will:
1. Send a login code to Telegram
2. Ask you to enter the code
3. Output your `SESSION_STRING`

Store this — it's your userbot authentication token (like a password — keep it secret).

---

## Step 4: Environment Configuration

Clone this repo, then create your `.env`:

```bash
cp config/.env.example config/.env
```

Edit `config/.env` with your credentials:

```env
API_ID=12345678
API_HASH=your_api_hash_here
SESSION_STRING=your_generated_session_string_here
MONGO_URI=mongodb+srv://forwarder:password@cluster0.xxxxx.mongodb.net/telegram_forwarder?retryWrites=true&w=majority
MONGO_DB=telegram_forwarder
SECRET_KEY=use-a-random-secret-key-here
LOG_LEVEL=INFO
```

---

## Step 5: Deploy to Render (Free Tier)

### Option A: One-Click Deploy

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/your-username/telegram-forwarder-pro)

### Option B: Manual Deploy

1. Fork this repository to your GitHub account
2. Go to [https://dashboard.render.com](https://dashboard.render.com)
3. Click **"New"** → **"Web Service"**
4. Connect your GitHub repo
5. Configure:
   - **Name**: `telegram-forwarder-pro`
   - **Region**: closest to your MongoDB cluster
   - **Branch**: `main`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120 main:app`
6. Add environment variables from your `.env` file
7. Click **"Create Web Service"**

> **Free tier note**: Render free tier includes 750 hours/month (enough for 24/7). Spins down after 15 min idle but cold-start is fast (~30s).

---

## Step 6: First Run

After deployment completes (2-3 minutes):

1. Visit your Render app URL (e.g., `https://telegram-forwarder-pro.onrender.com`)
2. The dashboard should show status: **Disconnected**
3. Click **"Start Forwarder"**
4. The status should change to **Running & Connected**
5. Add forwarding rules via the **"Forwarding Rules"** tab
6. Configure text transformations in the **"Text Rules"** tab
7. Exclude channels via the **"Blacklist"** tab

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `Invalid API ID` on login | Verify api_id/api_hash from my.telegram.org |
| `RPCError: AUTH_TOKEN_EXPIRED` | Regenerate SESSION_STRING |
| MongoDB connection timeout | Ensure 0.0.0.0/0 is whitelisted in Atlas |
| Dashboard not loading | Check all env vars are set in Render dashboard |
| Forwarding not happening | Check rules are active (`active: true`) and channels are accessible |

---

## Local Development

```bash
# Activate venv
source venv/bin/activate

# Run dashboard (development mode)
python main.py

# Run tests
python -m unittest discover -s tests -v
```

---

## Docker (Local Deployment)

```bash
docker build -t telegram-forwarder-pro .
docker run -p 5000:5000 --env-file config/.env telegram-forwarder-pro
```

Visit `http://localhost:5000` in your browser.
