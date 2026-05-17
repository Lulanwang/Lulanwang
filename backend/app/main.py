from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import (
    analytics,
    audit,
    auth,
    chat,
    dashboard,
    dicomweb_proxy,
    findings,
    health,
    icd10,
    jobs,
    patients,
    reports,
    studies,
    upload,
)
from app.core.logging import configure_logging
from app.workers.background import recover_orphaned_jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    recover_orphaned_jobs()
    yield


app = FastAPI(
    title="Lulan DICOM Analysis MVP",
    description="RESEARCH USE ONLY — NOT A MEDICAL DEVICE. See README.md.",
    version="0.1.0",
    lifespan=lifespan,
)

# Caddy is the only origin in the demo, so CORS is effectively a no-op.
# Configure broadly for local dev convenience.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"

app.include_router(health.router, prefix=API_PREFIX)
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(studies.router, prefix=API_PREFIX)
app.include_router(upload.router, prefix=API_PREFIX)
app.include_router(jobs.router, prefix=API_PREFIX)
app.include_router(reports.router, prefix=API_PREFIX)
app.include_router(findings.router, prefix=API_PREFIX)
app.include_router(icd10.router, prefix=API_PREFIX)
app.include_router(audit.router, prefix=API_PREFIX)
app.include_router(dashboard.router, prefix=API_PREFIX)
app.include_router(patients.router, prefix=API_PREFIX)
app.include_router(chat.router, prefix=API_PREFIX)
app.include_router(analytics.router, prefix=API_PREFIX)

# DICOMweb proxy is mounted at the root path so OHIF can call /dicom-web/*
# (Caddy routes /dicom-web/* into FastAPI directly without the /api prefix).
app.include_router(dicomweb_proxy.router)
