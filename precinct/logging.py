# logging_config.py
import logging
from logging.handlers import RotatingFileHandler
import os
import platform

LOGGER_NAME = "PrecinctLogger"

# Setup logger to file
def setup_logger():
    logger = logging.getLogger(LOGGER_NAME)
    if logger.hasHandlers():  # Logger is already configured
        return logger

    logger.setLevel(logging.INFO)

    # Define log paths for different platforms
    if platform.system() == 'Windows':
        log_directory = os.path.join(os.environ['LOCALAPPDATA'], 'Precinct', 'Logs')
    else:  # Unix/Linux/Mac
        log_directory = os.path.expanduser('~/.local/share/precinct/logs')

    # Ensure log directory exists
    if not os.path.exists(log_directory):
        try:
            os.makedirs(log_directory, exist_ok=True)
        except PermissionError:
            raise

    log_path = os.path.join(log_directory, "precinct.log")
    handler = RotatingFileHandler(log_path, maxBytes=10240, backupCount=3)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger

# Configure logger
logger = setup_logger()

def get_logger():
    return logger
