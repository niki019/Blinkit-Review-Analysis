import os
import sys

# Ensure the parent directory is in the sys.path to allow relative imports from the root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List

from database import SessionLocal, engine, Base
from models import RawReview, ExtractedTheme, ValidatedInsight
from schemas import ReviewResponse, ThemeResponse, ValidationRequest, ExportRequest
from mcp_server.google_client import GoogleWorkspaceClient

# We won't initialize the DB on every request in serverless, but we make sure tables exist
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Blinkit Review Analyzer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/api/reviews", response_model=List[ReviewResponse])
def get_reviews(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """Fetch raw reviews with pagination."""
    reviews = db.query(RawReview).order_by(RawReview.timestamp.desc()).offset(skip).limit(limit).all()
    return reviews

@app.get("/api/themes", response_model=List[ThemeResponse])
def get_themes(db: Session = Depends(get_db)):
    """
    Fetch themes ranked by frequency x source diversity.
    Because SQLite doesn't natively support easy nested aggregates across joins without subqueries,
    we do some processing in Python for clarity.
    """
    # Group by theme_tag
    themes_query = db.query(
        ExtractedTheme.theme_tag,
        func.count(ExtractedTheme.id).label('review_count'),
        func.avg(ExtractedTheme.sentiment_score).label('average_sentiment')
    ).group_by(ExtractedTheme.theme_tag).all()
    
    results = []
    for theme in themes_query:
        # Calculate source diversity
        # Find all reviews that have this theme
        review_ids = db.query(ExtractedTheme.review_id).filter(ExtractedTheme.theme_tag == theme.theme_tag).subquery()
        sources = db.query(RawReview.source).filter(RawReview.id.in_(review_ids)).distinct().all()
        source_diversity = len(sources)
        
        ranking_score = theme.review_count * source_diversity
        
        # Get sample quotes
        samples = db.query(ExtractedTheme.sentence_extract).filter(
            ExtractedTheme.theme_tag == theme.theme_tag
        ).limit(3).all()
        
        results.append(ThemeResponse(
            theme_tag=theme.theme_tag,
            review_count=theme.review_count,
            source_diversity=source_diversity,
            ranking_score=ranking_score,
            average_sentiment=theme.average_sentiment or 0.0,
            sample_quotes=[s[0] for s in samples]
        ))
        
    # Sort by ranking score descending
    results.sort(key=lambda x: x.ranking_score, reverse=True)
    return results

@app.post("/api/insights/validate")
def validate_insight(request: ValidationRequest, db: Session = Depends(get_db)):
    """Log or update an interview validation status for a theme."""
    insight = db.query(ValidatedInsight).filter(ValidatedInsight.theme_tag == request.theme_tag).first()
    
    if not insight:
        insight = ValidatedInsight(
            theme_tag=request.theme_tag,
            insight_statement=request.insight_statement,
            validation_status=request.validation_status,
            interview_quotes=request.interview_quotes
        )
        db.add(insight)
    else:
        insight.insight_statement = request.insight_statement
        insight.validation_status = request.validation_status
        insight.interview_quotes = request.interview_quotes
        
    db.commit()
    db.refresh(insight)
    return {"status": "success", "insight_id": insight.id}

@app.post("/api/problem-statement/export")
def export_problem_statement(request: ExportRequest, db: Session = Depends(get_db)):
    """Generate problem statement and export via Google Workspace MCP."""
    target_doc_id = request.google_doc_id or "1UD5zLCvLz6p8bNprxneDPai2Y366nuPcZR1qelGzWKA"
    
    # In a full implementation, you would trigger the Groq LLM here to summarize the ValidatedInsights.
    # For now, we fetch the validated insights and format a markdown string.
    insights = db.query(ValidatedInsight).all()
    
    if not insights:
        raise HTTPException(status_code=400, detail="No validated insights found to export.")
        
    markdown_content = f"# Blinkit Validated Research Insights - {request.week}\n\n"
    for insight in insights:
        markdown_content += f"### Theme: {insight.theme_tag}\n"
        markdown_content += f"**Status**: {insight.validation_status}\n\n"
        markdown_content += f"> {insight.insight_statement}\n\n"
        if insight.interview_quotes:
            markdown_content += "**Primary Research Quotes:**\n"
            for quote in insight.interview_quotes:
                markdown_content += f"- {quote}\n"
        markdown_content += "\n"
        
    # Send to Google Docs via our configured MCP client
    try:
        client = GoogleWorkspaceClient()
        doc_url = client.append_markdown_to_doc(
            doc_id=target_doc_id,
            title=f"Blinkit - Research Export [{request.week}]",
            markdown_content=markdown_content
        )
        return {"status": "success", "doc_url": doc_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

# Mount MCP SSE if necessary (Optional, FastMCP SSE support usually requires its own ASGIMiddleware)
# from mcp_server.server import mcp
# app.mount("/mcp", mcp.asgi_app()) # (Syntax depends on fastmcp version/implementation)
