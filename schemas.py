from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class ReviewResponse(BaseModel):
    id: str
    source: str
    rating: Optional[int] = None
    review_text: str
    timestamp: datetime
    app_version: Optional[str] = None
    
    class Config:
        from_attributes = True

class ThemeResponse(BaseModel):
    theme_tag: str
    review_count: int
    source_diversity: int
    ranking_score: float
    average_sentiment: float
    sample_quotes: List[str]

class ValidationRequest(BaseModel):
    theme_tag: str
    insight_statement: str
    validation_status: str
    interview_quotes: List[str] = Field(default_factory=list)

class ExportRequest(BaseModel):
    google_doc_id: Optional[str] = None
    week: str = Field(description="ISO week identifier e.g. 2026-W30")
