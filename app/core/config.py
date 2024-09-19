from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    APP_NAME: str = "FastAPI ML App"
    S3_BUCKET: str
    MONGO_URL: str
    API_KEYS: List[str]  # Change to a list of API keys
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str
    S3_BUCKET_NAME: str


    class Config:
        env_file = ".env"

settings = Settings()
