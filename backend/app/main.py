from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
import os
from backend.app.core.config import settings
from backend.app.core.database import engine, Base
import backend.app.models
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.users import router as users_router
from backend.app.api.v1.workspaces import router as workspaces_router
from backend.app.api.v1.suppliers import router as suppliers_router
from backend.app.api.v1.cases import router as cases_router
from backend.app.api.v1.documents import router as documents_router
from backend.app.api.v1.findings import router as findings_router
from backend.app.api.v1.exports import router as exports_router
from backend.app.api.v1.admin import router as admin_router
from backend.app.api.v1.audit import router as audit_router

# Ensure storage directories exist
os.makedirs(settings.LOCAL_STORAGE_DIR, exist_ok=True)
os.makedirs(settings.LOCAL_EXPORT_DIR, exist_ok=True)

# Create database tables if not existing
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Evidence-grounded financial reconciliation and exception detection for contracts, POs, and invoices.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers (documents_router mounted before cases_router so specific sub-paths match before /{case_id})
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(users_router, prefix=settings.API_V1_STR)
app.include_router(workspaces_router, prefix=settings.API_V1_STR)
app.include_router(suppliers_router, prefix=settings.API_V1_STR)
app.include_router(documents_router, prefix=settings.API_V1_STR)
app.include_router(cases_router, prefix=settings.API_V1_STR)
app.include_router(findings_router, prefix=settings.API_V1_STR)
app.include_router(exports_router, prefix=settings.API_V1_STR)
app.include_router(admin_router, prefix=settings.API_V1_STR)
app.include_router(audit_router, prefix=settings.API_V1_STR)

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)

@app.get("/health", tags=["System"])
@app.get(f"{settings.API_V1_STR}/health", tags=["System"])
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT
    }

@app.get("/", tags=["System"])
def root():
    return {
        "message": "Welcome to Contract & Invoice Leakage Finder API",
        "version": "1.0.0",
        "docs": "/docs"
    }
