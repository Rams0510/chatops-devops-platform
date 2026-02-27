from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///chatops.db")

# Fix Render PostgreSQL URL
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Try pg8000 driver for Python 3.14 compatibility
if "postgresql" in DATABASE_URL and "pg8000" not in DATABASE_URL and "psycopg2" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+pg8000://", 1)

print(f"Connecting to: {DATABASE_URL[:50]}...")

try:
    engine = create_engine(DATABASE_URL)
    print("Database engine created successfully!")
except Exception as e:
    print(f"Database connection error: {e}")
    # Fallback to SQLite
    engine = create_engine("sqlite:///chatops.db")
    print("Falling back to SQLite!")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base         = declarative_base()