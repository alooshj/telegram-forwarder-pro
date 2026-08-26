# Free Tier Deployment Matrix (Aug 2026)

## Platform Comparison for 24/7 Telegram Userbot

| Platform    | Free Specs                          | 24/7 Viability | Card Required | Verdict         |
|-------------|-------------------------------------|----------------|---------------|-----------------|
| **Render**  | 750 hrs/mo, 512MB RAM, 5GB egress   | With keep-alive | No            | ✅ Primary      |
| **Koyeb**   | Closed to new users (Mistral)       | N/A            | Yes           | ❌ Deprecated   |
| **Replit**  | Free apps expire after 30 days      | Not suitable   | No            | ❌ Not 24/7     |
| **Railway** | $5 trial → $1/mo                   | Not free       | Yes           | ❌ Not free     |
| **Fly.io**  | 2 VM-hr trial only                 | Trial only     | Yes           | ❌ No free tier |
| **Supabase**| 500MB DB, serverless functions      | Scale-to-zero  | No            | ⚠️ Backup only  |

## Key Constraints for Telegram Userbots
- **MTProto is a persistent TCP connection** → cannot scale-to-zero
- Requires **always-on process** → Render free tier with keep-alive ping is optimal
- Needs **port 443/80 outbound** for Telegram servers (unblocked on Render free tier)
- Requires **persistent storage** for session string + post history → MongoDB Atlas M0 or local SQLite

## MongoDB Atlas Free Tier (M0)
- **512MB storage**, shared RAM
- **No credit card required** for new accounts
- **Global IP whitelist** required (use 0.0.0.0/0 for Render)
- Connection string format:
  ```
  mongodb+srv://<username>:<password>@cluster0.<project_id>.mongodb.net/<db_name>?retryWrites=true&w=majority&appName=<app_name>
  ```

## Render Free Tier Setup
1. **Service Type**: Web Service
2. **Build Command**: `pip install -r requirements.txt`
3. **Start Command**: `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120 src.web.api:app`
4. **Environment Variables**:
   - `MONGODB_URI`: Atlas connection string
   - `API_ID`: From my.telegram.org
   - `API_HASH`: From my.telegram.org
   - `SESSION_STRING`: Generated via session_generator.py
5. **Keep-Alive**: UptimeRobot monitor on `/api/status` every 5 minutes

## Common Pitfalls
- **500 errors**: Often caused by missing env vars or Atlas IP restrictions
- **Connection timeouts**: `serverSelectionTimeoutMS=5000` may not be enough — fallback to SQLite
- **Port binding**: Render uses dynamic `$PORT` env var — never hardcode port
- **Log directory**: `/app/logs` may not exist on first deploy — create in `main.py`
