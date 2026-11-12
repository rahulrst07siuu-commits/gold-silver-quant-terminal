#!/usr/bin/env bash
# Gold & Silver Quantitative Intelligence Terminal (Mac/Linux Portable Launcher)

echo "==============================================================================="
echo "  GOLD & SILVER QUANTITATIVE INTELLIGENCE TERMINAL (PORTABLE RUNNER)"
echo "  MCX Algorithmic Research, Multi-Horizon AI Forecasting & Paper Trading"
echo "==============================================================================="
echo ""

# Navigate to script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1
echo "[*] Working Directory: $(pwd)"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 could not be found. Please install Python 3.10+."
    exit 1
fi

PY_VER=$(python3 --version)
echo "[*] Detected Python Runtime: $PY_VER"

# Check venv
if [ -d ".venv" ]; then
    echo "[*] Activating local virtual environment (.venv)..."
    source .venv/bin/activate
fi

# Check dependencies
echo "[*] Verifying dependencies..."
python3 -c "import streamlit, pandas, plotly, sklearn, sqlite3" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[!] Installing dependencies from requirements.txt..."
    python3 -m pip install -r requirements.txt
fi

echo ""
echo "==============================================================================="
echo "  STARTING APPLICATION TERMINAL ON http://localhost:8501"
echo "==============================================================================="
echo ""

# Open browser in background
if command -v xdg-open &> /dev/null; then
    (sleep 3 && xdg-open http://localhost:8501) &
elif command -v open &> /dev/null; then
    (sleep 3 && open http://localhost:8501) &
fi

python3 -m streamlit run app.py --server.port=8501 --server.address=localhost
