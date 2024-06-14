from pythonjsonlogger.jsonlogger import JsonFormatter
from gunicorn.glogging import CONFIG_DEFAULTS

logconfig_dict = CONFIG_DEFAULTS
logconfig_dict["loggers"]["gunicorn.access"] = {
    "level": "INFO",
    "handlers": ["json_request"],
    "propagate": False,
}
logconfig_dict["loggers"]["gunicorn.error"] = {
    "level": "INFO",
    "handlers": ["json_request"],
    "propagate": False,
}
logconfig_dict["handlers"]["json_request"] = {
    "class": "logging.StreamHandler",
    "formatter": "gunicorn_json",
}
logconfig_dict["formatters"]["gunicorn_json"] = {
    "()": JsonFormatter,
}
