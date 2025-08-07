# coding=utf-8

import logging

import wrapt

from scout_apm.core.tracked_request import TrackedRequest

try:
    import redis
except ImportError:  # pragma: no cover
    redis = None
else:
    if redis.VERSION[0] >= 3:
        from redis import Redis
        from redis.client import Pipeline
    else:  # pragma: no cover
        from redis import StrictRedis as Redis
        from redis.client import BasePipeline as Pipeline

logger = logging.getLogger(__name__)


have_patched_redis_execute_command = False
have_patched_pipeline_execute = False


def ensure_installed():
    global have_patched_redis_execute_command, have_patched_pipeline_execute

    logger.debug("Instrumenting redis.")

    if redis is None:
        logger.debug("Couldn't import redis - probably not installed.")
    else:
        if not have_patched_redis_execute_command:
            try:
                Redis.execute_command = wrapped_execute_command(Redis.execute_command)
            except Exception as exc:
                logger.warning(
                    "Failed to instrument redis.Redis.execute_command: %r",
                    exc,
                    exc_info=exc,
                )
            else:
                have_patched_redis_execute_command = True

        if not have_patched_pipeline_execute:
            try:
                Pipeline.execute = wrapped_execute(Pipeline.execute)
            except Exception as exc:
                logger.warning(
                    "Failed to instrument redis.Pipeline.execute: %r", exc, exc_info=exc
                )
            else:
                have_patched_pipeline_execute = True

    return True


@wrapt.decorator
def wrapped_execute_command(wrapped, instance, args, kwargs):
    try:
        op = args[0]
    except (IndexError, TypeError):
        op = "Unknown"

    tracked_request = TrackedRequest.instance()
    with tracked_request.span(operation="Redis/{}".format(op)):
        return wrapped(*args, **kwargs)


@wrapt.decorator
def wrapped_execute(wrapped, instance, args, kwargs):
    tracked_request = TrackedRequest.instance()
    with tracked_request.span(operation="Redis/MULTI"):
        return wrapped(*args, **kwargs)
