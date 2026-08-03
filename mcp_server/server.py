import os
import sys
import logging

# Add parent directory to sys.path to enable absolute imports of mcp_server
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from mcp_server.google_client import GoogleWorkspaceClient

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("workspace-mcp-server")

# Initialize FastMCP server
mcp = FastMCP("Workspace-Server")

# Lazy load Google Workspace client to prevent startup errors if token is missing
google_client = None

def get_google_client():
    global google_client
    if google_client is None:
        logger.info("Initializing Google Workspace Client...")
        google_client = GoogleWorkspaceClient()
    return google_client

@mcp.tool()
def append_to_doc(doc_id: str, title: str, markdown_content: str) -> str:
    """
    Appends a new dated section with formatting (markdown) to a Google Doc.
    
    Args:
        doc_id: The ID of the target Google Document (found in the document URL).
        title: The heading for this week's section (e.g. "Blinkit - Reviews Report [2026-W25]").
        markdown_content: The markdown formatted review summary content to append.
        
    Returns:
        The direct browser URL pointing to the newly added heading anchor in the Doc.
    """
    logger.info(f"Received request to append section '{title}' to Doc '{doc_id}'")
    try:
        client = get_google_client()
        anchor_url = client.append_markdown_to_doc(doc_id, title, markdown_content)
        logger.info(f"Successfully appended section. Anchor URL: {anchor_url}")
        return anchor_url
    except Exception as e:
        logger.error(f"Failed to append to Doc: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
def send_gmail_teaser(recipient: str, subject: str, html_body: str) -> str:
    """
    Sends an HTML formatted teaser email to stakeholders.
    
    Args:
        recipient: The email address of the recipient.
        subject: The subject line of the email.
        html_body: The HTML content of the email containing a deep link to the Google Doc section.
        
    Returns:
        The sent Gmail message ID.
    """
    logger.info(f"Received request to send email to '{recipient}' with subject '{subject}'")
    try:
        client = get_google_client()
        message_id = client.send_gmail_message(recipient, subject, html_body)
        logger.info(f"Successfully sent email. Message ID: {message_id}")
        return message_id
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return f"Error: {str(e)}"

import json
from sqlalchemy import func
from database import SessionLocal
from models import RawReview, ExtractedTheme, ValidatedInsight

@mcp.tool()
def fetch_themes_summary() -> str:
    """
    Fetches all NLP-extracted themes from the database, grouped by frequency and source diversity.
    Returns a JSON string of themes, which researchers can use to identify problem statements.
    """
    logger.info("Fetching themes summary from SQLite DB")
    db = SessionLocal()
    try:
        themes = db.query(
            ExtractedTheme.theme_tag,
            func.count(ExtractedTheme.id).label('review_count'),
            func.avg(ExtractedTheme.sentiment_score).label('average_sentiment')
        ).group_by(ExtractedTheme.theme_tag).all()
        
        results = []
        for theme in themes:
            review_ids = db.query(ExtractedTheme.review_id).filter(ExtractedTheme.theme_tag == theme.theme_tag).subquery()
            sources = db.query(RawReview.source).filter(RawReview.id.in_(review_ids)).distinct().all()
            
            results.append({
                "theme_tag": theme.theme_tag,
                "review_count": theme.review_count,
                "source_diversity": len(sources),
                "ranking_score": theme.review_count * len(sources),
                "average_sentiment": round(theme.average_sentiment, 2) if theme.average_sentiment else 0.0
            })
            
        results.sort(key=lambda x: x["ranking_score"], reverse=True)
        return json.dumps(results, indent=2)
    except Exception as e:
        logger.error(f"Error fetching themes: {e}")
        return f"Error: {str(e)}"
    finally:
        db.close()

@mcp.tool()
def save_validated_insight(theme_tag: str, insight_statement: str, validation_status: str, interview_quotes_json: str = "[]") -> str:
    """
    Saves or updates a validated insight (the problem statement) for a specific theme after reviewing it.
    
    Args:
        theme_tag: The theme being validated (e.g., 'quality doubt')
        insight_statement: The formal problem statement drafted from the reviews
        validation_status: E.g., 'Confirmed', 'Partially Confirmed', 'New Finding'
        interview_quotes_json: A JSON list of string quotes from interviews verifying this insight
    """
    logger.info(f"Saving validated insight for theme: {theme_tag}")
    db = SessionLocal()
    try:
        quotes = json.loads(interview_quotes_json)
        
        insight = db.query(ValidatedInsight).filter(ValidatedInsight.theme_tag == theme_tag).first()
        if not insight:
            insight = ValidatedInsight(
                theme_tag=theme_tag,
                insight_statement=insight_statement,
                validation_status=validation_status,
                interview_quotes=quotes
            )
            db.add(insight)
        else:
            insight.insight_statement = insight_statement
            insight.validation_status = validation_status
            insight.interview_quotes = quotes
            
        db.commit()
        return f"Successfully saved insight for theme '{theme_tag}'."
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving insight: {e}")
        return f"Error: {str(e)}"
    finally:
        db.close()

if __name__ == "__main__":
    # Start the FastMCP server (default runs via stdio transport)
    mcp.run()
