import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=env_path)
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL") or "sqlite:///./tmp/dev.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(
    bind=engine, 
    autoflush=False, 
    autocommit=False
)
