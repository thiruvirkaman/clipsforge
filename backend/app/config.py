"""Application settings for ClipForge, loaded from environment variables / .env."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Centralized application configuration."""

    APP_NAME: str = "ClipForge"

    # Database
    DATABASE_URL: str

    # Auth / JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Frontend / CORS
    FRONTEND_URL: str = "http://localhost:5173"
    # Plain comma-separated string (NOT list[str]) -- pydantic-settings tries
    # to JSON-decode any list-typed env var before field validators ever run,
    # which breaks on a human-friendly comma-separated .env value. Use
    # `allowed_origins` below to get the parsed list.
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost,http://localhost:80"

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # AI services (ASR / LLM)
    ASR_SERVICE_API_KEY: str = ""
    # Defaults to OpenAI's real Whisper endpoint -- WhisperAPITranscriptionService
    # posts to f"{ASR_SERVICE_BASE_URL}/v1/audio/transcriptions", the actual
    # OpenAI API path (not a placeholder). Point this at a different
    # OpenAI-compatible ASR provider (e.g. a self-hosted whisper.cpp server)
    # to swap providers.
    ASR_SERVICE_BASE_URL: str = "https://api.openai.com"
    ASR_MODEL: str = "whisper-1"
    LLM_SERVICE_API_KEY: str = ""

    # Optional: path to a Netscape-format cookies.txt file (see
    # app.services.youtube_service) used to authenticate yt-dlp requests.
    # Unset by default -- YouTube downloads work without it in most cases,
    # but some hosting providers' IP ranges get an anti-bot challenge
    # ("Sign in to confirm you're not a bot") that only cookies resolve.
    # Never commit a real cookies file; this should point at a file mounted
    # outside version control (e.g. a Docker bind mount to a `secrets/` dir).
    YOUTUBE_COOKIES_PATH: str = ""

    # Media storage
    MEDIA_STORAGE_PATH: str = "/data/media"
    MEDIA_STORAGE_BACKEND: str = "local"

    # Publishing platform OAuth credentials
    TIKTOK_CLIENT_ID: str = ""
    TIKTOK_CLIENT_SECRET: str = ""
    INSTAGRAM_CLIENT_ID: str = ""
    INSTAGRAM_CLIENT_SECRET: str = ""
    YOUTUBE_CLIENT_ID: str = ""
    YOUTUBE_CLIENT_SECRET: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
