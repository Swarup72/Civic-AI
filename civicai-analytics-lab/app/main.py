"""
CivicAI Analytics Lab — standalone FastAPI app.

STANDALONE PROTOTYPE. Not mounted into, imported by, or connected to the
production CivicAI backend in any way. No MongoDB, no production auth, no
production users/complaints. Operates only on local CSV/JSON data. Runs on
its own port (default 8003).
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version="0.1.0-prototype",
)

# Permissive CORS is acceptable here specifically because this is a local-only
# prototype with no auth and no sensitive data — never carry this into a
# production deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    return {
        "message": "CivicAI Analytics Lab — standalone prototype. NOT connected to the production CivicAI application.",
        "docs": "/docs",
        "health": "/api/health",
    }
