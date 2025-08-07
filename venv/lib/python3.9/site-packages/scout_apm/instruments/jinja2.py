# coding=utf-8

import logging
import sys

import wrapt

from scout_apm.core.tracked_request import TrackedRequest

try:
    from jinja2 import Environment
except ImportError:  # pragma: no cover
    Environment = None

try:
    from jinja2 import Template
except ImportError:  # pragma: no cover
    Template = None

# The async_ module can only be shipped on Python 3.6+
try:
    from scout_apm.async_.instruments.jinja2 import wrapped_render_async
except ImportError:
    wrapped_render_async = None


logger = logging.getLogger(__name__)


have_patched_environment_init = False
have_patched_template_render = False
have_patched_template_render_async = False


def ensure_installed():
    global have_patched_template_render

    logger.debug("Instrumenting Jinja2.")

    if Template is None:
        logger.debug("Couldn't import jinja2.Template - probably not installed.")
        return

    instrument_render_async()

    if not have_patched_template_render:
        try:
            Template.render = wrapped_render(Template.render)
        except Exception as exc:
            logger.warning(
                "Failed to instrument jinja2.Template.render: %r", exc, exc_info=exc
            )
        else:
            have_patched_template_render = True


def instrument_render_async():
    global have_patched_environment_init
    global have_patched_template_render_async

    if wrapped_render_async is None:
        return

    if not have_patched_environment_init and not hasattr(Template, "render_async"):
        try:
            Environment.__init__ = wrapped_environment_init_jinja_v2(
                Environment.__init__
            )
        except Exception as exc:
            logger.warning(
                "Failed to instrument jinja2.Environment.__init__: %r",
                exc,
                exc_info=exc,
            )
        else:
            have_patched_environment_init = True
    elif hasattr(Template, "render_async") and not have_patched_template_render_async:
        try:
            Template.render_async = wrapped_render_async(Template.render_async)
        except Exception as exc:
            logger.warning(
                "Failed to instrument jinja2.Template.render_async: %r",
                exc,
                exc_info=exc,
            )
        else:
            have_patched_template_render_async = True


@wrapt.decorator
def wrapped_render(wrapped, instance, args, kwargs):
    tracked_request = TrackedRequest.instance()
    with tracked_request.span(operation="Template/Render") as span:
        span.tag("name", instance.name)
        return wrapped(*args, **kwargs)


@wrapt.decorator
def wrapped_environment_init_jinja_v2(wrapped, instance, args, kwargs):
    """
    Delayed wrapping of render_async(), since Template won't have this method
    until after jinja2.asyncsupport is imported, which since Jinja2 2.11.0 is
    done conditionally in Environment.__init__:
    https://github.com/pallets/jinja/issues/765

    This is no longer needed since Jinja2 v3.0.0
    """
    global have_patched_template_render_async
    result = wrapped(*args, **kwargs)

    if (
        wrapped_render_async is not None
        and not have_patched_template_render_async
        and "jinja2.asyncsupport" in sys.modules
    ):
        try:
            Template.render_async = wrapped_render_async(Template.render_async)
        except Exception as exc:
            logger.warning(
                "Failed to instrument jinja2.Template.render_async: %r",
                exc,
                exc_info=exc,
            )
        else:
            have_patched_template_render_async = True

    return result
