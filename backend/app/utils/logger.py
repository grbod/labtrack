"""Logging configuration for COA Management System."""

import sys
from pathlib import Path
from loguru import logger
from app.config import settings


def setup_logger():
    """Configure the logger for the application."""
    # Remove default handler
    logger.remove()

    # Console handler
    logger.add(
        sys.stdout,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    # File handler
    if settings.log_file:
        logger.add(
            settings.log_file,
            level=settings.log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            rotation="10 MB",
            retention="30 days",
            compression="zip",
        )

    return logger


# Initialize logger
logger = setup_logger()
