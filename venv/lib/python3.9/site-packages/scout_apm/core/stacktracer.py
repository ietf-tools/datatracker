# coding=utf-8

import wrapt

from scout_apm.core.tracked_request import TrackedRequest


def trace_method(cls, method_name=None):
    def decorator(info_func):
        method_to_patch = method_name or info_func.__name__

        @wrapt.decorator
        def wrapper(wrapped, instance, args, kwargs):
            entry_type, detail = info_func(instance, *args, **kwargs)
            operation = entry_type
            if detail["name"] is not None:
                operation = operation + "/" + detail["name"]

            tracked_request = TrackedRequest.instance()
            with tracked_request.span(operation=operation) as span:
                for key, value in detail.items():
                    span.tag(key, value)

                return wrapped(*args, **kwargs)

        setattr(cls, method_to_patch, wrapper(getattr(cls, method_to_patch)))

        return wrapper

    return decorator
