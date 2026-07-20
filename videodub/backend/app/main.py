from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.api import dubbing, history, settings, cookies
from app.models.database import init_db

app = FastAPI(title="VideoDub API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("temp", exist_ok=True)
os.makedirs("output", exist_ok=True)

app.include_router(dubbing.router, prefix="/api/dubbing", tags=["dubbing"])
app.include_router(history.router, prefix="/api/history", tags=["history"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(cookies.router, prefix="/api/cookies", tags=["cookies"])


@app.on_event("startup")
async def startup():
    await init_db()


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "VideoDub API"}
