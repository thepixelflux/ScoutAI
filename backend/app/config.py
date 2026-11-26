from urllib.parse import urlsplit
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    database_url: str = 'postgresql+psycopg://scout:scout@localhost:5432/scout'
    cors_origins: str = 'http://localhost:5173'

    @field_validator('database_url')
    @classmethod
    def postgres_driver(cls, value):
        if value.startswith('postgres://'):
            return 'postgresql+psycopg://' + value[len('postgres://'):]
        if value.startswith('postgresql://'):
            return 'postgresql+psycopg://' + value[len('postgresql://'):]
        return value

    @field_validator('cors_origins')
    @classmethod
    def validate_origins(cls, value):
        for origin in filter(None, (x.strip() for x in value.split(','))):
            parsed = urlsplit(origin)
            if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
                raise ValueError('CORS origins must be explicit HTTP(S) origins without paths')
        return value

    @property
    def allowed_origins(self):
        return [x.strip() for x in self.cors_origins.split(',') if x.strip()]
    llm_api_key: str = ''
    llm_base_url: str = 'https://api.openai.com/v1'
    llm_model: str = 'gpt-4o-mini'
    embeddings_enabled: bool = False
    embedding_provider: str = "local"
    embedding_api_key: str = ""
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"
settings = Settings()
