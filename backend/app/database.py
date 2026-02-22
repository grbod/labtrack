"""Database configuration and session management."""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings
from app.utils.logger import logger

# Path to alembic.ini relative to this file (backend/app/database.py -> backend/alembic.ini)
_ALEMBIC_INI = str(Path(__file__).parent.parent / "alembic.ini")

# Create engine
engine = create_engine(settings.database_url, echo=settings.debug)

# Create session factory
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

# Create base class for models
Base = declarative_base()


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database using Alembic migrations, then seed if empty.

    Strategy:
    - Fresh DB (no tables): create_all() for full schema, then stamp Alembic at head.
    - Existing DB without alembic_version: stamp at head, then upgrade (no-op).
    - Existing DB with alembic_version: upgrade to apply pending migrations.
    - No alembic.ini (tests): fall back to create_all() only.
    """
    import app.models  # noqa: F401 — register all models with Base.metadata

    alembic_ini = Path(_ALEMBIC_INI)
    if alembic_ini.exists():
        try:
            from alembic.config import Config
            from alembic import command
            from sqlalchemy import inspect

            from sqlalchemy import text

            alembic_cfg = Config(str(alembic_ini))
            inspector = inspect(engine)
            has_tables = bool(inspector.get_table_names())
            has_alembic = inspector.has_table("alembic_version")

            # Check if alembic_version has an actual revision (not just empty table)
            alembic_has_revision = False
            if has_alembic:
                with engine.connect() as conn:
                    row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).first()
                    alembic_has_revision = row is not None

            if not has_tables:
                # Fresh database — create full schema, then stamp
                Base.metadata.create_all(bind=engine)
                command.stamp(alembic_cfg, "head")
                logger.info("Fresh database initialized and stamped at Alembic head")
            elif not alembic_has_revision:
                # Existing DB from create_all() or failed migration — stamp at head
                command.stamp(alembic_cfg, "head")
                logger.info("Stamped existing database at Alembic head")
            else:
                # Normal Alembic-managed DB — apply pending migrations
                command.upgrade(alembic_cfg, "head")
                logger.info("Database migrations applied successfully")
        except Exception as e:
            logger.error(f"Error running database migrations: {e}")
            raise
    else:
        # Fallback for tests or environments without alembic.ini
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created with create_all (no alembic.ini found)")

    from app.seed import seed_if_empty
    seed_if_empty(engine)
