"""
Central application configuration.

Values come from environment variables (optionally a backend/.env file) so the
same code runs locally on SQLite and in production on Postgres.
Settings.validate() refuses to start with unsafe production config.
"""
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

DEFAULT_DEV_SECRET = "dev-secret-change-me"


class Settings:
    APP_NAME: str = "Somastar — Adaptive Learning & Exam Intelligence"
    ENV: str = os.getenv("ENV", "development").lower()
    # Show the technical error type/message on failed analyses (dev only, never in production).
    DEBUG_ERRORS: bool = os.getenv("DEBUG_ERRORS", "false").lower() in {"1", "true", "yes"}

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./somastar.db")

    # Auth
    JWT_SECRET: str = os.getenv("JWT_SECRET", DEFAULT_DEV_SECRET)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24)))

    # File storage (see integrations/storage)
    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local")
    STORAGE_LOCAL_DIR: str = os.getenv("STORAGE_LOCAL_DIR", "./uploads")
    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "10"))

    # AI provider(s) (see integrations/llm). One name, or a comma-separated
    # fallback chain tried in order: "gemini", "anthropic,gemini", "mock".
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "mock").lower()
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    # One model, or a comma-separated fallback list tried in order (see gemini_provider).
    GEMINI_MODEL: str = os.getenv(
        "GEMINI_MODEL",
        "gemini-3.5-flash,gemini-3.6-flash,gemini-2.5-flash,gemini-3.5-flash-lite,gemini-2.5-flash-lite",
    )

    # CORS
    CORS_ORIGINS: list[str] = [
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()
    ]

    @property
    def provider_chain(self) -> list[str]:
        """Providers in the order they are tried, e.g. ['anthropic', 'gemini']."""
        return [p.strip() for p in self.LLM_PROVIDER.split(",") if p.strip()]

    def validate(self) -> None:
        problems: list[str] = []
        chain = self.provider_chain
        if not chain:
            problems.append("LLM_PROVIDER is empty. Use 'mock', 'anthropic', 'gemini', or a list like 'anthropic,gemini'.")
        for name in chain:
            if name not in {"mock", "anthropic", "gemini"}:
                problems.append(f"LLM_PROVIDER has unknown provider '{name}' (use mock, anthropic or gemini).")
        if "anthropic" in chain and not self.ANTHROPIC_API_KEY:
            problems.append("LLM_PROVIDER includes anthropic but ANTHROPIC_API_KEY is empty.")
        if "gemini" in chain and not self.GEMINI_API_KEY:
            problems.append("LLM_PROVIDER includes gemini but GEMINI_API_KEY is empty.")
        if self.ENV == "production":
            if self.DEBUG_ERRORS:
                problems.append("DEBUG_ERRORS must be off in production.")
            if self.JWT_SECRET == DEFAULT_DEV_SECRET or len(self.JWT_SECRET) < 32:
                problems.append("JWT_SECRET must be a random string of 32+ characters in production.")
            if "*" in self.CORS_ORIGINS:
                problems.append("CORS_ORIGINS must list explicit origins in production (no '*').")
        if problems:
            raise RuntimeError("Invalid configuration:\n - " + "\n - ".join(problems))


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.validate()
    return s