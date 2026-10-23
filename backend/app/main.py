import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import engine, Base
from app.routers import (
    auth, dashboard, zones, imagery,
    analysis, alerts, reports, notifications,
    users, settings as app_settings
)
from app.seed import seed_database_if_empty

# Initialize FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="TerraGuard AI — Satellite-Based Encroachment Detection and Land Monitoring System API",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static file mount for storage (images, change masks, evidence)
app.mount("/storage", StaticFiles(directory=settings.STORAGE_DIR), name="storage")

# Include API routers
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(zones.router)
app.include_router(imagery.router)
app.include_router(analysis.router)
app.include_router(alerts.router)
app.include_router(reports.router)
app.include_router(notifications.router)
app.include_router(users.router)
app.include_router(app_settings.router)

@app.on_event("startup")
def on_startup():
    # Create all DB tables
    Base.metadata.create_all(bind=engine)
    # Seed sample demonstration data if DB is newly created
    seed_database_if_empty()

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "TerraGuard AI Core Backend",
        "demo_mode": settings.DEMO_MODE,
        "environment": settings.ENVIRONMENT
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)
