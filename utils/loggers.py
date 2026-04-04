import logging
import sys
import os
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler


# Context variable to hold the request ID for each log entry, allowing us to trace logs back to specific requests in a multi-threaded or async environment.
request_id_var: ContextVar[str] = ContextVar('request_id', default='default')
user_id_var: ContextVar[str] = ContextVar('user_id', default= 'anonymous')

#create a custom logging filter to inject the request ID into log records
class RequestIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.user_id = user_id_var.get()
        return True

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    
    # Check if handlers ALREADY exist. If they don't, set them up.
    if not logger.handlers:
        # 1. Set the BASE logger level
        logger.setLevel(logging.DEBUG)

        # 2. Create console handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.DEBUG)

        # 3. Create a logs directory if it doesn't exist
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # 4. Rotating File Handler
        # maxBytes: 5 * 1024 * 1024 = 5 Megabytes per file
        # backupCount: Keep up to 3 old log files before deleting the oldest one
        fh = RotatingFileHandler(
            filename=os.path.join(log_dir, 'app.log'),
            maxBytes=5 * 1024 * 1024, 
            backupCount=3,
            encoding='utf-8' # Prevents character map crashes on Windows
        )
        fh.setLevel(logging.DEBUG)

        # 5. Create formatter
        formatter = logging.Formatter(
            '%(asctime)s | [%(user_id)s] | [%(request_id)s] | %(levelname)-8s | %(name)s | %(message)s', 
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 6. Set formatter for handlers
        ch.setFormatter(formatter)
        fh.setFormatter(formatter)
        # 7. Attach the custom filter to the handlers
        request_filter = RequestIDFilter()
        ch.addFilter(request_filter)
        fh.addFilter(request_filter)

        # 8. Add handlers to logger
        logger.addHandler(ch)
        logger.addHandler(fh)

    return logger