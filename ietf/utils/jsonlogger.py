# Copyright The IETF Trust 2024, All Rights Reserved
from pythonjsonlogger import jsonlogger
import time


class DatatrackerJsonFormatter(jsonlogger.JsonFormatter):
    converter = time.gmtime  # use UTC
    default_msec_format = "%s.%03d"  # '.' instead of ','
