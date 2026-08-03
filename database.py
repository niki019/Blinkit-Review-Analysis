from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
import os
from models import Base

# DB Path configuration
DB_FILE = os.path.join(os.path.dirname(__file__), "reviews.db")
DATABASE_URL = f"sqlite:///{DB_FILE}"

# Create Engine
engine = create_engine(
    DATABASE_URL, 
    connect_args={"timeout": 5} # 5000ms busy timeout to prevent write-locking
)

# SQLite event listeners for WAL mode and foreign key enforcement
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

# Session Factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initializes the SQLite database schema."""
    Base.metadata.create_all(bind=engine)
    print(f"Database initialized at: {DB_FILE} with WAL mode enabled.")

if __name__ == "__main__":
    init_db()
