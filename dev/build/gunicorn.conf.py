# Copyright The IETF Trust 2024, All Rights Reserved

# Log as JSON on stdout (to distinguish from Django's logs on stderr)
#
# This is applied as an update to gunicorn's glogging.CONFIG_DEFAULTS.
logconfig_dict = {
    "loggers": {
        "gunicorn.error": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
            "qualname": "gunicorn.error"
        },

        "gunicorn.access": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
            "qualname": "gunicorn.access"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout"
        },
    },
    "formatters": {
        "json": {
            "class": "ietf.utils.jsonlogger.DatatrackerJsonFormatter",
            "style": "{",
            "format": "{asctime}{levelname}{message}{name}{process}",
        }
    }
}
