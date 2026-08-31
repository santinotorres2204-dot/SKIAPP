from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://ski_app:ski_app@localhost:5432/ski_app"
    # Almacenamiento local de videos para esta etapa (spec seccion 3 pide S3 o
    # equivalente a futuro; local es suficiente para validar el flujo end-to-end).
    video_upload_dir: str = "media/videos"


settings = Settings()
