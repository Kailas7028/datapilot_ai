import logging
import sys
import os
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler

# Context variables for tracing
request_id_var: ContextVar[str] = ContextVar('request_id', default='default')
user_id_var: ContextVar[str] = ContextVar('user_id', default='anonymous')
org_id_var: ContextVar[str] = ContextVar('org_id', default='no_org')

class RequestIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.user_id = user_id_var.get()
        record.org_id = org_id_var.get()
        return True

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)

        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.DEBUG)

        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        fh = RotatingFileHandler(
            filename=os.path.join(log_dir, 'app.log'),
            maxBytes=5 * 1024 * 1024, 
            backupCount=3,
            encoding='utf-8'
        )
        fh.setLevel(logging.DEBUG)

        # The Format: [ORG] | [USER] | [REQUEST]
        formatter = logging.Formatter(
            '%(asctime)s | [%(org_id)s] | [%(user_id)s] | [%(request_id)s] | %(levelname)-8s | %(name)s | %(message)s', 
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        ch.setFormatter(formatter)
        fh.setFormatter(formatter)
        
        request_filter = RequestIDFilter()
        ch.addFilter(request_filter)
        fh.addFilter(request_filter)

        logger.addHandler(ch)
        logger.addHandler(fh)

    return logger