from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, HttpUrl

class Intent(BaseModel):
    skills: list[str] = Field(default_factory=list, max_length=30)
    interests: list[str] = Field(default_factory=list, max_length=20)
    location: str | None = Field(default=None, max_length=200)
    remote: bool | None = None
    kind: Literal['internship', 'project'] | None = None

class SearchRequest(BaseModel):
    query: str = Field(default='', max_length=2000)
    skills: list[str] = Field(default_factory=list, max_length=30)
    location: str | None = Field(default=None, max_length=200)
    remote: bool | None = None
    kind: Literal['internship', 'project'] | None = None
    limit: int = Field(default=20, ge=1, le=100)

class OpportunityOut(BaseModel):
    id: int
    title: str
    organization: str
    description: str
    kind: str
    location: str
    remote: bool
    source_type: str
    source_url: str | None
    source_date: date | None
    skills: list[str]
    score: float
    matched_skills: list[str]
    missing_skills: list[str]
    explanation: str

class SearchResponse(BaseModel):
    intent: Intent
    results: list[OpportunityOut]
    retrieval_mode: str
    intent_mode: str

class RecommendationRequest(SearchRequest):
    resume_text: str = Field(default='', max_length=30000)

class AgentRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
