import urllib.request
import urllib.error
import json
import hashlib
import datetime
import os
import sys
import re
from sqlalchemy.exc import IntegrityError
from database import SessionLocal, init_db
from models import RawReview

# Default Webhook URL for the n8n workflow.
# Note: Usually n8n webhooks use a specific path, e.g. /webhook/h7hGpQhZBPsHDy58 or similar.
# We make it configurable via environment variables, defaulting to the workflow path.
N8N_WEBHOOK_URL = os.environ.get(
    "N8N_WEBHOOK_URL", 
    "https://nikiagape.app.n8n.cloud/webhook/h7hGpQhZBPsHDy58"
)

def generate_content_hash(source, text, timestamp_str):
    """Generates a unique SHA-256 hash for deduplication."""
    hasher = hashlib.sha256()
    hasher.update(source.encode('utf-8'))
    hasher.update(text.encode('utf-8'))
    hasher.update(timestamp_str.encode('utf-8'))
    return hasher.hexdigest()

def normalize_date(date_val):
    """Normalizes various date formats into a datetime object."""
    if not date_val:
        return datetime.datetime.utcnow()
    if isinstance(date_val, (int, float)):
        return datetime.datetime.fromtimestamp(date_val)
    
    # Try parsing string formats
    for fmt in ('%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.datetime.strptime(date_val, fmt)
        except (ValueError, TypeError):
            continue
    return datetime.datetime.utcnow()

def contains_emojis_or_non_latin(text):
    """Returns True if the text contains emojis or non-Latin script alphabets (e.g. Devanagari, Cyrillic, Chinese)."""
    # Detect emojis (matches code points in plane 1+ and standard dingbats)
    emoji_pattern = re.compile(r'[\U00010000-\U0010ffff\u2600-\u27bf]')
    if emoji_pattern.search(text):
        return True
        
    # Detect non-Latin scripts (Devanagari, Tamil, Arabic, etc.)
    for char in text:
        if char.isalpha():
            cp = ord(char)
            # Latin character blocks range up to 0x024F (extended Latin)
            if cp > 0x024F:
                return True
    return False

def parse_review(raw_item, default_source="unknown"):
    """
    Parses a single review item from different schemas.
    Handles App Store, Play Store, Trustpilot, Quora, and generic review formats.
    """
    # 1. Determine Source
    source = raw_item.get("source", raw_item.get("platform", default_source)).lower()
    
    # 2. Extract review text
    review_text = raw_item.get("text", raw_item.get("review_text", raw_item.get("comment", raw_item.get("content", ""))))
    if not review_text or not isinstance(review_text, str):
        return None
    review_text = review_text.strip()
    
    # Word count check: remove reviews with less than 5 words
    words = review_text.split()
    if len(words) < 5:
        return None

    # Emoji & non-Latin script check
    if contains_emojis_or_non_latin(review_text):
        return None

    # 3. Extract rating / score
    rating = raw_item.get("rating", raw_item.get("stars", raw_item.get("upvotes", None)))
    if rating is not None:
        try:
            rating = int(rating)
        except ValueError:
            rating = None

    # 4. Extract date
    raw_date = raw_item.get("timestamp", raw_item.get("date", raw_item.get("created_at", None)))
    timestamp = normalize_date(raw_date)

    # 5. Extract metadata
    app_version = raw_item.get("app_version", raw_item.get("version", None))
    
    # Generate content hash for deduplication
    timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
    content_hash = generate_content_hash(source, review_text, timestamp_str)

    return RawReview(
        source=source,
        rating=rating,
        review_text=review_text,
        timestamp=timestamp,
        app_version=app_version,
        raw_payload=raw_item,
        content_hash=content_hash
    )

def fetch_from_n8n(webhook_url=N8N_WEBHOOK_URL):
    """Fetches reviews from the n8n workflow webhook with retry logic."""
    print(f"Triggering ingestion via n8n webhook: {webhook_url}")
    
    # Configure request (No authorization header required)
    req = urllib.request.Request(
        webhook_url,
        headers={"Content-Type": "application/json", "User-Agent": "BlinkitReviewAnalyzer/1.0"},
        method="POST"
    )
    
    # Send request with mock input params if required
    data = json.dumps({"action": "fetch_reviews", "platform": "blinkit"}).encode('utf-8')
    
    try:
        with urllib.request.urlopen(req, data=data, timeout=10) as response:
            if response.status == 200:
                payload = json.loads(response.read().decode('utf-8'))
                print("Successfully fetched payloads from n8n.")
                return payload
            else:
                print(f"n8n Webhook returned status code: {response.status}")
                return None
    except urllib.error.URLError as e:
        print(f"Failed to connect to n8n webhook: {e}")
        return None

def get_mock_reviews():
    """Generates mock reviews for development, testing, and validation fallback."""
    print("Generating mock reviews as fallback/dry-run...")
    mock_data = [
        # Play Store / App Store
        {
            "source": "play_store",
            "rating": 2,
            "text": "Blinkit app layout is clean but I keep ordering the same onions and milk. Why doesn't the app suggest some fresh vegetables or new snacks that are on discount? Recommendation is not useful.",
            "timestamp": "2026-08-01T10:00:00SZ",
            "app_version": "v12.4.2"
        },
        {
            "source": "app_store",
            "rating": 1,
            "text": "Too much repeat-cart buying! I am a new pet parent and I wanted to check out pet care items, but they are hidden under 4 layers of categories. I just went to another app.",
            "timestamp": "2026-08-02T11:15:00SZ",
            "version": "v12.4.0"
        },
        # Trustpilot
        {
            "source": "trustpilot",
            "rating": 2,
            "text": "Very poor quality doubt for fresh meat. Item was not fresh and packaging was leaking. I prefer going to the local offline butcher because I don't trust quick commerce for non-grocery categories.",
            "timestamp": "2026-08-03T14:30:00SZ"
        },
        # Quora / Forums
        {
            "source": "quora",
            "text": "Is it safe to buy cosmetics on Blinkit? I usually order standard items like Maggie or milk, but I am highly sensitive to price and quality authenticity for cosmetics. I would need verified ratings or return policies before trying.",
            "timestamp": "2026-08-03T18:22:00SZ"
        },
        # Reddit
        {
            "source": "reddit",
            "rating": 45, # Upvotes
            "text": "Hinglish feedback: Delivery to sahi time pe ho gaya par product expiry close tha. Autopilot ordering works for basic kitchen items, but for dairy I always doubt product shelf life.",
            "timestamp": "2026-08-03T20:10:00SZ"
        },
        {
            "source": "reddit",
            "rating": 12,
            "text": "I ordered pet food recently due to sudden relocation. But the search doesn't show deals or sample packs, making it hard to try new brands.",
            "timestamp": "2026-08-04T00:05:00SZ"
        }
    ]
    return mock_data

# Key fields to remove from review payloads
REMOVE_KEYS = [
    "reviewed", "userName", "username", "userImage", "userimage",
    "reviewCreated Version", "reviewCreatedVersion", "reviewcreated version",
    "at", "replyContent", "replycontent", "replied At", "repliedAt", "replied at"
]

def clean_payload(payload):
    """Returns a clean copy of the payload with the specified user keys removed."""
    if not isinstance(payload, dict):
        return payload
    cleaned = payload.copy()
    for key in REMOVE_KEYS:
        # Check matching key or variations with space removed
        for k in list(cleaned.keys()):
            k_lower = k.lower()
            key_lower = key.lower()
            if k_lower == key_lower or k_lower.replace(" ", "") == key_lower.replace(" ", ""):
                cleaned.pop(k, None)
    return cleaned

def ingest_reviews(dry_run=False):
    """Orchestrates the ingestion, parsing, deduplication, and database storage process."""
    init_db() # Ensure tables exist
    
    # 1. Fetch data
    raw_data = None
    if not dry_run:
        raw_data = fetch_from_n8n()
        
    # 2. Fallback to mock data if dry_run or fetch failed
    if not raw_data:
        raw_data = get_mock_reviews()
        
    # Standardize format: n8n might return a list directly, or wrapped in a dict
    if isinstance(raw_data, dict):
        reviews_list = raw_data.get("reviews", raw_data.get("data", []))
    elif isinstance(raw_data, list):
        reviews_list = raw_data
    else:
        print("Invalid payload format received.")
        return 0

    # Write actual reviews file (raw reviews fetched before normalization/filtering)
    raw_file_path = os.path.join(os.path.dirname(__file__), "raw_reviews.json")
    try:
        with open(raw_file_path, "w", encoding="utf-8") as f:
            json.dump(reviews_list, f, indent=2, ensure_ascii=False)
        print(f"Saved all actual raw reviews to: {raw_file_path}")
    except Exception as e:
        print(f"Failed to save raw_reviews.json: {e}")

    print(f"Processing {len(reviews_list)} ingested items...")
    db = SessionLocal()
    saved_count = 0
    duplicate_count = 0
    normalized_payloads = []
    
    try:
        for item in reviews_list:
            review_obj = parse_review(item)
            if not review_obj:
                continue
                
            try:
                db.add(review_obj)
                db.commit()
                saved_count += 1
                
                # If successfully saved to DB (i.e. passes duplicates check),
                # clean payload of target fields and add to normalized reviews list
                cleaned_item = clean_payload(item)
                normalized_payloads.append(cleaned_item)
            except IntegrityError:
                db.rollback()
                duplicate_count += 1
                
        print(f"Ingestion completed. Saved: {saved_count}, Skipped (Duplicate): {duplicate_count}")
        
        # Write normalized reviews file (filtered and fields removed)
        norm_file_path = os.path.join(os.path.dirname(__file__), "normalized_reviews.json")
        try:
            with open(norm_file_path, "w", encoding="utf-8") as f:
                json.dump(normalized_payloads, f, indent=2, ensure_ascii=False)
            print(f"Saved all normalized reviews to: {norm_file_path}")
        except Exception as e:
            print(f"Failed to save normalized_reviews.json: {e}")

    finally:
        db.close()
        
    return saved_count

if __name__ == "__main__":
    # Check if run with 'dry-run' command argument
    use_dry_run = "dry-run" in sys.argv or "--dry-run" in sys.argv
    ingest_reviews(dry_run=use_dry_run)
