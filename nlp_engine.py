import re
import math
from collections import Counter
from database import SessionLocal
from models import RawReview, ExtractedTheme

# --- Hinglish and English NLP Dictionaries ---

# Hinglish & English Sentiment Lexicon
SENTIMENT_LEXICON = {
    # Positive
    "good": 0.6, "great": 0.8, "excellent": 0.9, "fresh": 0.7, "fast": 0.6,
    "quick": 0.6, "sahi": 0.5, "mast": 0.8, "achha": 0.5, "acha": 0.5,
    "best": 0.8, "love": 0.8, "friendly": 0.6, "nice": 0.5, "happy": 0.7,
    "like": 0.4, "discount": 0.4, "saves": 0.5, "convenient": 0.7, "superb": 0.9,
    
    # Negative
    "bad": -0.6, "poor": -0.7, "worst": -0.9, "kharab": -0.7, "stale": -0.6,
    "rot": -0.7, "expire": -0.8, "expiring": -0.8, "deri": -0.5, "late": -0.5,
    "delayed": -0.6, "slow": -0.5, "leak": -0.6, "leaking": -0.7, "spill": -0.6,
    "spilled": -0.7, "damaged": -0.8, "fake": -0.8, "cheat": -0.8, "cheating": -0.9,
    "expensive": -0.5, "costly": -0.5, "mahanga": -0.6, "expensive": -0.5,
    "irrelevant": -0.6, "poor search": -0.7, "useless": -0.8, "worst support": -0.8,
    "confusing": -0.4, "dark pattern": -0.8, "fraud": -0.9, "bekar": -0.7,
    "defective": -0.7, "refuse": -0.5, "issue": -0.4, "problem": -0.4, "fail": -0.6
}

# Valence multipliers for negations
NEGATIONS = {"not", "no", "never", "nahi", "nahin", "don't", "cant", "cannot", "didnt", "wont"}

# Keyword-anchored taxonomy mapping themes to research questions & key phrases/words
TAXONOMY = {
    "habit/convenience": {
        "keywords": ["habit", "convenience", "routine", "autopilot", "repeat", "regular", "every week", "weekly", "daily", "save time", "saving time", "easy ordering", "loyalty"],
        "hinglish": ["aadat", "roz", "daily", "hamesha"]
    },
    "quality doubt": {
        "keywords": ["quality", "fresh", "stale", "rot", "expire", "smell", "bad look", "rotten", "shelf life", "authenticity", "unverified"],
        "hinglish": ["kharab", "sada", "sad gaya", "purana", "exipry"]
    },
    "trust deficit": {
        "keywords": ["trust", "fake", "original", "refund", "return", "cheat", "cheat", "scam", "fraud", "customer care", "customer support", "support", "help desk", "unhelpful"],
        "hinglish": ["dhokha", "nakli", "paise wapas", "care wale", "support wale"]
    },
    "price sensitivity": {
        "keywords": ["price", "cost", "expensive", "costly", "cheap", "charge", "fee", "tax", "delivery charge", "surge", "discount", "offer", "deal"],
        "hinglish": ["mahanga", "mehenga", "sasta", "loot", "extra charge"]
    },
    "no felt need": {
        "keywords": ["need", "unnecessary", "why try", "offline", "local shop", "kirana", "market", "go out"],
        "hinglish": ["zaroorat nahi", "bahar se", "dukaan से"]
    },
    "unfamiliarity": {
        "keywords": ["unfamiliar", "new brand", "dont know", "never heard", "first time", "explore", "try new", "variety"],
        "hinglish": ["pata nahi", "pehli baar", "naya brand"]
    },
    "recommendation module": {
        "keywords": ["recommend", "recommendation", "suggest", "suggestion", "layout", "view", "feed", "banner", "ad", "pop up", "pop-up"],
        "hinglish": ["suggest karta", "app dikhata", "ad", "banner"]
    },
    "search": {
        "keywords": ["search", "find", "query", "typing", "voice search", "result", "not showing"],
        "hinglish": ["khoj", "dhoond", "search kiya"]
    },
    "delivery/quality issues": {
        "keywords": ["late", "delay", "time", "hour", "minute", "waiting", "speed", "packaging", "spill", "leak", "damage", "torn", "missing", "wrong item"],
        "hinglish": ["deri", "late", "dhila", "packet phat", "gaya", "missing tha"]
    }
}

def clean_text(text):
    """Cleans review text by stripping bots, URLs, and extra characters while preserving words and basic emojis."""
    if not text:
        return ""
    # Strip URLs
    text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)
    # Convert text to lowercase
    text = text.lower()
    # Normalize whitespaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def sentence_segmenter(text):
    """Splits a review into individual sentences/phrases for sentence-level analysis."""
    # Split on periods, exclamation marks, or question marks
    sentences = re.split(r'[.!?]+', text)
    return [s.strip() for s in sentences if len(s.strip()) > 3]

def score_sentence_sentiment(sentence):
    """
    Computes a sentiment score for a sentence based on the lexicons.
    Accounts for basic negations.
    Returns a score between -1.0 and 1.0.
    """
    words = re.findall(r'\b\w+\b', sentence.lower())
    score = 0.0
    negate = False
    match_count = 0

    for idx, word in enumerate(words):
        # Handle Negation
        if word in NEGATIONS:
            negate = True
            continue
        
        # Match word in lexicon
        if word in SENTIMENT_LEXICON:
            val = SENTIMENT_LEXICON[word]
            if negate:
                val = -1.0 * val # Invert sentiment
                negate = False # Reset negation flag
            score += val
            match_count += 1
            
        # Reset negation after 2 non-lexicon words to prevent infinite scope
        if negate and idx > 0 and words[idx-1] not in NEGATIONS:
            negate = False

    if match_count > 0:
        # Normalize score between -1.0 and 1.0
        normalized_score = score / match_count
        return max(min(normalized_score, 1.0), -1.0)
    
    return 0.0 # Neutral

def classify_sentence_themes(sentence):
    """
    Matches a sentence to taxonomy theme tags based on keyword and Hinglish expressions.
    Returns a list of matched theme tags.
    """
    matched_themes = []
    sentence_lower = sentence.lower()
    
    for theme, matchers in TAXONOMY.items():
        # Check standard keywords
        for keyword in matchers["keywords"]:
            # Word boundary check
            if re.search(r'\b' + re.escape(keyword) + r'\b', sentence_lower):
                matched_themes.append(theme)
                break
        
        # Check Hinglish keywords
        if theme not in matched_themes:
            for hinglish_word in matchers["hinglish"]:
                if re.search(r'\b' + re.escape(hinglish_word) + r'\b', sentence_lower):
                    matched_themes.append(theme)
                    break
                    
    return matched_themes

def extract_unsupervised_topics(corpus, top_n=5):
    """
    Identifies recurring bigrams/trigrams (recurring phrases) that are NOT represented in the taxonomy.
    Acts as the unsupervised clustering discovery layer.
    """
    phrases = []
    # Stopwords to filter out from phrase extraction
    stopwords = {"the", "and", "this", "that", "with", "have", "from", "for", "was", "but", "not", "app", "blinkit"}
    
    # Simple bigram extractor
    for text in corpus:
        words = re.findall(r'\b\w+\b', text.lower())
        for i in range(len(words) - 1):
            w1, w2 = words[i], words[i+1]
            if w1 not in stopwords and w2 not in stopwords:
                phrase = f"{w1} {w2}"
                # Check if this phrase overlaps with existing taxonomy keywords
                is_taxonomy = False
                for matcher in TAXONOMY.values():
                    if any(w in matcher["keywords"] or w in matcher["hinglish"] for w in [w1, w2]):
                        is_taxonomy = True
                        break
                if not is_taxonomy:
                    phrases.append(phrase)
                    
    # Frequency count
    counter = Counter(phrases)
    return [item[0] for item in counter.most_common(top_n)]

def process_single_review(db, review):
    """
    Processes a single raw review entry:
    1. Segment into sentences.
    2. Extract theme tags and sentiment scores.
    3. Store hits in extracted_themes table.
    """
    cleaned = clean_text(review.review_text)
    sentences = sentence_segmenter(cleaned)
    
    # If no periods exist, process the entire review as one sentence
    if not sentences:
        sentences = [cleaned]
        
    theme_count = 0
    for sentence in sentences:
        sentiment = score_sentence_sentiment(sentence)
        themes = classify_sentence_themes(sentence)
        
        for theme in themes:
            theme_obj = ExtractedTheme(
                review_id=review.id,
                theme_tag=theme,
                sentiment_score=sentiment,
                sentence_extract=sentence
            )
            db.add(theme_obj)
            theme_count += 1
            
    db.commit()
    return theme_count

def run_nlp_pipeline():
    """Runs the NLP pipeline on all raw reviews that do not have extracted themes yet."""
    db = SessionLocal()
    try:
        # Query reviews that don't have theme mappings
        from sqlalchemy import not_
        subquery = db.query(ExtractedTheme.review_id).distinct()
        unprocessed_reviews = db.query(RawReview).filter(not_(RawReview.id.in_(subquery))).all()
        
        print(f"Found {len(unprocessed_reviews)} unprocessed reviews.")
        
        total_themes_created = 0
        for review in unprocessed_reviews:
            count = process_single_review(db, review)
            total_themes_created += count
            
        print(f"NLP Pipeline completed. Created {total_themes_created} theme extractions.")
        
        # Run unsupervised topic analysis for reporting
        all_reviews = db.query(RawReview).all()
        corpus = [r.review_text for r in all_reviews]
        unsupervised_themes = extract_unsupervised_topics(corpus)
        print("Unsupervised recurring phrase suggestions (outside taxonomy):")
        for idx, phrase in enumerate(unsupervised_themes):
            print(f" {idx+1}. '{phrase}'")
            
    finally:
        db.close()

if __name__ == "__main__":
    run_nlp_pipeline()
