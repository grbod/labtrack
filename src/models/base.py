"""Base model class with common fields for all models."""

from datetime import datetime
from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.ext.declarative import declared_attr
from src.database import Base


class BaseModel(Base):
    """Abstract base model with common fields."""

    __abstract__ = True

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    @declared_attr
    def __tablename__(cls):
        """Generate table name from class name."""
        return cls.__name__.lower() + "s"

    def __repr__(self):
        """Default string representation."""
        if hasattr(self, "id") and self.id is not None:
            return f"<{self.__class__.__name__}(id={self.id})>"
        else:
            # For models without id field (like association tables)
            return f"<{self.__class__.__name__}>"

    def to_dict(self):
        """Convert model to dictionary."""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
