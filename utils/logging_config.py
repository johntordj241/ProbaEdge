import logging
import sys
from datetime import datetime

# Configuration centralisée du logging
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = logging.INFO


def setup_logging(name: str = __name__) -> logging.Logger:
    """
    Configure et retourne un logger centralisé.

    Args:
        name: Nom du module (utiliser __name__)

    Returns:
        Logger configuré
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(LOG_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(LOG_LEVEL)

    return logger


# Alias pour import facile
get_logger = setup_logging

__all__ = ["setup_logging", "get_logger"]
