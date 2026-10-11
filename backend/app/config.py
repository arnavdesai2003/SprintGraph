from functools import lru_cache
from typing import Annotated
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    database_url: str = 'sqlite:///./sprintgraph.db'
    mode: str = 'demo'
    jwt_secret: str
    demo_password: str = ''
    github_webhook_secret: str = ''
    jira_webhook_secret: str = ''
    github_token: str = ''
    jira_url: str = ''
    jira_email: str = ''
    jira_token: str = ''
    llm_provider: str = 'demo'
    llm_base_url: str = 'https://api.openai.com/v1'
    llm_api_key: str = ''
    llm_model: str = 'gpt-4.1-mini'
    frontend_origin: str = 'http://localhost:3000'
    max_attempts: int = Field(default=3, ge=1, le=10)
    workflow_timeout_seconds: float = Field(default=120, ge=1, le=300)
    stalled_days: int = Field(default=7, ge=1, le=365)
    priority_weights: dict[str, Annotated[int, Field(ge=0, le=10000, strict=True)]] = Field(default_factory=lambda: {'Highest': 50, 'High': 35, 'Medium': 20, 'Low': 10, 'Lowest': 0})

@lru_cache
def settings():
    value = Settings()
    if len(value.jwt_secret) < 32:
        raise ValueError('JWT_SECRET must contain at least 32 characters')
    if value.mode not in {'demo', 'live'}:
        raise ValueError('MODE must be demo or live')
    if value.mode == 'live' and value.llm_provider == 'demo':
        raise ValueError('Live mode requires a configured LLM provider')
    return value
