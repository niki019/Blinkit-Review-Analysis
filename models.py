from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base
import datetime
import uuid

Base = declarative_base()

class RawReview(Base):
    __tablename__ = 'raw_reviews'
    
    # Using string representation of UUID for SQLite compatibility
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source = Column(String(50), nullable=False) # e.g. play_store, trustpilot, quora
    rating = Column(Integer, nullable=True)
    review_text = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    app_version = Column(String(50), nullable=True)
    raw_payload = Column(JSON, nullable=True)
    content_hash = Column(String(64), unique=True, nullable=False) # To prevent duplicates

    def __repr__(self):
        return f"<RawReview(source='{self.source}', rating={self.rating}, text_preview='{self.review_text[:20]}')>"

class ExtractedTheme(Base):
    __tablename__ = 'extracted_themes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    review_id = Column(String(36), ForeignKey('raw_reviews.id', ondelete='CASCADE'), nullable=False)
    theme_tag = Column(String(100), nullable=False) # e.g. 'quality doubt', 'trust deficit'
    sentiment_score = Column(Float, nullable=False) # -1.0 to 1.0
    sentence_extract = Column(Text, nullable=False)

    def __repr__(self):
        return f"<ExtractedTheme(theme_tag='{self.theme_tag}', sentiment={self.sentiment_score})>"

class ValidatedInsight(Base):
    __tablename__ = 'validated_insights'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    theme_tag = Column(String(100), unique=True, nullable=False)
    insight_statement = Column(Text, nullable=False)
    validation_status = Column(String(50), default="Pending") # Confirmed, Partially Confirmed, Contradicted, New Finding
    interview_quotes = Column(JSON, default=list) # List of paraphrased quotes
    last_updated = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<ValidatedInsight(theme_tag='{self.theme_tag}', status='{self.validation_status}')>"
