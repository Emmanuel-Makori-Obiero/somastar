import logging
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import auth, exams, assessment, revision
from app.config import BACKEND_DIR, get_settings
from app.services.exam_analysis.service import mark_interrupted_exams

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("somastar")

settings = get_settings()  # validates config; refuses to start on unsafe production settings


def run_migrations() -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(_: FastAPI):
    run_migrations()
    swept = mark_interrupted_exams()
    if swept:
        logger.warning("Marked %s interrupted exam(s) as failed.", swept)
    if settings.provider_chain == ["mock"]:
        logger.warning(
            "LLM provider is MOCK: uploaded files are NOT read and results are fake. "
            "Set LLM_PROVIDER=gemini (or anthropic) and the matching API key in backend/.env, then restart."
        )
    else:
        logger.info("LLM provider chain (tried in order): %s", " -> ".join(settings.provider_chain))
        if "gemini" in settings.provider_chain:
            logger.info("Gemini models (tried in order): %s", " -> ".join(
                x.strip() for x in settings.GEMINI_MODEL.split(",") if x.strip()))
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    first = errors[0] if errors else {}
    field = ".".join(str(p) for p in first.get("loc", []) if p not in ("body", "query", "form"))
    msg = str(first.get("msg", "Invalid input.")).removeprefix("Value error, ")
    message = f"{field}: {msg}" if field else msg
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "VALIDATION_ERROR", "message": message[:300], "details": None}},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Never expose internal stack traces to users (CLAUDE.md 31).
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "Something went wrong.", "details": None}},
    )


app.include_router(auth.router)
app.include_router(exams.router)
app.include_router(assessment.router)
app.include_router(revision.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "llm_provider": settings.LLM_PROVIDER, "llm_chain": settings.provider_chain}