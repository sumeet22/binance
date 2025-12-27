"""Logging configuration."""

import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logging(log_level: str = 'INFO', 
                  log_to_file: bool = True,
                  log_dir: str = 'logs') -> None:
    """Setup logging configuration."""
    if log_to_file:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    root_logger.handlers = []
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    if log_to_file:
        today = datetime.now().strftime('%Y%m%d')
        log_file = Path(log_dir) / f'trading_{today}.log'
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
