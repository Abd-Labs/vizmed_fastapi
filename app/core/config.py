from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    APP_NAME: str = "FastAPI ML App"
    S3_BUCKET: str
    API_KEYS: List[str]  # Change to a list of API keys
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str
    S3_BUCKET_NAME: str
    ROOT_DIR: str  = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    AXIAL_MODEL_PATH: str = os.getenv("AXIAL_MODEL_PATH", os.path.join(ROOT_DIR, 'assets', 'models', 'axial_best.hdf5'))
    CORONAL_MODEL_PATH: str = os.getenv("CORONAL_MODEL_PATH", os.path.join(ROOT_DIR, 'assets', 'models', 'coronal_best.hdf5'))
    SAGITTAL_MODEL_PATH: str = os.getenv("SAGITTAL_MODEL_PATH", os.path.join(ROOT_DIR, 'assets', 'models', 'sagittal_best.hdf5'))
    COLOR_SPECTRUM_FILE_PATH: str = os.getenv("COLOR_SPECTRUM_FILE", os.path.join(ROOT_DIR, 'assets', 'ColorSpectrum.jpg'))
    IS_DOCKER: bool = os.getenv("IS_DOCKER", "false").lower() == "true"

    class Config:
        env_file = ".env"


settings = Settings()
