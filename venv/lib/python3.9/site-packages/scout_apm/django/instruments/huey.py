# coding=utf-8

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

huey_instrumented = False


def ensure_huey_instrumented():
    global huey_instrumented
    if huey_instrumented:
        return
    huey_instrumented = True

    # Avoid importing if not installed
    if "huey.contrib.djhuey" not in settings.INSTALLED_APPS:  # pragma: no cover
        return

    try:
        from huey.contrib.djhuey import HUEY
    except ImportError:  # pragma: no cover
        return

    from scout_apm.huey import attach_scout_handlers

    attach_scout_handlers(HUEY)
    logger.debug("Instrumented huey.contrib.djhuey")
