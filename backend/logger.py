import logging
import sys
from pythonjsonlogger import jsonlogger

def setup_logging():
    """Setup structured JSON logging"""
    logger = logging.getLogger()
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Set log level
    log_level = getattr(logging, "INFO")
    logger.setLevel(log_level)
    
    # Create stdout handler
    handler = logging.StreamHandler(sys.stdout)
    
    # Create JSON formatter
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(levelname)s %(name)s %(message)s %(pathname)s %(lineno)d',
        rename_fields={
            'asctime': 'timestamp',
            'levelname': 'level',
            'pathname': 'file',
            'lineno': 'line'
        }
    )
    
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

# Initialize logger
logger = setup_logging()