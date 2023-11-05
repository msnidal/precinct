# logging_config.py
import logging
from logging.handlers import RotatingFileHandler
import os

LOGGER_NAME = "PrecinctLogger"

# Check if the logger has already been configured
if not logging.getLogger(LOGGER_NAME).hasHandlers():
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)

    log_path = os.path.join(os.path.dirname(__file__), "precinct.log")
    handler = RotatingFileHandler(log_path, maxBytes=10240, backupCount=3)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
else:
    logger = logging.getLogger("PrecinctLogger")


def get_logger():
    return logger
