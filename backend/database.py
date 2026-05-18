from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from contextlib import contextmanager
from config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


@contextmanager
def get_db_ctx():
    """Context manager for DB sessions (use in background tasks / services)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db():
    """FastAPI dependency for DB sessions."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _auto_migrate_columns():
    """Add any ORM-defined columns that are missing from existing SQLite tables."""
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    with engine.connect() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {col["name"] for col in inspector.get_columns(table.name)}
            for col in table.columns:
                if col.name not in existing:
                    col_type = col.type.compile(engine.dialect)
                    nullable = "NULL" if col.nullable else "NOT NULL"
                    default_clause = ""
                    if col.default is not None and col.default.is_scalar:
                        default_clause = f" DEFAULT {col.default.arg!r}"
                    elif col.nullable:
                        default_clause = " DEFAULT NULL"
                    stmt = (
                        f"ALTER TABLE {table.name} ADD COLUMN "
                        f"{col.name} {col_type}{default_clause}"
                    )
                    conn.execute(text(stmt))
                    conn.commit()
                    print(f"[migrate] Added column {table.name}.{col.name}")


def init_db():
    """Create all tables and auto-migrate missing columns (SQLite-safe)."""
    import models  # noqa: F401 — ensure models are registered
    Base.metadata.create_all(bind=engine)
    _auto_migrate_columns()
