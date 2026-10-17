import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def _path_from_env(value: str | None, fallback: Path) -> Path:
    if not value:
        return fallback
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT_DIR / path


@dataclass(frozen=True)
class Settings:
    database_path: Path = _path_from_env(os.getenv("SCAMSHIELD_DATABASE_PATH"), ROOT_DIR / "backend" / "data" / "scamshield.db")
    model_path: Path = _path_from_env(os.getenv("SCAMSHIELD_MODEL_DIR"), ROOT_DIR / "scamshield_roberta")
    model_device: str = os.getenv("SCAMSHIELD_MODEL_DEVICE", "auto").lower()
    scam_label_id: str | None = os.getenv("SCAMSHIELD_SCAM_LABEL_ID")
    translation_url: str | None = os.getenv("TRANSLATION_API_URL") or "http://127.0.0.1:5010/translate"
    translation_api_key: str | None = os.getenv("TRANSLATION_API_KEY")
    translation_timeout: float = float(os.getenv("TRANSLATION_API_TIMEOUT", "30"))
    # NLLB supports Marathi (mar_Deva) -> English (eng_Latn). The model is
    # fetched from Hugging Face on the first Marathi scan and cached locally.
    marathi_translation_model: str | None = os.getenv(
        "SCAMSHIELD_MARATHI_TRANSLATION_MODEL", "facebook/nllb-200-distilled-600M"
    )

    @property
    def model_configured(self) -> bool:
        return bool(os.getenv("SCAMSHIELD_MODEL_DIR")) or self.model_path.exists()


settings = Settings()
