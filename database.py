from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# Gets DATABASE_URL from environment
# Render sets this automatically when you link PostgreSQL
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///chatops.db")

# Render PostgreSQL uses "postgres://" but SQLAlchemy needs "postgresql://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

print(f"Using database: {DATABASE_URL[:30]}...")  # Print first 30 chars only

engine       = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base         = declarative_base()