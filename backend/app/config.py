from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "OSH Agriculture AI Global"
    database_url: str = "postgresql+psycopg://osh:osh_dev_password@localhost:5434/osh_global"
    enable_postgis: bool = False
    jwt_secret: str = "DEV_ONLY_CHANGE_ME"
    jwt_expire_minutes: int = 10080
    cors_origins: str = "http://localhost:8080"
    nasa_power_base_url: str = "https://power.larc.nasa.gov/api/temporal/daily/point"
    geboundaries_base_url: str = "https://www.geoboundaries.org/api/current/gbOpen"
    max_upload_mb: int = 25
    worker_poll_seconds: int = 3

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


settings = Settings()
