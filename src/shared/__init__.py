"""Shared utilities and configuration"""

from .config import config, Config
from .logging_config import logger, get_logger
from .embedding_service import (
    EmbeddingService,
    EmbeddingServiceError,
    EmbeddingModelUnavailableError
)

__all__ = [
    "config",
    "Config",
    "logger",
    "get_logger",
    "EmbeddingService",
    "EmbeddingServiceError",
    "EmbeddingModelUnavailableError"
]
