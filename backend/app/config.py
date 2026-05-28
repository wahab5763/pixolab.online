from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "Pixolab"
    environment: str = "development"
    secret_key: str = "change-this-secret-key-before-production"

    database_url: str = "sqlite:///./pixolab.db"
    backend_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    max_upload_mb: int = 10

    # Hugging Face — for AI background generation
    hf_token: str = ""
    hf_model_id: str = "black-forest-labs/FLUX.1-schnell"
    hf_provider: str = ""
    enable_hf_background: bool = False

    # Background removal toggle
    enable_background_removal: bool = True

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_list(self) -> List[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def storage_dir(self) -> Path:
        path = BASE_DIR / "storage"
        path.mkdir(exist_ok=True)
        (path / "uploads").mkdir(exist_ok=True)
        (path / "results").mkdir(exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
