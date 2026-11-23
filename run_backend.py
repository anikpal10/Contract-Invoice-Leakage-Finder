import uvicorn
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.app.main import app

if __name__ == "__main__":
    print("Starting Contract & Invoice Leakage Finder backend on http://127.0.0.1:8000...")
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False, log_level="info")

