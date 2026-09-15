"""
Entry point for CivicAI Text Intelligence Lab's standalone dev server.

    python run.py

Runs on its own port (default 8002, see .env / app/config.py) — separate
from the production CivicAI backend (8000) and civicai-vision-lab (8001).
Swagger UI: http://localhost:8002/docs
"""
import uvicorn

from app.config import settings

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
