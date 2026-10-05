#!/bin/bash
# ============================================================
# SmartSchedule - Quick Start Script
# ============================================================
set -e

echo "============================================="
echo "  ✦ SmartSchedule - Setup & Run"
echo "============================================="
echo ""

# Navigate to script directory
cd "$(dirname "$0")"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8+ first."
    exit 1
fi

PYVER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "🐍 Python version: $PYVER"

# Create venv if not exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install deps
echo "📥 Installing dependencies..."
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt -q

echo ""
echo "✅ Setup complete!"
echo ""
echo "📝 Next steps:"
echo "   1. Edit the .env file to configure Google Sheets (optional)"
echo "   2. Put your Google service account JSON as credentials.json"
echo "      or paste the JSON string into GOOGLE_SERVICE_ACCOUNT_JSON"
echo ""
echo "🚀 Starting SmartSchedule on http://localhost:8000 ..."
echo "   Press Ctrl+C to stop."
echo ""

HOST=""
PORT=""
if [ -f .env ]; then
    HOST=$(grep -E '^HOST=' .env | cut -d'=' -f2 || true)
    PORT=$(grep -E '^PORT=' .env | cut -d'=' -f2 || true)
fi
HOST=${HOST:-0.0.0.0}
PORT=${PORT:-8000}

python -m uvicorn smartschedule.main:app --host "$HOST" --port "$PORT" --reload
