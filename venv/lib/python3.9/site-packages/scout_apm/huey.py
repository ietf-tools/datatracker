# coding=utf-8

from huey.exceptions import RetryTask, TaskLockedException
from huey.signals import SIGNAL_CANCELED

import scout_apm.core
from scout_apm.core.tracked_request import TrackedRequest

# Because neither hooks nor signals are called in *all* cases, we need to use
# both in order to capture every case. See source:
# https://github.com/coleifer/huey/blob/e6710bd6a9f581ebc728e24f5923d26eb0047750/huey/api.py#L331  # noqa


def attach_scout(huey):
    installed = scout_apm.core.install()
    if installed:
        attach_scout_handlers(huey)


def attach_scout_handlers(huey):
    huey.pre_execute()(scout_on_pre_execute)
    huey.post_execute()(scout_on_post_execute)
    huey.signal(SIGNAL_CANCELED)(scout_on_cancelled)


def scout_on_pre_execute(task):
    tracked_request = TrackedRequest.instance()

    tracked_request.tag("task_id", task.id)

    operation = "Job/{}.{}".format(task.__module__, task.__class__.__name__)
    tracked_request.start_span(operation=operation)
    tracked_request.operation = operation


def scout_on_post_execute(task, task_value, exception):
    tracked_request = TrackedRequest.instance()
    if exception is None:
        tracked_request.is_real_request = True
    elif isinstance(exception, TaskLockedException):
        pass
    elif isinstance(exception, RetryTask):
        tracked_request.is_real_request = True
        tracked_request.tag("retrying", True)
    else:
        tracked_request.is_real_request = True
        tracked_request.tag("error", "true")
    tracked_request.stop_span()


def scout_on_cancelled(signal, task, exc=None):
    # In the case of a cancelled signal, Huey doesn't run the post_execute
    # handler, so we need to tidy up
    TrackedRequest.instance().stop_span()
