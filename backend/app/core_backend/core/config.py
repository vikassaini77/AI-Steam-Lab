from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "NeuroLab AI"
    # Add other configuration variables here
    
    class Config:
        env_file = ".env"

settings = Settings()
