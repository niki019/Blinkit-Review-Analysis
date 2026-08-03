import unittest
import os
import shutil
import datetime
from database import engine, SessionLocal
from models import Base, RawReview
from ingest import parse_review, generate_content_hash, ingest_reviews, clean_payload

class TestIngestionPipeline(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Setup test db file path
        cls.test_db_file = "test_reviews.db"
        
        # Override configuration in database and ingest modules
        import database
        import ingest
        database.DB_FILE = cls.test_db_file
        database.DATABASE_URL = f"sqlite:///{cls.test_db_file}"
        database.engine = database.create_engine(database.DATABASE_URL, connect_args={"timeout": 5})
        database.SessionLocal = database.sessionmaker(bind=database.engine)
        ingest.SessionLocal = database.SessionLocal
        
    @classmethod
    def tearDownClass(cls):
        # Dispose engine to release file locks on test DB
        import database
        database.engine.dispose()
        
        # Remove test db and WAL sidecar files
        for suffix in ("", "-wal", "-shm"):
            path = cls.test_db_file + suffix
            if os.path.exists(path):
                try:
                    os.remove(path)
                except PermissionError:
                    pass
            
    def setUp(self):
        # Recreate tables before each test
        import database
        Base.metadata.create_all(bind=database.engine)
        self.db = database.SessionLocal()
        
    def tearDown(self):
        self.db.close()
        import database
        Base.metadata.drop_all(bind=database.engine)

    def test_content_hash_generation(self):
        hash1 = generate_content_hash("play_store", "nice app", "2026-08-04 00:00:00")
        hash2 = generate_content_hash("play_store", "nice app", "2026-08-04 00:00:00")
        hash3 = generate_content_hash("play_store", "different review", "2026-08-04 00:00:00")
        
        self.assertEqual(hash1, hash2)
        self.assertNotEqual(hash1, hash3)

    def test_parsing_play_store_review(self):
        raw_item = {
            "source": "play_store",
            "rating": 5,
            "text": "Great service and fast delivery",
            "timestamp": "2026-08-04T12:00:00SZ",
            "app_version": "1.0.0"
        }
        review = parse_review(raw_item)
        self.assertIsNotNone(review)
        self.assertEqual(review.source, "play_store")
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.review_text, "Great service and fast delivery")
        self.assertEqual(review.app_version, "1.0.0")

    def test_parsing_quora_review(self):
        raw_item = {
            "platform": "Quora",
            "content": "Why is the packaging sometimes bad?",
            "created_at": "2026-08-04 10:15:30",
            "upvotes": 4
        }
        review = parse_review(raw_item)
        self.assertIsNotNone(review)
        self.assertEqual(review.source, "quora")
        self.assertEqual(review.review_text, "Why is the packaging sometimes bad?")
        self.assertEqual(review.rating, 4)

    def test_deduplication(self):
        raw_item = {
            "source": "trustpilot",
            "stars": 1,
            "review_text": "Bad items delivered in torn bag!",
            "date": "2026-08-04"
        }
        # Parse and save first
        review1 = parse_review(raw_item)
        self.db.add(review1)
        self.db.commit()
        
        # Try inserting again
        review2 = parse_review(raw_item)
        self.db.add(review2)
        
        with self.assertRaises(Exception): # SQLite IntegrityError
            self.db.commit()
        self.db.rollback()

    def test_short_review_ignored(self):
        raw_item = {
            "source": "play_store",
            "text": "Too bad!", # 2 words
            "timestamp": "2026-08-04T12:00:00SZ"
        }
        review = parse_review(raw_item)
        self.assertIsNone(review)

    def test_emoji_review_ignored(self):
        raw_item = {
            "source": "play_store",
            "text": "Great service and fast delivery 😡", # contains emoji
            "timestamp": "2026-08-04T12:00:00SZ"
        }
        review = parse_review(raw_item)
        self.assertIsNone(review)

    def test_non_latin_script_review_ignored(self):
        raw_item = {
            "source": "play_store",
            "text": "डिलिवरी बहुत लेट है भाई", # Devanagari script
            "timestamp": "2026-08-04T12:00:00SZ"
        }
        review = parse_review(raw_item)
        self.assertIsNone(review)

    def test_clean_payload(self):
        raw_item = {
            "source": "play_store",
            "text": "Blinkit app layout is clean",
            "userName": "Nikki Agape",
            "userImage": "avatar.png",
            "reviewed": True,
            "reviewCreated Version": "v1.2",
            "at": "2026-08-04",
            "replyContent": "Thank you",
            "replied At": "2026-08-05"
        }
        cleaned = clean_payload(raw_item)
        self.assertNotIn("userName", cleaned)
        self.assertNotIn("userImage", cleaned)
        self.assertNotIn("reviewed", cleaned)
        self.assertNotIn("reviewCreated Version", cleaned)
        self.assertNotIn("at", cleaned)
        self.assertNotIn("replyContent", cleaned)
        self.assertNotIn("replied At", cleaned)
        self.assertEqual(cleaned["source"], "play_store")
        self.assertEqual(cleaned["text"], "Blinkit app layout is clean")

    def test_dry_run_ingest(self):
        # Test bulk ingestion with mock data
        saved = ingest_reviews(dry_run=True)
        self.assertGreater(saved, 0)
        
        # Verify db contents
        reviews_in_db = self.db.query(RawReview).all()
        self.assertEqual(len(reviews_in_db), saved)
        
        # Re-running ingest should yield 0 saves due to duplicate hash detection
        saved_again = ingest_reviews(dry_run=True)
        self.assertEqual(saved_again, 0)

if __name__ == "__main__":
    unittest.main()
