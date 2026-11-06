import os
import db.models  # Ensure models are loaded
from sqlalchemy import text
from db.connection import Base, engine

try:
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                -- users
                ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 1;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS photo_url VARCHAR(500);
                ALTER TABLE users ADD COLUMN IF NOT EXISTS birth_date_text VARCHAR(100);
                ALTER TABLE users ADD COLUMN IF NOT EXISTS appointed_date_text VARCHAR(255);
                ALTER TABLE users ADD COLUMN IF NOT EXISTS specialization VARCHAR(255);
                ALTER TABLE users ADD COLUMN IF NOT EXISTS previous_workplace VARCHAR(255);
                ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS login VARCHAR(255);

                -- check_in_documents
                ALTER TABLE check_in_documents ADD COLUMN IF NOT EXISTS doc_type VARCHAR(50) DEFAULT 'regular';
                ALTER TABLE check_in_documents ADD COLUMN IF NOT EXISTS photo_url VARCHAR(500);
                ALTER TABLE check_in_documents ADD COLUMN IF NOT EXISTS pdf_url VARCHAR(500);
                ALTER TABLE check_in_documents ADD COLUMN IF NOT EXISTS notes TEXT;
                ALTER TABLE check_in_documents ADD COLUMN IF NOT EXISTS check_in_date DATE DEFAULT CURRENT_DATE;
                ALTER TABLE check_in_documents ADD COLUMN IF NOT EXISTS due_date DATE;
                ALTER TABLE check_in_documents ADD COLUMN IF NOT EXISTS previous_date DATE;
                ALTER TABLE check_in_documents ADD COLUMN IF NOT EXISTS requested_date DATE;
                ALTER TABLE check_in_documents ADD COLUMN IF NOT EXISTS new_date DATE;
                ALTER TABLE check_in_documents ADD COLUMN IF NOT EXISTS frequency_days INTEGER;
                ALTER TABLE check_in_documents ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'pending';
                ALTER TABLE check_in_documents ADD COLUMN IF NOT EXISTS rejection_reason TEXT;
                ALTER TABLE check_in_documents ADD COLUMN IF NOT EXISTS reviewed_by_id BIGINT;
                ALTER TABLE check_in_documents ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP WITHOUT TIME ZONE;
                ALTER TABLE check_in_documents ADD COLUMN IF NOT EXISTS seen_by_id BIGINT;
                ALTER TABLE check_in_documents ADD COLUMN IF NOT EXISTS seen_at TIMESTAMP WITHOUT TIME ZONE;

                -- document_messages
                ALTER TABLE document_messages ADD COLUMN IF NOT EXISTS message_type VARCHAR(50) DEFAULT 'text';
                ALTER TABLE document_messages ADD COLUMN IF NOT EXISTS requested_date DATE;
                ALTER TABLE document_messages ADD COLUMN IF NOT EXISTS granted_date DATE;

                -- person_category_assignments
                ALTER TABLE person_category_assignments ADD COLUMN IF NOT EXISTS frequency_days INTEGER;
                ALTER TABLE person_category_assignments ADD COLUMN IF NOT EXISTS assigned_roles JSON;
                ALTER TABLE person_category_assignments ADD COLUMN IF NOT EXISTS next_check_in_due DATE;
                ALTER TABLE person_category_assignments ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'active';
                ALTER TABLE person_category_assignments ADD COLUMN IF NOT EXISTS created_by_id BIGINT;
                """
            )
        )
    print("Database columns synchronized successfully.")
except Exception as e:
    print(f"DB auto-migration note: {e}")

# Run test demo data seed automatically in separate robust transactions (39 Qo'ng'irot Mahallas)
try:
    from backend.seed_demo_data import run_seed_demo_data
    run_seed_demo_data(engine)
except Exception as seed_err:
    print(f"[SEED NOTE]: {seed_err}")

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from backend.auth.controller import router as auth_router
from backend.users.controller import router as users_router
from backend.mahallas.controller import router as mahallas_router
from backend.categories.controller import router as categories_router
from backend.persons.controller import router as persons_router
from backend.documents.controller import router as documents_router
from backend.files.controller import router as files_router

app = FastAPI(
    title="Prokratura Uzbekistan API",
    description="Backend system for Prokratura oversight of Mahallas, Mahalla Yettiligi, and Special Categories Supervision",
    version="0.2.0",
    openapi_url="/openapi.json",
    docs_url=None,
    root_path="/api",
)

# Standard routes (without /api prefix)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(mahallas_router)
app.include_router(categories_router)
app.include_router(persons_router)
app.include_router(documents_router)
app.include_router(files_router)

# Also mount with /api prefix so both /api/... and /... work seamlessly
api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(mahallas_router)
api_router.include_router(categories_router)
api_router.include_router(persons_router)
api_router.include_router(documents_router)
api_router.include_router(files_router)
app.include_router(api_router)

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
