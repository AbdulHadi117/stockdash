from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    app_name: str = "StockDash API"


settings = Settings()