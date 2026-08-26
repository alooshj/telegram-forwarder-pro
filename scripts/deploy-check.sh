"""
Deployment Verification Script
-------------------------------
Checks that all required environment variables and files are present
before deploying to Render/Koyeb/etc.

Usage:
    chmod +x scripts/deploy-check.sh
    ./scripts/deploy-check.sh

Exits with 0 if all checks pass, 1 otherwise.
"""

#!/bin/bash
set -e

echo "🔍 Telegram Forwarder Pro — Pre-Deploy Checklist"
echo "================================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0

# ─── File Checks ──────────────────────
echo ""
echo "📁 Checking project files..."

for file in main.py render.yaml Dockerfile requirements.txt src/web/api.py src/forwarder/engine.py src/utils/config.py src/utils/database.py; do
    if [ -f "$file" ]; then
        echo "  ✅ $file"
    else
        echo "  ❌ $file — MISSING"
        ERRORS=$((ERRORS + 1))
    fi
done

# ─── Environment Variable Checks ──────
echo ""
echo "🔐 Checking environment variables..."

check_var() {
    if [ -n "$1" ]; then
        echo "  ✅ $2 (set, $3 chars)"
    else
        echo "  ⚠️  $2 — NOT SET"
        ERRORS=$((ERRORS + 1))
    fi
}

check_var "$API_ID" "API_ID" ${#API_ID}
check_var "$API_HASH" "API_HASH" ${#API_HASH}
check_var "$SESSION_STRING" "SESSION_STRING" ${#SESSION_STRING}
check_var "$MONGODB_URI" "MONGODB_URI" ${#MONGODB_URI}

# ─── Dependency Checks ─────────────────
echo ""
echo "📦 Checking Python dependencies..."

if [ -f "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
else
    PYTHON="python3"
fi

for module in flask flask_cors telethon pymongo dotenv; do
    if $PYTHON -c "import $module" 2>/dev/null; then
        echo "  ✅ $module"
    else
        echo "  ❌ $module — NOT INSTALLED"
        ERRORS=$((ERRORS + 1))
    fi
done

# ─── Test Checks ─────────────────────
echo ""
echo "🧪 Running test suite..."

if $PYTHON -m unittest discover -s tests 2>&1 | tail -1 | grep -q "OK"; then
    echo "  ✅ All tests passed"
else
    echo "  ❌ Some tests failed"
    ERRORS=$((ERRORS + 1))
fi

# ─── Summary ─────────────────────────
echo ""
echo "================================="
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed — ready for deployment${NC}"
    exit 0
else
    echo -e "${RED}❌ $ERRORS issues found — fix before deploying${NC}"
    exit 1
fi
