from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from config import settings

class Base(DeclarativeBase):
    pass

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def get_db():
    with SessionLocal() as session:
        yield session

def init_db():
    import models.tables  # register tables
    Base.metadata.create_all(engine)

if __name__ == "__main__":
    from database import init_db as initialize_database
    initialize_database()
