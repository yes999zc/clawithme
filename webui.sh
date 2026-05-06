#!/bin/bash
# clawithme WebUI launcher
# Usage: ./webui.sh

cd "$(dirname "$0")"
HERMES_PYTHON="/Users/bakeyzhang/.hermes/hermes-agent/venv/bin/python3.11"

if [ ! -f "$HERMES_PYTHON" ]; then
    echo "❌ Python 3.11 not found at $HERMES_PYTHON"
    echo "   Try: python3.11 -m clawithme.web.app"
    exit 1
fi

echo "🚀 Starting clawithme WebUI at http://localhost:8000"
exec "$HERMES_PYTHON" -m clawithme.web.app
