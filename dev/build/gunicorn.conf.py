# Copyright The IETF Trust 2024, All Rights Reserved

# Log as JSON on stdout (to distinguish from Django's logs on stderr)
#
# This is applied as an update to gunicorn's glogging.CONFIG_DEFAULTS.
logconfig_dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "root": {"level": "INFO", "handlers": ["console"]},
    "loggers": {
        "gunicorn.error": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
            "qualname": "gunicorn.error"
        },

        "gunicorn.access": {
            "level": "INFO",
            "handlers": ["access_console"],
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
        "access_console": {
            "class": "logging.StreamHandler",
            "formatter": "access_json",
            "stream": "ext://sys.stdout"
        },
    },
    "formatters": {
        "json": {
            "class": "ietf.utils.jsonlogger.DatatrackerJsonFormatter",
            "style": "{",
            "format": "{asctime}{levelname}{message}{name}{process}",
        },
        "access_json": {
            "class": "ietf.utils.jsonlogger.GunicornRequestJsonFormatter",
            "style": "{",
            "format": "{asctime}{levelname}{message}{name}{process}",
        }
    }
}
