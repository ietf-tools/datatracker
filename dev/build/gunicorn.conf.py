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

def pre_request(worker, req):
    client_ip = "-"
    cf_ray = "-"
    for (header, value) in req.headers:
        header = header.lower()
        if header == "cf-connecting-ip":
            client_ip = value
        elif header == "cf-ray":
            cf_ray = value
    worker.log.info(f"gunicorn starting to process {req.method} {req.path} (client_ip={client_ip}, cf_ray={cf_ray})")
