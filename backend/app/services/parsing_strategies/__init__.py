"""PDF parsing strategies for different lab formats."""

from .base_strategy import BaseParsingStrategy
from .lab_strategy import GenericLabStrategy

__all__ = ["BaseParsingStrategy", "GenericLabStrategy"]
