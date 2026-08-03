import unittest
import os
from database import Base, engine, SessionLocal
from models import RawReview, ExtractedTheme
from nlp_engine import (
    clean_text, sentence_segmenter, score_sentence_sentiment,
    classify_sentence_themes, extract_unsupervised_topics,
    process_single_review, run_nlp_pipeline
)

class TestNLPPipeline(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Setup test db file path
        cls.test_db_file = "test_nlp_reviews.db"
        
        # Override configuration in database and import modules
        import database
        import nlp_engine
        database.DB_FILE = cls.test_db_file
        database.DATABASE_URL = f"sqlite:///{cls.test_db_file}"
        database.engine = database.create_engine(database.DATABASE_URL, connect_args={"timeout": 5})
        database.SessionLocal = database.sessionmaker(bind=database.engine)
        nlp_engine.SessionLocal = database.SessionLocal

    @classmethod
    def tearDownClass(cls):
        # Dispose engine to release file locks
        import database
        database.engine.dispose()
        
        # Remove test db
        if os.path.exists(cls.test_db_file):
            try:
                os.remove(cls.test_db_file)
            except PermissionError:
                pass
            
    def setUp(self):
        import database
        Base.metadata.create_all(bind=database.engine)
        self.db = database.SessionLocal()
        
    def tearDown(self):
        self.db.close()
        import database
        Base.metadata.drop_all(bind=database.engine)

    def test_clean_text(self):
        self.assertEqual(clean_text("Test https://link.com Text"), "test text")
        self.assertEqual(clean_text("Hello   World  "), "hello world")

    def test_sentence_segmenter(self):
        text = "This is sentence one. That is sentence two! Is this three?"
        segments = sentence_segmenter(text)
        self.assertEqual(len(segments), 3)
        self.assertEqual(segments[0], "This is sentence one")
        self.assertEqual(segments[1], "That is sentence two")

    def test_sentiment_scoring_basics(self):
        # Positive review
        score_pos = score_sentence_sentiment("This fresh product is really great")
        self.assertGreater(score_pos, 0.0)

        # Negative review
        score_neg = score_sentence_sentiment("Bad product and stale bread")
        self.assertLess(score_neg, 0.0)

    def test_sentiment_negations(self):
        # Negated positive -> negative
        score = score_sentence_sentiment("This is not a great experience")
        self.assertLess(score, 0.0)

        # Negated negative -> positive (or less negative)
        score_neg_neg = score_sentence_sentiment("The quality is not bad")
        self.assertGreater(score_neg_neg, 0.0)

    def test_hinglish_sentiment(self):
        # Hinglish word matches
        score_hinglish = score_sentence_sentiment("Blinkit support is bekar and late delivery")
        self.assertLess(score_hinglish, 0.0)

    def test_taxonomy_theme_matching(self):
        # Matching quality doubt
        themes_q = classify_sentence_themes("This apple is stale and has bad quality")
        self.assertIn("quality doubt", themes_q)

        # Matching price sensitivity
        themes_p = classify_sentence_themes("The items are very mahanga and costly")
        self.assertIn("price sensitivity", themes_p)

        # Matching delivery/quality issues
        themes_d = classify_sentence_themes("My order was late and delivery delayed")
        self.assertIn("delivery/quality issues", themes_d)

    def test_unsupervised_topic_extraction(self):
        corpus = [
            "Users face login issues on checkout screen",
            "There are major login issues when opening payments page",
            "Payment failed and login issues occurred"
        ]
        phrases = extract_unsupervised_topics(corpus, top_n=2)
        # 'login issues' should be flagged since it's recurring and not in taxonomy keywords
        self.assertIn("login issues", phrases)

    def test_end_to_end_nlp_review_processing(self):
        # Insert a raw review
        review = RawReview(
            id="test-uuid-12345",
            source="reddit",
            rating=1,
            review_text="This apple is rotten and stale. Quality is poor.",
            content_hash="mock-hash-12345"
        )
        self.db.add(review)
        self.db.commit()
        
        # Run processing on it
        themes_created = process_single_review(self.db, review)
        self.assertEqual(themes_created, 2) # matches 'rotten and stale' (quality doubt), 'quality is poor' (quality doubt)
        
        # Verify db entries
        themes_in_db = self.db.query(ExtractedTheme).filter_by(review_id=review.id).all()
        self.assertEqual(len(themes_in_db), 2)
        self.assertEqual(themes_in_db[0].theme_tag, "quality doubt")

if __name__ == "__main__":
    unittest.main()
