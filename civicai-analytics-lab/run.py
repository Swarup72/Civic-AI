"""
Entry point for CivicAI Analytics Lab's standalone dev server.

    python run.py

Runs on its own port (default 8003, see .env / app/config.py) — separate
from production (8000), civicai-vision-lab (8001), and civicai-text-lab
(8002). Swagger UI: http://localhost:8003/docs
"""
import uvicorn

from app.config import settings

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
