from functools import lru_cache
from typing import Annotated, Literal
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
    jira_issue_api: Literal['enhanced', 'legacy'] = 'enhanced'
    jira_sprint_id: int | None = Field(default=None, gt=0)
    jira_status_map: dict[str, str] = Field(default_factory=dict)
    jira_severity_field: str = Field(default='', pattern=r'^(customfield_[0-9]+)?$')
    jira_severity_map: dict[str, Annotated[int, Field(ge=0, le=10, strict=True)]] = Field(default_factory=dict)
    llm_provider: Literal['demo', 'openai-compatible'] = 'demo'
    llm_inference_enabled: bool = False
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
    return value
