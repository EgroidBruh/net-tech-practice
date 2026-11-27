from sqlalchemy import create_engine, inspect, text
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
    # Additive migration for databases created by version 0.2; preserve all data.
    with engine.begin() as connection:
        columns = {column["name"] for column in inspect(connection).get_columns("employees")}
        if "sip_extension" not in columns:
            connection.execute(text("ALTER TABLE employees ADD COLUMN sip_extension VARCHAR(10)"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_employees_sip_extension ON employees (sip_extension)"))

        notification_columns = {c["name"] for c in inspect(connection).get_columns("notifications")}
        for name, sql_type in {"parent_id": "UUID", "confirmed_at": "TIMESTAMP WITH TIME ZONE", "dtmf_digit": "VARCHAR(1)"}.items():
            if name not in notification_columns:
                connection.execute(text(f"ALTER TABLE notifications ADD COLUMN {name} {sql_type}"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_notifications_parent_id ON notifications(parent_id)"))

if __name__ == "__main__":
    from database import init_db as initialize_database
    initialize_database()
