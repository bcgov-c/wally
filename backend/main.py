"""
Main application entrypoint that initializes FastAPI and registers the endpoints defined in app/router.py.
"""

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app import config
from app.router import api_router
from app.db.session import Session

import pdfkit

app = FastAPI(title=config.PROJECT_NAME, openapi_url="/api/v1/openapi.json")


# CORS
origins = ["*"]

# Set all CORS enabled origins
if config.BACKEND_CORS_ORIGINS:
    origins_raw = config.BACKEND_CORS_ORIGINS.split(",")
    for origin in origins_raw:
        use_origin = origin.strip()
        origins.append(use_origin)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    ),

app.add_middleware(GZipMiddleware)

app.include_router(api_router, prefix=config.API_V1_STR)


@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    request.state.db = Session()
    response = await call_next(request)
    request.state.db.close()
    return response


@app.get("/health")
def health_check():
    return Response(status_code=200, content=b"")

@app.get("/generate_report")
def generate_report():
    pdf_report = pdfkit.from_url(config.REPORT_URL, False)

    response = Response(
        content=pdf_report,
        media_type='application/pdf',
        headers={'Content-Disposition': 'attachment; filename=report.pdf'})
    return response
