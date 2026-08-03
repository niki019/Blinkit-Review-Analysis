# Task List: Blinkit Review Analyzer

## Phase 1: Ingestion & n8n Integration `[x]`
- `[x]` Database Initialization
  - `[x]` Define SQLAlchemy SQLite models for `raw_reviews`, `extracted_themes`, and `validated_insights`
  - `[x]` Write DB initialization script to create tables in WAL mode
- `[x]` n8n Webhook Connector
  - `[x]` Implement a client to POST request / GET payload from `https://nikiagape.app.n8n.cloud/workflow/h7hGpQhZBPsHDy58`
  - `[x]` Implement error handling and retries with backoff
- `[x]` Data Parsers & Web Scrapers
  - `[x]` Set up parsing handlers for App Store / Play Store raw schema
  - `[x]` Set up parsing handlers for Trustpilot review page payloads
  - `[x]` Set up parsing handlers for Quora thread Q&A text payloads
- `[x]` Deduplication Utility
  - `[x]` Write hash utility for `(source, review_text, timestamp)`
  - `[x]` Implement bulk upsert with conflict ignore in SQLite
- `[x]` Verification
  - `[x]` Write ingest verification tests
  - `[x]` Perform mock ingest run using n8n mock/live endpoint

## Phase 2: Processing & NLP Engine `[x]`
- `[x]` Text-cleaning pipeline
  - `[x]` Strip spam/bots and clean review text
  - `[x]` Retain transliterated Hinglish keywords (e.g., *“kharab”*, *“deri”*, *“late”*)
- `[x]` Sentiment Scorer
  - `[x]` Implement sentence-level sentiment scoring (Positive, Neutral, Negative)
  - `[x]` Set up Hinglish-aware sentiment qualifier mapping
- `[x]` Theme & Aspect Classifier
  - `[x]` Map review text to taxonomy theme tags (`trust deficit`, `quality doubt`, etc.)
  - `[x]` Integrate topic similarity/clustering to identify themes outside the keyword taxonomy
- `[x]` Processing Orchestration
  - `[x]` Write runner script to query unanalyzed reviews, execute NLP, and store extracted themes
- `[x]` Verification
  - `[x]` Write automated test script for NLP pipeline
  - `[x]` Run NLP pipeline over mock raw reviews in database
