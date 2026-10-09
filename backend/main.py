import os
import db.models  # Ensure models are loaded
from db.connection import Base, engine

try:
    Base.metadata.create_all(engine)
    print("Great")
except Exception as e:
    # If DB isn't reachable yet during build/import, defer to runtime
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from backend.auth.controller import router as auth_router
from backend.users.controller import router as users_router
from backend.mahallas.controller import router as mahallas_router
from backend.categories.controller import router as categories_router
from backend.persons.controller import router as persons_router
from backend.documents.controller import router as documents_router
from backend.files.controller import router as files_router
from backend.devices.controller import router as devices_router

app = FastAPI(
    title="Prokratura Uzbekistan API",
    description="Backend system for Prokratura oversight of Mahallas, Mahalla Yettiligi, and Special Categories Supervision",
    version="0.2.0",
    openapi_url="/openapi.json",
    docs_url=None,
    root_path="/api",
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(mahallas_router)
app.include_router(categories_router)
app.include_router(persons_router)
app.include_router(documents_router)
app.include_router(files_router)
app.include_router(devices_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from pydantic import BaseModel


class HealthResponse(BaseModel):
    message: str


@app.get("/", response_model=HealthResponse)
async def root():
    return HealthResponse(message="Prokratura Backend API is running")


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui():
    return get_swagger_ui_html(
        openapi_url="/api/openapi.json",
        title="Prokratura Swagger UI",
        swagger_ui_parameters={"tryItOutEnabled": True},
    )
