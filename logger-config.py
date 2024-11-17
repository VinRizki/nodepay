import sys
from loguru import logger
import os

# Create logs directory if it doesn't exist
LOGS_DIR = "logs"
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

LOG_FILE = os.path.join(LOGS_DIR, "nodepay.log")

# Remove default logger
logger.remove()

# Add console logger with colors
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    colorize=True,
    level="INFO"
)

# Add file logger
logger.add(
    LOG_FILE,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    rotation="1 day",  # Create new file daily
    retention="7 days",  # Keep logs for 7 days
    compression="zip",  # Compress old logs
    level="INFO"
)

# Function to handle uncaught exceptions
def handle_exception(type, value, traceback):
    logger.opt(exception=(type, value, traceback)).critical("Uncaught exception:")
    sys.__excepthook__(type, value, traceback)  # Call default handler as well

# Set exception handler
sys.excepthook = handle_exception

# Export logger instance
log = logger.bind()
