"""
Entry point for CivicAI Vision Lab's standalone dev server.

    python run.py

Runs on its own port (default 8001, see .env / app/config.py) — separate
from the production CivicAI backend's port 8000.
"""
import uvicorn

from app.config import settings

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
