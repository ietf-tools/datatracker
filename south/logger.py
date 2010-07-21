import sys
import logging
from django.conf import settings

class NullHandler(logging.Handler):
    def emit(self, record):
        pass

h = NullHandler()

_logger = logging.getLogger("south")
_logger.addHandler(h)
_logger.setLevel(logging.DEBUG)
# TODO: Add a log formatter?

def get_logger():
    debug_on = getattr(settings, "SOUTH_LOGGING_ON", False)
    logging_file = getattr(settings, "SOUTH_LOGGING_FILE", False)
    
    if debug_on:
        if logging_file:
            _logger.addHandler( logging.FileHandler(logging_file) )
            _logger.setLevel(logging.DEBUG)
        else:
            raise IOError, "SOUTH_LOGGING_ON is True. You also need a SOUTH_LOGGING_FILE setting."
    return _logger
